import os
from typing import Dict, Any, List, Optional
from kogniterm.core.context.workspace_context import WorkspaceContext
from kogniterm.core.context.ignore_pattern_manager import IgnorePatternManager
from kogniterm.core.context.config_file_analyzer import ConfigFileAnalyzer
import logging

logger = logging.getLogger(__name__)

async def initializeProjectContext(directory: str) -> WorkspaceContext:
    """
    Inicializa el contexto del proyecto KogniTerm recopilando información
    de varios módulos y devolviendo una instancia de WorkspaceContext.
    """
    # logger.debug("Inicializando contexto del proyecto en segundo plano...") # Eliminar

    # 1. Obtener patrones de ignorado
    ignore_pattern_manager = IgnorePatternManager()
    ignore_patterns = ignore_pattern_manager.get_ignore_patterns(directory)

    # 2. Crear instancia de WorkspaceContext
    workspace_context = WorkspaceContext(watch_workspace=True, ignore_patterns=ignore_patterns)
    workspace_context.addDirectory(directory)

    # 3. Analizar archivos de configuración usando el ConfigFileAnalyzer del workspace
    workspace_context.config_file_analyzer.find_and_parse_config_files(directory, ignore_patterns)

    # logger.debug("Contexto del proyecto inicializado correctamente.") # Eliminar
    return workspace_context
