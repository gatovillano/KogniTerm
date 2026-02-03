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

from .multi_provider_manager import get_provider_manager, MultiProviderManager

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

    # Limpiar el esquema de títulos y otros metadatos de Pydantic que a veces molestan a LiteLLM/OpenRouter
    def clean_schema(s):
        if not isinstance(s, dict):
            return s
        s.pop("title", None)
        s.pop("additionalProperties", None)
        s.pop("definitions", None)
        s.pop("$defs", None)
        if "properties" in s:
            for prop_name, prop_val in s["properties"].items():
                if isinstance(prop_val, dict):
                    clean_schema(prop_val)
                    # Algunos proveedores fallan con 'default' si no coincide exactamente con el tipo
                    prop_val.pop("default", None)
        return s

    cleaned_schema = clean_schema(args_schema)

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

# Lógica de fallback para credenciales
openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
litellm_model = os.getenv("LITELLM_MODEL")
litellm_api_base = os.getenv("LITELLM_API_BASE")

google_api_key = os.getenv("GOOGLE_API_KEY")
gemini_model = os.getenv("GEMINI_MODEL")

# Configuración global de LiteLLM para máxima compatibilidad
litellm.drop_params = True 
litellm.modify_params = False 
litellm.telemetry = False
# Silencio total para producción
os.environ['LITELLM_LOG'] = 'ERROR' 
litellm.set_verbose = False
litellm.suppress_debug_info = True # Nueva bandera para evitar mensajes de ayuda
litellm.add_fastapi_middleware = False # Evitar ruidos innecesarios

if openrouter_api_key and litellm_model:
    # Usar OpenRouter
    # Si el modelo no tiene el prefijo openrouter/, añadirlo
    if not litellm_model.startswith("openrouter/"):
        model_name = f"openrouter/{litellm_model}"
    else:
        model_name = litellm_model

    # Actualizar el environment
    os.environ["LITELLM_MODEL"] = model_name
    os.environ["OPENROUTER_API_KEY"] = openrouter_api_key

    # Cabeceras básicas para OpenRouter
    litellm.headers = {
        "HTTP-Referer": "https://github.com/gatovillano/KogniTerm",
        "X-Title": "KogniTerm"
    }

    # Configuración específica para OpenRouter
    litellm.api_base = litellm_api_base if litellm_api_base else "https://openrouter.ai/api/v1"

    print(f"🤖 Configuración activa: OpenRouter ({model_name})")
elif google_api_key and gemini_model:
    # Usar Google AI Studio
    os.environ["LITELLM_MODEL"] = f"gemini/{gemini_model}" # Asegurarse de que sea gemini/gemini-1.5-flash
    os.environ["LITELLM_API_KEY"] = google_api_key
    litellm.api_base = None # Asegurarse de que no haya un api_base de Vertex AI
    print(f"🤖 Configuración activa: Google AI Studio ({gemini_model})")
else:
    print("⚠️  ADVERTENCIA: No se encontraron credenciales válidas para OpenRouter ni Google AI Studio. Asegúrate de configurar OPENROUTER_API_KEY/LITELLM_MODEL o GOOGLE_API_KEY/GEMINI_MODEL en tu archivo .env", file=sys.stderr)

from .exceptions import UserConfirmationRequired # Importar la excepción
import tiktoken # Importar tiktoken
from .context.workspace_context import WorkspaceContext # Importar WorkspaceContext
from .history_manager import HistoryManager





