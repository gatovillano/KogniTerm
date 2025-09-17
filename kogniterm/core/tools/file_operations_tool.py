import os
import logging
from typing import Type, Optional, List, ClassVar
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

class FileOperationsTool(BaseTool):
    name: str = "file_operations"
    description: str = "Permite realizar operaciones CRUD (Crear, Leer, Actualizar, Borrar) en archivos y directorios."

    ignored_directories: ClassVar[List[str]] = ['venv', '.git', '__pycache__', '.venv']

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

    def _run(self, **kwargs) -> str:
        operation = kwargs.get("operation")
        try:
            if operation == "read_file":
                return self._read_file(kwargs["path"])
            elif operation == "write_file":
                return self._write_file(kwargs["path"], kwargs["content"])
            elif operation == "delete_file":
                return self._delete_file(kwargs["path"])
            elif operation == "list_directory":
                # Obtener el valor de recursive, por defecto False
                recursive = kwargs.get("recursive", False)
                items = self._list_directory(kwargs["path"], recursive=recursive) # Pasar recursive

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
        print(f"✨ KogniTerm: Leyendo archivo 📄: {path}") # <--- INDICADOR AÑADIDO
        path = path.strip().replace('@', '') # Limpiar la ruta
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            return f"FILE_CONTENT_START: {path}\n{content}\n:FILE_CONTENT_END"
        except FileNotFoundError:
            raise FileNotFoundError(f"El archivo '{path}' no fue encontrado.")
        except Exception as e:
            raise Exception(f"Error al leer el archivo '{path}': {e}")

    def _write_file(self, path: str, content: str) -> str:
        print(f"✍️ KogniTerm: Escribiendo en archivo 📄: {path}") # <--- INDICADOR AÑADIDO
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return ""
        except Exception as e:
            raise Exception(f"Error al escribir/crear el archivo '{path}': {e}")

    def _delete_file(self, path: str) -> str:
        print(f"🗑️ KogniTerm: Eliminando archivo 📄: {path}") # <--- INDICADOR AÑADIDO
        try:
            os.remove(path)
            return ""
        except FileNotFoundError:
            raise FileNotFoundError(f"El archivo '{path}' no fue encontrado.")
        except Exception as e:
            raise Exception(f"Error al eliminar el archivo '{path}': {e}")

    def _list_directory(self, path: str, recursive: bool = False, include_hidden: bool = False) -> List[str]:
        print(f"📂 KogniTerm: Listando directorio 📁: {path} (Recursivo: {recursive})") # <--- INDICADOR AÑADIDO
        path = path.strip().replace('@', '') # Limpiar la ruta
        try:
            if recursive:
                all_items = []
                for root, dirs, files in os.walk(path):
                    # Filtrar directorios ocultos si no se deben incluir
                    if not include_hidden:
                        dirs[:] = [d for d in dirs if not d.startswith('.')]
                        files[:] = [f for f in files if not f.startswith('.')]

                    # Calcular la ruta relativa desde el directorio inicial
                    relative_root = os.path.relpath(root, path)
                    if relative_root == ".": # Si es el directorio raíz, no añadir prefijo
                        relative_root = ""
                    else:
                        relative_root += os.sep # Añadir separador de directorio

                    for d in dirs:
                        all_items.append(os.path.join(relative_root, d) + os.sep) # Añadir / para directorios
                    for f in files:
                        all_items.append(os.path.join(relative_root, f))
                return all_items
            else:
                items = []
                with os.scandir(path) as entries:
                    for entry in entries:
                        # En modo no recursivo, también podemos filtrar ocultos si se desea
                        if not include_hidden and entry.name.startswith('.'):
                            continue
                        items.append(entry.name)
                return items
        except FileNotFoundError:
            raise FileNotFoundError(f"El directorio '{path}' no fue encontrado.")
        except Exception as e:
            raise Exception(f"Error al listar el directorio '{path}': {e}")

    def _read_many_files(self, paths: List[str]) -> str:
        print(f"📚 KogniTerm: Leyendo múltiples archivos 📄: {\', \'.join(paths)}") # <--- INDICADOR AÑADIDO
        combined_content = []
        for p in paths:
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    content = f.read()
                combined_content.append(content)
            except FileNotFoundError:
                combined_content.append(f"""--- Error: Archivo '{p}' no encontrado. ---\n""")
            except Exception as e:
                combined_content.append(f"""--- Error al leer '{p}': {e} ---\n""")
        return "\n".join(combined_content)

    def _create_directory(self, path: str) -> str:
        print(f"➕ KogniTerm: Creando directorio 📁: {path}") # <--- INDICADOR AÑADIDO
        path = path.strip().replace('@', '') # Limpiar la ruta
        try:
            os.makedirs(path, exist_ok=True)
            return ""
        except Exception as e:
            raise Exception(f"Error al crear el directorio '{path}': {e}")

    async def _arun(self, **kwargs) -> str:
        raise NotImplementedError("FileOperationsTool does not support async")

    # Sobrescribir args_schema para permitir múltiples operaciones
    # @property # <-- Eliminar este decorador
    # args_schema: Type[BaseModel] = FileOperationsInput # <-- Asignar directamente la clase
    class FileOperationsInput(BaseModel):
        operation: str = Field(description="La operación a realizar (read_file, write_file, delete_file, list_directory, read_many_files, create_directory).")
        # Los siguientes campos son opcionales y se usarán según la operación
        path: Optional[str] = Field(None, description="La ruta absoluta del archivo o directorio.")
        content: Optional[str] = Field(None, description="El contenido a escribir en el archivo (para write_file).")
        paths: Optional[List[str]] = Field(None, description="Una lista de rutas absolutas o patrones glob de archivos a leer (para read_many_files).")
        recursive: Optional[bool] = Field(None, description="Si es True, lista el contenido de forma recursiva (para list_directory).") # Nuevo campo
    args_schema: Type[BaseModel] = FileOperationsInput