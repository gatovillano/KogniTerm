import os
import pathlib
import fnmatch
from typing import List, Literal, TypedDict, Union

class FileNode(TypedDict):
    name: str
    type: Literal['file']
    path: str
    children: List[Any] # Files have no children, but included for structural consistency

class DirectoryNode(TypedDict):
    name: str
    type: Literal['directory']
    path: str
    children: List[Union['FileNode', 'DirectoryNode']]

# The root FolderStructure is always a directory
FolderStructure = DirectoryNode

class FolderStructureAnalyzer:
    def __init__(self, directory: str, ignore_patterns: List[str] = None):
        self.root_path = pathlib.Path(directory).resolve()
        self.ignore_patterns = ignore_patterns if ignore_patterns is not None else []
        self.structure = self.get_folder_structure(directory, self.ignore_patterns)

    def get_folder_structure(self, directory: str, ignore_patterns: List[str] = None) -> FolderStructure:
        if ignore_patterns is None:
            ignore_patterns = []

        base_path = pathlib.Path(directory)
        if not base_path.is_dir():
            raise ValueError(f"El directorio '{directory}' no existe o no es un directorio válido.")

        def _should_ignore(path_name: str, path_full: str) -> bool:
            for pattern in ignore_patterns:
                if fnmatch.fnmatch(path_name, pattern) or fnmatch.fnmatch(path_full, pattern):
                    return True
            return False

        def _traverse_directory(current_path: pathlib.Path) -> Union[FileNode, DirectoryNode, None]:
            name = current_path.name
            full_path = str(current_path)

            if _should_ignore(name, full_path):
                return None

            if current_path.is_file():
                return FileNode(
                    name=name,
                    type='file',
                    path=full_path,
                    children=[] # Files have no children
                )
            elif current_path.is_dir():
                children = []
                for item in current_path.iterdir():
                    child_structure = _traverse_directory(item)
                    if child_structure:
                        children.append(child_structure)
                return DirectoryNode(
                    name=name,
                    type='directory',
                    path=full_path,
                    children=children
                )
            return None

        root_structure = _traverse_directory(base_path)
        if root_structure is None or root_structure['type'] == 'file': # A folder structure must have a directory root
            # If the root_structure is None (e.g., only ignored files in root) or a file,
            # return an empty directory structure for the base_path
            return DirectoryNode(
                name=base_path.name,
                type='directory',
                path=str(base_path),
                children=[]
            )
        return root_structure
    
    def _find_node(self, path: str, node: Union[FileNode, DirectoryNode] = None) -> Union[FileNode, DirectoryNode, None]:
        if node is None:
            node = self.structure # self.structure is FolderStructure which is DirectoryNode
        
        if node['path'] == path:
            return node
        
        if node['type'] == 'directory': # Only directories have children to traverse
            for child in node['children']:
                found = self._find_node(path, child)
                if found:
                    return found
        return None

    def _find_parent_node(self, path: str, node: DirectoryNode = None) -> Union[DirectoryNode, None]:
        if node is None:
            node = self.structure # self.structure is FolderStructure which is DirectoryNode

        for child in node['children']:
            if child['path'] == path:
                return node
            if child['type'] == 'directory': # Only recurse into directory children
                found = self._find_parent_node(path, child)
                if found:
                    return found
        return None

    def on_created(self, path: str):
        p = pathlib.Path(path)
        parent_path = str(p.parent)
        parent_node = self._find_node(parent_path)

        if parent_node and parent_node['type'] == 'directory':
            if p.is_dir():
                new_node = DirectoryNode(
                    name=p.name,
                    type='directory',
                    path=path,
                    children=[]
                )
            else:
                new_node = FileNode(
                    name=p.name,
                    type='file',
                    path=path,
                    children=[]
                )
            parent_node['children'].append(new_node)
            # Sort children for consistent order
            parent_node['children'].sort(key=lambda x: x['name'])

    def on_deleted(self, path: str):
        parent_node = self._find_parent_node(path)
        if parent_node:
            parent_node['children'] = [child for child in parent_node['children'] if child['path'] != path]

    def on_moved(self, src_path: str, dest_path: str):
        self.on_deleted(src_path)
        self.on_created(dest_path)

if __name__ == '__main__':
    # Mantener el ejemplo de uso, pero adaptado a la nueva clase
    # Ejemplo de uso:
    # Crear algunos archivos y directorios temporales para probar
    test_dir = "test_folder_structure"
    os.makedirs(os.path.join(test_dir, "subdir1"), exist_ok=True)
    os.makedirs(os.path.join(test_dir, "subdir2"), exist_ok=True)
    with open(os.path.join(test_dir, "file1.txt"), "w") as f:
        f.write("contenido")
    with open(os.path.join(test_dir, "subdir1", "file2.py"), "w") as f:
        f.write("print('hello')")
    with open(os.path.join(test_dir, "subdir2", "temp.log"), "w") as f:
        f.write("log data")
    os.makedirs(os.path.join(test_dir, ".git"), exist_ok=True) # Hidden directory
    with open(os.path.join(test_dir, ".gitignore"), "w") as f:
        f.write("*.log")

    print("--- Estructura de carpeta sin ignorar ---")
    analyzer = FolderStructureAnalyzer(test_dir)
    import json
    print(json.dumps(analyzer.structure, indent=2))

    print("\n--- Estructura de carpeta ignorando *.log y .git ---")
    analyzer_ignored = FolderStructureAnalyzer(test_dir, ignore_patterns=["*.log", ".git", "test_folder_structure/.gitignore"])
    print(json.dumps(analyzer_ignored.structure, indent=2))
    
    # Ejemplo de actualización dinámica
    print("\n--- Actualización dinámica ---")
    new_file_path = os.path.join(test_dir, "subdir1", "new_file.txt")
    with open(new_file_path, "w") as f:
        f.write("new")
    
    analyzer_ignored.on_created(new_file_path)
    print("Estructura después de crear new_file.txt:")
    print(json.dumps(analyzer_ignored.structure, indent=2))

    moved_file_path = os.path.join(test_dir, "moved_file.txt")
    os.rename(new_file_path, moved_file_path)
    analyzer_ignored.on_moved(new_file_path, moved_file_path)
    print("\nEstructura después de mover new_file.txt a moved_file.txt:")
    print(json.dumps(analyzer_ignored.structure, indent=2))

    os.remove(moved_file_path)
    analyzer_ignored.on_deleted(moved_file_path)
    print("\nEstructura después de eliminar moved_file.txt:")
    print(json.dumps(analyzer_ignored.structure, indent=2))

    # Limpiar archivos y directorios temporales
    import shutil
    shutil.rmtree(test_dir)