class LLMService:
    def __init__(self, interrupt_queue: Optional[queue.Queue] = None, use_multi_provider: bool = True):
        # print("DEBUG: Iniciando LLMService.__init__...")
        # print("DEBUG: Iniciando LLMService.__init__...")
        from .tools.tool_manager import ToolManager
        
        # Inicializar MultiProviderManager
        self.use_multi_provider = use_multi_provider
        if use_multi_provider:
            self.provider_manager = get_provider_manager()
            # Realizar health check inicial
            self.provider_manager.health_check()
        else:
            self.provider_manager = None
        
        self.model_name = os.environ.get("LITELLM_MODEL", "google/gemini-1.5-flash")
        # Validación de seguridad: si el modelo parece una API Key de Google, corregirlo
        if self.model_name.startswith("AIza"):
            logger.warning(f"Se detectó una API Key en LITELLM_MODEL ('{self.model_name[:8]}...'). Corrigiendo a 'google/gemini-1.5-flash'.")
            self.model_name = "google/gemini-1.5-flash"
            
        self.api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("LITELLM_API_KEY")
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

        # print("DEBUG: Inicializando ToolManager...")
        self.tool_manager = ToolManager(
            llm_service=self, 
            embeddings_service=self.embeddings_service, 
            vector_db_manager=self.vector_db_manager
        )
        # print("DEBUG: Cargando herramientas...")
        self.tool_manager.load_tools()
        # print("DEBUG: Generando esquemas de herramientas...")
        self.tool_names = [tool.name for tool in self.tool_manager.get_tools()]
        self.tool_schemas = []
        for tool in self.tool_manager.get_tools():
            schema = {}
            if hasattr(tool, 'args_schema') and tool.args_schema is not None:
                if hasattr(tool.args_schema, 'schema'):
                    schema = tool.args_schema.schema()
                elif hasattr(tool.args_schema, 'model_json_schema'):
                    schema = tool.args_schema.model_json_schema()
            self.tool_schemas.append(schema)
        self.tool_map = {tool.name: tool for tool in self.tool_manager.get_tools()}
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
        self.max_history_messages = 20 # Valor por defecto, ajustar según necesidad
        self.max_history_chars = 15000 # Valor por defecto, ajustar según necesidad
        # print("DEBUG: Inicializando WorkspaceContext...")
        self.workspace_context = WorkspaceContext(root_dir=os.getcwd())
        self.workspace_context_initialized = False
        self.call_timestamps = deque() # Inicializar call_timestamps
        self.rate_limit_period = 60 # Por ejemplo, 60 segundos
        self.rate_limit_calls = 5 # Ajustado a 5 llamadas por minuto para evitar RateLimit
        self.generation_params = {"temperature": 0.7, "top_p": 0.95, "top_k": 40} # Parámetros de generación por defecto
        self.tool_execution_lock = threading.Lock() # Inicializar el lock
        self.active_tool_future = None # Referencia a la última tarea iniciada
        self.tool_executor = ThreadPoolExecutor(max_workers=10) # Aumentado para permitir paralelismo y llamadas anidadas
        # Inicializar HistoryManager para gestión optimizada del historial
        self.history_manager = HistoryManager(
            history_file_path=self.history_file_path,
            max_history_messages=self.max_history_messages,
            max_history_chars=self.max_history_chars
        )
        self.SUMMARY_MAX_TOKENS = 1500 # Tokens, longitud máxima del resumen de herramientas

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

    def _parse_tool_calls_from_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Parsea llamadas a herramientas desde texto plano para compatibilidad con modelos que no usan tool_calls nativos.
        Implementa un modo de parseo amplio y permisivo que detecta múltiples formatos de tool calls.
        
        Patrones soportados:
        - tool_call: nombre({args})
        - Llamar/ejecutar/usar herramienta nombre con args
        - Function calls: nombre({args})
        - Tool invocation: [TOOL_CALL] nombre args
        - JSON estructurado: {"tool_call": {...}}
        - YAML-like: nombre: {args}
        - XML-like: <tool_call name="nombre"><args>...</args> </tool_call>
        - Natural language: I need to call/using tool nombre with args
        - Code-like: nombre({args})
        - Model-specific formats for OpenAI, Anthropic, etc.
        """
        tool_calls = []
        import re
        
        # Normalizar texto: reemplazar múltiples espacios y normalizar caracteres
        normalized_text = re.sub(r'\s+', ' ', text.strip())
        
        # Función auxiliar para extraer argumentos de manera permisiva
        def extract_args(args_str):
            if not args_str:
                return {}
            
            # Intentar JSON primero
            try:
                return json.loads(args_str)
            except (json.JSONDecodeError, ValueError):
                pass
            
            # Intentar argumentos key=value
            kv_pattern = r'(\w+)\s*[:=]\s*([\w"\'\[\{].*?)(?:[,}]|$)'
            kv_matches = re.findall(kv_pattern, args_str)
            if kv_matches:
                result = {}
                for key, value in kv_matches:
                    try:
                        # Intentar convertir a número
                        if value.isdigit():
                            result[key] = int(value)
                        elif value.replace('.', '').isdigit():
                            result[key] = float(value)
                        elif value.lower() in ['true', 'false']:
                            result[key] = value.lower() == 'true'
                        elif value.startswith('[') and value.endswith(']'):
                            # Lista simple
                            result[key] = [v.strip().strip('"\'\'') for v in value[1:-1].split(',')]
                        else:
                            # Cadena
                            result[key] = value.strip('"\'\'')
                    except:
                        result[key] = value.strip('"\'\'')
                return result
            
            # Fallback: argumentos vacíos
            return {}
        
        # PATRÓN 1: tool_call: nombre({args})
        pattern1 = r'tool_call\s*:\s*(\w+)\s*\(\s*([^)]*?)\s*\)'
        matches1 = re.findall(pattern1, normalized_text, re.IGNORECASE | re.DOTALL)
        for name, args_str in matches1:
            if name not in self.tool_map:
                continue
            args = extract_args(args_str)
            tool_calls.append({
                "id": self._generate_short_id(),
                "name": name,
                "args": args
            })

        # PATRÓN 2: llamar/ejecutar/usar herramienta nombre con args
        pattern2 = r'(?:llamar|ejecutar|usar|invoke|call)\s+(?:a\s+)?(?:la\s+)?(?:herramienta|tool)\s+(\w+)\s*(?:con\s+args?|con\s+argumentos?)?\s*[:\-]?\s*(\{[^}]*\}|\([^)]*\)|.*?)$'
        matches2 = re.findall(pattern2, normalized_text, re.IGNORECASE | re.DOTALL)
        for name, args_str in matches2:
            if name not in self.tool_map:
                continue
            # Limpiar la cadena de argumentos
            args_str = args_str.strip().strip('{}()')
            args = extract_args(args_str)
            tool_calls.append({
                "id": self._generate_short_id(),
                "name": name,
                "args": args
            })

        # PATRÓN 3: Function calls estilo código - nombre({args})
        pattern3 = r'\b(\w+)\s*\(\s*([^)]*?)\s*\)'
        matches3 = re.findall(pattern3, normalized_text)
        for name, args_str in matches3:
            # Filtrar funciones comunes que no son herramientas
            if name.lower() in ['print', 'len', 'str', 'int', 'float', 'bool', 'list', 'dict', 'set', 'tuple', 'range', 'type', 'isinstance', 'hasattr', 'getattr', 'open', 'input', 'print', 'exec', 'eval']:
                continue
            
            # CRÍTICO: Solo agregar si el nombre es una herramienta registrada
            if name not in self.tool_map:
                continue
            
            args = extract_args(args_str)
            if args or args_str.strip():  # Solo agregar si hay argumentos o si es una llamada clara
                tool_calls.append({
                    "id": self._generate_short_id(),
                    "name": name,
                    "args": args
                })

        # PATRÓN 3.1: Python function calls con parámetros específicos (ej: call_agent)
        # Buscar patrones como call_agent(agent_name="researcher_agent", task="...")
        # Usar un enfoque que maneja correctamente los paréntesis anidados
        python_func_patterns = [
            r'\b(call_agent|invoke_agent|execute_agent|run_agent)\s*\(',
            r'\b(llamar_agent|ejecutar_funcion|usar_funcion)\s*\('
        ]
        
        for pattern in python_func_patterns:
            matches = re.findall(pattern, normalized_text, re.IGNORECASE)
            for func_name in matches:
                # Encontrar la posición del match
                start_pos = normalized_text.lower().find(func_name.lower())
                if start_pos == -1:
                    continue
                    
                # Buscar el paréntesis de apertura
                paren_start = normalized_text.find('(', start_pos)
                if paren_start == -1:
                    continue
                    
                # Extraer el contenido entre paréntesis balanceados
                args_str = self._extract_balanced_content(normalized_text, paren_start)
                # Extraer argumentos específicos de funciones de agentes
                agent_args = {}
                
                # Buscar agent_name o agent
                agent_match = re.search(r'(?:agent_name|agent)\s*=\s*["\']([^"\']+)["\']', args_str)
                if agent_match:
                    agent_args['agent_name'] = agent_match.group(1)
                
                # Buscar task (el parámetro correcto del call_agent tool) - enfoque más simple y robusto
                # Buscar desde task= hasta el final del string o hasta el siguiente parámetro
                task_pattern = r'(?:task)\s*=\s*["\'](.*?)(?:["\']\s*(?:,|\)|$))'
                task_match = re.search(task_pattern, args_str, re.DOTALL)
                if not task_match:
                    # Fallback: también buscar task_description para compatibilidad
                    task_pattern = r'(?:task_description)\s*=\s*["\'](.*?)(?:["\']\s*(?:,|\)|$))'
                    task_match = re.search(task_pattern, args_str, re.DOTALL)
                if task_match:
                    agent_args['task'] = task_match.group(1)  # Usar 'task' no 'task_description'
                
                # Buscar context o parameters
                context_match = re.search(r'(?:context|parameters)\s*=\s*(\{[^}]*\})', args_str)
                if context_match:
                    try:
                        agent_args['context'] = json.loads(context_match.group(1))
                    except:
                        agent_args['context'] = context_match.group(1)
                
                # Si no se encontraron argumentos específicos, usar el parser general
                if not agent_args:
                    agent_args = extract_args(args_str)
                
                tool_calls.append({
                    "id": self._generate_short_id(),
                    "name": func_name,
                    "args": agent_args
                })

        # PATRÓN 4: [TOOL_CALL] formato
        pattern4 = r'\[TOOL_CALL\]\s*(\w+)\s*[:\-]?\s*(\{[^}]*\}|\([^)]*\)|[^\n]+)'
        matches4 = re.findall(pattern4, normalized_text, re.IGNORECASE)
        for name, args_str in matches4:
            args_str = args_str.strip().strip('{}()')
            args = extract_args(args_str)
            tool_calls.append({
                "id": self._generate_short_id(),
                "name": name,
                "args": args
            })

        # PATRÓN 5: JSON estructurado expandido
        # Buscar cualquier objeto JSON que contenga información de herramientas
        json_patterns = [
            r'\{[^}]*"(?:tool_call|function_call|action|operation)"\s*:\s*\{[^}]*"(?:name|tool|function)"\s*:\s*["\']([^"\']+)["\'][^}]*"(?:args|arguments|parameters)"\s*:\s*(\{[^}]*\})[^}]*\}',
            r'\{[^}]*"(?:name|tool|function)"\s*:\s*["\']([^"\']+)["\'][^}]*"(?:args|arguments|parameters)"\s*:\s*(\{[^}]*\})[^}]*\}',
            r'\{[^}]*"(\w+)"\s*:\s*(\{[^}]*\})[^}]*"(?:tool|function|operation)"\s*:\s*true[^}]*\}',
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, normalized_text, re.DOTALL)
            for name, args_str in matches:
                try:
                    args = json.loads(args_str)
                    tool_calls.append({
                        "id": self._generate_short_id(),
                        "name": name,
                        "args": args
                    })
                except (json.JSONDecodeError, ValueError):
                    args = extract_args(args_str)
                    tool_calls.append({
                        "id": self._generate_short_id(),
                        "name": name,
                        "args": args
                    })

        # PATRÓN 6: YAML-like formato
        pattern6 = r'^(\w+)\s*:\s*(\{[^}]*\}|\([^)]*\)|[^\n]+)$'
        matches6 = re.findall(pattern6, normalized_text, re.MULTILINE)
        for name, args_str in matches6:
            args_str = args_str.strip().strip('{}()')
            args = extract_args(args_str)
            tool_calls.append({
                "id": self._generate_short_id(),
                "name": name,
                "args": args
            })

        # PATRÓN 7: XML-like formato
        pattern7 = r'<(?:tool_call|function|action)\s+(?:name|id)\s*=\s*["\']([^"\']+)["\'][^>]*>(?:<args[^>]*>)?([^<]*?)(?:</args>)?</(?:tool_call|function|action)>'
        matches7 = re.findall(pattern7, normalized_text, re.IGNORECASE | re.DOTALL)
        for name, args_str in matches7:
            args = extract_args(args_str)
            tool_calls.append({
                "id": self._generate_short_id(),
                "name": name,
                "args": args
            })

        # PATRÓN 8: Lenguaje natural expandido
        natural_patterns = [
            r'(?:i\s+need\s+to|i\s+want\s+to|i\s+should|i\s+must)\s+(?:call|use|execute|invoke|run)\s+(?:the\s+)?(?:tool|function|action)\s+(\w+)\s*(?:with\s+args?|with\s+arguments?|with\s+parameters?)?\s*[:\-]?\s*(\{[^}]*\}|\([^)]*\)|[^\.]+)',
            r'(?:let\s+me\s+|please\s+)?(?:call|use|execute|invoke|run)\s+(?:the\s+)?(?:tool|function|action)\s+(\w+)\s*(?:with\s+args?|with\s+arguments?)?\s*[:\-]?\s*(\{[^}]*\}|\([^)]*\)|[^\.]+)',
            r'(?:we\s+need\s+to|we\s+should|we\s+can)\s+(?:call|use|execute|invoke|run)\s+(?:the\s+)?(?:tool|function|action)\s+(\w+)\s*(?:with\s+args?|with\s+arguments?)?\s*[:\-]?\s*(\{[^}]*\}|\([^)]*\)|[^\.]+)'
        ]
        
        for pattern in natural_patterns:
            matches = re.findall(pattern, normalized_text, re.IGNORECASE | re.DOTALL)
            for name, args_str in matches:
                args_str = args_str.strip().strip('{}()')
                args = extract_args(args_str)
                tool_calls.append({
                    "id": self._generate_short_id(),
                    "name": name,
                    "args": args
                })

        # PATRÓN 9: Formatos específicos de proveedores
        # OpenAI function calling format
        openai_pattern = r'"name"\s*:\s*["\']([^"\']+)["\'][^}]*"arguments"\s*:\s*(\{[^}]*\})'
        openai_matches = re.findall(openai_pattern, normalized_text)
        for name, args_str in openai_matches:
            try:
                args = json.loads(args_str)
                tool_calls.append({
                    "id": self._generate_short_id(),
                    "name": name,
                    "args": args
                })
            except (json.JSONDecodeError, ValueError):
                args = extract_args(args_str)
                tool_calls.append({
                    "id": self._generate_short_id(),
                    "name": name,
                    "args": args
                })

        # PATRÓN 10: Formato de lista/bloque
        list_pattern = r'^(?:\d+\.\s*|-\s*|\*\s*)?(\w+)\s*[:\-]\s*(\{[^}]*\}|\([^)]*\)|[^\n]+)$'
        list_matches = re.findall(list_pattern, normalized_text, re.MULTILINE)
        for name, args_str in list_matches:
            # Filtrar elementos que claramente no son herramientas
            if name.lower() in ['step', 'note', 'important', 'warning', 'error', 'info', 'debug']:
                continue
            
            args_str = args_str.strip().strip('{}()')
            args = extract_args(args_str)
            tool_calls.append({
                "id": self._generate_short_id(),
                "name": name,
                "args": args
            })

        # Filtrar y validar llamadas a herramientas
        valid_tool_calls = []
        seen_names = set()
        
        for tc in tool_calls:
            name = tc['name']
            
            # 1. Validar que el nombre de la herramienta exista en el tool_map
            if name not in self.tool_map:
                # Intentar búsqueda insensible a mayúsculas/minúsculas si no se encuentra exacto
                found_match = False
                for registered_name in self.tool_map.keys():
                    if name.lower() == registered_name.lower():
                        tc['name'] = registered_name
                        name = registered_name
                        found_match = True
                        break
                
                if not found_match:
                    logger.debug(f"Ignorando supuesta llamada a herramienta inexistente: {name}")
                    continue
            
            # 2. Evitar duplicados en la misma respuesta
            if name in seen_names:
                continue
                
            # 3. Validación de calidad mínima de argumentos
            # Si la herramienta requiere argumentos pero están vacíos, podría ser un falso positivo
            # a menos que sea una llamada muy explícita (ej: PATRÓN 1 o PATRÓN 4)
            tool_instance = self.tool_map[name]
            requires_args = False
            if hasattr(tool_instance, 'args_schema') and tool_instance.args_schema:
                # Verificar si tiene campos requeridos
                if hasattr(tool_instance.args_schema, 'model_fields'):
                    requires_args = any(f.is_required() for f in tool_instance.args_schema.model_fields.values())
            
            if requires_args and not tc.get('args'):
                # Si requiere argumentos y no los tiene, es sospechoso
                # Pero si el patrón era muy específico (como tool_call:), lo mantenemos
                # Aquí podríamos añadir lógica más compleja, por ahora solo logueamos
                logger.debug(f"Herramienta {name} detectada sin argumentos pero los requiere.")
            
            seen_names.add(name)
            valid_tool_calls.append(tc)
        
        return valid_tool_calls

    def _extract_balanced_content(self, text: str, start_pos: int) -> str:
        """
        Extrae contenido balanceado entre paréntesis desde una posición dada.
        Maneja paréntesis anidados correctamente.
        """
        if start_pos >= len(text) or text[start_pos] != '(':
            return ''
        
        depth = 0
        content = ''
        in_string = False
        string_char = None
        i = start_pos
        
        while i < len(text):
            char = text[i]
            
            # Manejar strings
            if char in ['"', "'"]:
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char and (i == 0 or text[i-1] != '\\'):
                    in_string = False
                    string_char = None
            
            # Solo contar paréntesis fuera de strings
            if not in_string:
                if char == '(':
                    depth += 1
                elif char == ')':
                    depth -= 1
                    if depth == 0:
                        # Paréntesis de cierre encontrado, terminar
                        break
            
            content += char
            i += 1
        
        # Remover el paréntesis de apertura y cierre
        if content.startswith('(') and content.endswith(')'):
            content = content[1:-1]
        
        return content.strip()

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
                for tc in tool_calls_data:
                    function_data = tc.get("function")
                    if function_data:
                        args = function_data.get("arguments", "")
                        # Asegurarse de que los argumentos se manejen como un diccionario
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except json.JSONDecodeError:
                                args = {} # Fallback si no es un JSON válido
                        tool_calls.append({
                            "id": tc.get("id", self._generate_short_id()),
                            "name": function_data.get("name", ""),
                            "args": args
                        })
                return AIMessage(content=content, tool_calls=tool_calls)
            else:
                return AIMessage(content=content)
        elif role == "tool":
            return ToolMessage(content=content, tool_call_id=message.get("tool_call_id"))
        elif role == "system":
            return SystemMessage(content=content)
        else:
            raise ValueError(f"Tipo de mensaje desconocido de LiteLLM para LangChain: {role}")

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
            return {"role": "user", "content": message.content}
        elif isinstance(message, AIMessage):
            tool_calls = getattr(message, 'tool_calls', [])
            content = message.content
            if isinstance(content, list):
                # Handle cases where content is a list of dicts (e.g. from a tool call)
                content = json.dumps(content)

            msg = {"role": "assistant", "content": content or "..."}
            
            # Preservar razonamiento para OpenRouter/LiteLLM
            reasoning = message.additional_kwargs.get("reasoning_content") or getattr(message, 'reasoning_content', None)
            if reasoning:
                msg["reasoning_content"] = reasoning

            if tool_calls:
                serialized_tool_calls = []
                for tc in tool_calls:
                    tc_id = get_compliant_id(tc.get("id"))
                    tc_name = tc.get("name", "")
                    tc_args = tc.get("args", {})
                    # Asegurarse de que los argumentos sean siempre una cadena JSON válida.
                    # LiteLLM espera un string para poder convertirlo correctamente entre proveedores (ej. OpenAI -> Gemini).
                    arguments_json = json.dumps(tc_args) if tc_args else "{}"
                    
                    serialized_tool_calls.append({
                        "id": tc_id,
                        "type": "function",
                        "function": {"name": tc_name, "arguments": arguments_json},
                    })
                
                if not content or not str(content).strip():
                    msg["content"] = "Ejecutando herramientas..."
                
                msg["tool_calls"] = serialized_tool_calls
            
            return msg
        elif isinstance(message, ToolMessage):
            content = message.content
            if isinstance(content, list):
                content = json.dumps(content)
            if not content or not str(content).strip():
                content = "Operación completada (sin salida)."
            
            tc_id = get_compliant_id(getattr(message, 'tool_call_id', ''))
            return {"role": "tool", "content": content, "tool_call_id": tc_id}
        elif isinstance(message, SystemMessage):
            return {"role": "system", "content": message.content}
        return {"role": "user", "content": str(message)}

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
        return self.tool_manager.get_tools()

    def register_tool(self, tool_instance: BaseTool):
        """Registra una herramienta dinámicamente y actualiza las estructuras internas."""
        self.tool_manager.register_tool(tool_instance)
        # Actualizar las estructuras internas de LLMService
        self.tool_map[tool_instance.name] = tool_instance
        self.tool_names.append(tool_instance.name)
        # Tools will be converted at runtime, so no need to update litellm_tools here

    def _get_litellm_tools(self) -> List[dict]:
        """Convierte las herramientas al formato LiteLLM apropiado para el modelo actual."""
        if self.litellm_tools is None:
            logger.info(f"🔧 Convirtiendo herramientas para modelo: {self.model_name}")
            converted_tools = []
            for tool in self.tool_manager.get_tools():
                converted = _convert_langchain_tool_to_litellm(tool, self.model_name)
                logger.info(f"✅ Herramienta convertida: {tool.name} -> {converted.get('type', 'standard')}")
                converted_tools.append(converted)
            self.litellm_tools = converted_tools
            logger.info(f"📋 Total herramientas convertidas: {len(converted_tools)}")
        return self.litellm_tools

    def set_model(self, model_name: str):
        """Cambia el modelo actual en tiempo de ejecución."""
        self.model_name = model_name
        os.environ["LITELLM_MODEL"] = model_name
        
        # Invalidar caché de herramientas para que se regeneren con el formato correcto para el nuevo modelo
        self.litellm_tools = None
        
        # Actualizar configuración de LiteLLM si es necesario (ej: OpenRouter)
        if model_name.startswith("openrouter/"):
            litellm_model = model_name
            # Asegurarse de que la API Key de OpenRouter esté configurada si cambiamos a un modelo OpenRouter
            if not os.environ.get("OPENROUTER_API_KEY"):
                logger.warning("Cambiando a modelo OpenRouter pero OPENROUTER_API_KEY no está definida.")
        elif model_name.startswith("gemini/"):
             # Asegurarse de que la API Key de Google esté configurada
            if not os.environ.get("GOOGLE_API_KEY"):
                 logger.warning("Cambiando a modelo Gemini pero GOOGLE_API_KEY no está definida.")

        logger.info(f"🔄 Modelo cambiado dinámicamente a: {model_name}")

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

    def invoke(self, history: Optional[List[BaseMessage]] = None, system_message: Optional[str] = None, interrupt_queue: Optional[queue.Queue] = None, save_history: bool = True) -> Generator[Union[AIMessage, str], None, None]:
        """
        Invoca al modelo LLM con el historial proporcionado.
        """
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
            "2. Si el usuario aprueba, responde con el ToolMessage original con `confirm: True`.\n"
            "3. Si deniega, explica por qué en un mensaje de texto.\n"
            "4. Prioriza seguridad e intención del usuario."
        )
        if not any(tool_confirmation_instruction in sc for sc in system_contents):
            system_contents.append(tool_confirmation_instruction)

        # Añadir el mensaje de contexto del espacio de trabajo si está inicializado
        workspace_context_message = self._build_llm_context_message()
        if workspace_context_message:
            system_contents.append(workspace_context_message.content)

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
        for i, msg in enumerate(raw_conv_messages):
            role = msg["role"]
            
            if role == "user":
                # Evitar duplicados consecutivos
                if msg["content"] != last_user_content:
                    litellm_messages.append(msg)
                    last_user_content = msg["content"]
            elif role == "assistant":
                if msg.get("tool_calls"):
                    # Si tiene tool_calls, verificar que existan las respuestas correspondientes en el historial
                    # Si es el ÚLTIMO mensaje, Mistral fallará si tiene tool_calls pendientes.
                    # En ese caso, si no hay respuestas, eliminamos los tool_calls para evitar el error 400.
                    has_responses = False
                    for j in range(i + 1, len(raw_conv_messages)):
                        next_msg = raw_conv_messages[j]
                        if next_msg["role"] == "tool":
                            has_responses = True
                            break
                        if next_msg["role"] in ["user", "assistant"]:
                            break
                    
                    if has_responses or i < len(raw_conv_messages) - 1:
                        # Mantener tool_calls si hay respuestas o no es el último (aunque lo ideal es que tenga respuestas)
                        for tc in msg["tool_calls"]:
                            known_tool_call_ids.add(tc["id"])
                        litellm_messages.append(msg)
                    else:
                        # Si es el último y no tiene respuestas, quitar tool_calls para evitar error 400
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
            "timeout": 120,    # Según el ejemplo del usuario
        }
        
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
            if "gpt" in self.model_name.lower() or "openai" in self.model_name.lower() or "gemini" in self.model_name.lower():
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
                response_generator = self.provider_manager.execute_with_fallback(
                    model_name=self.model_name,
                    messages=completion_kwargs["messages"],
                    stream=completion_kwargs.get("stream", True),
                    temperature=completion_kwargs.get("temperature", 0.7),
                    max_tokens=completion_kwargs.get("max_tokens", 8192),
                    tools=completion_kwargs.get("tools"),
                )
            else:
                # Fallback al comportamiento original
                response_generator = completion(
                    **completion_kwargs
                )
            logger.debug("DEBUG: litellm.completion llamada exitosa, procesando chunks...")
            end_time = time.perf_counter()
            self.call_timestamps.append(time.time())
            for chunk in response_generator:
                # Verificar la cola de interrupción
                if interrupt_queue and not interrupt_queue.empty():
                    while not interrupt_queue.empty(): # Vaciar la cola
                        interrupt_queue.get_nowait()
                    self.stop_generation_flag = True
                    print("DEBUG: Interrupción detectada desde la cola.", file=sys.stderr) # Para depuración
                    break # Salir del bucle de chunks

                if self.stop_generation_flag:
                    # print("DEBUG: Generación detenida por bandera.", file=sys.stderr)
                    break

                choices = getattr(chunk, 'choices', None)
                if not choices or not isinstance(choices, list) or not choices[0]:
                    continue
                
                choice = choices[0]
                delta = getattr(choice, 'delta', None)
                if not delta:
                    logger.debug("DEBUG: Delta vacío, continuando...")
                    continue
                
                # Log the raw delta for debugging
                logger.debug(f"DEBUG: LiteLLM Delta recibido: {delta}")

                # Capturar contenido de razonamiento (Thinking) si está disponible
                reasoning_delta = getattr(delta, 'reasoning_content', None)
                if reasoning_delta is not None:
                    full_reasoning_content += str(reasoning_delta)
                    yield f"__THINKING__:{reasoning_delta}"

                if getattr(delta, 'content', None) is not None:
                    full_response_content += str(delta.content)
                    yield str(delta.content)
                
                tool_calls_from_delta = getattr(delta, 'tool_calls', None)
                if tool_calls_from_delta is not None:
                    # Acumular tool_calls
                    for tc in tool_calls_from_delta:
                        # Asegurarse de que la lista tool_calls tenga el tamaño suficiente
                        while tc.index >= len(tool_calls):
                            tool_calls.append({"id": "", "function": {"name": "", "arguments": ""}})
                        
                        # Actualizar el ID si está presente en el chunk, si no generar uno nuevo si es el inicio
                        if getattr(tc, 'id', None) is not None:
                            tool_calls[tc.index]["id"] = tc.id
                        elif not tool_calls[tc.index]["id"]:
                            tool_calls[tc.index]["id"] = self._generate_short_id()
                        
                        # Actualizar el nombre de la función si está presente
                        if getattr(tc.function, 'name', None) is not None:
                            tool_calls[tc.index]["function"]["name"] = tc.function.name
                            # Acumular los argumentos
                            if getattr(tc.function, 'arguments', None) is not None:
                                tool_calls[tc.index]["function"]["arguments"] += tc.function.arguments


            if self.stop_generation_flag:
                # Si se interrumpe, el AIMessage final se construye con el mensaje de interrupción
                yield AIMessage(content="Generación de respuesta interrumpida por el usuario. 🛑")
            elif tool_calls:
                formatted_tool_calls = []
                for tc in tool_calls:
                    # Asegurarse de que 'arguments' sea una cadena antes de intentar json.loads
                    args_str = tc["function"]["arguments"] if isinstance(tc["function"]["arguments"], str) else ""
                    try:
                        args = json.loads(args_str)
                    except json.JSONDecodeError as e:
                        logger.error(f"JSONDecodeError al decodificar argumentos de herramienta para '{tc['function']['name']}': {e}. Argumentos recibidos (truncados a 500 chars): '{args_str[:500]}'. Longitud total: {len(args_str)}")
                        args = {}
                    formatted_tool_calls.append({
                        "id": tc["id"],
                        "name": tc["function"]["name"],
                        "args": args
                    })
                # El AIMessage final incluye el contenido acumulado y los tool_calls
                # IMPORTANTE: No permitir mensajes vacíos, ya que rompen LangGraph/LangChain
                if not full_response_content or not full_response_content.strip():
                    # Si hay tool_calls pero no hay texto, algunos proveedores fallan si el content es ""
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
                    # IMPORTANTE: No permitir mensajes vacíos, ya que rompen LangGraph/LangChain
                    if not full_response_content.strip():
                        full_response_content = "Ejecutando herramientas..."
                    yield AIMessage(
                        content=full_response_content, 
                        tool_calls=enhanced_tool_calls,
                        additional_kwargs={"reasoning_content": full_reasoning_content} if full_reasoning_content else {}
                    )
                else:
                    if not full_response_content.strip():
                        logger.debug("DEBUG: full_response_content vacío al finalizar la generación.")
                        full_response_content = "El modelo devolvió una respuesta vacía. Esto puede deberse a un problema temporal del proveedor o a un filtro de seguridad. Por favor, intenta reformular tu pregunta."
                    
                    # El AIMessage final incluye solo el contenido acumulado y razonamiento si lo hay
                    yield AIMessage(
                        content=full_response_content,
                        additional_kwargs={"reasoning_content": full_reasoning_content} if full_reasoning_content else {}
                    )

        except Exception as e:
            # Manejo de errores más amigable para el usuario
            error_type = type(e).__name__
            error_msg = str(e)
            
            # Si es un error 20015 de SiliconFlow (requiere formato 'function'), intentar con configuración alternativa
            if ("20015" in error_msg and "Input should be 'function'" in error_msg) or ("20015" in error_msg and "Field required" in error_msg and "openrouter" in self.model_name.lower()):
                logger.info("Intentando configuración alternativa para SiliconFlow (formato 'function')...")
                try:
                    # Crear configuración alternativa más específica
                    alt_kwargs = {
                        "model": completion_kwargs["model"],
                        "messages": completion_kwargs["messages"],
                        "stream": True,
                        "api_key": completion_kwargs["api_key"],
                        "temperature": completion_kwargs.get("temperature", 0.7),
                        "max_tokens": completion_kwargs.get("max_tokens", 4096),
                        "user": f"user_{self._generate_short_id(12)}",
                        "num_retries": 1,  # Reducir reintentos en fallback
                        "timeout": 60     # Timeout más corto en fallback
                    }
                    
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
        
        # 1. Convertir el historial a un formato de texto plano para evitar errores de secuencia de herramientas
        history_text = []
        for msg in history_source:
            role = "Sistema" if isinstance(msg, SystemMessage) else "Usuario" if isinstance(msg, HumanMessage) else "Asistente" if isinstance(msg, AIMessage) else "Herramienta"
            content = msg.content
            
            # Si es un mensaje de asistente con llamadas a herramientas, incluirlas en el texto
            if isinstance(msg, AIMessage) and msg.tool_calls:
                tool_info = []
                for tc in msg.tool_calls:
                    tool_info.append(f"[Llamada a herramienta: {tc['name']}({tc['args']})]")
                content = f"{content}\n" + "\n".join(tool_info)
            
            # Si es una respuesta de herramienta, indicar qué herramienta fue
            if isinstance(msg, ToolMessage):
                role = f"Respuesta de Herramienta ({msg.tool_call_id})"
            
            history_text.append(f"### {role}:\n{content}")

        flat_history = "\n\n".join(history_text)

        # 2. Crear un único mensaje de usuario con todo el historial y las instrucciones
        summarize_prompt = f"""Genera un resumen EXTENSO y DETALLADO de la conversación anterior. 
        
