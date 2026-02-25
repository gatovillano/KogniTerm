# Imports de herramientas legacy eliminados (Sistema migrado a Skills)
import logging

logger = logging.getLogger(__name__)

# Importar sistema de skills (opcional para compatibilidad)
try:
    from ...core.skills import SkillManager
    SKILLS_AVAILABLE = True
except ImportError:
    SKILLS_AVAILABLE = False

# Lista de todas las clases de herramientas para fácil acceso
ALL_TOOLS_CLASSES = [
    # CodeAnalysisTool,
    # BraveSearchTool,
    # WebFetchTool,
    # WebScrapingTool,
    # GitHubTool,
    # ExecuteCommandTool,
    # MemoryInitTool,
    # MemoryReadTool,
    # MemoryAppendTool,
    # MemorySummarizeTool,
    # PythonTool,
    # FileSearchTool,
    # FileOperationsTool,
    # AdvancedFileEditorTool,
    # PCInteractionTool,
    # PlanCreationTool,
    # TaskCompleteTool,
    # CallAgentTool,
    # CodebaseSearchTool,
    # FileUpdateTool,
    # FileReadDirectoryTool,
    # SearchMemoryTool,
    # SetLLMInstructionsTool,
    # TavilySearchTool,
    # ThinkTool
]

import queue
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class ToolManager:
    def __init__(
        self,
        llm_service=None,
        interrupt_queue: Optional[queue.Queue] = None,
        terminal_ui=None,
        embeddings_service=None,
        vector_db_manager=None,
        approval_handler=None,
        skill_manager: Optional['SkillManager'] = None
    ):
        self.llm_service = llm_service
        self.interrupt_queue = interrupt_queue
        self.terminal_ui = terminal_ui
        self.embeddings_service = embeddings_service
        self.vector_db_manager = vector_db_manager
        self.approval_handler = approval_handler

        # Sistema de skills (opcional)
        self.skill_manager = skill_manager
        self.legacy_tools: List[Any] = []  # Herramientas legacy cargadas
        self.legacy_tool_map: Dict[str, Any] = {}  # Mapa de herramientas legacy

        self.tools: List[Any] = []
        self.tool_map: Dict[str, Any] = {}

    def set_skill_manager(self, skill_manager: 'SkillManager'):
        """Inyecta el SkillManager para cargar skills."""
        self.skill_manager = skill_manager

    def load_tools(
        self,
        load_legacy: bool = False,
        load_skills: bool = True,
        agent_context: Optional[dict] = None
    ):
        """
        Carga herramientas, priorizando skills sobre legacy.

        Args:
            load_legacy: Si cargar herramientas legacy
            load_skills: Si cargar skills desde SkillManager
            agent_context: Contexto del agente para filtrado de permisos
        """
        # 1. Cargar skills si está disponible
        if load_skills and self.skill_manager and SKILLS_AVAILABLE:
            try:
                skills = self.skill_manager.discover_all_skills()
                for skill in skills:
                    success = self.skill_manager.load_skill(skill.name, agent_context)
                    if success:
                        logger.debug(f"Skill cargada: {skill.name}")

                # Registrar herramientas de skills en tool_map
                # Al refrescar, vaciamos para asegurar que solo queden las actuales
                for tool_name, tool_info in self.skill_manager.tool_registry.items():
                    self.tools.append(tool_info['tool'])
                    self.tool_map[tool_name] = tool_info['tool']
                    logger.debug(f"Herramienta de skill registrada: {tool_name}")
            except Exception as e:
                print(f"Error cargando skills: {e}")
                import traceback
                traceback.print_exc()

        # 2. Cargar herramientas legacy (para compatibilidad hacia atrás)
        if load_legacy:
            for ToolClass in ALL_TOOLS_CLASSES:
                try:
                    tool_kwargs = {}

                    import inspect
                    try:
                        init_params = inspect.signature(ToolClass.__init__).parameters
                    except ValueError:
                        init_params = {}

                    if 'llm_service' in init_params:
                        tool_kwargs['llm_service'] = self.llm_service
                    if 'llm_service_instance' in init_params:
                        tool_kwargs['llm_service_instance'] = self.llm_service
                    if 'interrupt_queue' in init_params:
                        tool_kwargs['interrupt_queue'] = self.interrupt_queue
                    if 'terminal_ui' in init_params:
                        tool_kwargs['terminal_ui'] = self.terminal_ui
                    if 'embeddings_service' in init_params:
                        tool_kwargs['embeddings_service'] = self.embeddings_service
                    if 'vector_db_manager' in init_params:
                        tool_kwargs['vector_db_manager'] = self.vector_db_manager
                    if 'approval_handler' in init_params:
                        tool_kwargs['approval_handler'] = self.approval_handler

                    try:
                        # Pre-comprobar si la herramienta ya existe como skill antes de instanciar
                        # Esto evita arranques innecesarios y costosos (como kernels de Jupyter)
                        base_name_pre = getattr(ToolClass, 'name', None)
                        if base_name_pre is None and hasattr(ToolClass, '__fields__') and 'name' in ToolClass.__fields__:
                            base_name_pre = ToolClass.__fields__['name'].default
                        if base_name_pre is None:
                            base_name_pre = ToolClass.__name__

                        if base_name_pre in self.tool_map and self.skill_manager:
                            logger.info(f"Skipping legacy tool '{base_name_pre}' (skill already loaded, skipping instantiation)")
                            continue

                        tool_instance = ToolClass(**tool_kwargs)
                        # Ensure unique tool name to avoid duplicate function declarations in LLM metadata
                        base_name = getattr(tool_instance, 'name', ToolClass.__name__)
                        unique_name = base_name
                        suffix = 1
                        while unique_name in self.tool_map:
                            unique_name = f"{base_name}_{suffix}"
                            suffix += 1
                        if unique_name != base_name:
                            try:
                                setattr(tool_instance, 'name', unique_name)
                            except Exception:
                                pass
                            logger.warning(f"Warning: duplicate tool name '{base_name}' renamed to '{unique_name}'")

                        self.tools.append(tool_instance)
                        self.tool_map[unique_name] = tool_instance

                        # También registrar en legacy_tools para referencia
                        self.legacy_tools.append(tool_instance)
                        self.legacy_tool_map[base_name] = tool_instance

                    except Exception as e:
                        print(f"Error al instanciar herramienta {ToolClass.__name__}: {e}")
                        import traceback
                        traceback.print_exc()
                except Exception as e:
                    print(f"Error crítico al procesar la clase de herramienta {ToolClass.__name__}: {e}")
                    import traceback
                    traceback.print_exc()

    def refresh_skills(self, agent_context: Optional[dict] = None):
        """
        Re-escanea los directorios de skills y carga las nuevas encontradas
        o actualiza las existentes en el registro de herramientas.
        """
        if self.skill_manager and SKILLS_AVAILABLE:
            logger.info("Refrescando sistema de skills...")
            
            # Limpiar listas internas para forzar recarga limpia
            self.tools = []
            self.tool_map = {}
            self.legacy_tools = []
            self.legacy_tool_map = {}
            
            # 1. Re-descubrir skills
            self.skill_manager.discover_all_skills()
            
            # 2. Cargar las herramientas
            self.load_tools(load_legacy=False, load_skills=True, agent_context=agent_context)
            
            # 3. Invalidar la caché del LLMService para que regenere los esquemas
            if self.llm_service:
                self.llm_service.litellm_tools = None
                logger.info("Caché de herramientas de LLMService invalidada.")
            
            logger.info(f"Refresco completado. Total herramientas: {len(self.tool_map)}")
            return True
        return False

    def register_tool(self, tool_instance):
        """Registra una herramienta manualmente."""
        base_name = getattr(tool_instance, 'name', None) or tool_instance.__class__.__name__
        unique_name = base_name
        suffix = 1
        while unique_name in self.tool_map:
            unique_name = f"{base_name}_{suffix}"
            suffix += 1
        if unique_name != base_name:
            try:
                setattr(tool_instance, 'name', unique_name)
            except Exception:
                pass
            logger.warning(f"Warning: duplicate tool name '{base_name}' renamed to '{unique_name}'")
        if unique_name not in self.tool_map:
            self.tools.append(tool_instance)
            self.tool_map[unique_name] = tool_instance

    def get_tools(self):
        return self.tools

    def get_tool(self, tool_name: str):
        """
        Obtiene herramienta, primero de skills, luego legacy.

        Prioridad:
        1. Skill cargada (si skill_manager disponible)
        2. Herramienta legacy
        """
        # Primero buscar en skills
        if self.skill_manager and SKILLS_AVAILABLE:
            tool_info = self.skill_manager.get_tool(tool_name)
            if tool_info:
                return tool_info['tool']

        # Luego buscar en legacy
        return self.tool_map.get(tool_name) or self.legacy_tool_map.get(tool_name)

    def get_tools_for_llm(self, agent_context: dict = None):
        """
        Devuelve lista de herramientas en formato LLM (con metadatos de skill).

        Returns:
            Lista de diccionarios con: name, description, skill, security_level, parameters
        """
        tools_metadata = []

        # Recopilar de skills
        if self.skill_manager and SKILLS_AVAILABLE:
            for tool_name, tool_info in self.skill_manager.tool_registry.items():
                tool = tool_info['tool']
                metadata = {
                    'name': tool_name,
                    'description': getattr(tool, 'description', ''),
                    'skill': tool_info['skill'],
                    'security_level': tool_info['security_level'],
                    'sandbox_required': tool_info['sandbox_required'],
                    'permissions': tool_info.get('permissions', [])
                }
                # Extraer schema de parámetros
                if hasattr(tool, 'parameters_schema'):
                    metadata['parameters'] = tool.parameters_schema
                elif hasattr(tool, 'run') and hasattr(tool.run, '__annotations__'):
                    # Inferir desde type hints
                    metadata['parameters'] = self._infer_schema_from_hints(tool.run)

                tools_metadata.append(metadata)

        # Recopilar de legacy (sin skill info)
        for tool in self.legacy_tools:
            if tool not in self.tools:  # Evitar duplicados
                base_name = getattr(tool, 'name', tool.__class__.__name__)
                metadata = {
                    'name': base_name,
                    'description': getattr(tool, 'description', ''),
                    'skill': 'core_legacy',
                    'security_level': 'unknown',
                    'sandbox_required': False,
                    'permissions': []
                }
                if hasattr(tool, 'parameters_schema'):
                    metadata['parameters'] = tool.parameters_schema
                elif hasattr(tool, 'run') and hasattr(tool.run, '__annotations__'):
                    metadata['parameters'] = self._infer_schema_from_hints(tool.run)

                tools_metadata.append(metadata)

        return tools_metadata

    def _infer_schema_from_hints(self, func):
        """Infiere schema de parámetros desde type hints (simplificado)."""
        import inspect
        from typing import get_type_hints

        try:
            sig = inspect.signature(func)
            type_hints = get_type_hints(func)

            properties = {}
            required = []

            for param_name, param in sig.parameters.items():
                if param_name in ['self', 'cls']:
                    continue

                param_type = type_hints.get(param_name, str)
                type_str = self._type_to_json_schema(param_type)

                properties[param_name] = {
                    'type': type_str,
                    'description': ''  # Podríamos extraer docstring
                }

                if param.default == inspect.Parameter.empty:
                    required.append(param_name)

            return {
                'type': 'object',
                'properties': properties,
                'required': required
            }
        except Exception:
            return None

    def _type_to_json_schema(self, typ) -> str:
        """Convierte tipo Python a JSON Schema type."""
        type_map = {
            str: 'string',
            int: 'integer',
            float: 'number',
            bool: 'boolean',
            list: 'array',
            dict: 'object'
        }
        return type_map.get(typ, 'string')

    def set_agent_state(self, agent_state):
        for tool in self.tools:
            if hasattr(tool, 'agent_state'):
                tool.agent_state = agent_state
