import os
import logging
import json
import difflib
from typing import Type, Optional, List, ClassVar, Any, Dict

from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from kogniterm.core.exceptions import UserConfirmationRequired # Importar aquí

logger = logging.getLogger(__name__)


import queue


class FileOperationsTool(BaseTool):
    name: str = "file_operations"
    description: str = "Permite realizar operaciones CRUD (Crear, Leer, Actualizar, Borrar) en archivos y directorios."

    ignored_directories: ClassVar[List[str]] = ['venv', '.git', '__pycache__', '.venv']
    llm_service: Any
    interrupt_queue: Optional[queue.Queue] = None
    workspace_context: Any = Field(default=None, description="Contexto del espacio de trabajo actual.") # ¡Nuevo!

    def __init__(self, llm_service: Any, workspace_context: Any = None, **kwargs): # ¡Modificado!
        super().__init__(llm_service=llm_service, **kwargs)
        self.llm_service = llm_service
        self.workspace_context = workspace_context # ¡Nuevo!

    # --- Sub-clases para los esquemas de argumentos de cada operación ---

    class ReadFileInput(BaseModel):
        path: str = Field(description="La ruta absoluta del archivo a leer.")

    class WriteFileInput(BaseModel):
        path: str = Field(description="La ruta absoluta del archivo a escribir/crear.")
        content: str = Field(description="El contenido a escribir en el archivo.")

    class DeleteFileInput(BaseModel):
        path: str = Field(description="La ruta absoluta del archivo a borrar.")

    class ListDirectoryInput(BaseModel):
        path: str = Field(description="La ruta absoluta del directorio a listar.")
        recursive: Optional[bool] = Field(default=False, description="Si es True, lista el contenido de forma recursiva.")

    class ReadManyFilesInput(BaseModel):
        paths: List[str] = Field(description="Una lista de rutas absolutas o patrones glob de archivos a leer.")

    # --- Implementación de las operaciones ---

    def _run(self, **kwargs) -> str | Dict[str, Any]:
        operation = kwargs.get("operation")
        confirm = kwargs.get("confirm", False)

        try:
            if confirm:
                if operation == "write_file":
                    return self._perform_write_file(kwargs["path"], kwargs["content"])
                elif operation == "delete_file":
                    return self._perform_delete_file(kwargs["path"])
                else:
                    return f"Operación '{operation}' no soporta confirmación directa."

            if operation == "read_file":
                return self._read_file(kwargs["path"])
            elif operation == "write_file":
                # Ahora _write_file lanza UserConfirmationRequired
                return self._write_file(kwargs["path"], kwargs["content"])
            elif operation == "delete_file":
                # Ahora _delete_file lanza UserConfirmationRequired
                return self._delete_file(kwargs["path"])
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


    def _read_file(self, path: str) -> str:
        if self.interrupt_queue and not self.interrupt_queue.empty():
            self.interrupt_queue.get()
            raise InterruptedError("Operación de lectura de archivo interrumpida por el usuario.")

        print(f"✨ KogniTerm: Leyendo archivo 📄: {path}")
        path = path.strip().replace('@', '')
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            return f"FILE_CONTENT_START: {path}\n{content}\n:FILE_CONTENT_END"
        except FileNotFoundError:
            raise FileNotFoundError(f"El archivo '{path}' no fue encontrado.")
        except Exception as e:
            raise Exception(f"Error al leer el archivo '{path}': {e}")

    def _write_file(self, path: str, content: str) -> str | Dict[str, Any]:
        if self.interrupt_queue and not self.interrupt_queue.empty():
            self.interrupt_queue.get()
            raise InterruptedError("Operación de escritura de archivo interrumpida por el usuario.")

        print(f"✍️ KogniTerm: Escribiendo en archivo 📄: {path}")
        
        original_content = ""
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                original_content = f.read()

        diff = "".join(difflib.unified_diff(
            original_content.splitlines(keepends=True),
            content.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm=''
        ))

        if not diff:
            return self._perform_write_file(path, content)

        raise UserConfirmationRequired(
            message=f"Se detectaron cambios para '{path}'. Por favor, confirma para aplicar.",
            tool_name=self.name,
            tool_args={
                "operation": "write_file",
                "path": path,
                "content": content,
            },
            raw_tool_output=json.dumps({
                "status": "requires_confirmation",
                "tool_name": self.name,
                "path": path,
                "diff": diff,
                "message": f"Se detectaron cambios para '{path}'. Por favor, confirma para aplicar.",
                "new_content": content,
            })
        )

    def _perform_write_file(self, path: str, content: str) -> str:
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return "Archivo escrito con éxito."
        except Exception as e:
            raise Exception(f"Error al escribir/crear el archivo '{path}': {e}")

    def _delete_file(self, path: str) -> str | Dict[str, Any]:
        if self.interrupt_queue and not self.interrupt_queue.empty():
            self.interrupt_queue.get()
            raise InterruptedError("Operación de eliminación de archivo interrumpida por el usuario.")

        print(f"🗑️ KogniTerm: Eliminando archivo 📄: {path}")
        
        if not os.path.exists(path):
            raise FileNotFoundError(f"El archivo '{path}' no fue encontrado para eliminar.")

        raise UserConfirmationRequired(
            message=f"Se solicita eliminar el archivo '{path}'. Por favor, confirma para proceder.",
            tool_name=self.name,
            tool_args={
                "operation": "delete_file",
                "path": path,
            },
            raw_tool_output=json.dumps({
                "status": "requires_confirmation",
                "tool_name": self.name,
                "path": path,
                "message": f"Se solicita eliminar el archivo '{path}'. Por favor, confirma para proceder.",
            })
        )

    def _perform_delete_file(self, path: str) -> str:
        try:
            os.remove(path)
            return "Archivo eliminado con éxito."
        except FileNotFoundError:
            raise FileNotFoundError(f"El archivo '{path}' no fue encontrado.")
        except Exception as e:
            raise Exception(f"Error al eliminar el archivo '{path}': {e}")

    def _list_directory(self, path: str, recursive: bool = False, include_hidden: bool = False, silent_mode: bool = False) -> List[str]:
        if not silent_mode:
            print(f"📂 KogniTerm: Listando directorio 📁: {path} (Recursivo: {recursive})")
        path = path.strip().replace('@', '')
        try:
            if recursive:
                all_items = []
                for root, dirs, files in os.walk(path):
                    if self.interrupt_queue and not self.interrupt_queue.empty():
                        self.interrupt_queue.get()
                        raise InterruptedError("Operación de listado de directorio interrumpida por el usuario.")

                    if not include_hidden:
                        dirs[:] = [d for d in dirs if not d.startswith('.')]
                        files[:] = [f for f in files if not f.startswith('.')]

                    relative_root = os.path.relpath(root, path)
                    if relative_root == ".":
                        relative_root = ""
                    else:
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

    def _read_many_files(self, paths: List[str]) -> str:
        print(f"📚 KogniTerm: Leyendo múltiples archivos 📄: {', '.join(paths)}")
        combined_content = []
        for p in paths:
            if self.interrupt_queue and not self.interrupt_queue.empty():
                self.interrupt_queue.get()
                raise InterruptedError("Operación de lectura de múltiples archivos interrumpida por el usuario.")

            try:
                with open(p, 'r', encoding='utf-8') as f:
                    content = f.read()
                combined_content.append(content)
            except FileNotFoundError:
                combined_content.append(f"""--- Error: Archivo '{p}' no encontrado. ---""")
            except Exception as e:
                combined_content.append(f"""--- Error al leer '{p}': {e} ---""")
        return "\n".join(combined_content)

    def _create_directory(self, path: str) -> str:
        if self.interrupt_queue and not self.interrupt_queue.empty():
            self.interrupt_queue.get()
            raise InterruptedError("Operación de creación de directorio interrumpida por el usuario.")

        print(f"➕ KogniTerm: Creando directorio 📁: {path}")
        path = path.strip().replace('@', '')
        try:
            os.makedirs(path, exist_ok=True)
            return ""
        except Exception as e:
            raise Exception(f"Error al crear el directorio '{path}': {e}")

    def _confirm_action(self, action_description: str, operation_name: str, operation_args: dict) -> Dict[str, Any]:
        return {"_requires_confirmation": True, "action_description": action_description, "operation": operation_name, "args": operation_args}

    async def _arun(self, **kwargs) -> str:
        raise NotImplementedError("FileOperationsTool does not support async")

    class FileOperationsInput(BaseModel):
        operation: str = Field(description="La operación a realizar (read_file, write_file, delete_file, list_directory, read_many_files, create_directory).")
        path: Optional[str] = Field(None, description="La ruta absoluta del archivo o directorio.")
        content: Optional[str] = Field(None, description="El contenido a escribir en el archivo (para write_file).")
        paths: Optional[List[str]] = Field(None, description="Una lista de rutas absolutas o patrones glob de archivos a leer (para read_many_files).")
        recursive: Optional[bool] = Field(None, description="Si es True, lista el contenido de forma recursiva (para list_directory).")
    args_schema: Type[BaseModel] = FileOperationsInput
