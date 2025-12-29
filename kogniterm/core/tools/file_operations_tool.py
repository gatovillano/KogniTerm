import os
import logging
from typing import Type, Optional, List, ClassVar, Any, Dict

from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


import queue
import difflib # Añadir esta línea


class FileOperationsTool(BaseTool):
    name: str = "file_operations"
    description: str = "Permite realizar operaciones CRUD (Crear, Leer, Actualizar, Borrar) en archivos y directorios. La confirmación de los cambios se gestiona de forma conversacional."

    ignored_directories: ClassVar[List[str]] = ['venv', '.git', '__pycache__', '.venv']
    llm_service: Any
    interrupt_queue: Optional[queue.Queue] = None
    workspace_context: Any = Field(default=None, description="Contexto del espacio de trabajo actual.") # ¡Nuevo!
    _git_ignore_patterns: List[str] = [] # Atributo privado para evitar errores de Pydantic

    def __init__(self, llm_service: Any, workspace_context: Any = None, **kwargs): # ¡Modificado!
        super().__init__(llm_service=llm_service, **kwargs)
        self.llm_service = llm_service
        self.workspace_context = workspace_context # ¡Nuevo!
        self._git_ignore_patterns = self._load_ignore_patterns()

    def get_action_description(self, **kwargs) -> str:
        operation = kwargs.get("operation")
        path = kwargs.get("path", "")
        if operation == "read_file":
            return f"Leyendo el archivo: {path}"
        elif operation == "write_file":
            return f"Escribiendo en el archivo: {path}"
        elif operation == "delete_file":
            return f"Eliminando el archivo: {path}"
        elif operation == "list_directory":
            return f"Listando el directorio: {path}"
        elif operation == "read_many_files":
            paths = kwargs.get("paths", [])
            return f"Leyendo {len(paths)} archivos"
        elif operation == "create_directory":
            return f"Creando el directorio: {path}"
        return "Realizando operación de archivos"

    def _load_ignore_patterns(self) -> List[str]:
        """Loads ignore patterns from .gitignore and .kognitermignore."""
        patterns = []
        # Intentar obtener el directorio raíz del workspace_context o usar el CWD
        root_dir = os.getcwd()
        if self.workspace_context and hasattr(self.workspace_context, 'root_dir'):
            root_dir = self.workspace_context.root_dir
            
        for filename in ['.gitignore', '.kognitermignore']:
            file_path = os.path.join(root_dir, filename)
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                patterns.append(line)
                except Exception:
                    pass
        return patterns

    def _matches_ignore_patterns(self, item_name: str, rel_path: str, is_dir: bool) -> bool:
        """Checks if a path matches any of the ignore patterns."""
        import fnmatch
        # Normalizar la ruta para comparaciones consistentes
        rel_path = rel_path.replace(os.sep, '/')
        
        # 1. Verificar patrones fijos (ignored_directories)
        if is_dir and item_name in self.ignored_directories:
            return True
            
        # 2. Verificar patrones de .gitignore
        for pattern in self._git_ignore_patterns:
            pattern = pattern.replace(os.sep, '/')
            if not pattern: continue
            
            if pattern.endswith('/'):
                if not is_dir: continue
                pattern = pattern.rstrip('/')

            if fnmatch.fnmatch(item_name, pattern) or \
               fnmatch.fnmatch(rel_path, pattern) or \
               rel_path.startswith(pattern + '/') or \
               any(fnmatch.fnmatch(part, pattern) for part in rel_path.split('/')):
                return True
        return False

    # --- Sub-clases para los esquemas de argumentos de cada operación ---

    class ReadFileInput(BaseModel):
        path: str = Field(description="La ruta absoluta del archivo a leer.")

    class WriteFileInput(BaseModel):
        path: str = Field(description="La ruta absoluta del archivo a escribir/crear.")
        content: str = Field(description="El contenido a escribir en el archivo.")
        confirm: Optional[bool] = Field(default=False, description="Si es True, confirma la operación de escritura sin requerir aprobación adicional.")

    class DeleteFileInput(BaseModel):
        path: str = Field(description="La ruta absoluta del archivo a borrar.")
        confirm: Optional[bool] = Field(default=False, description="Si es True, confirma la operación de eliminación sin requerir aprobación adicional.")

    class ListDirectoryInput(BaseModel):
        path: str = Field(description="La ruta absoluta del directorio a listar.")
        recursive: Optional[bool] = Field(default=False, description="Si es True, lista el contenido de forma recursiva.")

    class ReadManyFilesInput(BaseModel):
        paths: List[str] = Field(description="Una lista de rutas absolutas o patrones glob de archivos a leer.")

    # --- Implementación de las operaciones ---

    def _run(self, **kwargs) -> str | Dict[str, Any]:
        logger.debug(f"DEBUG: _run - Recibiendo kwargs: {kwargs}") # <-- Añadir este log
        # print(f"*** DEBUG PRINT: _run - Recibiendo kwargs: {kwargs} ***") # <-- Añadir este print
        operation = kwargs.get("operation")
        confirm = kwargs.get("confirm", False)
        result: str | Dict[str, Any] | None = None
        try:
            if operation == "read_file":
                return self._read_file(kwargs["path"])
            elif operation == "write_file":
                result = self._write_file(kwargs["path"], kwargs["content"], confirm=confirm)
                if isinstance(result, dict) and result.get("status") == "requires_confirmation":
                    return result
                return result
            elif operation == "delete_file":
                result = self._delete_file(kwargs["path"], confirm=confirm)
                if isinstance(result, dict) and result.get("status") == "requires_confirmation":
                    return result
                return result
            elif operation == "list_directory":
                recursive = kwargs.get("recursive", False)
                items = self._list_directory(kwargs["path"], recursive=recursive)

                if recursive:
                    return "\n".join(items)
                else:
                    return "\n".join(items)
            elif operation == "read_many_files":
                return self._read_many_files(kwargs["paths"])
            elif operation == "create_directory":
                return self._create_directory(kwargs["path"])
            else:
                return "Operación no soportada."
        except (FileNotFoundError, PermissionError, Exception) as e:
            return f"Error en la operación '{operation}': {e}"



    def _read_file(self, path: str) -> Dict[str, Any]:
        if self.interrupt_queue and not self.interrupt_queue.empty():
            self.interrupt_queue.get()
            raise InterruptedError("Operación de lectura de archivo interrumpida por el usuario.")

        path = path.strip().replace('@', '')
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return {"file_path": path, "content": content}
        except FileNotFoundError:
            raise FileNotFoundError(f"El archivo '{path}' no fue encontrado.")
        except Exception as e:
            raise Exception(f"Error al leer el archivo '{path}': {e}")

    def _write_file(self, path: str, content: str, confirm: bool = False) -> str | Dict[str, Any]:
        if self.interrupt_queue and not self.interrupt_queue.empty():
            self.interrupt_queue.get()
            raise InterruptedError("Operación de escritura de archivo interrumpida por el usuario.")

        logger.debug(f"DEBUG: _write_file - confirm: {confirm}")
        # print(f"*** DEBUG PRINT: _write_file - confirm: {confirm} ***")
        if confirm:
            logger.debug("DEBUG: _write_file - Ejecutando _perform_write_file (confirm=True).")
            # print("*** DEBUG PRINT: _write_file - Ejecutando _perform_write_file (confirm=True). ***")
            result = self._perform_write_file(path, content)
            logger.debug(f"DEBUG: _write_file - Devolviendo status success: {result}")
            logger.debug(f"DEBUG: _write_file - Devolviendo status success: {result}")
            return {"status": "success", "message": result}
        else:
            logger.debug("DEBUG: _write_file - Solicitando confirmación (confirm=False).")
            logger.debug("DEBUG: _write_file - Solicitando confirmación (confirm=False).")
            original_content = ""
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        original_content = f.read()
                except Exception:
                    pass # Ignorar errores de lectura si el archivo no existe o no es legible

            diff = "".join(difflib.unified_diff(
                original_content.splitlines(keepends=True),
                content.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}"
            ))
            logger.debug(f"DEBUG: _write_file - Devolviendo requires_confirmation. Diff: {diff[:200]}...")
            logger.debug(f"DEBUG: _write_file - Devolviendo requires_confirmation. Diff: {diff[:200]}...")
            return {
                "status": "requires_confirmation",
                "action_description": f"escribir en el archivo '{path}'",
                "operation": "file_operations",
                "args": {"operation": "write_file", "path": path, "content": content, "confirm": True},
                "diff": diff,
                "new_content": content,
            }

    def _perform_write_file(self, path: str, content: str) -> str:
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return "Archivo escrito con éxito."
        except Exception as e:
            raise Exception(f"Error al escribir/crear el archivo '{path}': {e}")

    def _delete_file(self, path: str, confirm: bool = False) -> str | Dict[str, Any]:
        if self.interrupt_queue and not self.interrupt_queue.empty():
            self.interrupt_queue.get()
            raise InterruptedError("Operación de eliminación de archivo interrumpida por el usuario.")

        logger.debug(f"DEBUG: _delete_file - confirm: {confirm}")
        print(f"*** DEBUG PRINT: _delete_file - confirm: {confirm} ***")
        if confirm:
            logger.debug("DEBUG: _delete_file - Ejecutando _perform_delete_file (confirm=True).")
            print("*** DEBUG PRINT: _delete_file - Ejecutando _perform_delete_file (confirm=True). ***")
            result = self._perform_delete_file(path)
            logger.debug(f"DEBUG: _delete_file - Devolviendo status success: {result}")
            print(f"*** DEBUG PRINT: _delete_file - Devolviendo status success: {result} ***")
            return {"status": "success", "message": result}
        else:
            logger.debug("DEBUG: _delete_file - Solicitando confirmación (confirm=False).")
            print("*** DEBUG PRINT: _delete_file - Solicitando confirmación (confirm=False). ***")
            return {
                "status": "requires_confirmation",
                "action_description": f"eliminar el archivo '{path}'",
                "operation": "file_operations",
                "args": {"operation": "delete_file", "path": path, "confirm": True}
            }

    def _perform_delete_file(self, path: str) -> str:
        try:
            os.remove(path)
            return "Archivo eliminado con éxito."
        except FileNotFoundError:
            raise FileNotFoundError(f"El archivo '{path}' no fue encontrado.")
        except Exception as e:
            raise Exception(f"Error al eliminar el archivo '{path}': {e}")

    def _list_directory(self, path: str, recursive: bool = False, include_hidden: bool = False, silent_mode: bool = False) -> List[str]:
        path = path.strip().replace('@', '')
        try:
            if recursive:
                all_items = []
                for root, dirs, files in os.walk(path):
                    if self.interrupt_queue and not self.interrupt_queue.empty():
                        self.interrupt_queue.get()
                        raise InterruptedError("Operación de listado de directorio interrumpida por el usuario.")

                    relative_root = os.path.relpath(root, path)
                    if relative_root == ".":
                        relative_root = ""
                    
                    if not include_hidden:
                        dirs[:] = [d for d in dirs if not d.startswith('.') and not self._matches_ignore_patterns(d, os.path.join(relative_root, d), True)]
                        files[:] = [f for f in files if not f.startswith('.') and not self._matches_ignore_patterns(f, os.path.join(relative_root, f), False)]
                    else:
                        dirs[:] = [d for d in dirs if not self._matches_ignore_patterns(d, os.path.join(relative_root, d), True)]
                        files[:] = [f for f in files if not self._matches_ignore_patterns(f, os.path.join(relative_root, f), False)]

                    if relative_root != "":
                        relative_root += os.sep

                    for d in dirs:
                        all_items.append(os.path.join(relative_root, d) + os.sep)
                    for f in files:
                        all_items.append(os.path.join(relative_root, f))
                return all_items
            else:
                items = []
                with os.scandir(path) as entries:
                    for entry in entries:
                        if self.interrupt_queue and not self.interrupt_queue.empty():
                            self.interrupt_queue.get()
                            raise InterruptedError("Operación de listado de directorio interrumpida por el usuario.")

                        if not include_hidden and entry.name.startswith('.'):
                            continue
                        items.append(entry.name)
                return items
        except FileNotFoundError:
            raise FileNotFoundError(f"El directorio '{path}' no fue encontrado.")
        except Exception as e:
            raise Exception(f"Error al listar el directorio '{path}': {e}")

    def _read_many_files(self, paths: List[str]) -> Dict[str, Any]:
        combined_content = []
        for p in paths:
            if self.interrupt_queue and not self.interrupt_queue.empty():
                self.interrupt_queue.get()
                raise InterruptedError("Operación de lectura de múltiples archivos interrumpida por el usuario.")

            try:
                with open(p, 'r', encoding='utf-8') as f:
                    content = f.read()
                combined_content.append({"file_path": p, "content": content})
            except FileNotFoundError:
                combined_content.append({"file_path": p, "error": f"Archivo '{p}' no encontrado."})
            except Exception as e:
                combined_content.append({"file_path": p, "error": f"Error al leer '{p}': {e}"})
        return {"files": combined_content}

    def _create_directory(self, path: str) -> str:
        if self.interrupt_queue and not self.interrupt_queue.empty():
            self.interrupt_queue.get()
            raise InterruptedError("Operación de creación de directorio interrumpida por el usuario.")

        path = path.strip().replace('@', '')
        try:
            os.makedirs(path, exist_ok=True)
            return ""
        except Exception as e:
            raise Exception(f"Error al crear el directorio '{path}': {e}")


    async def _arun(self, **kwargs) -> str:
        raise NotImplementedError("FileOperationsTool does not support async")

    class FileOperationsInput(BaseModel):
        operation: str = Field(description="La operación a realizar (read_file, write_file, delete_file, list_directory, read_many_files, create_directory).")
        path: Optional[str] = Field(None, description="La ruta absoluta del archivo o directorio.")
        content: Optional[str] = Field(None, description="El contenido a escribir en el archivo (para write_file).")
        paths: Optional[List[str]] = Field(None, description="Una lista de rutas absolutas o patrones glob de archivos a leer (para read_many_files).")
        recursive: Optional[bool] = Field(None, description="Si es True, lista el contenido de forma recursiva (para list_directory).")
    args_schema: Type[BaseModel] = FileOperationsInput
