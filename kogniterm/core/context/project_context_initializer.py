import os
from typing import Dict, Any, List, Optional
from kogniterm.core.context.workspace_context import WorkspaceContext
from kogniterm.core.context.ignore_pattern_manager import IgnorePatternManager
from kogniterm.core.context.folder_structure_analyzer import FolderStructureAnalyzer, FolderStructure
from kogniterm.core.context.file_search_module import findFiles
from kogniterm.core.context.config_file_analyzer import parsePackageJson, parseTsconfigJson, parseEslintrcJson, PackageJson, TsconfigJson, EslintrcJson
# Asumo que GitInteractionModule existe o que se creará.
# Por ahora, usaré un placeholder si no lo encuentro.
# from kogniterm.core.context.git_interaction_module import GitInteractionModule 

class GitInteractionModule:
    def get_git_status(self, directory: str) -> Dict[str, Any]:
        print(f"Simulando obtener estado de Git para {directory}")
        return {"has_git": False, "branch": None, "last_commit_message": None}

    def get_tracked_files(self, directory: str, ignore_patterns: List[str] = None) -> List[str]:
        print(f"Simulando obtener archivos rastreados por Git para {directory}")
        return []

async def initializeProjectContext(directory: str) -> Dict[str, Any]:
    """
    Inicializa el contexto del proyecto KogniTerm recopilando información
    de varios módulos.
    """
    print("Inicializando contexto del proyecto en segundo plano...")

    # 1. Obtener patrones de ignorado
    ignore_pattern_manager = IgnorePatternManager()
    ignore_patterns = ignore_pattern_manager.get_ignore_patterns(directory)

    # 2. Crear instancia de WorkspaceContext
    workspace_context = WorkspaceContext(watch_workspace=True, ignore_patterns=ignore_patterns)
    workspace_context.addDirectory(directory)

    # 3. Obtener estructura de carpetas
    folder_structure_analyzer = FolderStructureAnalyzer(directory, ignore_patterns)
    folder_structure: FolderStructure = folder_structure_analyzer.structure

    # 4. Buscar archivos de configuración relevantes
    config_files: Dict[str, Optional[str]] = {
        "package_json_path": None,
        "tsconfig_json_path": None,
        "eslintrc_js_path": None,
    }

    # package.json
    package_json_files = findFiles(directory, 'package.json', ignore_patterns)
    if package_json_files:
        config_files["package_json_path"] = package_json_files[0]

    # tsconfig.json
    tsconfig_json_files = findFiles(directory, 'tsconfig.json', ignore_patterns)
    if tsconfig_json_files:
        config_files["tsconfig_json_path"] = tsconfig_json_files[0]

    # .eslintrc.js
    eslintrc_js_files = findFiles(directory, '.eslintrc.js', ignore_patterns)
    if eslintrc_js_files:
        config_files["eslintrc_js_path"] = eslintrc_js_files[0]

    # 5. Analizar archivos de configuración
    package_json: Optional[PackageJson] = None
    if config_files["package_json_path"]:
        try:
            package_json = parsePackageJson(config_files["package_json_path"])
        except Exception as e:
            print(f"Error al parsear package.json: {e}")

    tsconfig_json: Optional[TsconfigJson] = None
    if config_files["tsconfig_json_path"]:
        try:
            tsconfig_json = parseTsconfigJson(config_files["tsconfig_json_path"])
        except Exception as e:
            print(f"Error al parsear tsconfig.json: {e}")

    eslintrc_js: Optional[EslintrcJson] = None
    if config_files["eslintrc_js_path"]:
        try:
            eslintrc_js = parseEslintrcJson(config_files["eslintrc_js_path"])
        except Exception as e:
            print(f"Error al parsear .eslintrc.js: {e}")
            
    # 6. Obtener información de Git
    git_interaction_module = GitInteractionModule()
    git_info = git_interaction_module.get_git_status(directory)
    git_tracked_files = git_interaction_module.get_tracked_files(directory, ignore_patterns)

    # El FileSystemWatcher ya se inicializa con WorkspaceContext si watch_workspace=True
    # y los callbacks se añadirían al workspace_context si es necesario.
    # Por ejemplo, para un callback que actualice la estructura de carpetas:
    # workspace_context.onDirectoriesChanged(lambda: print("Los directorios han cambiado, se necesita actualizar el contexto."))
    print("Contexto del proyecto inicializado correctamente.")
    return {
        "workspace_context": workspace_context,
        "ignore_patterns": ignore_patterns,
        "folder_structure": folder_structure,
        "package_json": package_json,
        "tsconfig_json": tsconfig_json,
        "eslintrc_js": eslintrc_js,
        "git_info": git_info,
        "git_tracked_files": git_tracked_files,
    }