CONTEXTO DE LA CONVERSACIÓN:
{flat_history}

INSTRUCCIONES:
Incluye todos los puntos clave, decisiones tomadas, tareas pendientes, el contexto esencial para la continuidad, cualquier información relevante que ayude a retomar la conversación sin perder el hilo, y **especialmente, cualquier error de herramienta encontrado, las razones de su fallo y las acciones intentadas para resolverlos**. 
Limita el resumen a 4000 caracteres. Sé exhaustivo y enfocado en la información crítica."""

        litellm_messages_for_summary = [{"role": "user", "content": summarize_prompt}]
        
        litellm_generation_params = self.generation_params

        litellm_generation_params = self.generation_params

        summary_completion_kwargs = {
            "model": self.model_name,
            "messages": litellm_messages_for_summary,
            "api_key": self.api_key, # Pasar la API Key directamente
            "temperature": litellm_generation_params.get("temperature", 0.7),
            "stream": False,
            # Añadir reintentos para errores 503 y otros errores de servidor
            "num_retries": 3,
            "retry_strategy": "exponential_backoff_retry",
            "tools": [], # CRÍTICO: Asegurar que no se pasen herramientas para la resumirización
            "tool_choice": "none", # CRÍTICO: Forzar al modelo a no usar herramientas
        }
        if "top_p" in litellm_generation_params:
            summary_completion_kwargs["top_p"] = litellm_generation_params["top_p"]
        if "top_k" in litellm_generation_params:
            summary_completion_kwargs["top_k"] = litellm_generation_params["top_k"]

        try:
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

    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """Encuentra y devuelve una herramienta de LangChain por su nombre."""
        tool = self.tool_manager.get_tool(tool_name)
        return tool if isinstance(tool, BaseTool) else None

    def close(self):
        """Libera recursos y cierra conexiones de servicios internos."""
        try:
            if hasattr(self, 'vector_db_manager') and self.vector_db_manager:
                self.vector_db_manager.close()
                logger.info("LLMService: VectorDBManager cerrado.")
            
            if hasattr(self, 'tool_executor') and self.tool_executor:
                self.tool_executor.shutdown(wait=False)
                logger.info("LLMService: Executor de herramientas detenido.")
            
            if hasattr(self, 'provider_manager') and self.provider_manager:
                self.provider_manager.close()
                logger.info("LLMService: ProviderManager cerrado.")
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

    def _invoke_tool_with_interrupt(self, tool: BaseTool, tool_args: dict) -> Generator[Any, None, None]:
        """Invoca una herramienta en un hilo separado, permitiendo la interrupción."""
        def _tool_target():
            try:
                result = tool._run(**tool_args) # Usar _run directamente para obtener el generador si existe
                if isinstance(result, dict) and result.get("status") == "requires_confirmation":
                    raise UserConfirmationRequired(
                        message=result.get("action_description", "Confirmación requerida"),
                        tool_name=result.get("operation", tool.name),
                        tool_args=result.get("args", tool_args),
                        raw_tool_output=result
                    )
                return result
            except UserConfirmationRequired as e:
                raise e
            except Exception as e:
                raise e

        with self.tool_execution_lock:
            # Eliminamos la restricción de 'una sola herramienta' para permitir que agentes (que son herramientas)
            # puedan invocar otras herramientas de forma anidada.
            future = self.tool_executor.submit(_tool_target)
            self.active_tool_future = future

        try:
            full_tool_output = "" # Eliminar esta línea, la acumulación se hará en el llamador
            while True:
                try:
                    # Intentar obtener el resultado. Si es un generador, iterar sobre él.
                    result = future.result(timeout=0.01)
                    if isinstance(result, Generator):
                        yield from result # Ceder directamente del generador de la herramienta
                        return # El generador de la herramienta ha terminado
                    else:
                        # Si no es un generador, ceder el resultado directamente
                        yield result
                        return
                except TimeoutError:
                    if self.interrupt_queue and not self.interrupt_queue.empty():
                        # print("DEBUG: _invoke_tool_with_interrupt - Interrupción detectada en la cola (via TimeoutError).", file=sys.stderr)
                        self.interrupt_queue.get()
                        if future.running():
                            # print("DEBUG: _invoke_tool_with_interrupt - Intentando cancelar la tarea (via TimeoutError).", file=sys.stderr)
                            future.cancel()
                            # print("DEBUG: _invoke_tool_with_interrupt - Lanzando InterruptedError (via TimeoutError).", file=sys.stderr)
                            raise InterruptedError("Ejecución de herramienta interrumpida por el usuario.")
                except InterruptedError:
                    raise
                except UserConfirmationRequired as e:
                    raise e
                except Exception as e:
                    raise e
        except InterruptedError:
            raise
        except UserConfirmationRequired as e:
            raise e
        except Exception as e:
            raise e
        finally:
            with self.tool_execution_lock:
                if self.active_tool_future is future:
                    self.active_tool_future = None
