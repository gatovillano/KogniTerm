import os
import sys
import time
import json
import queue
from typing import List, Any, Generator, Optional, Union, Dict
from collections import deque
from langchain_core.tools import BaseTool
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from litellm import completion, litellm
import uuid
import random
import string
import traceback
import re
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import threading
from typing import Union # ¡Nueva importación para Union!

# Importar ConfigManager para gestión centralizada de credenciales
from kogniterm.terminal.config_manager import ConfigManager

from .multi_provider_manager import get_provider_manager, MultiProviderManager
from .utils.tool_utils import normalize_tool_parameters_schema

def _convert_langchain_tool_to_litellm(tool: BaseTool, model_name: str = "") -> dict:
    """Convierte una herramienta de LangChain (BaseTool) a un formato compatible con LiteLLM."""
    args_schema = {"type": "object", "properties": {}}

    # Obtener el esquema de argumentos de manera más robusta
    if hasattr(tool, 'args_schema') and tool.args_schema is not None:
        try:
            # Si args_schema es directamente un dict, usarlo
            if isinstance(tool.args_schema, dict):
                args_schema = tool.args_schema
            # Intentar obtener el esquema usando el método schema() si está disponible (Pydantic v1)
            elif hasattr(tool.args_schema, 'schema') and callable(getattr(tool.args_schema, 'schema', None)):
                try:
                    args_schema = tool.args_schema.schema()
                except Exception:
                    # Si falla el método schema(), intentar model_json_schema() para Pydantic v2
                    if hasattr(tool.args_schema, 'model_json_schema') and callable(getattr(tool.args_schema, 'model_json_schema', None)):
                        args_schema = tool.args_schema.model_json_schema()
            # Si args_schema es una clase Pydantic, intentar obtener su esquema (Pydantic v2)
            elif hasattr(tool.args_schema, 'model_json_schema'):
                args_schema = tool.args_schema.model_json_schema()
            else:
                # Fallback: intentar usar model_fields para Pydantic v2
                if hasattr(tool.args_schema, 'model_fields'):
                    properties = {}
                    for field_name, field_info in tool.args_schema.model_fields.items():
                        # Excluir campos marcados con exclude=True o que no deberían estar en el esquema de argumentos
                        # como account_id, workspace_id, telegram_id, thread_id
                        if field_name not in ["account_id", "workspace_id", "telegram_id", "thread_id"] and not getattr(field_info, 'exclude', False):
                            field_type = 'string'  # Tipo por defecto
                            if hasattr(field_info, 'annotation'):
                                # Intentar inferir el tipo de la anotación
                                if field_info.annotation == str:
                                    field_type = 'string'
                                elif field_info.annotation == int:
                                    field_type = 'integer'
                                elif field_info.annotation == bool:
                                    field_type = 'boolean'
                                elif field_info.annotation == list:
                                    field_type = 'array'
                                elif field_info.annotation == dict:
                                    field_type = 'object'

                            properties[field_name] = {
                                "type": field_type,
                                "description": getattr(field_info, 'description', "") or f"Parámetro {field_name}"
                            }
                    args_schema = {
                        "type": "object",
                        "properties": properties,
                        "required": [name for name, info in tool.args_schema.model_fields.items() if info.is_required() and name in properties]
                    }
        except Exception as e:
            tool_name = getattr(tool, 'name', 'Desconocido')
            logger.error(f"Error extracting schema for tool {tool_name}: {e}")
            args_schema = {"type": "object", "properties": {}}
    elif hasattr(tool, 'parameters_schema') and tool.parameters_schema is not None:
        # Soporte para skills que usan parameters_schema directo (JSON Schema)
        args_schema = tool.parameters_schema

    cleaned_schema = normalize_tool_parameters_schema(args_schema)

    # Asegurarse de que el esquema sea válido para proveedores estrictos
    if not cleaned_schema.get("properties"):
        cleaned_schema = {
            "type": "object",
            "properties": {},
            "required": []
        }

    # Usar el formato estándar de OpenAI "tools" (type: function) por defecto
    # Esto es compatible con la mayoría de proveedores modernos y requerido por SiliconFlow
    logger.info(f"🔧 Generando definición de herramienta para: {tool.name}")
    tool_definition = {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description[:1024],
            "parameters": cleaned_schema,
        }
    }

    return tool_definition

import logging

logger = logging.getLogger(__name__)


load_dotenv()

# --- Gestión centralizada de credenciales con ConfigManager ---
config_manager = ConfigManager()


litellm_model = os.getenv("LITELLM_MODEL")
litellm_api_base = os.getenv("LITELLM_API_BASE")
gemini_model = os.getenv("GEMINI_MODEL")
ollama_api_base = os.getenv("OLLAMA_API_BASE")
ollama_api_key = os.getenv("OLLAMA_API_KEY")
ollama_target = (os.getenv("OLLAMA_PROVIDER_TARGET") or "").strip().lower()

# Configuración global de LiteLLM para máxima compatibilidad
litellm.drop_params = True 
litellm.modify_params = False 
litellm.telemetry = False
# Silencio total para producción
os.environ['LITELLM_LOG'] = 'ERROR' 
litellm.set_verbose = False
litellm.suppress_debug_info = True # Nueva bandera para evitar mensajes de ayuda
litellm.add_fastapi_middleware = False # Evitar ruidos innecesarios

# Configuración inicial de modelo y proveedor
# Si no hay modelo en el env, intentamos priorizar ollama si está configurado
default_model = "ollama/llama3" if (os.getenv("OLLAMA_PROVIDER_TARGET") or "").strip().lower() in ["local", "ollama"] else "google/gemini-1.5-flash"
model_to_use = litellm_model or (f"gemini/{gemini_model}" if gemini_model else default_model)

# Variables para configuración de Ollama
ollama_api_base = os.getenv("OLLAMA_API_BASE")
ollama_api_key = os.getenv("OLLAMA_API_KEY")
ollama_cloud_key = os.getenv("OLLAMA_CLOUD_API_KEY")
ollama_target = (os.getenv("OLLAMA_PROVIDER_TARGET") or "").strip().lower()

# Detección robusta de proveedor prioritario (solo para logging inicial)
if model_to_use.startswith("ollama/"):
    use_cloud_init = False
    if ollama_target in ["cloud", "ollama_cloud"]:
        use_cloud_init = True
    elif ollama_target in ["local", "ollama"]:
        use_cloud_init = False
    elif ollama_api_base and any(h in ollama_api_base for h in ["localhost", "127.0.0.1", "0.0.0.0", "::1"]):
        use_cloud_init = False
    elif ollama_cloud_key:
        use_cloud_init = True
    
    if use_cloud_init:
        base = os.getenv("OLLAMA_CLOUD_API_BASE") or "https://ollama.com/v1"
        logger.info(f"☁️ Configuración inicial detectada: Ollama Cloud ({model_to_use}) en {base}")
    else:
        base = ollama_api_base or "http://localhost:11434/v1"
        logger.info(f"🦙 Configuración inicial detectada: Ollama Local ({model_to_use}) en {base}")
elif model_to_use.startswith("gemini/") or ("gemini" in model_to_use.lower() and not "openrouter" in model_to_use.lower() and not "antigravity" in model_to_use.lower()):
    logger.info(f"🤖 Configuración inicial detectada: Gemini ({model_to_use})")
else:
    logger.info(f"🤖 Configuración inicial detectada: Proveedor Genérico ({model_to_use})")

from .exceptions import UserConfirmationRequired # Importar la excepción
import tiktoken # Importar tiktoken
from .context.workspace_context import WorkspaceContext # Importar WorkspaceContext
from .history_manager import HistoryManager





