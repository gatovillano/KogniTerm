"""
SkillManager: Gestión centralizada de skills con discovery, loading y registro.

Este módulo implementa un sistema modular de skills que permite:
- Discovery automático de skills en múltiples ubicaciones
- Carga dinámica (JIT) de módulos Python
- Registro centralizado de herramientas
- Filtrado por contexto y permisos
- Compatibilidad con sistema legacy de herramientas
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, get_type_hints
import yaml
import importlib.util
import sys
import logging
import json
import queue
import inspect
import re
from types import ModuleType
from dataclasses import dataclass, field
from datetime import datetime
from langchain_core.messages import SystemMessage

logger = logging.getLogger(__name__)


@dataclass
class Skill:
    """Representación de una skill con sus metadatos y herramientas."""
    path: Path
    name: str
    version: str = "1.0.0"
    author: str = ""
    description: str = ""
    category: str = "general"
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    required_permissions: List[str] = field(default_factory=list)
    allowed_tools: List[str] = field(default_factory=list)
    denied_tools: List[str] = field(default_factory=list)
    security_level: str = "low"  # low, medium, high, elevated
    allowlist: bool = False
    auto_approve: bool = False
    instructions: str = ""
    resources: List[str] = field(default_factory=list)
    assets: List[str] = field(default_factory=list)
    compatibility: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    scripts_path: Path = field(init=False)
    references_path: Path = field(init=False)
    assets_path: Path = field(init=False)
    loaded: bool = False
    tools: List[Any] = field(default_factory=list)

    def __post_init__(self):
        self.scripts_path = self.path / 'scripts'
        self.references_path = self.path / 'references'
        self.assets_path = self.path / 'assets'


class SkillValidator:
    """Valida la estructura y metadatos de una skill."""

    REQUIRED_FIELDS = ['name', 'description']
    VALID_SECURITY_LEVELS = ['low', 'standard', 'medium', 'high', 'elevated']

    def validate_skill(self, skill_path: Path) -> Tuple[bool, List[str]]:
        """
        Valida que una skill tenga la estructura correcta.

        Returns:
            (is_valid, errors)
        """
        errors = []

        # 1. Verificar que es un directorio
        if not skill_path.is_dir():
            errors.append(f"Skill path no es un directorio: {skill_path}")
            return False, errors

        # 2. Verificar SKILL.md existe
        skill_file = skill_path / 'SKILL.md'
        if not skill_file.exists():
            errors.append(f"SKILL.md no encontrado en {skill_path}")
            return False, errors

        # 3. Parsear y validar SKILL.md
        config, parse_error = self._parse_skill_file(skill_file)
        if parse_error:
            errors.append(f"Error parseando SKILL.md: {parse_error}")
            return False, errors

        # 4. Verificar campos requeridos
        for field in self.REQUIRED_FIELDS:
            if field not in config:
                errors.append(f"Campo requerido faltante en SKILL.md: {field}")

        scripts_dir = skill_path / 'scripts'
        has_scripts_dir = scripts_dir.exists() and scripts_dir.is_dir()

        # 4.1. Verificar que exista al menos una vía útil: instrucciones o scripts/
        instructions = str(config.get('instructions', '')).strip()
        if not instructions and not has_scripts_dir:
            errors.append("SKILL.md debe incluir instrucciones o un directorio scripts/")

        # 5. Verificar security_level
        if 'security_level' in config:
            if config['security_level'] not in self.VALID_SECURITY_LEVELS:
                errors.append(f"security_level inválido: {config['security_level']}. "
                              f"Válidos: {self.VALID_SECURITY_LEVELS}")

        # 6. Verificar estructura de directorios opcionales
        if scripts_dir.exists() and not scripts_dir.is_dir():
            errors.append(f"'scripts/' no es un directorio")

        references_dir = skill_path / 'references'
        if references_dir.exists() and not references_dir.is_dir():
            errors.append(f"'references/' no es un directorio")

        assets_dir = skill_path / 'assets'
        if assets_dir.exists() and not assets_dir.is_dir():
            errors.append(f"'assets/' no es un directorio")

        # 7. Si existe scripts/, verificar que tenga archivos Python o al menos sea un contenedor válido
        if scripts_dir.exists() and scripts_dir.is_dir():
            # El estándar permite skills solo-instrucciones; scripts/ puede estar vacío.
            # Si el directorio existe, no forzamos presencia de código.
            pass

        return len(errors) == 0, errors

    def _parse_skill_file(self, skill_file: Path) -> Tuple[Optional[dict], Optional[str]]:
        """Parsea el SKILL.md con frontmatter YAML."""
        try:
            with open(skill_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Buscar frontmatter YAML entre ---
            if content.startswith('---'):
                end_idx = content.find('---', 3)
                if end_idx != -1:
                    yaml_content = content[3:end_idx].strip()
                    body = content[end_idx + 3:].strip()
                    raw_config = yaml.safe_load(yaml_content) or {}
                    config = self._normalize_manifest(raw_config)
                    config['instructions'] = body
                    return config, None
            return None, "Formato frontmatter YAML inválido (debe empezar con ---)"
        except yaml.YAMLError as e:
            return None, f"Error YAML: {str(e)}"
        except Exception as e:
            return None, f"Error leyendo archivo: {str(e)}"

    def _normalize_manifest(self, raw_config: Dict[str, Any]) -> Dict[str, Any]:
        """Normaliza claves del manifiesto al formato interno de KogniTerm."""
        key_map = {
            'allowed-tools': 'allowed_tools',
            'denied-tools': 'denied_tools',
            'required-tools': 'required_tools',
            'security-level': 'security_level',
            'required-permissions': 'required_permissions',
        }

        normalized: Dict[str, Any] = {}
        for key, value in raw_config.items():
            normalized_key = key_map.get(key, key)
            normalized[normalized_key] = value

        for list_key in ('tags', 'dependencies', 'required_permissions', 'allowed_tools', 'denied_tools', 'resources', 'assets'):
            value = normalized.get(list_key)
            if value is None:
                continue
            if isinstance(value, str):
                normalized[list_key] = [value]
            elif not isinstance(value, list):
                normalized[list_key] = list(value) if isinstance(value, (tuple, set)) else [value]

        if 'metadata' not in normalized or normalized['metadata'] is None:
            normalized['metadata'] = {}
        if 'compatibility' not in normalized or normalized['compatibility'] is None:
            normalized['compatibility'] = {}

        # Conservar campos estándar adicionales sin romper la construcción del dataclass Skill.
        allowed_field_names = {
            name for name, field_info in Skill.__dataclass_fields__.items()
            if field_info.init
        }
        extra_fields = {
            key: value for key, value in normalized.items()
            if key not in allowed_field_names
        }
        if extra_fields:
            existing_metadata = normalized.get('metadata', {}) or {}
            if not isinstance(existing_metadata, dict):
                existing_metadata = {'value': existing_metadata}
            merged_metadata = dict(existing_metadata)
            merged_metadata.setdefault('frontmatter', {})
            if not isinstance(merged_metadata['frontmatter'], dict):
                merged_metadata['frontmatter'] = {'value': merged_metadata['frontmatter']}
            merged_metadata['frontmatter'].update(extra_fields)
            normalized['metadata'] = merged_metadata

        normalized = {
            key: value for key, value in normalized.items()
            if key in allowed_field_names
        }

        return normalized


class SkillLoader:
    """Carga dinámica de módulos Python desde scripts/."""

    DYNAMIC_SKILLS_PACKAGE = "kogniterm_dynamic_skills"

    def load_tools_from_skill(self, skill: Skill) -> List[Any]:
        """
        Importa todas las herramientas desde scripts/ de una skill.

        Busca funciones o clases callables que tengan atributo 'name' o método 'run'.
        """
        tools = []

        script_candidates: List[Path] = []
        if skill.scripts_path.exists() and skill.scripts_path.is_dir():
            script_candidates.extend(sorted(skill.scripts_path.rglob('*.py')))
        else:
            script_candidates.extend(sorted(skill.path.glob('*.py')))

        for script_file in script_candidates:
            try:
                module_tools = self._load_module_tools(script_file, skill.name)
                tools.extend(module_tools)
                logger.debug(f"Cargados {len(module_tools)} herramientas desde {script_file.name}")
            except Exception as e:
                logger.error(f"Error cargando módulo {script_file}: {e}", exc_info=True)

        return tools

    def _load_module_tools(self, script_file: Path, skill_name: str) -> List[Any]:
        """Carga un módulo Python y extrae las herramientas."""
        module_name = self._build_dynamic_module_name(skill_name, script_file.stem)
        package_name = module_name.rsplit('.', 1)[0]
        self._ensure_namespace_package(package_name, script_file.parent)

        spec = importlib.util.spec_from_file_location(module_name, script_file)

        if spec is None or spec.loader is None:
            raise ImportError(f"No se pudo cargar spec para {script_file}")

        if module_name in sys.modules:
            module = sys.modules[module_name]
        else:
            module = importlib.util.module_from_spec(spec)
            module.__package__ = package_name
            sys.modules[module_name] = module  # Registrar en sys.modules
            spec.loader.exec_module(module)

        # Buscar callables que sean herramientas
        tools = []

        # Obtener metadatos del módulo para inyectar en las funciones si es necesario
        module_name_attr = getattr(module, 'name', None)
        module_desc_attr = getattr(module, 'description', None)
        module_params_attr = getattr(module, 'parameters_schema', None)
        module_tool_schema = getattr(module, 'tool_schema', None)

        # Funciones que claramente NO son herramientas (helpers, descripción, etc.)
        excluded_names = (
            'get_action_description', 'get_description', 'description',
            'set_llm_service', 'validate', 'sanitize', 'format_output', 'format_input'
        )

        # Estrategia 1: Buscar objetos con atributos 'name' o método 'run' (clases legacy)
        for attr_name in dir(module):
            if attr_name.startswith('_') or attr_name in excluded_names:
                continue
            attr = getattr(module, attr_name)
            if callable(attr):
                 # Solo procesar objetos definidos en el módulo (no imports)
                if getattr(attr, '__module__', None) != module_name:
                    continue
                if hasattr(attr, 'name') or hasattr(attr, 'run'):
                    tools.append(attr)

        # Estrategia 2: Si no se encontraron herramientas, buscar funciones callables
        # y verificar si el módulo tiene variables 'name' y 'description'
        if not tools:
            seen_objects = set()
            for attr_name in sorted(dir(module)): # Origen consistente
                if attr_name.startswith('_') or attr_name in excluded_names:
                    continue
                attr = getattr(module, attr_name)
                
                # Solo procesar callables definidos en el módulo (no imports)
                if callable(attr) and getattr(attr, '__module__', None) == module_name:
                    # Evitar clases de esquema (Pydantic models) o clases que no son herramientas
                    if isinstance(attr, type):
                        # Solo permitir clases si tienen 'run' o 'name' (clases legacy)
                        if not (hasattr(attr, 'run') or hasattr(attr, 'name')):
                            continue
                            
                    if id(attr) in seen_objects:
                        continue
                        
                    is_tool = False
                    reason = ""
                    
                    # Si ya encontramos una herramienta que coincide con el nombre del módulo, no agregar más
                    if tools and module_name_attr and attr_name != module_name_attr:
                        continue
                    
                    # Caso A: El nombre de la función coincide con 'name' del módulo
                    if module_name_attr and attr_name == module_name_attr:
                        is_tool = True
                        reason = "match_module_name"
                    # Caso B: Funciones conocidas
                    elif attr_name in ['execute_command', 'file_operations', 'memory_append', 'memory_read', 'memory_init', 'call_agent', 'think', 'web_fetch', 'pc_interaction']:
                        is_tool = True
                        reason = "known_name"
                    # Caso C: La función termina en _skill o _tool
                    elif attr_name.endswith('_skill') or attr_name.endswith('_tool'):
                        is_tool = True
                        reason = "convention_suffix"
                    # Caso D: Es la única función principal o se llama igual que la skill
                    elif attr_name == skill_name:
                        is_tool = True
                        reason = "match_skill_name"
                    # Caso E: tool.py y no tenemos nada aún (solo la primera función útil)
                    elif script_file.name == 'tool.py' and not tools and not attr_name.endswith('_sync'):
                        is_tool = True
                        reason = "tool_py_default"

                    if is_tool:
                        # Inyectar metadata solo si no la tiene
                        has_name = hasattr(attr, 'name')
                        has_desc = hasattr(attr, 'description')
                        has_params = hasattr(attr, 'parameters_schema')

                        # 1. Determinar el nombre
                        if not has_name:
                            # Priorizar concordancia exacta
                            if module_name_attr and attr_name == module_name_attr:
                                attr.name = module_name_attr
                            elif module_tool_schema and module_tool_schema.get('name') == attr_name:
                                attr.name = attr_name
                            elif reason == "tool_py_default" and len(tools) == 0 and module_name_attr:
                                # Si es la primera/única y el módulo tiene un nombre oficial, usarlo
                                attr.name = module_name_attr
                            elif reason == "tool_py_default" and len(tools) == 0 and module_tool_schema and module_tool_schema.get('name'):
                                attr.name = module_tool_schema.get('name')
                            else:
                                # Por defecto, el nombre de la función
                                attr.name = attr_name

                        # 2. Determinar la descripción
                        if not has_desc:
                            # Priorizar: tool_schema['description'] -> module.description -> docstring
                            suggested_desc = module_desc_attr
                            if not suggested_desc and module_tool_schema:
                                suggested_desc = module_tool_schema.get('description')
                            
                            # Check if current tool matches the module "main" tool definition
                            current_name = getattr(attr, 'name', '')
                            main_module_name = module_name_attr or (module_tool_schema.get('name') if module_tool_schema else None)
                            
                            is_main_tool = (current_name == main_module_name) if main_module_name else (reason == "tool_py_default")

                            if suggested_desc and is_main_tool:
                                attr.description = suggested_desc
                            else:
                                attr.description = (attr.__doc__.strip() if attr.__doc__ else "") or suggested_desc or ""

                        # 3. Determinar el esquema de parámetros
                        if not has_params:
                            # Intentar buscar en un mapa de esquemas del módulo (tool_schemas)
                            module_schemas = getattr(module, 'tool_schemas', None)
                            if isinstance(module_schemas, dict) and attr_name in module_schemas:
                                attr.parameters_schema = module_schemas[attr_name]
                            else:
                                # Fallback al esquema global para la herramienta principal
                                suggested_params = module_params_attr
                                if not suggested_params and module_tool_schema:
                                    suggested_params = module_tool_schema.get('parameters')
                                
                                current_name = getattr(attr, 'name', '')
                                main_module_name = module_name_attr or (module_tool_schema.get('name') if module_tool_schema else None)
                                is_main_tool = (current_name == main_module_name) if main_module_name else (reason == "tool_py_default")
                                
                                if suggested_params and is_main_tool:
                                    attr.parameters_schema = suggested_params
                        
                        # 4. Inyectar get_action_description si existe en el módulo
                        if not hasattr(attr, 'get_action_description'):
                            get_desc_func = getattr(module, 'get_action_description', None)
                            if get_desc_func and callable(get_desc_func):
                                # Solo inyectar en la herramienta principal o si el nombre coincide
                                current_name = getattr(attr, 'name', '')
                                main_module_name = module_name_attr or (module_tool_schema.get('name') if module_tool_schema else None)
                                is_main_tool = (current_name == main_module_name) if main_module_name else (reason == "tool_py_default")
                                
                                if is_main_tool:
                                    attr.get_action_description = get_desc_func
                                    logger.debug(f"Inyectado get_action_description en {attr.name}")

                        # 5. Asegurar método invoke para compatibilidad con LangChain
                        if not hasattr(attr, 'invoke'):
                            # Crear un wrapper para que funcione como una herramienta de LangChain
                            def create_invoke(func):
                                def invoke(input_data=None, config=None, **kwargs):
                                    # Manejar diferentes formas de pasar argumentos
                                    if isinstance(input_data, dict):
                                        return func(**input_data)
                                    return func(**kwargs)
                                return invoke
                            attr.invoke = create_invoke(attr)

                        # 6. Detectar parámetros de inyección de dependencias
                        try:
                            import inspect
                            sig = inspect.signature(attr)
                            known_injection_params = {
                                'llm_service', 'terminal_ui', 'interrupt_queue',
                                'approval_handler', 'agent_state', 'command_executor',
                                'history_manager', 'session_manager'
                            }
                            injection_params = {}
                            for param_name, param in sig.parameters.items():
                                if param_name in known_injection_params:
                                    injection_params[param_name] = True
                            if injection_params:
                                attr._kogniterm_injection_params = injection_params
                                logger.debug(f"Parámetros de inyección detectados en {attr.name}: {list(injection_params.keys())}")
                        except Exception as e:
                            logger.debug(f"No se pudieron detectar parámetros de inyección en {attr_name}: {e}")

                        tools.append(attr)
                        seen_objects.add(id(attr))


        return tools

    def _build_dynamic_module_name(self, skill_name: str, module_stem: str) -> str:
        """Construye un nombre de módulo válido y estable para imports relativos."""
        safe_skill_name = self._to_valid_module_part(skill_name)
        safe_module_stem = self._to_valid_module_part(module_stem)
        return f"{self.DYNAMIC_SKILLS_PACKAGE}.{safe_skill_name}.scripts.{safe_module_stem}"

    @staticmethod
    def _to_valid_module_part(value: str) -> str:
        """Normaliza texto para usarlo como parte de un nombre de módulo Python."""
        normalized = re.sub(r'[^0-9a-zA-Z_]', '_', value)
        if not normalized:
            return "module"
        if normalized[0].isdigit():
            return f"_{normalized}"
        return normalized

    def _ensure_namespace_package(self, package_name: str, package_path: Path) -> None:
        """Crea paquetes namespace dinámicos para soportar imports relativos entre scripts."""
        parts = package_name.split('.')
        current_name = ""

        for index, part in enumerate(parts):
            current_name = part if not current_name else f"{current_name}.{part}"
            module = sys.modules.get(current_name)

            if module is None:
                module = ModuleType(current_name)
                module.__package__ = current_name
                module.__path__ = []
                sys.modules[current_name] = module

            # Solo el paquete leaf (scripts) necesita saber dónde buscar submódulos.
            if index == len(parts) - 1:
                existing_paths = list(getattr(module, '__path__', []))
                path_str = str(package_path)
                if path_str not in existing_paths:
                    existing_paths.append(path_str)
                module.__path__ = existing_paths


class SkillManager:
    """
    Gestor principal de skills.

    Responsabilidades:
    - Discovery de skills en múltiples ubicaciones
    - Validación de estructura y metadatos
    - Carga JIT de módulos Python
    - Registro centralizado de herramientas
    - Filtrado por contexto y permisos
    """

    def __init__(
        self,
        base_path: Optional[Path] = None,
        user_skills_path: Optional[Path] = None,
        global_skills_path: Optional[Path] = None,
        llm_service=None,
        interrupt_queue: Optional[queue.Queue] = None,
        terminal_ui=None,
        embeddings_service=None,
        vector_db_manager=None,
        approval_handler=None
    ):
        """
        Inicializa el SkillManager.

        Args:
            base_path: Ruta base del proyecto (kogniterm/)
            user_skills_path: Ruta de skills de usuario (~/.kogniterm/skills)
            global_skills_path: Ruta de skills globales del agente (~/.agent/skills).
                                 Si es None se usa el valor por defecto.
            llm_service: Instancia de LLMService
            interrupt_queue: Cola de interrupción
            terminal_ui: Interfaz de terminal
            embeddings_service: Servicio de embeddings
            vector_db_manager: Gestor de base de datos vectorial
            approval_handler: Manejador de aprobación de comandos
        """
        self.base_path = base_path or Path(__file__).parent.parent.parent
        self.user_skills_path = user_skills_path or Path.home() / '.kogniterm' / 'skills'

        # Ruta de skills instaladas globalmente (compartidas entre agentes)
        self.global_skills_path = global_skills_path or Path.home() / '.agents' / 'skills'

        # Contexto compartido
        self.llm_service = llm_service
        self.interrupt_queue = interrupt_queue
        self.terminal_ui = terminal_ui
        self.embeddings_service = embeddings_service
        self.vector_db_manager = vector_db_manager
        self.approval_handler = approval_handler

        # Rutas de skills por nivel
        self.bundled_path = self.base_path / 'skills' / 'bundled'
        self.legacy_bundled_path = self.base_path / 'bundled'
        self.managed_path = self.user_skills_path / 'managed'
        self.workspace_path = self.base_path / 'skills' / 'workspace'
        self.legacy_workspace_path = self.base_path / 'workspace'
        self.external_path = self.base_path / 'skills' / 'external'
        self.legacy_external_path = self.base_path / 'external'

        # Registros
        self.skills: Dict[str, Skill] = {}  # name -> Skill
        self.loaded_skills: set = set()     # Nombres de skills cargadas
        self.tool_registry: Dict[str, Dict[str, Any]] = {}  # tool_name -> {tool, skill, security_level}
        self.skill_embeddings: Dict[str, List[float]] = {}  # name -> embedding vector

        # Componentes
        self.validator = SkillValidator()
        self.loader = SkillLoader()

        logger.info(
            f"SkillManager inicializado. Bases: bundled={self.bundled_path}, "
            f"global={self.global_skills_path}, managed={self.managed_path}, "
            f"workspace={self.workspace_path}"
        )

    def discover_all_skills(self) -> List[Skill]:
        """
        Descubre todas las skills disponibles en todas las ubicaciones.

        Orden de prioridad (mayor a menor):
          1. bundled   – skills integradas con KogniTerm
          2. global    – skills instaladas globalmente en ~/.agent/skills
          3. managed   – skills del usuario (~/.kogniterm/skills/managed)
          4. workspace – skills del proyecto actual
          5. external  – skills externas / legacy

        Returns:
            Lista de objetos Skill descubiertos (no necesariamente cargados)
        """
        discovered = []
        search_paths = [
            ('bundled',   self.bundled_path),
            ('bundled',   self.legacy_bundled_path),
            ('global',    self.global_skills_path),   # ← ~/.agent/skills
            ('managed',   self.managed_path),
            ('workspace', self.workspace_path),
            ('workspace', self.legacy_workspace_path),
            ('external',  self.external_path),
            ('external',  self.legacy_external_path),
        ]

        seen_skill_paths = set()
        for level, base_dir in search_paths:
            if not base_dir.exists():
                logger.debug(f"Directorio no existe (skip): {base_dir}")
                continue

            logger.info(f"Buscando skills en {level}: {base_dir}")
            skills_in_dir = self._discover_in_dir(base_dir, level)
            for skill in skills_in_dir:
                resolved_path = skill.path.resolve()
                if resolved_path in seen_skill_paths:
                    continue
                seen_skill_paths.add(resolved_path)
                discovered.append(skill)

        # Registrar en diccionario
        for skill in discovered:
            if skill.name in self.skills:
                skill.loaded = self.skills[skill.name].loaded
                skill.tools = self.skills[skill.name].tools
            self.skills[skill.name] = skill

        logger.info(f"Discovery completado: {len(discovered)} skills encontradas")
        return discovered

    def _discover_in_dir(self, base_dir: Path, level: str) -> List[Skill]:
        """Busca skills en un directorio base."""
        skills = []

        seen_paths = set()
        for skill_file in base_dir.rglob('SKILL.md'):
            skill_dir = skill_file.parent

            # Saltar directorios ocultos o de soporte (relativos al base_dir)
            try:
                relative_parts = skill_dir.relative_to(base_dir).parts
            except ValueError:
                relative_parts = skill_dir.parts
            if any(part.startswith('.') or part.startswith('_') for part in relative_parts):
                continue
            if skill_dir in seen_paths:
                continue
            seen_paths.add(skill_dir)

            try:
                is_valid, errors = self.validator.validate_skill(skill_dir)
                if not is_valid:
                    logger.warning(f"Skill inválida en {skill_dir}: {errors}")
                    continue

                config, _ = self.validator._parse_skill_file(skill_file)
                if not config:
                    continue
                skill = Skill(path=skill_dir, **config)
                skills.append(skill)
                logger.debug(f"Skill descubierta: {skill.name} (nivel: {level})")

            except Exception as e:
                logger.error(f"Error procesando skill {skill_dir}: {e}", exc_info=True)

        return skills

    def load_skill(self, skill_name: str, agent_context: Optional[dict] = None) -> bool:
        """
        Carga una skill si existe y no está ya cargada.

        Args:
            skill_name: Nombre de la skill a cargar
            agent_context: Contexto del agente (para filtrado de permisos)

        Returns:
            True si se cargó exitosamente, False en caso contrario
        """
        if skill_name not in self.skills:
            logger.warning(f"Skill '{skill_name}' no encontrada en registry")
            return False

        if skill_name in self.loaded_skills:
            logger.debug(f"Skill '{skill_name}' ya está cargada")
            return True

        skill = self.skills[skill_name]

        # Validar permisos contra contexto del agente (futuro)
        if agent_context and not self._check_permissions(skill, agent_context):
            logger.warning(f"Skill '{skill_name}' no tiene permisos para este agente")
            return False

        try:
            # 1. Validar dependencias
            self._validate_dependencies(skill.dependencies)

            # 2. Cargar herramientas desde scripts/ o archivos Python del skill
            tools = self.loader.load_tools_from_skill(skill)
            if not tools and not skill.instructions.strip():
                logger.error(f"La skill '{skill_name}' no tiene herramientas ni instrucciones")
                return False

            if not tools and skill.instructions.strip():
                # Crear herramienta procedimental por defecto
                def procedural_tool(**kwargs) -> str:
                    return f"### INSTRUCCIONES DE LA SKILL '{skill.name}' ###\n\n{skill.instructions}"
                
                procedural_tool.name = skill.name
                procedural_tool.description = skill.description or f"Lee las instrucciones de la skill {skill.name}"
                procedural_tool.parameters_schema = {"type": "object", "properties": {}}
                procedural_tool.invoke = lambda *args, **kwargs: procedural_tool()
                
                tools.append(procedural_tool)
                logger.info(f"Creada herramienta procedimental para '{skill_name}'")

            # Inyectar llm_service en el módulo y herramientas
            if self.llm_service:
                # Inyectar en el módulo (variable global _llm_service)
                for tool in tools:
                    module_name = getattr(tool, '__module__', None)
                    if module_name:
                        module = sys.modules.get(module_name)
                        if module and hasattr(module, '_llm_service'):
                            setattr(module, '_llm_service', self.llm_service)
                
                # Inyectar en cada herramienta individual si lo soporta
                for tool in tools:
                    if hasattr(tool, 'llm_service'):
                        try:
                            setattr(tool, 'llm_service', self.llm_service)
                        except Exception:
                            pass

            # Inyectar terminal_ui en el módulo y herramientas
            if self.terminal_ui:
                for tool in tools:
                    module_name = getattr(tool, '__module__', None)
                    if module_name:
                        module = sys.modules.get(module_name)
                        if module and hasattr(module, '_terminal_ui'):
                            setattr(module, '_terminal_ui', self.terminal_ui)

                for tool in tools:
                    if hasattr(tool, 'terminal_ui'):
                        try:
                            setattr(tool, 'terminal_ui', self.terminal_ui)
                        except Exception:
                            pass

            # Inyectar helpers de estado persistente (Proposal C)
            state_file = self.base_path / '.kogniterm' / 'state' / f"{skill_name}.json"

            # task_tracker no persiste entre sesiones: borrar estado previo al cargar
            if skill_name == "task_tracker" and state_file.exists():
                try:
                    state_file.unlink()
                    logger.debug("Estado previo de task_tracker borrado al iniciar sesión.")
                except Exception as _e:
                    logger.debug(f"No se pudo borrar estado de task_tracker: {_e}")

            def get_state() -> dict:
                if state_file.exists():
                    try:
                        with open(state_file, 'r', encoding='utf-8') as sf:
                            return json.load(sf)
                    except Exception as e:
                        logger.error(f"Error leyendo estado para {skill_name}: {e}")
                return {}
                
            def save_state(state: dict):
                try:
                    state_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(state_file, 'w', encoding='utf-8') as sf:
                        json.dump(state, sf, ensure_ascii=False, indent=2)
                except Exception as e:
                    logger.error(f"Error guardando estado para {skill_name}: {e}")

            for tool in tools:
                module_name = getattr(tool, '__module__', None)
                if module_name:
                    module = sys.modules.get(module_name)
                    if module:
                        setattr(module, 'get_skill_state', get_state)
                        setattr(module, 'save_skill_state', save_state)

            # 3. Registrar cada herramienta en tool_registry
            for tool in tools:
                tool_name = getattr(tool, 'name', tool.__class__.__name__)
                # Asegurar nombre único
                unique_name = self._get_unique_tool_name(tool_name, skill_name)
                if unique_name != tool_name and hasattr(tool, 'name'):
                    try:
                        setattr(tool, 'name', unique_name)
                    except Exception:
                        pass

                # Inyectar parameters_schema inferido si no existe
                if not hasattr(tool, 'parameters_schema'):
                    if hasattr(tool, 'run') and hasattr(tool.run, '__annotations__'):
                        try:
                            setattr(tool, 'parameters_schema', self._infer_schema_from_hints(tool.run))
                        except Exception:
                            pass
                    elif callable(tool) and hasattr(tool, '__annotations__'):
                        try:
                            setattr(tool, 'parameters_schema', self._infer_schema_from_hints(tool))
                        except Exception:
                            pass

                self.tool_registry[unique_name] = {
                    'tool': tool,
                    'skill': skill.name,
                    'security_level': skill.security_level,
                    'permissions': skill.required_permissions
                }
                logger.debug(f"Herramienta registrada: {unique_name} (skill: {skill.name})")

            # 4. Marcar skill como cargada
            skill.loaded = True
            skill.tools = tools
            self.loaded_skills.add(skill_name)

            logger.info(f"✅ Skill '{skill_name}' cargada ({len(tools)} herramientas)")
            return True

        except Exception as e:
            logger.error(f"❌ Error cargando skill '{skill_name}': {e}", exc_info=True)
            return False

    def _get_unique_tool_name(self, base_name: str, skill_name: Optional[str] = None) -> str:
        """Genera un nombre único para evitar colisiones."""
        unique_name = base_name
        if unique_name in self.tool_registry:
            # Si la herramienta ya existe y pertenece a la misma skill, permitimos el override
            if skill_name and self.tool_registry.get(unique_name, {}).get('skill') == skill_name:
                return unique_name

            suffix = 1
            while unique_name in self.tool_registry:
                unique_name = f"{base_name}_{suffix}"
                suffix += 1
        return unique_name

    def _check_permissions(self, skill: Skill, agent_context: dict) -> bool:
        """
        Verifica si el agente tiene permisos para usar esta skill.

        TODO: Implementar lógica de permisos basada en agent_context
        """
        # Por ahora, siempre True
        return True

    def _validate_dependencies(self, dependencies: List[str]):
        """
        Valida e instala automáticamente dependencias faltantes usando pip.
        """
        import subprocess
        import sys
        import importlib.metadata
        
        for dep in dependencies:
            package_name = dep
            for op in ['==', '>=', '<=', '>', '<']:
                if op in dep:
                    package_name = dep.split(op)[0]
                    break
            
            package_name = package_name.strip()
            # Normalizar nombre para buscar en metadatos (e.g. reemplazar "_" por "-")
            normalized_name = package_name.replace('_', '-')
            
            installed = False
            for name in [package_name, normalized_name]:
                try:
                    importlib.metadata.version(name)
                    installed = True
                    break
                except importlib.metadata.PackageNotFoundError:
                    continue
            
            if not installed:
                logger.info(f"Instalando dependencia faltante para skill: {dep}...")
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", dep])
                    logger.info(f"✅ Dependencia '{dep}' instalada exitosamente.")
                except Exception as e:
                    logger.error(f"❌ Error al instalar dependencia '{dep}': {e}")

    def unload_skill(self, skill_name: str):
        """Descarga una skill (útil para recargar o desinstalar)."""
        if skill_name not in self.loaded_skills:
            return

        # Remover herramientas del registro
        to_remove = [k for k, v in self.tool_registry.items() if v['skill'] == skill_name]
        for key in to_remove:
            del self.tool_registry[key]

        self.loaded_skills.remove(skill_name)
        if skill_name in self.skills:
            self.skills[skill_name].loaded = False
            self.skills[skill_name].tools = []

        # Remover módulos cargados de sys.modules para permitir recarga limpia
        safe_skill_name = self._to_valid_module_part(skill_name)
        prefix = f"{self.DYNAMIC_SKILLS_PACKAGE}.{safe_skill_name}"
        modules_to_remove = [
            name for name in list(sys.modules.keys())
            if name == prefix or name.startswith(prefix + ".")
        ]
        for name in modules_to_remove:
            sys.modules.pop(name, None)

        logger.info(f"Skill '{skill_name}' descargada ({len(to_remove)} herramientas removidas)")

    def reload_skill(self, skill_name: str) -> bool:
        """Recarga una skill (útil en desarrollo)."""
        if skill_name not in self.skills:
            return False

        skill_path = self.skills[skill_name].path
        self.unload_skill(skill_name)

        # Re-descubrir esta skill específica
        is_valid, errors = self.validator.validate_skill(skill_path)
        if not is_valid:
            logger.error(f"No se puede recargar skill '{skill_name}': {errors}")
            return False

        config, _ = self.validator._parse_skill_file(skill_path / 'SKILL.md')
        self.skills[skill_name] = Skill(path=skill_path, **(config or {}))

        # Volver a cargar la skill
        return self.load_skill(skill_name)

    def register_tool(self, tool_instance: Any):
        """Registra dinámicamente una herramienta individual en el gestor."""
        tool_name = getattr(tool_instance, 'name', tool_instance.__class__.__name__)
        # Asegurar nombre único
        unique_name = self._get_unique_tool_name(tool_name, "dynamic")
        if unique_name != tool_name and hasattr(tool_instance, 'name'):
            try:
                setattr(tool_instance, 'name', unique_name)
            except Exception:
                pass

        # Asegurar método invoke para compatibilidad con LangChain
        if not hasattr(tool_instance, 'invoke'):
            def create_invoke(func):
                def invoke(input_data=None, config=None, **kwargs):
                    if isinstance(input_data, dict):
                        return func(**input_data)
                    return func(**kwargs)
                return invoke
            tool_instance.invoke = create_invoke(tool_instance)

        self.tool_registry[unique_name] = {
            'tool': tool_instance,
            'skill': 'dynamic',
            'security_level': 'low',
            'permissions': []
        }
        logger.info(f"Herramienta dinámica registrada en SkillManager: {unique_name}")

    def get_tool(self, tool_name: str) -> Optional[Any]:
        """Obtiene la instancia de una herramienta por nombre.

        No hay sandbox de procesos: las herramientas se ejecutan en el mismo
        intérprete. El aislamiento de recursos (memoria, fds) y la protección
        de credenciales se aplican caso por caso aguas arriba cuando la
        herramienta lo requiere (ver ``CommandApprovalHandler`` y
        ``command_executor``).
        """
        tool_info = self.tool_registry.get(tool_name)
        if tool_info:
            return tool_info.get('tool')
        return None

    def get_skill_for_tool(self, tool_name: str) -> Optional[Skill]:
        """Obtiene la skill que provee una herramienta."""
        tool_info = self.tool_registry.get(tool_name)
        if tool_info:
            skill_name = tool_info['skill']
            return self.skills.get(skill_name)
        return None

    def get_available_tools(self, agent_context: Optional[dict] = None) -> List[Dict[str, Any]]:
        """
        Obtiene todas las herramientas disponibles, opcionalmente filtradas por contexto.

        Returns:
            Lista de diccionarios con metadata de cada herramienta
        """
        available = []

        for tool_name, tool_info in self.tool_registry.items():
            # Filtrar por allowlist del agente (futuro)
            skill = self.skills.get(tool_info['skill'])

            metadata = {
                'name': tool_name,
                'description': getattr(tool_info['tool'], 'description', ''),
                'skill': tool_info['skill'],
                'security_level': tool_info['security_level'],
                'permissions': tool_info.get('permissions', []),
                'loaded': skill.loaded if skill else False
            }
            available.append(metadata)

        return available

    def get_tools_by_security_level(self, level: str) -> List[Dict[str, Any]]:
        """Filtra herramientas por nivel de seguridad."""
        return [
            t for t in self.get_available_tools()
            if t['security_level'] == level
        ]

    def get_tools_by_permission(self, permission: str) -> List[Dict[str, Any]]:
        """Filtra herramientas por permiso requerido."""
        return [
            t for t in self.get_available_tools()
            if permission in t['permissions']
        ]

    def list_skills(self) -> List[Dict[str, Any]]:
        """Lista todas las skills con su estado."""
        return [
            {
                'name': skill.name,
                'version': skill.version,
                'description': skill.description,
                'category': skill.category,
                'tags': skill.tags,
                'loaded': skill.loaded,
                'tool_count': len(skill.tools),
                'path': str(skill.path)
            }
            for skill in self.skills.values()
        ]

    def get_skill_info(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """Obtiene información detallada de una skill."""
        if skill_name not in self.skills:
            return None

        skill = self.skills[skill_name]
        return {
            'name': skill.name,
            'version': skill.version,
            'description': skill.description,
            'category': skill.category,
            'tags': skill.tags,
            'dependencies': skill.dependencies,
            'required_permissions': skill.required_permissions,
            'allowed_tools': skill.allowed_tools,
            'denied_tools': skill.denied_tools,
            'security_level': skill.security_level,
            'allowlist': skill.allowlist,
            'auto_approve': skill.auto_approve,
            'instructions': skill.instructions,
            'loaded': skill.loaded,
            'tool_count': len(skill.tools),
            'tools': [getattr(t, 'name', t.__class__.__name__) for t in skill.tools],
            'resources': skill.resources,
            'assets': skill.assets,
            'compatibility': skill.compatibility,
            'metadata': skill.metadata,
            'path': str(skill.path)
        }

    def _score_skill_relevance(self, skill: Skill, query: str, query_embedding: Optional[List[float]] = None) -> float:
        """
        Calcula una puntuación de relevancia para una skill basada en la query.
        Mejoras: Mayor peso a las tags y nombre exacto.
        También utiliza similitud de coseno si se proporcionan embeddings.
        """
        if not query:
            return 1.0

        normalized_query = re.sub(r"\s+", " ", query.lower()).strip()
        if not normalized_query:
            return 0.0

        score = 0.0
        
        # Similitud semántica usando embeddings
        if query_embedding and self.embeddings_service and skill.name in self.skill_embeddings:
            try:
                import numpy as np
                skill_vec = np.array(self.skill_embeddings[skill.name])
                query_vec = np.array(query_embedding)
                
                # Cosine similarity
                dot_product = np.dot(query_vec, skill_vec)
                norm_q = np.linalg.norm(query_vec)
                norm_s = np.linalg.norm(skill_vec)
                
                if norm_q > 0 and norm_s > 0:
                    cosine_sim = dot_product / (norm_q * norm_s)
                    # Añadir la similitud al score (escalado para tener peso en el score final)
                    if cosine_sim > 0.4:
                        score += (cosine_sim * 10.0)
            except Exception as e:
                logger.debug(f"Error computing cosine similarity for skill {skill.name}: {e}")

        haystack_parts = [
            skill.name,
            skill.description,
            skill.category,
            " ".join(skill.tags),
            " ".join(skill.required_permissions),
            skill.instructions,
            str(skill.metadata),
            str(skill.compatibility),
        ]
        haystack = " ".join(part for part in haystack_parts if part).lower()

        query_tokens = [token for token in re.split(r"\W+", normalized_query) if token]
        if not query_tokens:
            return score

        if normalized_query in haystack:
            score += 6.0

        if skill.name.lower() in normalized_query:
            score += 5.0

        for token in query_tokens:
            if token in skill.name.lower():
                score += 3.0
            if token in skill.description.lower():
                score += 2.0
            if any(token == tag.lower() for tag in skill.tags):
                score += 2.5
            if token in skill.instructions.lower():
                score += 1.0

        return score

    def find_relevant_skills(
        self,
        query: str,
        limit: int = 5,
        include_unloaded: bool = True,
    ) -> List[Dict[str, Any]]:
        """Busca skills relevantes para una consulta textual utilizando embeddings y similitud semántica."""
        candidates = self.skills.values() if include_unloaded else [s for s in self.skills.values() if s.loaded]
        scored = []
        
        query_embedding = None
        if self.embeddings_service and query.strip():
            try:
                query_embedding = self.embeddings_service.embed_query(query)
                
                # Asegurar que todas las skills candidatas tengan embeddings pre-computados
                skills_to_embed = [s for s in candidates if s.name not in self.skill_embeddings]
                if skills_to_embed:
                    texts_to_embed = []
                    for s in skills_to_embed:
                        # Crear un documento representativo de la skill
                        doc = f"{s.name}. {s.description}. Categoría: {s.category}. Tags: {', '.join(s.tags)}. {s.instructions[:500]}"
                        texts_to_embed.append(doc)
                    
                    if texts_to_embed:
                        new_embeddings = self.embeddings_service.generate_embeddings(texts_to_embed)
                        for s, emb in zip(skills_to_embed, new_embeddings):
                            self.skill_embeddings[s.name] = emb
            except Exception as e:
                logger.warning(f"Error generating embeddings for semantic skill search: {e}")

        for skill in candidates:
            score = self._score_skill_relevance(skill, query, query_embedding)
            if score <= 0:
                continue
            scored.append((score, skill))

        scored.sort(key=lambda item: (-item[0], item[1].name))
        results = []
        for score, skill in scored[:limit]:
            results.append({
                'name': skill.name,
                'version': skill.version,
                'description': skill.description,
                'category': skill.category,
                'tags': skill.tags,
                'loaded': skill.loaded,
                'tool_count': len(skill.tools),
                'path': str(skill.path),
                'score': round(score, 3),
            })

        return results

    def get_loaded_skill_instructions(self, query: Optional[str] = None, limit: int = 5) -> List[str]:
        """Devuelve bloques de instrucciones de las skills cargadas, priorizando relevancia si hay query."""
        loaded_skills = [skill for skill in self.skills.values() if skill.loaded]
        if query:
            query_embedding = None
            if self.embeddings_service:
                try:
                    query_embedding = self.embeddings_service.embed_query(query)
                except Exception as e:
                    logger.warning(f"Error embedding query for skill instructions: {e}")

            ranked = sorted(
                ((self._score_skill_relevance(skill, query, query_embedding), skill) for skill in loaded_skills),
                key=lambda item: (-item[0], item[1].name)
            )
            loaded_skills = [skill for score, skill in ranked if score > 0][:limit]

        blocks: List[str] = []
        for skill in loaded_skills:
            instructions = (skill.instructions or "").strip()
            if not instructions:
                continue

            blocks.append(
                f"### Skill: {skill.name}\n"
                f"- description: {skill.description}\n"
                f"- category: {skill.category}\n"
                f"- security_level: {skill.security_level}\n\n"
                f"{instructions}"
            )

        return blocks

    def build_skill_context_message(self, query: Optional[str] = None) -> Optional[SystemMessage]:
        """Construye un bloque de contexto para skills cargadas, filtrado por query si existe."""
        blocks = self.get_loaded_skill_instructions(query=query)
        if not blocks:
            return None

        content = "## 🧩 CONTEXTO DE SKILLS\n\n" + "\n\n".join(blocks)
        return SystemMessage(content=content)

    def refresh_skills(self, agent_context: Optional[dict] = None, force: bool = False):
        """
        Re-escanea los directorios de skills y carga las nuevas encontradas
        o actualiza las existentes en el registro de herramientas.
        """
        # Si ya tenemos herramientas y no se fuerza, evitar refresco costoso
        if not force and self.tool_registry:
            logger.debug("Omitiendo refresco de skills (ya cargadas). Use force=True si es necesario.")
            return True
            
        logger.info("Refrescando sistema de skills...")
        
        # Limpiar registros para forzar recarga limpia
        self.loaded_skills = set()
        self.tool_registry = {}
        
        # 1. Re-descubrir skills
        self.discover_all_skills()
        
        # 2. Cargar todas las skills descubiertas
        for skill_name in self.skills:
            self.load_skill(skill_name, agent_context)
        
        # 3. Invalidar la caché del LLMService para que regenere los esquemas
        if self.llm_service:
            self.llm_service.litellm_tools = None
            logger.info("Caché de herramientas de LLMService invalidada.")
        
        logger.info(f"Refresco completado. Total herramientas: {len(self.tool_registry)}")
        return True

    def get_tools_for_llm(self, agent_context: dict = None) -> List[Dict[str, Any]]:
        """
        Devuelve lista de herramientas en formato compatible con LLM.
        
        Returns:
            Lista de diccionarios con: name, description, skill, security_level, parameters
        """
        tools_metadata = []

        for tool_name, tool_info in self.tool_registry.items():
            tool = tool_info['tool']
            metadata = {
                'name': tool_name,
                'description': getattr(tool, 'description', ''),
                'skill': tool_info['skill'],
                'security_level': tool_info['security_level'],
                'permissions': tool_info.get('permissions', [])
            }
            # Extraer schema de parámetros
            if hasattr(tool, 'parameters_schema'):
                metadata['parameters'] = tool.parameters_schema
            elif hasattr(tool, 'run') and hasattr(tool.run, '__annotations__'):
                # Inferir desde type hints
                metadata['parameters'] = self._infer_schema_from_hints(tool.run)
            elif callable(tool) and hasattr(tool, '__annotations__'):
                metadata['parameters'] = self._infer_schema_from_hints(tool)

            tools_metadata.append(metadata)

        return tools_metadata

    def _infer_schema_from_hints(self, func) -> Optional[Dict[str, Any]]:
        """Infiere schema de parámetros desde type hints (simplificado)."""
        try:
            sig = inspect.signature(func)
            type_hints = get_type_hints(func)

            properties = {}
            required = []

            for param_name, param in sig.parameters.items():
                if param_name in ['self', 'cls', 'llm_service', 'terminal_ui', 'interrupt_queue', 'approval_handler']:
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
        from typing import Union, get_args, get_origin
        
        origin = get_origin(typ)
        if origin is Union:
            args = get_args(typ)
            # Buscar el primer tipo que no sea None
            for arg in args:
                if arg is not type(None):
                    typ = arg
                    origin = get_origin(typ)
                    break
        
        if origin is list or typ is list:
            return 'array'
        if origin is dict or typ is dict:
            return 'object'

        type_map = {
            str: 'string',
            int: 'integer',
            float: 'number',
            bool: 'boolean'
        }
        return type_map.get(typ, 'string')

    def set_agent_state(self, agent_state):
        """Inyecta el estado del agente en todas las herramientas que lo soporten."""
        for tool_info in self.tool_registry.values():
            tool = tool_info['tool']
            if hasattr(tool, 'agent_state'):
                tool.agent_state = agent_state
            # También para clases
            elif isinstance(tool, type) and hasattr(tool, 'agent_state'):
                tool.agent_state = agent_state

    def get_tools(self) -> List[Any]:
        """Devuelve lista de todas las herramientas (objetos/funciones) registradas."""
        return [info['tool'] for info in self.tool_registry.values()]
