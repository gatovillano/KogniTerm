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

def _convert_langchain_tool_to_litellm(tool: BaseTool) -> dict:
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

    return {
        "name": tool.name,
        "description": tool.description[:1024], # Límite de descripción para algunos proveedores
        "parameters": cleaned_schema,
    }

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
    
    os.environ["LITELLM_MODEL"] = model_name
    os.environ["OPENROUTER_API_KEY"] = openrouter_api_key
    
    # Cabeceras requeridas/recomendadas por OpenRouter
    litellm.headers = {
        "HTTP-Referer": "https://github.com/gatovillano/KogniTerm",
        "X-Title": "KogniTerm",
    }
    
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
    def __init__(self, interrupt_queue: Optional[queue.Queue] = None):
        # print("DEBUG: Iniciando LLMService.__init__...")
        # print("DEBUG: Iniciando LLMService.__init__...")
        from .tools.tool_manager import ToolManager
        self.model_name = os.environ.get("LITELLM_MODEL", "google/gemini-1.5-flash")
        self.api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("LITELLM_API_KEY")
        self.interrupt_queue = interrupt_queue
        self.stop_generation_flag = False
        from .embeddings_service import EmbeddingsService
        from .context.vector_db_manager import VectorDBManager
        # print("DEBUG: Inicializando EmbeddingsService...")
        self.embeddings_service = EmbeddingsService()
        # print("DEBUG: Inicializando VectorDBManager...")
        self.vector_db_manager = VectorDBManager(project_path=os.getcwd())
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
        self.litellm_tools = [_convert_langchain_tool_to_litellm(tool) for tool in self.tool_manager.get_tools()]
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

    def _to_litellm_message(self, message: BaseMessage) -> Dict[str, Any]:
        if isinstance(message, HumanMessage):
            return {"role": "user", "content": message.content}
        elif isinstance(message, AIMessage):
            tool_calls = getattr(message, 'tool_calls', [])
            content = message.content
            if isinstance(content, list):
                # Handle cases where content is a list of dicts (e.g. from a tool call)
                content = json.dumps(content)

            if tool_calls:
                serialized_tool_calls = []
                for tc in tool_calls:
                    tc_id = tc.get("id") or self._generate_short_id()
                    tc_name = tc.get("name", "")
                    tc_args = tc.get("args", {})
                    serialized_tool_calls.append({
                        "id": tc_id,
                        "function": {"name": tc_name, "arguments": json.dumps(tc_args)},
                    })
                
                if not content or not str(content).strip():
                    content = "Ejecutando herramientas..."
                
                return {"role": "assistant", "content": content, "tool_calls": serialized_tool_calls}
            return {"role": "assistant", "content": content or "..."}
        elif isinstance(message, ToolMessage):
            content = message.content
            if isinstance(content, list):
                content = json.dumps(content)
            if not content or not str(content).strip():
                content = "Operación completada (sin salida)."
            
            tc_id = getattr(message, 'tool_call_id', '')
            return {"role": "tool", "content": content, "tool_call_id": tc_id}
        elif isinstance(message, SystemMessage):
            return {"role": "system", "content": message.content}
        return {"role": "user", "content": str(message)}

    def _truncate_messages(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        # Implementación de truncamiento de mensajes
        # ... (la lógica de truncamiento se mantiene igual)
        return messages

    def _get_token_count(self, text: str) -> int:
        return len(self.tokenizer.encode(text))

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
        self.litellm_tools.append(_convert_langchain_tool_to_litellm(tool_instance))

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
        
        # Primero convertimos y filtramos mensajes de asistente vacíos
        raw_conv_messages = []
        for msg in processed_history:
            if isinstance(msg, SystemMessage):
                continue
            
            litellm_msg = self._to_litellm_message(msg)
            
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
                if tool_id and (tool_id in known_tool_call_ids or any(tool_id == known_id[:len(tool_id)] for known_id in known_tool_call_ids if len(tool_id) <= len(known_id))):
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
            "max_tokens": 4096,
            "num_retries": 3, # Aumentado para manejar errores temporales
            "timeout": 120,    # Según el ejemplo del usuario
        }
        
        # --- Lógica de Selección de Herramientas y Validación de Secuencia ---
        final_tools = []
        if self.litellm_tools:
            for t in self.litellm_tools:
                if isinstance(t, dict) and "name" in t:
                    final_tools.append(t)

        if final_tools:
            completion_kwargs["tools"] = final_tools
            # Forzar tool_choice="auto" para modelos que lo soporten
            if "gpt" in self.model_name.lower() or "openai" in self.model_name.lower() or "gemini" in self.model_name.lower():
                completion_kwargs["tool_choice"] = "auto"

        # Validación estricta de secuencia para Mistral/OpenRouter
        validated_messages = []
        last_user_content = None # INICIALIZACIÓN CORREGIDA
        in_tool_sequence = False # Bandera para asegurar que tool messages siguen inmediatamente a assistant con tool_calls
        
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
                    has_next_tool = (i + 1 < len(raw_conv_messages) and raw_conv_messages[i+1]["role"] == "tool")

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
                if msg.get("tool_call_id") and in_tool_sequence:
                    validated_messages.append(msg)
                last_user_content = None

        # Unificar mensajes de sistema y combinar
        final_messages = []
        if system_contents:
            final_messages.append({"role": "system", "content": "\n\n".join(system_contents)})
        final_messages.extend(validated_messages)

        completion_kwargs["messages"] = final_messages
    
        try:
            sys.stderr.flush()
            start_time = time.perf_counter()
            response_generator = completion(
                **completion_kwargs
            )
            end_time = time.perf_counter()
            self.call_timestamps.append(time.time())
            
            full_response_content = ""
            tool_calls = []
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
                    continue
                
                # Log the raw delta for debugging
                logger.debug(f"DEBUG: LiteLLM Delta recibido: {delta}")

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
                    try:
                        args = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError:
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
                yield AIMessage(content=full_response_content, tool_calls=formatted_tool_calls)
            else:
                # El AIMessage final incluye solo el contenido acumulado
                # IMPORTANTE: No permitir mensajes vacíos, ya que rompen LangGraph/LangChain
                if not full_response_content.strip():
                    full_response_content = "El modelo devolvió una respuesta vacía. Esto puede deberse a un problema temporal del proveedor o a un filtro de seguridad. Por favor, intenta reformular tu pregunta."
                yield AIMessage(content=full_response_content)

        except Exception as e:
            # Manejo de errores más amigable para el usuario
            error_type = type(e).__name__
            error_msg = str(e)
            
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
                friendly_message = f"¡Ups! 🌐 El proveedor del modelo (OpenRouter) está experimentando problemas técnicos temporales: '{error_msg}'. Por favor, intenta de nuevo en unos momentos."
            elif "RateLimitError" in error_type or "429" in error_msg:
                friendly_message = "¡Vaya! 🚦 Hemos alcanzado el límite de velocidad del modelo. Esperemos un momento antes de intentarlo de nuevo."
            elif "APIConnectionError" in error_type:
                friendly_message = "¡Vaya! 🔌 Parece que hay un problema de conexión con el servidor del modelo. Revisa tu conexión a internet."
            else:
                friendly_message = f"¡Ups! 😵 Ocurrió un error inesperado al comunicarme con el modelo ({error_type}): {e}. Por favor, intenta de nuevo."

            # Loguear el error completo para depuración interna, pero no ensuciar la terminal del usuario
            logger.error(f"Error detallado en LLMService.invoke: {error_msg}")
            if not any(x in error_msg for x in ["Upstream error", "RateLimitError"]):
                 logger.debug(traceback.format_exc())
            
            yield AIMessage(content=friendly_message)

    def summarize_conversation_history(self, messages_to_summarize: Optional[List[BaseMessage]] = None) -> str:
        """Resume el historial de conversación actual utilizando el modelo LLM a través de LiteLLM."""
        history_source = messages_to_summarize if messages_to_summarize is not None else self.conversation_history
        if not history_source:
            return ""
        
        # Convertir el historial a mensajes de LiteLLM para aplicar la lógica de filtrado
        litellm_history_for_summary = [self._to_litellm_message(msg) for msg in history_source]

        # Convertir de nuevo a mensajes de LangChain para añadir el summarize_prompt
        # ELIMINADO: La lógica de filtrado de huérfanos redundante.
        # Confiamos en que history_source ya viene limpio o que el modelo manejará el resumen.
        langchain_processed_history = [self._from_litellm_message(msg) for msg in litellm_history_for_summary]

        summarize_prompt = HumanMessage(content="Genera un resumen EXTENSO y DETALLADO de la conversación anterior. Incluye todos los puntos clave, decisiones tomadas, tareas pendientes, el contexto esencial para la continuidad y cualquier información relevante que ayude a retomar la conversación sin perder el hilo. Limita el resumen a 4000 caracteres. Sé exhaustivo y enfocado en la información crítica.")
        
        temp_history_for_summary = langchain_processed_history + [summarize_prompt]

        try:
            # --- Lógica de Rate Limit ---
            current_time = time.time()
            while self.call_timestamps and self.call_timestamps[0] <= current_time - self.rate_limit_period:
                self.call_timestamps.popleft()

            if len(self.call_timestamps) >= self.rate_limit_calls:
                time_to_wait = self.rate_limit_period - (current_time - self.call_timestamps[0])
                if time_to_wait > 0:
                    if self.console:
                        self.console.print(f"[yellow]Rate limit alcanzado en resumen. Esperando {time_to_wait:.2f} segundos...[/yellow]")
                    time.sleep(time_to_wait)
                    current_time = time.time()
                    while self.call_timestamps and self.call_timestamps[0] <= current_time - self.rate_limit_period:
                        self.call_timestamps.popleft()
            # ---------------------------

            litellm_messages_for_summary = [self._to_litellm_message(msg) for msg in temp_history_for_summary]
            
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
            }
            if "top_p" in litellm_generation_params:
                summary_completion_kwargs["top_p"] = litellm_generation_params["top_p"]
            if "top_k" in litellm_generation_params:
                summary_completion_kwargs["top_k"] = litellm_generation_params["top_k"]

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
            import traceback
            print(f"Error de LiteLLM al resumir el historial: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return f"Error: Ocurrió un error inesperado al resumir el historial con LiteLLM: {e}."

    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """Encuentra y devuelve una herramienta de LangChain por su nombre."""
        tool = self.tool_manager.get_tool(tool_name)
        return tool if isinstance(tool, BaseTool) else None

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