class LLMService:
    def __init__(self, interrupt_queue: Optional[queue.Queue] = None, use_multi_provider: bool = True):
        # print("DEBUG: Iniciando LLMService.__init__...")
        
        # Inicializar MultiProviderManager
        self.use_multi_provider = use_multi_provider
        if use_multi_provider:
            self.provider_manager = get_provider_manager()
            # Realizar health check inicial (Comentado para evitar lentitud e inestabilidad al arranque)
            # self.provider_manager.health_check()
        else:
            self.provider_manager = None
        
        self.model_name = os.environ.get("LITELLM_MODEL", default_model)
        # Validación de seguridad: si el modelo parece una API Key de Google, corregirlo
        if self.model_name.startswith("AIza"):
            logger.warning(f"Se detectó una API Key en LITELLM_MODEL ('{self.model_name[:8]}...'). Corrigiendo a '{default_model}'.")
            self.model_name = default_model
        
        # Modelo para resumen de historial (fallback/summary) - usa el mismo por defecto
        self.summary_model = self.model_name
            
        # Determinar API Key de forma inteligente según el modelo inicial (prioriza config.json)
        if self.model_name.startswith("antigravity/"):
            self.api_key = "antigravity-session-token"
        elif self.model_name.startswith("gemini/"):
            self.api_key = config_manager.get_api_key("google") or os.environ.get("GOOGLE_API_KEY") or os.environ.get("LITELLM_API_KEY")
            if self.api_key:
                os.environ["GEMINI_API_KEY"] = self.api_key
        elif self.model_name.startswith("openrouter/"):
            self.api_key = config_manager.get_api_key("openrouter") or os.environ.get("OPENROUTER_API_KEY") or os.environ.get("LITELLM_API_KEY")
        elif self.model_name.startswith("openai/"):
            self.api_key = config_manager.get_api_key("openai") or os.environ.get("OPENAI_API_KEY") or os.environ.get("LITELLM_API_KEY")
        elif self.model_name.startswith("anthropic/"):
            self.api_key = config_manager.get_api_key("anthropic") or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("LITELLM_API_KEY")
        elif self.model_name.startswith("ollama_cloud/"):
            self.api_key = config_manager.get_api_key("ollama_cloud") or os.environ.get("OLLAMA_CLOUD_API_KEY") or os.environ.get("LITELLM_API_KEY")
        else:
            # Fallback: cualquier key válida
            self.api_key = (
                config_manager.get_api_key("openrouter")
                or config_manager.get_api_key("google")
                or config_manager.get_api_key("openai")
                or config_manager.get_api_key("anthropic")
                or config_manager.get_api_key("ollama_cloud")
                or os.environ.get("LITELLM_API_KEY")
                or os.environ.get("OPENROUTER_API_KEY")
                or os.environ.get("GOOGLE_API_KEY")
                or os.environ.get("OPENAI_API_KEY")
                or os.environ.get("ANTHROPIC_API_KEY")
                or os.environ.get("OLLAMA_CLOUD_API_KEY")
            )

        self.interrupt_queue = interrupt_queue
        self.stop_generation_flag = False
        from .embeddings_service import EmbeddingsService
        from .context.vector_db_manager import VectorDBManager
        # print("DEBUG: Inicializando EmbeddingsService...")
        self.embeddings_service = EmbeddingsService()
        # print("DEBUG: Inicializando VectorDBManager...")
        try:
            self.vector_db_manager = VectorDBManager(project_path=os.getcwd())
        except Exception as e:
            logger.error(f"⚠️ Error crítico al inicializar ChromaDB: {e}")
            logger.warning("La aplicación continuará en MODO SEGURO (sin búsqueda vectorial).")
            self.vector_db_manager = None

        # Inicializar DelegationManager y HeartbeatMonitor
        from kogniterm.core.delegation import DelegationManager, HeartbeatMonitor
        self.delegation_manager = DelegationManager()
        self.heartbeat_monitor = HeartbeatMonitor()
        self.heartbeat_monitor.start()
        self._thread_local = threading.local()

        # print("DEBUG: Inicializando SkillManager...")
        from .skills.skill_manager import SkillManager
        self.skill_manager = SkillManager(
            llm_service=self,
            interrupt_queue=self.interrupt_queue,
            embeddings_service=self.embeddings_service,
            vector_db_manager=self.vector_db_manager
        )
        # print("DEBUG: Cargando skills...")
        self.skill_manager.discover_all_skills()
        for skill_name in self.skill_manager.skills:
            self.skill_manager.load_skill(skill_name)
            
        # print("DEBUG: Generando esquemas de herramientas...")
        self.tool_names = [getattr(tool, 'name', tool.__class__.__name__) for tool in self.skill_manager.get_tools()]
        self.tool_schemas = []
        for tool in self.skill_manager.get_tools():
            schema = {}
            if hasattr(tool, 'args_schema') and tool.args_schema is not None:
                if hasattr(tool.args_schema, 'schema'):
                    schema = tool.args_schema.schema()
                elif hasattr(tool.args_schema, 'model_json_schema'):
                    schema = tool.args_schema.model_json_schema()
            elif hasattr(tool, 'parameters_schema') and tool.parameters_schema is not None:
                schema = tool.parameters_schema
            self.tool_schemas.append(schema)
        self.tool_map = {getattr(tool, 'name', tool.__class__.__name__): tool for tool in self.skill_manager.get_tools()}
        # Tools will be converted at runtime based on the actual model being used
        self.litellm_tools = None
        self.max_conversation_tokens = 128000 # Gemini 1.5 Flash context window
        self.max_tool_output_tokens = 100000 # Max tokens for tool output
        self.MAX_TOOL_MESSAGE_CONTENT_LENGTH = 100000 # Nuevo: Límite de caracteres para el contenido de ToolMessage
        self.max_history_tokens = self.max_conversation_tokens - self.max_tool_output_tokens # Remaining for history
        # print("DEBUG: Inicializando Tokenizer (esto puede tardar si descarga)...")
        self.tokenizer = tiktoken.encoding_for_model("gpt-4") # Usar un tokenizer compatible
        # print("DEBUG: Tokenizer listo.")
        self.history_file_path = os.path.join(os.getcwd(), ".kogniterm", "history.json") # Inicializar history_file_path
        self.console = None # Inicializar console
        self.max_history_messages = 40 # Aumentado para mejor contexto y menor latencia por resumenes
        self.max_history_chars = 40000 # Aumentado para mejor contexto
        self.auto_save_interval = float(os.getenv("KOGNITERM_AUTO_SAVE_INTERVAL", "0")) or None  # Intervalo en segundos para autoguardado, 0 para desactivar
        # print("DEBUG: Inicializando WorkspaceContext...")
        self.workspace_context = WorkspaceContext(root_dir=os.getcwd())
        self.workspace_context_initialized = False
        self.call_timestamps = deque() # Inicializar call_timestamps
        self.rate_limit_period = 60 # Por ejemplo, 60 segundos
        self.rate_limit_calls = 100 # Aumentado para reducir latencia artificial entre turnos
        self.generation_params = {"temperature": 0.7, "top_p": 0.95, "top_k": 40} # Parámetros de generación por defecto
        configured_reasoning_effort = self._normalize_reasoning_effort(os.getenv("KOGNITERM_REASONING_EFFORT"))
        if configured_reasoning_effort:
            self.generation_params["reasoning_effort"] = configured_reasoning_effort
        # Configurable timeouts (env vars)
        # KOGNITERM_AGENT_POLL_MS: poll interval (ms) used when waiting on tool futures (default 100 ms)
        self.tool_poll_timeout = float(os.getenv("KOGNITERM_AGENT_POLL_MS", "100")) / 1000.0
        # KOGNITERM_API_TIMEOUT_S: timeout for LLM/API calls in seconds (default 120 s)
        self.api_timeout_seconds = float(os.getenv("KOGNITERM_API_TIMEOUT_S", "120"))
        # Optional fallback timeout for alternative calls
        self.api_timeout_fallback_seconds = float(os.getenv("KOGNITERM_API_FALLBACK_TIMEOUT_S", "90"))
        # KOGNITERM_STREAM_OVERALL_TIMEOUT_S: total timeout for streaming responses (default 1800 s)
        self.stream_overall_timeout = float(os.getenv("KOGNITERM_STREAM_OVERALL_TIMEOUT_S", "1800"))
        # KOGNITERM_STREAM_CHUNK_TIMEOUT_S: timeout between chunks in streaming (default 45 s)
        self.stream_chunk_timeout = float(os.getenv("KOGNITERM_STREAM_CHUNK_TIMEOUT_S", "45"))
        # Máximo de reintentos automáticos de continuación cuando la respuesta se corta (por finish_reason 'length')
        self.max_continuations = int(os.getenv("KOGNITERM_MAX_CONTINUATIONS", "3"))

        self.tool_execution_lock = threading.Lock() # Inicializar el lock
        self.active_tool_future = None # Referencia a la última tarea iniciada
        self.tool_executor = ThreadPoolExecutor(max_workers=20) # Aumentado para permitir mayor paralelismo en ejecución de herramientas
        # Inicializar HistoryManager para gestión optimizada del historial
        self.history_manager = HistoryManager(
            history_file_path=self.history_file_path,
            max_history_messages=self.max_history_messages,
            max_history_chars=self.max_history_chars,
            auto_save_interval=self.auto_save_interval
        )
        self.SUMMARY_MAX_TOKENS = 1500 # Tokens, longitud máxima del resumen de herramientas
        
    @property
    def current_delegation_context(self):
        return getattr(self._thread_local, "delegation_context", None)

    @current_delegation_context.setter
    def current_delegation_context(self, value):
        self._thread_local.delegation_context = value

    @property
    def conversation_history(self) -> List[BaseMessage]:
        """Proxy para acceder al historial gestionado por HistoryManager."""
        return self.history_manager.conversation_history

    @conversation_history.setter
    def conversation_history(self, valueList: List[BaseMessage]):
        """Permite actualizar el historial de HistoryManager."""
        self.history_manager.conversation_history = valueList

    def is_thinking_model(self) -> bool:
        """ Detecta si el modelo actual tiene capacidades de razonamiento nativo. """
        model_lower = self.model_name.lower()
        # Evitar el CoT manual (<thought>) en Gemini, ya que Gemini funciona de forma
        # errática con herramientas si se le obliga a escribir explicaciones de pensamiento manuales.
        # Los modelos Gemini >= 2.0/2.5/3.x ya usan razonamiento nativo.
        if "gemini" in model_lower:
            return True

        thinking_keywords = [
            "deepseek-reasoner", "deepseek-r1", 
            "o1-", "o3-", 
            "thinking", "reasoner"
        ]
        if any(kw in model_lower for kw in thinking_keywords):
            return True
        return False

    @property
    def conversation_history(self):
        """Propiedad de compatibilidad que delega al history_manager."""
        return self.history_manager.conversation_history
    
    @conversation_history.setter
    def conversation_history(self, value):
        """Setter de compatibilidad que delega al history_manager."""
        self.history_manager.conversation_history = value

    def _generate_short_id(self, length: int = 9) -> str:
        """Genera un ID alfanumérico corto compatible con proveedores estrictos como Mistral."""
        chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for _ in range(length))

    def _normalize_reasoning_effort(self, effort: Optional[str]) -> Optional[str]:
        """Normaliza y valida el esfuerzo de razonamiento soportado por modelos compatibles."""
        if not effort:
            return None
        normalized = str(effort).strip().lower()
        if normalized in {"low", "medium", "high"}:
            return normalized
        return None

    def _apply_reasoning_effort_param(self, completion_kwargs: Dict[str, Any], model_name: Optional[str] = None):
        """Inyecta reasoning_effort cuando está configurado.

        LiteLLM tiene `drop_params=True`, por lo que proveedores incompatibles ignoran el campo.
        """
        effort = self._normalize_reasoning_effort(self.generation_params.get("reasoning_effort"))
        if not effort:
            return
        completion_kwargs["reasoning_effort"] = effort

    def _parse_tool_calls_from_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Analiza el texto para encontrar llamadas a herramientas usando múltiples estrategias.
        Versión conservadora: evita falsos positivos con palabras comunes y JSONs genéricos.
        """
        if not text:
            return []

        tool_calls = []
        seen_combinations = set()
        valid_tool_calls = []
        import re
        import json
        
        # 1. Limpieza inicial: Quitar caracteres de control invisibles
        clean_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
        
        # ESTRATEGIA A: Patrones explícitos "LLAMADA_A_HERRAMIENTA: name {args}"
        # Estos son los más seguros porque tienen un prefijo claro.
        explicit_patterns = [
            r'LLAMADA_A_HERRAMIENTA:\s*(\w+)',
            r'Herramienta:\s*(\w+)',
            r'\[TOOL_CALL\]\s*(\w+)',
            r'Tool:\s*(\w+)'
        ]
        for pat in explicit_patterns:
            for match in re.finditer(pat, clean_text, re.IGNORECASE):
                tool_name = match.group(1).strip()
                # El nombre debe existir en el mapa de herramientas
                if tool_name in self.tool_map or tool_name.lower() in self.tool_map or tool_name in ['call_agent', 'think', 'execute_command']:
                    search_start = match.end()
                    json_start = clean_text.find('{', search_start)
                    # El JSON debe estar cerca del nombre
                    if json_start != -1 and (json_start - search_start) < 100:
                        args_str = self._extract_balanced_content(clean_text, json_start)
                        if args_str:
                            args = self.extract_args(args_str)
                            tool_calls.append({"id": self._generate_short_id(), "name": tool_name, "args": args if isinstance(args, dict) else {}})

        # ESTRATEGIA B: Bloques JSON estructurados
        i = 0
        while i < len(clean_text):
            if clean_text[i] == '{':
                json_str = self._extract_balanced_content(clean_text, i)
                if json_str:
                    try:
                        data = json.loads(json_str)
                        if isinstance(data, dict) and data:
                            # Formato 1: {"name": "...", "args": {...}} o similares
                            name_key = next((k for k in ["name", "tool", "function", "skill"] if k in data), None)
                            if name_key:
                                name = data.get(name_key)
                                args = data.get("args") or data.get("arguments") or data.get("parameters") or {}
                                
                                if isinstance(name, str) and (name in self.tool_map or name.lower() in self.tool_map or name in ['call_agent', 'think', 'execute_command']):
                                    tool_calls.append({"id": self._generate_short_id(), "name": name, "args": args if isinstance(args, dict) else {}})
                                    i += len(json_str)
                                    continue
                            
                            # Formato 2: {"tool_name": {...args...}}
                            # MUY RESTRICTIVO: Solo si tiene exactamente una clave, esa clave es una herramienta, 
                            # el valor es un objeto, y el nombre es lo suficientemente largo/específico.
                            elif len(data) == 1:
                                potential_name = list(data.keys())[0]
                                potential_args = data[potential_name]
                                if isinstance(potential_args, dict) and (potential_name in self.tool_map or potential_name.lower() in self.tool_map):
                                    # Evitar palabras comunes de menos de 4 letras a menos que sea un match exacto con case
                                    if len(potential_name) > 3 or potential_name in self.tool_map:
                                        tool_calls.append({"id": self._generate_short_id(), "name": potential_name, "args": potential_args})
                                        i += len(json_str)
                                        continue
                    except:
                        pass
            i += 1

        # ESTRATEGIA C: Formatos Legacy tipo Código "name({args})"
        # Solo si el nombre es una herramienta válida y está seguido por ({
        legacy_pattern = r'\b(\w+)\s*\(\s*(\{.*?\})\s*\)'
        for match in re.finditer(legacy_pattern, clean_text, re.DOTALL):
            name = match.group(1)
            # Solo aceptar funciones que estén en el tool_map o sean comandos conocidos
            if name in self.tool_map or name.lower() in self.tool_map or name in ['call_agent', 'think', 'execute_command']:
                # Evitar funciones comunes de Python
                if name.lower() not in ['print', 'len', 'str', 'int', 'float', 'bool', 'list', 'dict', 'range', 'open']:
                    try:
                        args = json.loads(match.group(2))
                        if isinstance(args, dict):
                            tool_calls.append({"id": self._generate_short_id(), "name": name, "args": args})
                    except:
                        pass

        # Filtrar duplicados y consolidar
        for tc in tool_calls:
            try:
                args_json = json.dumps(tc['args'], sort_keys=True)
                key = f"{tc['name']}:{args_json}"
                if key not in seen_combinations:
                    seen_combinations.add(key)
                    valid_tool_calls.append(tc)
            except:
                if tc not in valid_tool_calls: 
                    valid_tool_calls.append(tc)

        return valid_tool_calls

    def extract_args(self, args_str: str) -> Dict[str, Any]:
        """Extrae argumentos de una cadena de texto de forma permisiva."""
        if not args_str: return {}
        args_str = args_str.strip()
        try:
            return json.loads(args_str)
        except:
            # Fallback a extracción por regex para casos muy sucios
            result = {}
            pair_pattern = r'(\w+)\s*[:=]\s*(?:"([^"]*)"|\'([^\']*)\'|(\d+)|([^\s,{}]+))'
            for m in re.finditer(pair_pattern, args_str):
                key = m.group(1)
                value = m.group(2) or m.group(3) or m.group(4) or m.group(5)
                if value and value.isdigit(): value = int(value)
                result[key] = value
            return result

    def _extract_balanced_content(self, text: str, start_pos: int) -> Optional[str]:
        """Extrae contenido balanceado entre {}, [] o () manejando anidamiento y strings."""
        if start_pos >= len(text): return None
        chars = {'{': '}', '[': ']', '(': ')'}
        open_char = text[start_pos]
        if open_char not in chars: return None
        close_char = chars[open_char]
        
        depth = 0
        in_string = False
        string_char = None
        for i in range(start_pos, len(text)):
            char = text[i]
            if char in ['"', "'"] and (i == 0 or text[i-1] != '\\'):
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    in_string = False
            
            if not in_string:
                if char == open_char: depth += 1
                elif char == close_char:
                    depth -= 1
                    if depth == 0: return text[start_pos : i + 1]
        return None

    def _from_litellm_message(self, message):
        """Convierte un mensaje de LiteLLM a un formato compatible con LangChain."""
        role = message.get("role")
        content = message.get("content", "")
        if role == "user":
            return HumanMessage(content=content)
        elif role == "assistant":
            tool_calls_data = message.get("tool_calls")
            if tool_calls_data:
                tool_calls = []
                thought_signatures = {}
                for tc in tool_calls_data:
                    function_data = tc.get("function")
                    if function_data:
                        args = function_data.get("arguments", "")
                        if isinstance(args, str):
                            try: args = json.loads(args)
                            except: args = {}
                        tc_id = tc.get("id") or self._generate_short_id()
                        tool_calls.append({
                            "id": tc_id,
                            "name": function_data.get("name", ""),
                            "args": args
                        })
                        tsig = tc.get("thought_signature") or tc.get("thoughtSignature")
                        if tsig:
                            thought_signatures[tc_id] = tsig
                kwargs = {}
                if thought_signatures:
                    kwargs["additional_kwargs"] = {"thought_signatures": thought_signatures}
                return AIMessage(content=content, tool_calls=tool_calls, **kwargs)
            return AIMessage(content=content)
        elif role == "tool":
            # Incluir el nombre de la herramienta si está presente, para que map_messages
            # de Antigravity pueda resolver functionResponse.name sin depender del lookback.
            return ToolMessage(
                content=content,
                tool_call_id=message.get("tool_call_id"),
                name=message.get("name") or "",
            )
        elif role == "system":
            return SystemMessage(content=content)
        return HumanMessage(content=content)

    def _build_llm_context_message(self) -> Optional[SystemMessage]:
        if self.workspace_context_initialized:
            return self.workspace_context.build_context_message()
        return None

    def initialize_workspace_context(self, files_to_include: Optional[List[str]] = None):
        self.workspace_context.initialize_context(files_to_include=files_to_include)
        self.workspace_context_initialized = True

    def _format_tool_code_for_llm(self, tool_code: str) -> str:
        return f"""```python
{tool_code}
```"""

    def _format_tool_output_for_llm(self, tool_output: str) -> str:
        return f"""```text
{tool_output}
```"""

    def _to_litellm_message(self, message: BaseMessage, id_map: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Convierte un mensaje de LangChain a un formato compatible con LiteLLM, con soporte para mapeo de IDs."""
        is_mistral = "mistral" in self.model_name.lower()
        
        def get_compliant_id(original_id):
            if not is_mistral:
                return original_id or self._generate_short_id()
            
            # Para Mistral, el ID debe ser alfanumérico de 9 caracteres
            if original_id and len(original_id) == 9 and original_id.isalnum():
                return original_id
            
            if not original_id:
                return self._generate_short_id()
            
            # Si tenemos un mapa, intentar recuperar o crear un nuevo ID mapeado
            if id_map is not None:
                if original_id not in id_map:
                    id_map[original_id] = self._generate_short_id()
                return id_map[original_id]
            
            # Fallback: generar uno nuevo si no hay mapa
            return self._generate_short_id()

        if isinstance(message, HumanMessage):
            content = message.content
            if not isinstance(content, str):
                content = json.dumps(content) if isinstance(content, (dict, list)) else str(content)
            return {"role": "user", "content": content}
        elif isinstance(message, AIMessage):
            tool_calls = getattr(message, 'tool_calls', [])
            content = message.content
            if not isinstance(content, str):
                # Handle cases where content is a list/dict of objects (e.g. from a tool call or reasoning)
                content = json.dumps(content) if isinstance(content, (dict, list)) else str(content)

            msg = {"role": "assistant", "content": content or "..."}
            
            # Preservar razonamiento para OpenRouter/LiteLLM
            reasoning = message.additional_kwargs.get("reasoning_content") or getattr(message, 'reasoning_content', None)
            if reasoning:
                msg["reasoning_content"] = str(reasoning)

            if tool_calls:
                serialized_tool_calls = []
                for tc in tool_calls:
                    tc_id = get_compliant_id(tc.get("id"))
                    tc_name = tc.get("name", "")
                    tc_args = tc.get("args", {})
                    # Asegurarse de que los argumentos sean siempre una cadena JSON válida.
                    arguments_json = json.dumps(tc_args) if tc_args else "{}"
                    
                    serialized_tc = {
                        "id": tc_id,
                        "type": "function",
                        "function": {"name": tc_name, "arguments": arguments_json},
                    }
                    # Propagar thought_signature para Antigravity
                    thought_sig = tc.get("thought_signature")
                    if not thought_sig and isinstance(message, AIMessage):
                        thought_sigs = message.additional_kwargs.get("thought_signatures", {})
                        if isinstance(thought_sigs, dict):
                            # Se busca por el ID original del tool call
                            thought_sig = thought_sigs.get(tc.get("id"))
                    
                    if thought_sig:
                        serialized_tc["thought_signature"] = thought_sig
                    serialized_tool_calls.append(serialized_tc)
                
                if not content or not str(content).strip():
                    msg["content"] = "Ejecutando herramientas..."
                
                msg["tool_calls"] = serialized_tool_calls
            
            return msg
        elif isinstance(message, ToolMessage):
            content = message.content
            # ASEGURAR SIEMPRE QUE EL CONTENIDO SEA STRING PARA EL LLM
            if not isinstance(content, str):
                content = json.dumps(content) if isinstance(content, (dict, list)) else str(content)
            
            if not content or not str(content).strip():
                content = "Operación completada (sin salida)."
            
            tc_id = get_compliant_id(getattr(message, 'tool_call_id', ''))
            
            # Propagar el nombre de la herramienta si está presente
            name = getattr(message, 'name', None)
            tool_msg = {"role": "tool", "content": content, "tool_call_id": tc_id}
            if name:
                tool_msg["name"] = name
            return tool_msg
        elif isinstance(message, SystemMessage):
            content = message.content
            if not isinstance(content, str):
                content = json.dumps(content) if isinstance(content, (dict, list)) else str(content)
            return {"role": "system", "content": content}
        
        # Fallback para cualquier otro tipo de mensaje
        content = getattr(message, 'content', str(message))
        if not isinstance(content, str):
            content = json.dumps(content) if isinstance(content, (dict, list)) else str(content)
        return {"role": "user", "content": content}

    def _truncate_messages(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        # Implementación de truncamiento de mensajes
        # ... (la lógica de truncamiento se mantiene igual)
        return messages

    def _get_token_count(self, text: str) -> int:
        try:
            return len(self.tokenizer.encode(text))
        except Exception:
            # Fallback si el tokenizer falla
            return len(text) // 4

    def _get_messages_token_count(self, messages: List[Dict[str, Any]]) -> int:
        """Calcula el total aproximado de tokens en una lista de mensajes formateados para LiteLLM."""
        total_tokens = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total_tokens += self._get_token_count(content)
            elif isinstance(content, list):
                # Manejar contenido multimodal o estructurado
                total_tokens += self._get_token_count(json.dumps(content))
            
            # Overhead por rol y estructura (aprox 4 tokens por mensaje)
            total_tokens += 4
            
            if msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    total_tokens += self._get_token_count(json.dumps(tc))
            
            if msg.get("tool_call_id"):
                total_tokens += 10 # Overhead por ID de herramienta
                
        return total_tokens

    def _save_history(self, history: List[BaseMessage]):
        """Método de compatibilidad que delega al history_manager."""
        self.history_manager._save_history(history)

    def _load_history(self) -> List[BaseMessage]:
        """Método de compatibilidad que delega al history_manager."""
        return self.history_manager._load_history()

    def get_tools(self) -> List[BaseTool]:
        return self.skill_manager.get_tools()

    def register_tool(self, tool_instance: BaseTool):
        """Registra una herramienta dinámicamente y actualiza las estructuras internas."""
        self.skill_manager.register_tool(tool_instance)
        # Actualizar las estructuras internas de LLMService
        self.tool_map[tool_instance.name] = tool_instance
        self.tool_names.append(tool_instance.name)
        # Tools will be converted at runtime, so no need to update litellm_tools here

    def sync_tools(self):
        """Sincroniza el caché interno de herramientas con el estado actual de SkillManager."""
        logger.info("Sincronizando herramientas en LLMService...")
        self.litellm_tools = None  # Invalidar caché
        tools = self.skill_manager.get_tools()
        self.tool_names = [getattr(tool, 'name', tool.__class__.__name__) for tool in tools]
        self.tool_schemas = []
        for tool in tools:
            schema = {}
            if hasattr(tool, 'args_schema') and tool.args_schema is not None:
                if hasattr(tool.args_schema, 'schema'):
                    schema = tool.args_schema.schema()
                elif hasattr(tool.args_schema, 'model_json_schema'):
                    schema = tool.args_schema.model_json_schema()
            elif hasattr(tool, 'parameters_schema') and tool.parameters_schema is not None:
                schema = tool.parameters_schema
            self.tool_schemas.append(schema)
        self.tool_map = {getattr(tool, 'name', tool.__class__.__name__): tool for tool in tools}

    def _get_litellm_tools(self) -> List[dict]:
        """Convierte las herramientas al formato LiteLLM apropiado para el modelo actual."""
        if self.litellm_tools is None:
            logger.info(f"🔧 Convirtiendo herramientas para modelo: {self.model_name}")
            # Asegurar que la skill task_tracker esté cargada si está disponible
            try:
                if hasattr(self, 'skill_manager') and 'task_tracker' in getattr(self.skill_manager, 'skills', {}):
                    if 'task_tracker' not in getattr(self.skill_manager, 'loaded_skills', set()):
                        try:
                            self.skill_manager.load_skill('task_tracker')
                        except Exception as e:
                            logger.debug(f"No se pudo cargar skill 'task_tracker': {e}")
            except Exception:
                pass

            converted_tools = []
            is_thinking = self.is_thinking_model()
            for tool in self.skill_manager.get_tools():
                if is_thinking and getattr(tool, 'name', '') == 'think':
                    logger.info("🧠 Excluyendo la herramienta 'think' porque el modelo soporta razonamiento nativo.")
                    continue
                converted = _convert_langchain_tool_to_litellm(tool, self.model_name)
                logger.info(f"✅ Herramienta convertida: {tool.name} -> {converted.get('type', 'standard')}")
                converted_tools.append(converted)
            # Reconstruir el mapa de herramientas para incluir las recién cargadas
            try:
                self.tool_map = {getattr(tool, 'name', tool.__class__.__name__): tool for tool in self.skill_manager.get_tools()}
            except Exception:
                pass
            self.litellm_tools = converted_tools
            logger.info(f"📋 Total herramientas convertidas: {len(converted_tools)}")
        return self.litellm_tools

    def set_model(self, model_name: str):
        """Cambia el modelo actual en tiempo de ejecución de forma robusta."""
        self.model_name = model_name
        self.summary_model = model_name  # Sincronizar modelo de resumen
        os.environ["LITELLM_MODEL"] = model_name
        os.environ["SUMMARY_MODEL"] = model_name # Persistir también en env
        
        # Invalidar caché de herramientas
        self.litellm_tools = None
        
        # Lógica de configuración específica por proveedor
        if model_name.startswith("openrouter/"):
            key = os.environ.get("OPENROUTER_API_KEY")
            if key:
                self.api_key = key
                os.environ["LITELLM_API_KEY"] = key
            
            litellm.api_base = os.environ.get("LITELLM_API_BASE") or "https://openrouter.ai/api/v1"
            litellm.headers = {
                "HTTP-Referer": "https://github.com/gatovillano/KogniTerm",
                "X-Title": "KogniTerm"
            }
            logger.info(f"🌐 Cambiado a OpenRouter: {model_name}")
            
        elif model_name.startswith("gemini/"):
            key = os.environ.get("GOOGLE_API_KEY")
            if key:
                self.api_key = key
                os.environ["LITELLM_API_KEY"] = key
                os.environ["GEMINI_API_KEY"] = key
            
            litellm.api_base = None  # Crucial para que no intente usar OpenRouter
            litellm.headers = {}
            logger.info(f"🤖 Cambiado a Google Nativo: {model_name}")
            
        elif model_name.startswith("ollama/"):
            # Configuración robusta para Ollama Local y Cloud
            api_base_local = os.environ.get("OLLAMA_API_BASE")
            api_key_cloud = os.environ.get("OLLAMA_CLOUD_API_KEY")
            api_key_local = os.environ.get("OLLAMA_API_KEY")
            target = (os.environ.get("OLLAMA_PROVIDER_TARGET") or "").strip().lower()

            # Decidir si usar modo Cloud
            use_cloud = False
            if target in ["cloud", "ollama_cloud"]:
                use_cloud = True
            elif target in ["local", "ollama"]:
                use_cloud = False
            elif api_base_local and any(h in api_base_local for h in ["localhost", "127.0.0.1", "0.0.0.0", "::1"]):
                use_cloud = False
            elif api_key_cloud:
                use_cloud = True

            if use_cloud:
                self.api_base = os.environ.get("OLLAMA_CLOUD_API_BASE") or "https://ollama.com/v1"
                self.api_key = api_key_cloud or api_key_local
                if self.api_key:
                    self.headers = {"Authorization": f"Bearer {self.api_key}"}
                    logger.info(f"☁️ Cambiado a Ollama Cloud: {model_name} en {self.api_base}")
                else:
                    self.headers = {}
                    logger.warning(f"⚠️ Cambiado a Ollama Cloud: {model_name} pero SIN API KEY.")
            else:
                self.api_base = api_base_local or "http://localhost:11434/v1"
                self.api_key = "ollama"
                self.headers = {}
                logger.info(f"🦙 Cambiado a Ollama Local: {model_name} en {self.api_base}")
            
            # Limpiar estado global de litellm para evitar interferencias
            litellm.api_base = None
            litellm.headers = None
            # Para Ollama Cloud, usar el API key real; para local, usar "ollama"
            litellm.api_key = self.api_key if use_cloud and self.api_key else (self.api_key or "ollama")
            
        else:
            # Otros proveedores genéricos
            litellm.api_base = os.environ.get("LITELLM_API_BASE")
            litellm.headers = {}
            logger.info(f"🔄 Cambiado a modelo: {model_name}")

        logger.info(f"✅ Estado de LiteLLM actualizado satisfactoriamente.")

    def set_summary_model(self, summary_model: str):
        """Cambia el modelo usado para resumir historial en tiempo de ejecución."""
        self.summary_model = summary_model
        os.environ["SUMMARY_MODEL"] = summary_model
        logger.info(f"📝 Modelo de resumen establecido: {summary_model}")

    def _initialize_memory(self):
        """Inicializa la memoria si no existe."""
        memory_init_tool = self.get_tool("memory_init")
        if memory_init_tool:
            try:
                # La herramienta memory_init puede necesitar acceso al history_file_path
                # Si es así, se deberá pasar como argumento o hacer que la herramienta lo obtenga de llm_service.
                if hasattr(memory_init_tool, 'invoke'):
                    memory_init_tool.invoke({"history_file_path": self.history_file_path})
            except Exception as e:
                # print(f"Advertencia: Error al inicializar la memoria: {e}", file=sys.stderr)
                pass # No es crítico si falla la inicialización de memoria

    def reload_config(self):
        """Recarga la configuración (modelo y API key) desde ConfigManager y el entorno."""
        from kogniterm.terminal.config_manager import ConfigManager
        cm = ConfigManager()
        
        # Recargar modelo
        new_model = cm.get_config("default_model") or os.environ.get("LITELLM_MODEL") or default_model
        if new_model.startswith("AIza"):
            logger.warning(f"Se detectó una API Key en LITELLM_MODEL. Corrigiendo a '{default_model}'.")
            new_model = default_model
        
        self.model_name = new_model
        self.summary_model = self.model_name
        
        # Recargar API Key
        if self.model_name.startswith("gemini/"):
            self.api_key = cm.get_api_key("google") or os.environ.get("GOOGLE_API_KEY") or os.environ.get("LITELLM_API_KEY")
        elif self.model_name.startswith("openrouter/"):
            self.api_key = cm.get_api_key("openrouter") or os.environ.get("OPENROUTER_API_KEY") or os.environ.get("LITELLM_API_KEY")
        elif self.model_name.startswith("openai/"):
            self.api_key = cm.get_api_key("openai") or os.environ.get("OPENAI_API_KEY") or os.environ.get("LITELLM_API_KEY")
        elif self.model_name.startswith("anthropic/"):
            self.api_key = cm.get_api_key("anthropic") or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("LITELLM_API_KEY")
        elif self.model_name.startswith("ollama_cloud/"):
            self.api_key = cm.get_api_key("ollama_cloud") or os.environ.get("OLLAMA_CLOUD_API_KEY") or os.environ.get("LITELLM_API_KEY")
        else:
            # Fallback
            self.api_key = (
                cm.get_api_key("openrouter")
                or cm.get_api_key("google")
                or cm.get_api_key("openai")
                or cm.get_api_key("anthropic")
                or cm.get_api_key("ollama_cloud")
                or os.environ.get("LITELLM_API_KEY")
                or os.environ.get("OPENROUTER_API_KEY")
                or os.environ.get("GOOGLE_API_KEY")
                or os.environ.get("OPENAI_API_KEY")
                or os.environ.get("ANTHROPIC_API_KEY")
                or os.environ.get("OLLAMA_CLOUD_API_KEY")
            )
        
        logger.info(f"LLMService: Configuración recargada. Nuevo modelo: {self.model_name}")

    def invoke(self, history: Optional[List[BaseMessage]] = None, system_message: Optional[str] = None, interrupt_queue: Optional[queue.Queue] = None, save_history: bool = True, include_tools: bool = True) -> Generator[Union[AIMessage, str], None, None]:
        """
        Invoca al modelo LLM con el historial proporcionado.
        """
        # Actualizar latido/heartbeat de delegación si hay contexto activo en este hilo
        ctx = self.current_delegation_context
        if ctx and hasattr(self, "heartbeat_monitor") and self.heartbeat_monitor:
            self.heartbeat_monitor.update_heartbeat(ctx.agent_id, threshold=300.0)

        # 1. Determinar el historial base
        messages_to_process = history if history is not None else self.conversation_history
        if messages_to_process is None:
            messages_to_process = []

        # 2. Procesar historial usando HistoryManager (truncamiento, resumen, limpieza de huérfanos)
        processed_history = self.history_manager.get_processed_history_for_llm(
            llm_service_summarize_method=self.summarize_conversation_history,
            max_history_messages=self.max_history_messages,
            max_history_chars=self.max_history_chars,
            console=self.console,
            save_history=save_history,
            history=messages_to_process
        )

        # 3. Construir mensajes para LiteLLM
        litellm_messages = []
        system_contents = []
        
        # Extraer todos los mensajes de sistema (del historial y del argumento system_message)
        for msg in processed_history:
            if isinstance(msg, SystemMessage):
                system_contents.append(msg.content)
        
        if system_message:
            system_contents.append(system_message)
            
        # Añadir instrucción de confirmación si no está presente
        tool_confirmation_instruction = (
            "**INSTRUCCIÓN CRÍTICA PARA HERRAMIENTAS Y CONFIRMACIÓN:**\n"
            "1. Cuando recibas un ToolMessage con un `status: \"requires_confirmation\"`, la herramienta está PENDIENTE. DEBES ESPERAR al usuario. NO generes nuevas tool_calls ni texto hasta la confirmación.\n"
            "2. NO.envíes ToolMessages con `confirm: True`. La confirmación la hace el usuario directamente en la interfaz, no tú.\n"
            "3. Simplemente espera a que el usuario confirme o niegue a través de la interfaz.\n"
            "4. Si el usuario aprueba, la herramienta se ejecutará automáticamente.\n"
            "5. NO generes texto ni intentes confirmar tú mismo.\n"
        )
        if not any(tool_confirmation_instruction in sc for sc in system_contents):
            system_contents.append(tool_confirmation_instruction)

        # Añadir el mensaje de contexto del espacio de trabajo si está inicializado y no está en el historial
        workspace_context_message = self._build_llm_context_message()
        if workspace_context_message:
            # Solo añadir si no hay ya un mensaje con ese encabezado en el historial procesado
            if not any("## 📁 CONTEXTO DEL PROYECTO" in str(msg.content) for msg in processed_history):
                system_contents.append(workspace_context_message.content)

        # Añadir el contexto de skills cargadas/relevantes (Semantic Routing) (Proposal A)
        if hasattr(self, 'skill_manager') and self.skill_manager:
            user_query = ""
            for msg in reversed(processed_history):
                if isinstance(msg, HumanMessage) and isinstance(msg.content, str):
                    user_query = msg.content
                    break
            
            skill_context_message = self.skill_manager.build_skill_context_message(query=user_query)
            if skill_context_message:
                if not any("## 🧩 CONTEXTO DE SKILLS" in str(msg.content) for msg in processed_history):
                    system_contents.append(skill_context_message.content)

        # Unificar todos los mensajes de sistema al principio (Requerido por muchos proveedores)
        if system_contents:
            litellm_messages.append({"role": "system", "content": "\n\n".join(system_contents)})

        # Añadir el resto de mensajes (user, assistant, tool)
        last_user_content = None
        known_tool_call_ids = set()
        id_map = {} # Mapa para normalizar IDs (especialmente para Mistral)
        
        # Primero convertimos y filtramos mensajes de asistente vacíos
        raw_conv_messages = []
        for msg in processed_history:
            if isinstance(msg, SystemMessage):
                continue
            
            litellm_msg = self._to_litellm_message(msg, id_map=id_map)
            
            # Filtrar asistentes vacíos sin tool_calls
            if litellm_msg["role"] == "assistant":
                if not litellm_msg.get("content") and not litellm_msg.get("tool_calls"):
                    continue
            
            raw_conv_messages.append(litellm_msg)

        # Validar secuencia para Mistral/OpenRouter
        # Regla: assistant(tool_calls) -> tool(s) -> assistant/user
        if "antigravity" in self.model_name.lower() or "gemini" in self.model_name.lower():
            # Para Antigravity y Gemini, mantener la secuencia original 1:1 sin alterar ni remover tool_calls o tool messages
            # para evitar violar las restricciones estrictas de alternancia de turnos de la API de Gemini.
            for msg in raw_conv_messages:
                role = msg["role"]
                if role == "user":
                    if msg["content"] != last_user_content:
                        litellm_messages.append(msg)
                        last_user_content = msg["content"]
                else:
                    litellm_messages.append(msg)
                    last_user_content = None
        else:
            for i, msg in enumerate(raw_conv_messages):
                role = msg["role"]
                
                if role == "user":
                    # Evitar duplicados consecutivos
                    if msg["content"] != last_user_content:
                        litellm_messages.append(msg)
                        last_user_content = msg["content"]
                elif role == "assistant":
                    if msg.get("tool_calls"):
                        # Validar secuencia estricta: assistant(tool_calls) debe tener ToolMessage(s)
                        # con IDs que coincidan antes del siguiente user/assistant.
                        responded_tool_ids = set()
                        for j in range(i + 1, len(raw_conv_messages)):
                            next_msg = raw_conv_messages[j]
                            if next_msg["role"] == "tool":
                                next_tool_id = next_msg.get("tool_call_id")
                                if next_tool_id:
                                    responded_tool_ids.add(next_tool_id)
                                continue
                            if next_msg["role"] in ["user", "assistant"]:
                                break

                        original_tool_calls = msg.get("tool_calls", [])
                        valid_tool_calls = [
                            tc for tc in original_tool_calls
                            if tc.get("id") and tc.get("id") in responded_tool_ids
                        ]

                        # Si no hay respuestas válidas y no es el último, permitir continuar sin tool_calls.
                        # Esto evita errores de formato en proveedores estrictos (ej. Baidu via OpenRouter).
                        if valid_tool_calls:
                            msg_copy = msg.copy()
                            msg_copy["tool_calls"] = valid_tool_calls
                            for tc in valid_tool_calls:
                                known_tool_call_ids.add(tc["id"])
                            litellm_messages.append(msg_copy)
                        elif i < len(raw_conv_messages) - 1:
                            msg_copy = msg.copy()
                            msg_copy.pop("tool_calls", None)
                            if msg_copy.get("content"):
                                litellm_messages.append(msg_copy)
                        else:
                            # Último mensaje con tool_calls pendientes: remover tool_calls para evitar 400.
                            msg_copy = msg.copy()
                            msg_copy.pop("tool_calls", None)
                            if msg_copy.get("content"):
                                litellm_messages.append(msg_copy)
                    else:
                        litellm_messages.append(msg)
                    last_user_content = None
                elif role == "tool":
                    # Solo añadir si el ID es conocido (evitar huérfanos)
                    tool_id = msg.get("tool_call_id")
                    if tool_id and tool_id in known_tool_call_ids:
                        litellm_messages.append(msg)
                    last_user_content = None

        # 4. Manejo de Rate Limit
        current_time = time.time()
        while self.call_timestamps and self.call_timestamps[0] <= current_time - self.rate_limit_period:
            self.call_timestamps.popleft()

        if len(self.call_timestamps) >= self.rate_limit_calls:
            time_to_wait = self.rate_limit_period - (current_time - self.call_timestamps[0])
            if time_to_wait > 0:
                time.sleep(time_to_wait)
                current_time = time.time()

        self.stop_generation_flag = False

        # 5. Configuración de la llamada
        completion_kwargs = {
            "model": self.model_name,
            "messages": litellm_messages,
            "stream": True,
            "api_key": self.api_key,
            "temperature": self.generation_params.get("temperature", 0.7),
            "max_tokens": 8192,
            "num_retries": 3, # Aumentado para manejar errores temporales
        }
        
        # Añadir herramientas si están disponibles y el modelo las soporta
        if include_tools:
            try:
                tools = self._get_litellm_tools()
                if tools:
                    completion_kwargs["tools"] = tools
                    # Forzar tool_choice a auto para incentivar el uso de herramientas
                    completion_kwargs["tool_choice"] = "auto"
                    logger.info(f"🔧 Incluyendo {len(tools)} herramientas en la llamada al LLM")
            except Exception as e:
                logger.warning(f"No se pudieron cargar las herramientas para el LLM: {e}")
        self._apply_reasoning_effort_param(completion_kwargs, self.model_name)

        # Pasar api_base y headers explícitamente si están definidos
        if hasattr(self, 'api_base') and self.api_base:
            completion_kwargs["api_base"] = self.api_base
        if hasattr(self, 'headers') and self.headers:
            completion_kwargs["headers"] = self.headers
        
        # Configuración específica para Gemini (Google AI Studio)
        if self.model_name.startswith("gemini/") or ("gemini" in self.model_name.lower() and "openrouter" not in self.model_name.lower() and "antigravity" not in self.model_name.lower()):
            completion_kwargs["custom_llm_provider"] = "gemini"
            if self.api_key:
                os.environ["GEMINI_API_KEY"] = self.api_key

        # Configuración específica para OpenRouter/SiliconFlow con campos adicionales
        if "openrouter" in self.model_name.lower():
            # Asegurar formato correcto del modelo
            if not completion_kwargs["model"].startswith("openrouter/"):
                completion_kwargs["model"] = f"openrouter/{self.model_name}"
            
            # Habilitar Reasoning por defecto para OpenRouter
            if "extra_body" not in completion_kwargs:
                completion_kwargs["extra_body"] = {}
            completion_kwargs["extra_body"]["reasoning"] = { "type": "enabled" }
            # También añadir el parámetro directo si LiteLLM lo soporta
            completion_kwargs["include_reasoning"] = True
            
            # Para modelos específicos como Nex-AGI, usar configuración más simple
            if "nex-agi" in self.model_name.lower() or "deepseek" in self.model_name.lower():
                # Configuración minimalista para Nex-AGI/DeepSeek
                completion_kwargs["user"] = f"user_{self._generate_short_id(12)}"
                # NO enviar campos adicionales que puedan causar problemas
                logger.debug(f"Configuración minimalista para Nex-AGI/DeepSeek: {completion_kwargs['model']}")
            else:
                # Configuración estándar para otros modelos
                completion_kwargs["user"] = f"user_{self._generate_short_id(12)}"
                completion_kwargs["metadata"] = {
                    "user_id": completion_kwargs["user"],
                    "application_name": "KogniTerm"
                }
            
            # Logging para debug
            logger.debug(f"OpenRouter configuration: model={completion_kwargs['model']}, user={completion_kwargs.get('user', 'N/A')}")
        
        # --- Lógica de Selección de Herramientas y Validación de Secuencia ---
        final_tools = []
        litellm_tools = self._get_litellm_tools()
        if litellm_tools:
            for t in litellm_tools:
                if isinstance(t, dict):
                    # Handle both standard format {"name": "...", "description": "...", "parameters": {...}}
                    # and SiliconFlow/OpenRouter format {"type": "function", "function": {...}}
                    if "name" in t or ("type" in t and t.get("type") == "function"):
                        final_tools.append(t)

        if final_tools:
            completion_kwargs["tools"] = final_tools
            # Forzar tool_choice="auto" para modelos que lo soporten
            if (
                "gpt" in self.model_name.lower()
                or "openai" in self.model_name.lower()
                or "gemini" in self.model_name.lower()
                or self.model_name.lower().startswith("ollama/")
                or "ollama" in self.model_name.lower()
            ):
                completion_kwargs["tool_choice"] = "auto"

        # Validación estricta de secuencia para Mistral/OpenRouter
        validated_messages = []
        last_user_content = None
        in_tool_sequence = False
        
        # Filtrar y validar secuencia
        for i, msg in enumerate(raw_conv_messages):
            role = msg["role"]
            
            if role == "user":
                if msg["content"] != last_user_content:
                    validated_messages.append(msg)
                    last_user_content = msg["content"]
                in_tool_sequence = False
            
            elif role == "assistant":
                if msg.get("tool_calls"):
                    # Verificar si el SIGUIENTE mensaje es una herramienta
                    has_next_tool = False
                    for j in range(i + 1, len(raw_conv_messages)):
                        if raw_conv_messages[j]["role"] == "tool":
                            has_next_tool = True
                            break
                        if raw_conv_messages[j]["role"] in ["user", "assistant"]:
                            break

                    if has_next_tool:
                        validated_messages.append(msg)
                        in_tool_sequence = True
                    else:
                        # Si no hay herramienta después, "neutralizamos" el mensaje quitando tool_calls
                        # Esto evita el error 400 de Mistral
                        msg_copy = msg.copy()
                        msg_copy.pop("tool_calls", None)
                        if not msg_copy.get("content"):
                            msg_copy["content"] = "Procesando..." # No puede estar vacío
                        validated_messages.append(msg_copy)
                        in_tool_sequence = False
                else:
                    if not msg.get("content"):
                        msg["content"] = "..." # Evitar asistentes vacíos
                    validated_messages.append(msg)
                    in_tool_sequence = False
                last_user_content = None
            
            elif role == "tool":
                # Solo añadir si el ID existe y está en secuencia de herramientas (evitar huérfanos)
                # El ID ya fue normalizado en el paso anterior mediante id_map
                if msg.get("tool_call_id") and in_tool_sequence:
                    validated_messages.append(msg)
                last_user_content = None

        # Unificar mensajes de sistema y combinar
        final_messages = []
        if system_contents:
            final_messages.append({"role": "system", "content": "\n\n".join(system_contents)})
        final_messages.extend(validated_messages)

        completion_kwargs["messages"] = final_messages
        
        # Variables para todos los niveles de fallback (inicializadas fuera del try para evitar UnboundError)
        full_response_content = ""
        full_reasoning_content = ""
        tool_calls = []

        try:
            sys.stderr.flush()
            start_time = time.perf_counter()
            
            logger.debug(f"DEBUG: Enviando mensajes al LLM: {json.dumps(completion_kwargs['messages'], indent=2)}")
            logger.debug(f"DEBUG: completion_kwargs: {json.dumps(completion_kwargs, indent=2)}")
            
            # Usar MultiProviderManager si está habilitado
            if self.use_multi_provider and self.provider_manager:
                logger.info("🔄 Usando MultiProviderManager con fallback automático")
                
                # Inyectar custom_llm_provider si es kilocode
                extra_args = {}
                if "kilocode" in self.model_name.lower() or (hasattr(self, 'api_base') and self.api_base and "kilo.ai" in self.api_base):
                    extra_args["custom_llm_provider"] = "openai"

                response_generator = self.provider_manager.execute_with_fallback(
                    model_name=self.model_name,
                    messages=completion_kwargs["messages"],
                    stream=completion_kwargs.get("stream", True),
                    api_key=completion_kwargs.get("api_key"),
                    api_base=completion_kwargs.get("api_base"),
                    headers=completion_kwargs.get("headers"),
                    temperature=completion_kwargs.get("temperature", 0.7),
                    reasoning_effort=completion_kwargs.get("reasoning_effort"),
                    max_tokens=completion_kwargs.get("max_tokens", 8192),
                    tools=completion_kwargs.get("tools"),
                    tool_choice=completion_kwargs.get("tool_choice"),
                    **extra_args
                )
            else:
                # Fallback al comportamiento original
                response_generator = completion(
                    **completion_kwargs
                )
            logger.debug("DEBUG: litellm.completion llamada exitosa, procesando chunks...")
            end_time = time.perf_counter()
            self.call_timestamps.append(time.time())
            start_time = time.time()
            last_chunk_time = time.time()
            chunk_timeout = self.stream_chunk_timeout
            overall_timeout = self.stream_overall_timeout
            
            # Variables para detección de truncamiento y reintentos de continuación
            last_finish_reason = None
            continuation_attempts = 0
            
            # Variables para detección acumulativa de CoT manual (etiquetas <thought>)
            stream_buffer = ""
            processed_index = 0
            in_manual_thought = False
            
            def get_safe_yield_index(text: str) -> int:
                tags = ["<thought>", "<thinking>"]
                for tag in tags:
                    for i in range(1, len(tag)):
                        prefix = tag[:i]
                        if text.endswith(prefix):
                            return len(text) - len(prefix)
                return len(text)

            def get_safe_thinking_yield_index(text: str) -> int:
                tags = ["</thought>", "</thinking>"]
                for tag in tags:
                    for i in range(1, len(tag)):
                        prefix = tag[:i]
                        if text.endswith(prefix):
                            return len(text) - len(prefix)
                return len(text)

            for chunk in response_generator:
                current_time = time.time()
                
                # Detectar estancamiento entre chunks
                if current_time - last_chunk_time > chunk_timeout:
                    logger.warning(f"⚠️ Estancamiento detectado: {current_time - last_chunk_time:.1f}s sin chunks. Intentando esperar un poco más...")
                    if current_time - last_chunk_time > (chunk_timeout * 2):
                         logger.error(f"❌ Timeout severo de chunk alcanzado: {current_time - last_chunk_time:.1f}s.")
                         break

                last_chunk_time = current_time                
                # Detectar timeout total de la solicitud
                if current_time - start_time > overall_timeout:
                    logger.error(f"Timeout total de {overall_timeout}s alcanzado en el stream.")
                    yield f"\n\n⚠️ Error: Tiempo de espera agotado ({overall_timeout}s). La conexión se ha cerrado.\n"
                    break

                # Verificar la cola de interrupción
                if interrupt_queue and not interrupt_queue.empty():
                    while not interrupt_queue.empty(): # Vaciar la cola
                        interrupt_queue.get_nowait()
                    self.stop_generation_flag = True
                    logger.info("Interrupción detectada desde la cola.")
                    break # Salir del bucle de chunks

                if self.stop_generation_flag:
                    break

                choices = getattr(chunk, 'choices', None)
                if not choices or not isinstance(choices, list) or not choices[0]:
                    continue
                
                choice = choices[0]
                # Registrar finish_reason si está presente (p.ej. 'length' cuando se corta por max_tokens)
                fr = getattr(choice, 'finish_reason', None)
                if fr:
                    last_finish_reason = fr
                delta = getattr(choice, 'delta', None)
                if not delta:
                    logger.debug("DEBUG: Delta vacío, continuando...")
                    continue
                
                # Log the raw delta for debugging
                logger.debug(f"DEBUG: LiteLLM Delta recibido: {delta}")

                # Capturar contenido de razonamiento (Thinking) nativo si está disponible
                reasoning_delta = getattr(delta, 'reasoning_content', None)
                if reasoning_delta is not None:
                    full_reasoning_content += str(reasoning_delta)
                    yield f"__THINKING__:{reasoning_delta}"

                content_delta = getattr(delta, 'content', None)
                if content_delta is not None:
                    chunk_str = str(content_delta)
                    # Acumular en el buffer
                    stream_buffer += chunk_str
                    # Normalizar etiquetas
                    stream_buffer = stream_buffer.replace("<thinking>", "<thought>").replace("</thinking>", "</thought>")
                    
                    # Bucle para procesar el buffer de forma acumulativa
                    while processed_index < len(stream_buffer):
                        remaining_text = stream_buffer[processed_index:]
                        
                        if not in_manual_thought:
                            # Caso A: Fuera del bloque de pensamiento
                            # Buscar etiqueta de inicio
                            tag_idx = remaining_text.find("<thought>")
                            if tag_idx == -1:
                                # No hay etiqueta de inicio completa en lo que queda.
                                # Verificar si el final del buffer contiene un prefijo parcial de la etiqueta
                                safe_len = get_safe_yield_index(remaining_text)
                                if safe_len > 0:
                                    text_to_yield = remaining_text[:safe_len]
                                    full_response_content += text_to_yield
                                    yield text_to_yield
                                    processed_index += safe_len
                                else:
                                    # Esperar al siguiente chunk (todo lo que queda es un prefijo parcial)
                                    break
                            else:
                                # Etiqueta de inicio encontrada
                                text_before = remaining_text[:tag_idx]
                                if text_before:
                                    full_response_content += text_before
                                    yield text_before
                                
                                processed_index += tag_idx + len("<thought>")
                                in_manual_thought = True
                                logger.info("🧠 Inicio de pensamiento manual detectado (<thought>)")
                        else:
                            # Caso B: Dentro del bloque de pensamiento
                            # Buscar etiqueta de cierre
                            close_idx = remaining_text.find("</thought>")
                            if close_idx == -1:
                                # No hay etiqueta de cierre completa.
                                # Verificar si el final contiene un prefijo parcial del cierre
                                safe_len = get_safe_thinking_yield_index(remaining_text)
                                if safe_len > 0:
                                    thought_to_yield = remaining_text[:safe_len]
                                    full_reasoning_content += thought_to_yield
                                    yield f"__THINKING__:{thought_to_yield}"
                                    processed_index += safe_len
                                else:
                                    # Esperar al siguiente chunk (todo lo que queda es un prefijo parcial de cierre)
                                    break
                            else:
                                # Etiqueta de cierre encontrada
                                thought_before = remaining_text[:close_idx]
                                if thought_before:
                                    full_reasoning_content += thought_before
                                    yield f"__THINKING__:{thought_before}"
                                
                                processed_index += close_idx + len("</thought>")
                                in_manual_thought = False
                                logger.info("🧠 Fin de pensamiento manual detectado (</thought>)")
                
                tool_calls_from_delta = getattr(delta, 'tool_calls', None)
                if tool_calls_from_delta is not None:
                    # Acumular tool_calls
                    for tc in tool_calls_from_delta:
                        idx = getattr(tc, 'index', 0)
                        
                        # Asegurarse de que la lista tool_calls tenga el tamaño suficiente
                        while idx >= len(tool_calls):
                            tool_calls.append({"id": "", "function": {"name": "", "arguments": ""}})
                        
                        # Actualizar el ID si está presente
                        if getattr(tc, 'id', None) is not None:
                            tool_calls[idx]["id"] = tc.id
                        elif not tool_calls[idx]["id"]:
                            tool_calls[idx]["id"] = self._generate_short_id()
                        
                        # Capturar thought_signature (requerido por Antigravity para el segundo turno)
                        if getattr(tc, 'thought_signature', None):
                            tool_calls[idx]["thought_signature"] = tc.thought_signature
                        
                        # Actualizar el nombre de la función
                        if getattr(tc, 'function', None) is not None:
                            if getattr(tc.function, 'name', None) is not None and tc.function.name:
                                tool_calls[idx]["function"]["name"] = tc.function.name
                            
                            # Acumular los argumentos asegurando que son strings
                            if getattr(tc.function, 'arguments', None) is not None:
                                tool_calls[idx]["function"]["arguments"] += str(tc.function.arguments)


            if self.stop_generation_flag:
                # Si se interrumpe, el AIMessage final se construye con el mensaje de interrupción
                yield AIMessage(content="Generación de respuesta interrumpida por el usuario. 🛑")
            else:
                # LÓGICA UNIFICADA: Combinar tool_calls nativos y manuales detectados en el texto
                final_tool_calls = []

                # Reintentos automáticos: si el modelo truncó la respuesta por límite de tokens, intentar continuar
                if last_finish_reason and any(k in str(last_finish_reason).lower() for k in ("length","max","token")) and getattr(self, 'max_continuations', 3) > 0:
                    attempts = 0
                    while attempts < getattr(self, 'max_continuations', 3):
                        attempts += 1
                        logger.info(f"Intentando continuación automática (intento {attempts}/{self.max_continuations})...")
                        try:
                            cont_msgs = [m.copy() for m in completion_kwargs.get("messages", [])]
                            # Añadir la respuesta parcial como mensaje del asistente para que el modelo pueda continuar
                            cont_msgs.append({"role": "assistant", "content": full_response_content})
                            cont_msgs.append({"role": "user", "content": "Por favor, continúa la respuesta anterior, sin repetir lo ya dicho. Continúa desde donde te quedaste."})

                            if self.use_multi_provider and self.provider_manager:
                                cont_gen = self.provider_manager.execute_with_fallback(
                                    model_name=self.model_name,
                                    messages=cont_msgs,
                                    stream=True,
                                    temperature=completion_kwargs.get("temperature", 0.7),
                                    reasoning_effort=completion_kwargs.get("reasoning_effort"),
                                    max_tokens=min(4096, completion_kwargs.get("max_tokens", 8192)),
                                    tools=completion_kwargs.get("tools"),
                                )
                            else:
                                cont_kwargs = dict(completion_kwargs)
                                cont_kwargs["messages"] = cont_msgs
                                cont_kwargs["max_tokens"] = min(4096, completion_kwargs.get("max_tokens", 8192))
                                cont_kwargs["num_retries"] = 1
                                cont_kwargs["timeout"] = self.api_timeout_seconds
                                cont_gen = completion(**cont_kwargs)

                            cont_last_chunk_time = time.time()
                            for cont_chunk in cont_gen:
                                current_time = time.time()
                                # Detectar estancamiento entre chunks durante la continuación
                                if current_time - cont_last_chunk_time > self.stream_chunk_timeout:
                                    logger.warning(f"⚠️ Estancamiento detectado en continuación: {current_time - cont_last_chunk_time:.1f}s sin chunks.")
                                    if current_time - cont_last_chunk_time > (self.stream_chunk_timeout * 2):
                                        logger.error(f"❌ Timeout severo de continuación alcanzado: {current_time - cont_last_chunk_time:.1f}s.")
                                        break
                                cont_last_chunk_time = current_time
                                
                                # Detectar timeout total de la solicitud durante la continuación
                                if current_time - start_time > self.stream_overall_timeout:
                                    logger.error(f"Timeout total de {self.stream_overall_timeout}s alcanzado en el stream de continuación.")
                                    yield f"\n\n⚠️ Error: Tiempo de espera agotado ({self.stream_overall_timeout}s). La conexión se ha cerrado.\n"
                                    break

                                cont_choices = getattr(cont_chunk, 'choices', None)
                                if not cont_choices or not isinstance(cont_choices, list) or not cont_choices[0]:
                                    continue

                                cont_choice = cont_choices[0]
                                fr = getattr(cont_choice, 'finish_reason', None)
                                if fr:
                                    last_finish_reason = fr

                                cont_delta = getattr(cont_choice, 'delta', None)
                                if not cont_delta:
                                    logger.debug("DEBUG: Continuation delta vacío, continuando...")
                                    continue

                                reasoning_delta = getattr(cont_delta, 'reasoning_content', None)
                                if reasoning_delta is not None:
                                    full_reasoning_content += str(reasoning_delta)
                                    yield f"__THINKING__:{reasoning_delta}"

                                if getattr(cont_delta, 'content', None) is not None:
                                    full_response_content += str(cont_delta.content)
                                    yield str(cont_delta.content)

                                cont_tool_calls = getattr(cont_delta, 'tool_calls', None)
                                if cont_tool_calls is not None:
                                    for tc in cont_tool_calls:
                                        idx = getattr(tc, 'index', 0)
                                        while idx >= len(tool_calls):
                                            tool_calls.append({"id": "", "function": {"name": "", "arguments": ""}})
                                        if getattr(tc, 'id', None) is not None:
                                            tool_calls[idx]["id"] = tc.id
                                        elif not tool_calls[idx]["id"]:
                                            tool_calls[idx]["id"] = self._generate_short_id()
                                        if getattr(tc, 'function', None) is not None:
                                            if getattr(tc.function, 'name', None) is not None and tc.function.name:
                                                tool_calls[idx]["function"]["name"] = tc.function.name
                                            if getattr(tc.function, 'arguments', None) is not None:
                                                tool_calls[idx]["function"]["arguments"] += str(tc.function.arguments)

                            # Si la continuación ya no termina por límite de tokens, salir del bucle de reintentos
                            if not (last_finish_reason and any(k in str(last_finish_reason).lower() for k in ("length","max","token"))):
                                break

                        except Exception as cont_err:
                            logger.warning(f"Falló la continuación automática en intento {attempts}: {cont_err}")
                            break

                # 1. Procesar tool_calls nativos acumulados durante el streaming
                if tool_calls:
                    for tc in tool_calls:
                        args_str = tc["function"]["arguments"] if isinstance(tc["function"]["arguments"], str) else ""
                        try:
                            args = json.loads(args_str)
                        except json.JSONDecodeError:
                            args = {}
                        
                        tc_final = {
                            "id": tc["id"],
                            "name": tc["function"]["name"],
                            "args": args
                        }
                        # Propagar thought_signature (Antigravity lo requiere en el segundo turno)
                        if tc.get("thought_signature"):
                            tc_final["thought_signature"] = tc["thought_signature"]
                        final_tool_calls.append(tc_final)
                
                # 2. Complementar con parseo de texto (siempre, para máxima robustez)
                # Combinar contenido de respuesta y razonamiento para el parser, así no importa dónde lo escriba el modelo
                parsing_source = []
                if full_response_content and full_response_content.strip():
                    parsing_source.append(full_response_content)
                if full_reasoning_content and full_reasoning_content.strip():
                    parsing_source.append(full_reasoning_content)
                
                combined_text = "\n".join(parsing_source)
                
                if combined_text.strip():
                    text_tool_calls = self._parse_tool_calls_from_text(combined_text)
                    
                    # Fusionar evitando duplicados. Si ya existe una llamada nativa CON argumentos, preferirla.
                    # Si la nativa está vacía pero la del texto tiene argumentos, preferir la del texto.
                    for tc_text in text_tool_calls:
                        found_index = -1
                        for i, tc_final in enumerate(final_tool_calls):
                            if tc_final['name'] == tc_text['name']:
                                found_index = i
                                break
                        
                        if found_index >= 0:
                            # Si la existente no tiene argumentos pero la nueva sí, actualizar
                            if not final_tool_calls[found_index]['args'] and tc_text.get('args'):
                                final_tool_calls[found_index]['args'] = tc_text['args']
                        else:
                            # No existe, añadirla
                            final_tool_calls.append(tc_text)
                
                if final_tool_calls:
                    if not full_response_content or not full_response_content.strip():
                        full_response_content = "Ejecutando herramientas..."
                    
                    # Extraer thought_signature de final_tool_calls para evitar errores de validación de LangChain
                    thought_signatures = {}
                    for tc in final_tool_calls:
                        tsig = tc.pop("thought_signature", None)
                        if tsig:
                            thought_signatures[tc["id"]] = tsig
                    
                    additional_kwargs = {}
                    if full_reasoning_content:
                        additional_kwargs["reasoning_content"] = full_reasoning_content
                    if thought_signatures:
                        additional_kwargs["thought_signatures"] = thought_signatures

                    yield AIMessage(
                        content=full_response_content, 
                        tool_calls=final_tool_calls,
                        additional_kwargs=additional_kwargs
                    )
                else:
                    if not full_response_content.strip():
                        logger.debug("DEBUG: full_response_content vacío al finalizar la generación.")
                        full_response_content = "El modelo devolvió una respuesta vacía. Por favor, intenta reformular tu pregunta si el problema persiste."
                    
                    yield AIMessage(
                        content=full_response_content,
                        additional_kwargs={"reasoning_content": full_reasoning_content} if full_reasoning_content else {}
                    )

        except Exception as e:
            # Manejo de errores más amigable para el usuario
            error_type = type(e).__name__
            error_msg = str(e)
            
            # Si es un error de herramientas (SiliconFlow 20015 o OpenRouter 404 No endpoints)
            is_tool_error = (
                ("20015" in error_msg and "Input should be 'function'" in error_msg) or 
                ("20015" in error_msg and "Field required" in error_msg and "openrouter" in self.model_name.lower()) or
                ("No endpoints found that support tool use" in error_msg)
            )

            if is_tool_error:
                logger.info(f"🔄 Detectado modelo sin soporte nativo de herramientas ({self.model_name}). Activando Bypass...")
                try:
                    # Preparar mensajes con herramientas inyectadas en el prompt si es necesario
                    messages_with_tools = [m.copy() for m in completion_kwargs["messages"]]
                    
                    # Si el error es por falta de soporte (OpenRouter 404), inyectar herramientas en el prompt de sistema
                    if "No endpoints found" in error_msg:
                        tools_desc = ""
                        if completion_kwargs.get("tools"):
                            tools_desc = "\n\n### HERRAMIENTAS DISPONIBLES\n"
                            tools_desc += "ESTÁS EN MODO BYPASS: Este modelo NO soporta Function Calling nativo. DEBES llamar a las herramientas escribiendo EXACTAMENTE este formato en tu respuesta:\n"
                            tools_desc += "LLAMADA_A_HERRAMIENTA: nombre_herramienta {\"arg1\": \"valor1\"}\n\n"
                            for t in completion_kwargs["tools"]:
                                func = t.get("function", t)
                                name = func.get("name")
                                desc = func.get("description", "")
                                params = func.get("parameters", {}).get("properties", {})
                                tools_desc += f"- **{name}**: {desc}\n  Argumentos requeridos: {list(params.keys())}\n"
                        
                        # Inyectar en el primer mensaje de sistema
                        if messages_with_tools and messages_with_tools[0]["role"] == "system":
                            messages_with_tools[0]["content"] += tools_desc
                        else:
                            messages_with_tools.insert(0, {"role": "system", "content": tools_desc})

                    # Crear configuración alternativa más específica
                    alt_kwargs = {
                        "model": completion_kwargs["model"],
                        "messages": messages_with_tools,
                        "stream": True,
                        "api_key": completion_kwargs["api_key"],
                        "temperature": completion_kwargs.get("temperature", 0.7),
                        "max_tokens": completion_kwargs.get("max_tokens", 4096),
                        "user": f"user_{self._generate_short_id(12)}",
                        "num_retries": 1, 
                        "timeout": self.api_timeout_fallback_seconds
                    }
                    
                    # Aplicar reasoning_effort si está configurado
                    if completion_kwargs.get("reasoning_effort"):
                        alt_kwargs["reasoning_effort"] = completion_kwargs["reasoning_effort"]
                    
                    # IMPORTANTE: Si es error de soporte, quitamos 'tools' de la llamada para que el servidor no la rechace
                    if "No endpoints found" in error_msg:
                        alt_kwargs.pop("tools", None)
                        alt_kwargs.pop("tool_choice", None)
                    
                    
                    # Solo agregar parámetros adicionales si el modelo no es Nex-AGI/DeepSeek
                    if not ("nex-agi" in self.model_name.lower() or "deepseek" in self.model_name.lower()):
                        alt_kwargs["top_k"] = self.generation_params.get("top_k", 40)
                        alt_kwargs["top_p"] = self.generation_params.get("top_p", 0.95)
                    
                    logger.debug(f"Configuración alternativa: {list(alt_kwargs.keys())}")
                    
                    # Intentar llamada alternativa
                    response_generator = completion(**alt_kwargs)
                    
                    # Si llegamos aquí, el fallback funcionó, procesar respuesta normalmente
                    for chunk in response_generator:
                        # Comprobación de interrupción prioritaria
                        if interrupt_queue and not interrupt_queue.empty():
                            while not interrupt_queue.empty():
                                interrupt_queue.get_nowait()
                            self.stop_generation_flag = True
                            logger.info("Interrupción detectada en el bucle principal de streaming.")
                            break

                        if self.stop_generation_flag:
                            break

                        choices = getattr(chunk, 'choices', None)
                        if not choices or not isinstance(choices, list) or not choices[0]:
                            continue
                        
                        choice = choices[0]
                        delta = getattr(choice, 'delta', None)
                        if not delta:
                            continue
                        
                        if getattr(delta, 'content', None) is not None:
                            full_response_content += str(delta.content)
                            yield str(delta.content)
                        
                        # Capturar razonamiento en fallback
                        reasoning_delta = getattr(delta, 'reasoning_content', None)
                        if reasoning_delta is not None:
                            full_reasoning_content += str(reasoning_delta)
                            yield f"__THINKING__:{reasoning_delta}"
                        
                        tool_calls_from_delta = getattr(delta, 'tool_calls', None)
                        if tool_calls_from_delta is not None:
                            # Acumular tool_calls
                            for tc in tool_calls_from_delta:
                                while tc.index >= len(tool_calls):
                                    tool_calls.append({"id": "", "function": {"name": "", "arguments": ""}})
                                
                                if getattr(tc, 'id', None) is not None:
                                    tool_calls[tc.index]["id"] = tc.id
                                elif not tool_calls[tc.index]["id"]:
                                    tool_calls[tc.index]["id"] = self._generate_short_id()
                                
                                if getattr(tc.function, 'name', None) is not None:
                                    tool_calls[tc.index]["function"]["name"] = tc.function.name
                                    if getattr(tc.function, 'arguments', None) is not None:
                                        tool_calls[tc.index]["function"]["arguments"] += tc.function.arguments
                    
                    # Procesar respuesta final del fallback
                    if self.stop_generation_flag:
                        yield AIMessage(content="Generación de respuesta interrumpida por el usuario. 🛑")
                    elif tool_calls:
                        formatted_tool_calls = []
                        for tc in tool_calls:
                            # Asegurarse de que 'arguments' sea una cadena antes de intentar json.loads
                            args_str = tc["function"]["arguments"] if isinstance(tc["function"]["arguments"], str) else ""
                            try:
                                args = json.loads(args_str)
                            except json.JSONDecodeError as e:
                                logger.error(f"JSONDecodeError al decodificar argumentos de herramienta para '{tc['function']['name']}' en fallback: {e}. Argumentos recibidos (truncados a 500 chars): '{args_str[:500]}'. Longitud total: {len(args_str)}")
                                args = {}
                            formatted_tool_calls.append({
                                "id": tc["id"],
                                "name": tc["function"]["name"],
                                "args": args
                            })
                        if not full_response_content or not full_response_content.strip():
                            full_response_content = "Ejecutando herramientas..."
                        yield AIMessage(
                            content=full_response_content, 
                            tool_calls=formatted_tool_calls,
                            additional_kwargs={"reasoning_content": full_reasoning_content} if full_reasoning_content else {}
                        )
                    else:
                        # NUEVA LÓGICA: Si no hay tool_calls nativos, verificar si el contenido contiene tool calls en texto
                        enhanced_tool_calls = []
                        if full_response_content and full_response_content.strip():
                            enhanced_tool_calls = self._parse_tool_calls_from_text(full_response_content)
                        
                        if enhanced_tool_calls:
                            # Si encontramos tool calls en el texto, crear AIMessage con ellos
                            if not full_response_content.strip():
                                full_response_content = "Ejecutando herramientas..."
                            yield AIMessage(
                                content=full_response_content, 
                                tool_calls=enhanced_tool_calls,
                                additional_kwargs={"reasoning_content": full_reasoning_content} if full_reasoning_content else {}
                            )
                        else:
                            if not full_response_content.strip():
                                full_response_content = "El modelo devolvió una respuesta vacía. Esto puede deberse a un problema temporal del proveedor o a un filtro de seguridad. Por favor, intenta reformular tu pregunta."
                            yield AIMessage(
                                content=full_response_content,
                                additional_kwargs={"reasoning_content": full_reasoning_content} if full_reasoning_content else {}
                            )
                    
                    # Si llegamos aquí, el fallback funcionó, retornar
                    return
                    
                except Exception as fallback_error:
                    logger.warning(f"Fallback también falló: {fallback_error}")
                    
                    # Intentar configuración ultra-minimalista para modelos muy específicos
                    if "nex-agi" in self.model_name.lower() or "deepseek" in self.model_name.lower():
                        logger.info("Intentando configuración ultra-minimalista para Nex-AGI/DeepSeek...")
                        try:
                            ultra_kwargs = {
                                "model": completion_kwargs["model"],
                                "messages": completion_kwargs["messages"],
                                "stream": True,
                                "api_key": completion_kwargs["api_key"],
                                "user": f"user_{self._generate_short_id(8)}"  # ID más corto
                            }
                            
                            # Aplicar reasoning_effort si está configurado
                            if completion_kwargs.get("reasoning_effort"):
                                ultra_kwargs["reasoning_effort"] = completion_kwargs["reasoning_effort"]
                            
                            logger.debug(f"Configuración ultra-minimalista: {list(ultra_kwargs.keys())}")
                            response_generator = completion(**ultra_kwargs)
                            
                            # Procesar respuesta con configuración ultra-minimalista
                            for chunk in response_generator:
                                # Comprobación de interrupción prioritaria
                                if interrupt_queue and not interrupt_queue.empty():
                                    while not interrupt_queue.empty():
                                        interrupt_queue.get_nowait()
                                    self.stop_generation_flag = True
                                    logger.info("Interrupción detectada en el bucle principal de streaming.")
                                    break

                                if self.stop_generation_flag:
                                    break
                        
                                choices = getattr(chunk, 'choices', None)
                                if not choices or not isinstance(choices, list) or not choices[0]:
                                    continue
                                
                                choice = choices[0]
                                delta = getattr(choice, 'delta', None)
                                if not delta:
                                    continue
                                
                                if getattr(delta, 'content', None) is not None:
                                    full_response_content += str(delta.content)
                                    yield str(delta.content)
                                
                                tool_calls_from_delta = getattr(delta, 'tool_calls', None)
                                if tool_calls_from_delta is not None:
                                    for tc in tool_calls_from_delta:
                                        while tc.index >= len(tool_calls):
                                            tool_calls.append({"id": "", "function": {"name": "", "arguments": ""}})
                                        
                                        if getattr(tc, 'id', None) is not None:
                                            tool_calls[tc.index]["id"] = tc.id
                                        elif not tool_calls[tc.index]["id"]:
                                            tool_calls[tc.index]["id"] = self._generate_short_id()
                                        
                                        if getattr(tc.function, 'name', None) is not None:
                                            tool_calls[tc.index]["function"]["name"] = tc.function.name
                                            if getattr(tc.function, 'arguments', None) is not None:
                                                tool_calls[tc.index]["function"]["arguments"] += tc.function.arguments
                            
                            # Procesar respuesta final del fallback ultra-minimalista
                            if self.stop_generation_flag:
                                yield AIMessage(content="Generación de respuesta interrumpida por el usuario. 🛑")
                            elif tool_calls:
                                formatted_tool_calls = []
                                for tc in tool_calls:
                                    try:
                                        args = json.loads(tc["function"]["arguments"])
                                    except json.JSONDecodeError as e:
                                        logger.error(f"JSONDecodeError al decodificar argumentos de herramienta para '{tc['function']['name']}' en ultra-fallback: {e}. Argumentos recibidos (truncados a 500 chars): '{tc['function']['arguments'][:500]}'. Longitud total: {len(tc['function']['arguments'])}")
                                        args = {}
                                    formatted_tool_calls.append({
                                        "id": tc["id"],
                                        "name": tc["function"]["name"],
                                        "args": args
                                    })
                                if not full_response_content or not full_response_content.strip():
                                    full_response_content = "Ejecutando herramientas..."
                                yield AIMessage(content=full_response_content, tool_calls=formatted_tool_calls)
                            else:
                                # NUEVA LÓGICA: Si no hay tool_calls nativos, verificar si el contenido contiene tool calls en texto
                                enhanced_tool_calls = []
                                if full_response_content and full_response_content.strip():
                                    enhanced_tool_calls = self._parse_tool_calls_from_text(full_response_content)
                                
                                if enhanced_tool_calls:
                                    # Si encontramos tool calls en el texto, crear AIMessage con ellos
                                    if not full_response_content.strip():
                                        full_response_content = "Ejecutando herramientas..."
                                    yield AIMessage(content=full_response_content, tool_calls=enhanced_tool_calls)
                                else:
                                    if not full_response_content.strip():
                                        full_response_content = "El modelo devolvió una respuesta vacía. Esto puede deberse a un problema temporal del proveedor o a un filtro de seguridad. Por favor, intenta reformular tu pregunta."
                                    yield AIMessage(content=full_response_content)
                            
                            # Si llegamos aquí, el fallback ultra-minimalista funcionó
                            return
                            
                        except Exception as ultra_fallback_error:
                            logger.warning(f"Fallback ultra-minimalista también falló: {ultra_fallback_error}")
                    
                    # Continuar con el manejo de errores original
                    error_msg = str(fallback_error)
            
            # Identificar errores comunes de proveedores (OpenRouter, Google, etc.)
            if "Missing corresponding tool call for tool response message" in error_msg:
                friendly_message = "¡Ups! 🔧 Se detectó un problema con la secuencia de herramientas en el historial. Estoy limpiando el historial para continuar. Por favor, repite tu última solicitud si es necesario."
                # Limpiar el historial removiendo tool messages huérfanos
                cleaned_history = []
                in_sequence = False
                for msg in self.conversation_history:
                    if isinstance(msg, AIMessage) and msg.tool_calls:
                        cleaned_history.append(msg)
                        in_sequence = True
                    elif isinstance(msg, ToolMessage):
                        if in_sequence:
                            cleaned_history.append(msg)
                        # else skip tool message huérfano
                    else:
                        cleaned_history.append(msg)
                        in_sequence = False
                self.conversation_history = cleaned_history
                self._save_history(self.conversation_history)
            elif "OpenrouterException" in error_msg or "Upstream error" in error_msg:
                if "No endpoints found" in error_msg:
                    friendly_message = "⚠️ El modelo solicitado no está disponible con los parámetros actuales. Verifica que el nombre del modelo sea correcto y que esté disponible en OpenRouter."
                elif "Function name was" in error_msg:
                    friendly_message = "¡Ups! 🛠️ El modelo intentó usar una herramienta con un formato incorrecto. He neutralizado la llamada a la herramienta para que la conversación pueda continuar. Por favor, intenta reformular tu solicitud o sé más específico sobre cómo quieres usar la herramienta."
                    # En este caso, no queremos que el AIMessage tenga tool_calls,
                    # así que lo generamos directamente aquí.
                    yield AIMessage(content=friendly_message)
                    return # Salir de la función después de ceder el mensaje de error
                else:
                    friendly_message = f"¡Ups! 🌐 El proveedor del modelo (OpenRouter) está experimentando problemas técnicos temporales: '{error_msg}'. Por favor, intenta de nuevo en unos momentos."
            elif "RateLimitError" in error_type or "429" in error_msg:
                friendly_message = "¡Vaya! 🚦 Hemos alcanzado el límite de velocidad del modelo. Esperemos un momento antes de intentarlo de nuevo."
            elif "APIConnectionError" in error_type:
                friendly_message = "¡Vaya! 🔌 Parece que hay un problema de conexión con el servidor del modelo. Revisa tu conexión a internet."
            else:
                friendly_message = f"¡Ups! 😵 Ocurrió un error inesperado al comunicarme con el modelo ({error_type}): {e}. Por favor, intenta de nuevo."

            # Loguear el error completo para depuración interna, pero no ensuciar la terminal del usuario
            logger.error(f"Error detallado en LLMService.invoke: {error_msg}")
            
            # Logging adicional para errores de OpenRouter
            if "OpenrouterException" in error_msg or "20015" in error_msg:
                logger.error(f"Configuración del modelo: {self.model_name}")
                logger.error(f"API Key presente: {'Sí' if self.api_key else 'No'}")
                logger.error(f"Headers configurados: {litellm.headers}")
            
            if not any(x in error_msg for x in ["Upstream error", "RateLimitError"]):
                 logger.debug(traceback.format_exc())
            
            yield AIMessage(content=friendly_message)

    def summarize_conversation_history(self, messages_to_summarize: Optional[List[BaseMessage]] = None, force_truncate: bool = False) -> str:
        """
        Resume el historial de conversación actual utilizando el modelo LLM a través de LiteLLM.
        
        Args:
            messages_to_summarize: Lista opcional de mensajes a resumir. Si es None, usa el historial actual.
            force_truncate: Si es True, recorta agresivamente el historial para que quepa en los límites de tokens del modelo.
        """
        history_source = messages_to_summarize if messages_to_summarize is not None else self.conversation_history
        if not history_source:
            return ""
        
        # 1. Separar resúmenes anteriores de los mensajes recientes a resumir
        previous_summaries = []
        recent_messages_text = []
        
        for msg in history_source:
            content = msg.content or ""
            # Si es un SystemMessage con algún resumen anterior, lo extraemos para consolidación
            if isinstance(msg, SystemMessage) and ("Resumen de la conversación" in content or "Resumen forzado" in content):
                # Extraer el contenido limpio del resumen
                clean_content = content
                if content.startswith("Resumen de la conversación anterior:"):
                    clean_content = content[len("Resumen de la conversación anterior:"):].strip()
                elif content.startswith("Resumen forzado de la conversación:"):
                    clean_content = content[len("Resumen forzado de la conversación:"):].strip()
                previous_summaries.append(clean_content)
                continue
                
            role = "Sistema" if isinstance(msg, SystemMessage) else "Usuario" if isinstance(msg, HumanMessage) else "Asistente" if isinstance(msg, AIMessage) else "Herramienta"
            
            # Truncar localmente el contenido de mensajes individuales extremadamente largos (ej. outputs gigantes de herramientas)
            # para evitar que desplacen a otros mensajes del historial de resumen.
            max_msg_content_len = 5000
            if len(content) > max_msg_content_len:
                content = content[:2500] + f"\n\n... [Contenido largo de {len(content)} caracteres truncado para el proceso de resumen] ...\n\n" + content[-2500:]
            
            # Si es un mensaje de asistente con llamadas a herramientas, incluirlas en el texto
            if isinstance(msg, AIMessage) and msg.tool_calls:
                tool_info = []
                for tc in msg.tool_calls:
                    try:
                        args_str = json.dumps(tc.get('args', {}), ensure_ascii=False)
                    except Exception:
                        args_str = str(tc.get('args', {}))
                    tool_info.append(f"[Llamada a herramienta: {tc.get('name', '')}({args_str})]")
                content = f"{content}\n" + "\n".join(tool_info)
            
            # Si es una respuesta de herramienta, indicar qué herramienta fue
            if isinstance(msg, ToolMessage):
                role = f"Respuesta de Herramienta ({msg.tool_call_id})"
            
            recent_messages_text.append(f"### {role}:\n{content}")

        flat_history = "\n\n".join(recent_messages_text)
        
        # Prevenir errores de contexto excedido en el modelo de resumen.
        # Aumentamos a 100,000 chars ya que los modelos modernos tienen contextos grandes y
        # así evitamos perder mensajes intermedios en conversaciones largas.
        max_history_chars = 100000
        if len(flat_history) > max_history_chars:
            flat_history = "... [Mensajes intermedios antiguos truncados para resumen] ...\n\n" + flat_history[-max_history_chars:]

        merged_previous_summary = "\n\n---\n\n".join(previous_summaries) if previous_summaries else ""

        # 2. Crear un único mensaje de usuario con todo el historial y las instrucciones
        if merged_previous_summary:
            summarize_prompt = f"""Genera un nuevo resumen consolidado, EXTENSO y DETALLADO de toda la conversación anterior, integrando el resumen del pasado lejano con los nuevos eventos recientes.
            
RESUMEN DE LA CONVERSACIÓN ANTERIOR (PASADO LEJANO):
{merged_previous_summary}

NUEVOS EVENTOS RECIENTES A INCORPORAR:
{flat_history}

INSTRUCCIONES PARA EL NUEVO RESUMEN CONSOLIDADO:
- **Mantener y expandir:** Integra la información del 'RESUMEN DE LA CONVERSACIÓN ANTERIOR' con los 'NUEVOS EVENTOS RECIENTES'. NO pierdas datos clave del pasado lejano (objetivos iniciales, decisiones tomadas, estado del proyecto, etc.).
- **Estado actual:** ¿En qué punto nos encontramos ahora al final de estos nuevos eventos?
- **Decisiones consolidadas:** Lista todas las decisiones importantes tomadas desde el inicio de la conversación hasta ahora.
- **Tareas pendientes:** ¿Qué acciones están en progreso o planeadas para el futuro?
- **Errores y soluciones:** Problemas relevantes encontrados y cómo se resolvieron.
- **Contexto esencial:** Datos críticos de todo el transcurso de la sesión que el asistente necesita para continuar.

IMPORTANTE: El resumen resultante debe ser sumamente completo y autónomo. Un nuevo asistente debe poder leer este único resumen y continuar trabajando perfectamente como si hubiera estado presente desde el inicio de la sesión.
Limita el resumen consolidado a 5000 caracteres. Sé exhaustivo en los puntos clave pero conciso en los detalles menores."""
        else:
            summarize_prompt = f"""Genera un resumen EXTENSO y DETALLADO de la conversación anterior que permita retomar el hilo sin perder contexto.
            
CONTEXTO DE LA CONVERSACIÓN:
{flat_history}

INSTRUCCIONES PARA EL RESUMEN:
- **Estado actual de la conversación:** ¿En qué punto estábamos? ¿Qué tarea o tema se estaba discutiendo?
- **Decisiones tomadas:** ¿Qué decisiones se han tomado hasta ahora?
- **Tareas pendientes:** ¿Qué acciones estaban en progreso o planeadas?
- **Errores y problemas:** Cualquier error de herramienta, fallo o problema encontrado, y las acciones tomadas para resolverlos.
- **Contexto esencial:** Información crítica que el asistente necesita recordar para continuar coherentemente.
- **Hilo de la conversación:** El flujo lógico de la discusión para no perder la continuidad.

IMPORTANTE: El resumen debe ser lo suficientemente detallado para que un asistente pueda retomar la conversación exactamente donde se dejó, sin hacer preguntas innecesarias sobre el pasado reciente.
Limita el resumen a 5000 caracteres. Sé exhaustivo en los puntos clave pero conciso en los detalles menores."""

        litellm_messages_for_summary = [{"role": "user", "content": summarize_prompt}]
        
        litellm_generation_params = self.generation_params

        litellm_generation_params = self.generation_params

        summary_completion_kwargs = {
            "model": self.summary_model,
            "messages": litellm_messages_for_summary,
            "api_key": self.api_key, # Pasar la API Key directamente
            "temperature": litellm_generation_params.get("temperature", 0.7),
            "stream": False,
            # Añadir reintentos para errores 503 y otros errores de servidor
            "num_retries": 3,
        }
        self._apply_reasoning_effort_param(summary_completion_kwargs, self.summary_model)
        if "top_p" in litellm_generation_params:
            summary_completion_kwargs["top_p"] = litellm_generation_params["top_p"]
        if "top_k" in litellm_generation_params:
            summary_completion_kwargs["top_k"] = litellm_generation_params["top_k"]

        # Pasar api_base y headers explícitamente si están definidos para que el resumen use el mismo canal que el principal
        if hasattr(self, 'api_base') and self.api_base:
            summary_completion_kwargs["api_base"] = self.api_base
        if hasattr(self, 'headers') and self.headers:
            summary_completion_kwargs["headers"] = self.headers

        # Configuración específica para OpenRouter/SiliconFlow con campos adicionales
        if "openrouter" in self.summary_model.lower():
            # Asegurar formato correcto del modelo
            if not summary_completion_kwargs["model"].startswith("openrouter/"):
                summary_completion_kwargs["model"] = f"openrouter/{self.summary_model}"

            # Habilitar Reasoning por defecto para OpenRouter
            if "extra_body" not in summary_completion_kwargs:
                summary_completion_kwargs["extra_body"] = {}
            summary_completion_kwargs["extra_body"]["reasoning"] = { "type": "enabled" }
            # También añadir el parámetro directo si LiteLLM lo soporta
            summary_completion_kwargs["include_reasoning"] = True

            # Para modelos específicos como Nex-AGI, usar configuración más simple
            if "nex-agi" in self.summary_model.lower() or "deepseek" in self.summary_model.lower():
                # Configuración minimalista para Nex-AGI/DeepSeek
                summary_completion_kwargs["user"] = f"user_{self._generate_short_id(12)}"
                # NO enviar campos adicionales que puedan causar problemas
                logger.debug(f"Configuración minimalista para Nex-AGI/DeepSeek (resumen): {summary_completion_kwargs['model']}")
            else:
                # Configuración estándar para otros modelos
                summary_completion_kwargs["user"] = f"user_{self._generate_short_id(12)}"
                summary_completion_kwargs["metadata"] = {
                    "user_id": summary_completion_kwargs["user"],
                    "application_name": "KogniTerm"
                }

            # Logging para debug
            logger.debug(f"OpenRouter configuration (resumen): model={summary_completion_kwargs['model']}, user={summary_completion_kwargs.get('user', 'N/A')}")

        try:
            # Usar MultiProviderManager si está disponible para aprovechar fallbacks y prefijos correctos
            if self.provider_manager:
                # Extraer parámetros para pasarlos por separado a execute
                model = summary_completion_kwargs.pop("model")
                messages = summary_completion_kwargs.pop("messages")
                temp = summary_completion_kwargs.pop("temperature", 0.7)
                # Pop top_p, top_k y stream de kwargs para evitar "multiple values"
                top_p = summary_completion_kwargs.pop("top_p", None)
                top_k = summary_completion_kwargs.pop("top_k", None)
                summary_completion_kwargs.pop("stream", None)  # ya se pasa explícitamente

                response_gen = self.provider_manager.execute(
                    model_name=model,
                    messages=messages,
                    stream=False,
                    temperature=temp,
                    top_p=top_p,
                    top_k=top_k,
                    **summary_completion_kwargs
                )
                response = next(response_gen)
            else:
                response = completion(
                    **summary_completion_kwargs
                )
            self.call_timestamps.append(time.time()) # Registrar llamada de resumen
            
            # Asegurarse de que la respuesta no sea un generador inesperado y tenga el atributo 'choices'
            try:
                choices = getattr(response, 'choices', None)
                if choices is not None:
                    # Convertir a lista si es iterable
                    if hasattr(choices, '__iter__'):
                        try:
                            choices_list = list(choices)
                            if choices_list and len(choices_list) > 0:
                                first_choice = choices_list[0]
                                message = getattr(first_choice, 'message', None)
                                if message is not None:
                                    content = getattr(message, 'content', None)
                                    if content is not None:
                                        return str(content)
                        except (TypeError, AttributeError, IndexError):
                            pass
                    else:
                        # Si no es iterable, intentar acceso directo
                        if hasattr(choices, '__getitem__') and len(choices) > 0:
                            first_choice = choices[0]
                            message = getattr(first_choice, 'message', None)
                            if message is not None:
                                content = getattr(message, 'content', None)
                                if content is not None:
                                    return str(content)
            except Exception:
                pass
            return "Error: No se pudo generar el resumen de la conversación."
        except Exception as e:
            # No usar traceback.print_exc para no ensuciar la terminal si falla la resumirización
            logger.error(f"Error de LiteLLM al resumir el historial: {e}")
            # En lugar de devolver un mensaje de error que se guardará en el historial,
            # devolvemos una cadena vacía para que el sistema sepa que no hubo resumen.
            return ""

    def force_summarize_history(self) -> str:
        """
        Fuerza un resumen del historial actual para mejorar la gestión de contexto.
        Útil cuando el agente parece perder el hilo de la conversación.
        
        Returns:
            Mensaje confirmando el resumen realizado
        """
        try:
            # Obtener el historial actual
            current_history = self.conversation_history
            if len(current_history) <= 10:
                return "El historial es demasiado corto para resumir (menos de 10 mensajes)."
            
            # Generar resumen
            summary = self.summarize_conversation_history(current_history)
            if not summary:
                return "No se pudo generar el resumen del historial."
            
            # Crear nuevo historial con resumen
            summary_message = SystemMessage(content=f"Resumen forzado de la conversación: {summary}")
            new_history = [summary_message] + current_history[-20:]  # Mantener los últimos 20 mensajes
            
            # Actualizar historial
            self.conversation_history = new_history
            self._save_history(self.conversation_history)
            
            return f"Historial resumido exitosamente. Se conservaron los últimos {len(new_history)-1} mensajes con un resumen del contexto anterior."
            
        except Exception as e:
            logger.error(f"Error al forzar resumen del historial: {e}")
            return f"Error al resumir el historial: {str(e)}"

    def get_tool(self, tool_name: str) -> Optional[Any]:
        """Encuentra y devuelve una herramienta por su nombre (soporta BaseTool y Callables)."""
        return self.skill_manager.get_tool(tool_name)

    def close(self):
        """Libera recursos y cierra conexiones de servicios internos."""
        try:
            if hasattr(self, 'heartbeat_monitor') and self.heartbeat_monitor:
                self.heartbeat_monitor.stop()
                logger.info("LLMService: HeartbeatMonitor detenido.")

            if hasattr(self, 'vector_db_manager') and self.vector_db_manager:
                self.vector_db_manager.close()
                logger.info("LLMService: VectorDBManager cerrado.")
            
            if hasattr(self, 'tool_executor') and self.tool_executor:
                self.tool_executor.shutdown(wait=False)
                logger.info("LLMService: Executor de herramientas detenido.")
            
            if hasattr(self, 'provider_manager') and self.provider_manager:
                self.provider_manager.close()
                logger.info("LLMService: ProviderManager cerrado.")
            
            if hasattr(self, 'history_manager') and self.history_manager:
                self.history_manager.stop_auto_save()
                logger.info("LLMService: Autoguardado de historial detenido.")
        except Exception as e:
            logger.error(f"Error al cerrar LLMService: {e}")
    
    def get_provider_metrics(self) -> Dict[str, Any]:
        """Obtiene métricas de los proveedores si está usando MultiProviderManager."""
        if self.use_multi_provider and self.provider_manager:
            return self.provider_manager.get_metrics_report()
        return {"error": "MultiProviderManager no está habilitado"}
    
    def print_provider_metrics(self):
        """Imprime métricas de proveedores formateadas."""
        if self.use_multi_provider and self.provider_manager:
            self.provider_manager.print_metrics_report()
        else:
            print("MultiProviderManager no está habilitado")

    def _invoke_tool_with_interrupt(self, tool: BaseTool, tool_args: dict, delegation_context: Optional[Any] = None, terminal_ui: Optional[Any] = None) -> Generator[Any, None, None]:
        """Invoca una herramienta en un hilo separado, permitiendo la interrupción."""
        def _tool_target():
            try:
                # Soporte para diferentes tipos de ejecución de herramientas
                if hasattr(tool, '_run'):
                    # Herramientas BaseTool de LangChain
                    import inspect
                    sig = inspect.signature(tool._run)
                    if 'delegation_context' in sig.parameters:
                        result = tool._run(**tool_args, delegation_context=delegation_context)
                    else:
                        result = tool._run(**tool_args)
                elif hasattr(tool, 'run'):
                    # Objetos con método run
                    import inspect
                    sig = inspect.signature(tool.run)
                    if 'delegation_context' in sig.parameters:
                        result = tool.run(**tool_args, delegation_context=delegation_context)
                    else:
                        result = tool.run(**tool_args)
                elif callable(tool):
                    # Funciones directas (común en el sistema de skills)
                    import inspect
                    sig = inspect.signature(tool)
                    injected_args = tool_args.copy()
                    
                    if 'llm_service' in sig.parameters:
                        injected_args['llm_service'] = self
                    if 'terminal_ui' in sig.parameters:
                        injected_args['terminal_ui'] = terminal_ui or getattr(self, 'terminal_ui', None)
                    if 'interrupt_queue' in sig.parameters:
                        injected_args['interrupt_queue'] = getattr(self, 'interrupt_queue', None)
                    if 'approval_handler' in sig.parameters and hasattr(self, 'skill_manager') and hasattr(self.skill_manager, 'approval_handler'):
                        injected_args['approval_handler'] = self.skill_manager.approval_handler
                    if 'delegation_context' in sig.parameters:
                        injected_args['delegation_context'] = delegation_context
                        
                    result = tool(**injected_args)
                else:
                    raise Exception(f"La herramienta '{getattr(tool, 'name', tool.__class__.__name__)}' no es ejecutable.")

                if isinstance(result, dict) and result.get("status") == "requires_confirmation":
                    # Intentar obtener el nombre más descriptivo posible
                    inferred_tool_name = (
                        result.get("operation") or 
                        getattr(tool, 'name', None) or 
                        getattr(tool, '__name__', None) or 
                        tool.__class__.__name__
                    )

                    raise UserConfirmationRequired(
                        message=result.get("action_description", "Confirmación requerida"),
                        tool_name=inferred_tool_name,
                        tool_args=result.get("args", tool_args),
                        raw_tool_output=result
                    )
                return result
            except UserConfirmationRequired as e:
                raise e
            except Exception as e:
                raise e

        future = self.tool_executor.submit(_tool_target)
        if not hasattr(self, 'active_tool_futures'):
            self.active_tool_futures = []
        self.active_tool_futures.append(future)

        try:
            while not future.done():
                if self.interrupt_queue and not self.interrupt_queue.empty():
                    raise InterruptedError("Interrupción detectada")
                try:
                    result = future.result(timeout=self.tool_poll_timeout)
                    
                    # Robust check for generators
                    import inspect
                    if inspect.isgenerator(result):
                        yield from result
                    else:
                        yield result
                    return
                except TimeoutError:
                    continue
        finally:
            if future in self.active_tool_futures:
                self.active_tool_futures.remove(future)
            with self.tool_execution_lock:
                if getattr(self, 'active_tool_future', None) is future:
                    self.active_tool_future = None
