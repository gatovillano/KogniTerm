import os
import sys
import time
import json
import queue
from typing import List, Any, Generator, Optional, Union, Dict
from collections import deque
from langchain_core.tools import BaseTool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage, BaseMessage
from litellm import completion, litellm
import uuid
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
                                'type': field_type,
                                'description': field_info.description or f'Parámetro {field_name}'
                            }
                    args_schema = {"type": "object", "properties": properties}
        except Exception as e:
            tool_name = getattr(tool, 'name', 'Desconocido')
            tool_type = type(tool)
            print(f"Advertencia: Error al obtener el esquema de la herramienta '{tool_name}' de tipo '{tool_type}': {e}. Se usará un esquema vacío.", file=sys.stderr)

    # Si el esquema está vacío pero sabemos que la herramienta necesita argumentos,
    # intentar inferirlos del método _run o de la documentación
    if not args_schema.get('properties') and hasattr(tool, 'name'):
        tool_name = tool.name
        # Para herramientas conocidas, proporcionar esquemas por defecto
        if tool_name == 'file_read_tool':
            args_schema = {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "La ruta del archivo a leer."
                    }
                },
                "required": ["path"]
            }
        elif tool_name == 'file_update_tool':
            args_schema = {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "La ruta del archivo a actualizar."
                    },
                    "content": {
                        "type": "string",
                        "description": "El nuevo contenido del archivo."
                    }
                },
                "required": ["path", "content"]
            }

    # Asegurarse de que cada propiedad en args_schema['properties'] tenga un 'type'
    if 'properties' in args_schema:
        for prop_name, prop_details in args_schema['properties'].items():
            if 'type' not in prop_details:
                # Intentar inferir el tipo o establecer un valor predeterminado
                args_schema['properties'][prop_name]['type'] = 'string'

    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": args_schema
        }
    }

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

load_dotenv()

# Lógica de fallback para credenciales
openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
litellm_model = os.getenv("LITELLM_MODEL")
litellm_api_base = os.getenv("LITELLM_API_BASE")

google_api_key = os.getenv("GOOGLE_API_KEY")
gemini_model = os.getenv("GEMINI_MODEL")

logger.debug(f"OPENROUTER_API_KEY: {openrouter_api_key is not None}")
logger.debug(f"LITELLM_MODEL: {litellm_model}")
logger.debug(f"LITELLM_API_BASE: {litellm_api_base}")
logger.debug(f"GOOGLE_API_KEY: {google_api_key is not None}")
logger.debug(f"GEMINI_MODEL: {gemini_model}")

if openrouter_api_key and litellm_model:
    # Usar OpenRouter
    os.environ["LITELLM_MODEL"] = litellm_model
    os.environ["OPENROUTER_API_KEY"] = openrouter_api_key
    litellm.api_base = litellm_api_base if litellm_api_base else "https://openrouter.ai/api/v1"
    logger.debug("Usando configuración de OpenRouter.")
elif google_api_key and gemini_model:
    # Usar Google AI Studio
    os.environ["LITELLM_MODEL"] = f"gemini/{gemini_model}" # Asegurarse de que sea gemini/gemini-1.5-flash
    os.environ["LITELLM_API_KEY"] = google_api_key
    litellm.api_base = None # Asegurarse de que no haya un api_base de Vertex AI
    logger.debug("Usando configuración de Google AI Studio.")
else:
    logger.warning("No se encontraron credenciales válidas para OpenRouter ni Google AI Studio. Asegúrate de configurar OPENROUTER_API_KEY/LITELLM_MODEL o GOOGLE_API_KEY/GEMINI_MODEL en tu archivo .env")

from .exceptions import UserConfirmationRequired # Importar la excepción
from .tools.tool_manager import ToolManager
import tiktoken # Importar tiktoken
from .context.workspace_context import WorkspaceContext # Importar WorkspaceContext





class LLMService:
    def __init__(self, interrupt_queue: Optional[queue.Queue] = None):
        self.model_name = os.environ.get("LITELLM_MODEL", "google/gemini-1.5-flash")
        self.api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("LITELLM_API_KEY")
        self.conversation_history: List[Union[HumanMessage, AIMessage, ToolMessage]] = []
        self.interrupt_queue = interrupt_queue
        self.stop_generation_flag = False
        self.tool_manager = ToolManager(llm_service=self)
        self.tool_manager.load_tools()
        self.tool_names = [tool.name for tool in self.tool_manager.get_tools()]
        self.tool_schemas = [tool.args_schema.schema() for tool in self.tool_manager.get_tools()]
        self.tool_map = {tool.name: tool for tool in self.tool_manager.get_tools()}
        self.litellm_tools = [_convert_langchain_tool_to_litellm(tool) for tool in self.tool_manager.get_tools()]
        self.max_conversation_tokens = 128000 # Gemini 1.5 Flash context window
        self.max_tool_output_tokens = 100000 # Max tokens for tool output
        self.MAX_TOOL_MESSAGE_CONTENT_LENGTH = 100000 # Nuevo: Límite de caracteres para el contenido de ToolMessage
        self.max_history_tokens = self.max_conversation_tokens - self.max_tool_output_tokens # Remaining for history
        self.tokenizer = tiktoken.encoding_for_model("gpt-4") # Usar un tokenizer compatible
        self.history_file_path = os.path.join(os.getcwd(), ".kogniterm", "history.json") # Inicializar history_file_path
        self.console = None # Inicializar console
        self.max_history_messages = 50 # Aumentado para preservar más contexto
        self.max_history_chars = 30000 # Aumentado para preservar más contexto
        self.workspace_context = WorkspaceContext(root_dir=os.getcwd())
        self.workspace_context_initialized = False
        self.call_timestamps = deque() # Inicializar call_timestamps
        self.rate_limit_period = 60 # Por ejemplo, 60 segundos
        self.rate_limit_calls = 10 # Por ejemplo, 10 llamadas por período
        self.generation_params = {"temperature": 0.7, "top_p": 0.95, "top_k": 40} # Parámetros de generación por defecto
        self.tool_execution_lock = threading.Lock() # Inicializar el lock
        self.active_tool_future = None # Inicializar la referencia a la tarea activa
        self.tool_executor = ThreadPoolExecutor(max_workers=1) # Inicializar el ThreadPoolExecutor
        self.conversation_history = self._load_history()
        self.SUMMARY_MAX_TOKENS = 750 # Tokens, longitud máxima del resumen de herramientas

    def _from_litellm_message(self, message: Union[Dict, BaseMessage]):
        """Convierte un mensaje de LiteLLM (dict) o LangChain (BaseMessage) a un formato compatible con LangChain."""
        if isinstance(message, BaseMessage): # Ya es un mensaje de LangChain, retornarlo directamente
            return message

        # Si es un diccionario, procesarlo
        role = message.get("role")
        content = message.get("content", "")
        logger.debug(f"_from_litellm_message - Convirtiendo de LiteLLM a LangChain. Rol: {role}, Contenido: {content[:100]}...")
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
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except json.JSONDecodeError:
                                args = {} # Fallback si no es un JSON válido
                        tool_call_item = {
                            "id": tc.get("id", str(uuid.uuid4())),
                            "name": function_data.get("name", ""),
                            "args": args
                        }
                        tool_calls.append(tool_call_item)
                        logger.debug(f"_from_litellm_message - ToolCall convertido: {tool_call_item}")
                return AIMessage(content=content, tool_calls=tool_calls)
            else:
                return AIMessage(content=content)
        elif role == "tool":
            tool_message = ToolMessage(content=content, tool_call_id=message.get("tool_call_id"))
            logger.debug(f"_from_litellm_message - ToolMessage convertido: {tool_message}")
            return tool_message
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

    def _to_litellm_message(self, message: Union[HumanMessage, AIMessage, ToolMessage]) -> Dict[str, Any]:
        logger.debug(f"DEBUG: _to_litellm_message - Convirtiendo de LangChain a LiteLLM. Tipo: {type(message).__name__}, Contenido: {str(message.content)[:100]}...")
        if isinstance(message, HumanMessage):
            return {"role": "user", "content": message.content}
        elif isinstance(message, AIMessage):
            if message.tool_calls:
                serialized_tool_calls = []
                for tc in message.tool_calls:
                    # Asegurarse de que tc sea un diccionario y acceder a sus elementos como tal
                    tc_id = tc.get("id", str(uuid.uuid4()))
                    tc_name = tc.get("name", "")
                    tc_args = tc.get("args", {})

                    serialized_tool_call_item = {
                        "id": tc_id,
                        "function": {
                            "name": tc_name,
                            "arguments": json.dumps(tc_args)
                        }
                    }
                    serialized_tool_calls.append(serialized_tool_call_item)
                    logger.debug(f"DEBUG: _to_litellm_message - ToolCall serializado: {serialized_tool_call_item}")
                return {"role": "assistant", "content": message.content, "tool_calls": serialized_tool_calls}
            return {"role": "assistant", "content": message.content}
        elif isinstance(message, ToolMessage):
            content = message.content
            # Si el contenido es un diccionario, serializarlo a JSON
            if isinstance(content, dict):
                content = json.dumps(content, ensure_ascii=False)
            
            # Truncar el contenido del ToolMessage si es demasiado largo
            if len(content) > self.MAX_TOOL_MESSAGE_CONTENT_LENGTH:
                truncated_content = content[:self.MAX_TOOL_MESSAGE_CONTENT_LENGTH] + "\n... [Contenido de ToolMessage truncado]"
                logger.debug(f"DEBUG: _to_litellm_message - ToolMessage content truncado de {len(content)} a {len(truncated_content)} caracteres.")
                content = truncated_content
            litellm_tool_message = {"role": "tool", "content": content, "tool_call_id": message.tool_call_id}
            logger.debug(f"DEBUG: _to_litellm_message - ToolMessage serializado: {litellm_tool_message}")
            return litellm_tool_message
        return {"role": "user", "content": str(message)} # Fallback





    def _get_token_count(self, text: str) -> int:
        return len(self.tokenizer.encode(text))

    def _save_history(self, history: List[Union[HumanMessage, AIMessage, ToolMessage]]):
        history_dir = os.path.dirname(self.history_file_path)
        if not os.path.exists(history_dir):
            os.makedirs(history_dir)
        
        serializable_history = []
        for msg in history:
            if isinstance(msg, HumanMessage):
                serializable_history.append({"type": "human", "content": msg.content})
            elif isinstance(msg, AIMessage):
                tool_calls_data = []
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_calls_data.append({
                            "id": tc.get("id"),
                            "name": tc.get("name"),
                            "args": tc.get("args")
                        })
                serializable_history.append({"type": "ai", "content": msg.content, "tool_calls": tool_calls_data})
            elif isinstance(msg, ToolMessage):
                serializable_history.append({"type": "tool", "content": msg.content, "tool_call_id": msg.tool_call_id})
            elif isinstance(msg, SystemMessage):
                serializable_history.append({"type": "system", "content": msg.content})
        
        with open(self.history_file_path, 'w', encoding='utf-8') as f:
            json.dump(serializable_history, f, ensure_ascii=False, indent=2)

    def _load_history(self) -> List[Union[HumanMessage, AIMessage, ToolMessage]]:
        if not os.path.exists(self.history_file_path):
            return []
        
        try:
            with open(self.history_file_path, 'r', encoding='utf-8') as f:
                serializable_history = json.load(f)
            
            loaded_messages = []
            for msg_data in serializable_history:
                msg_type = msg_data.get("type")
                content = msg_data.get("content", "")
                if msg_type == "human":
                    loaded_messages.append(HumanMessage(content=content))
                elif msg_type == "ai":
                    tool_calls_data = msg_data.get("tool_calls")
                    tool_calls = []
                    if tool_calls_data:
                        for tc_data in tool_calls_data:
                            tool_calls.append({
                                "id": tc_data.get("id"),
                                "name": tc_data.get("name"),
                                "args": tc_data.get("args")
                            })
                    loaded_messages.append(AIMessage(content=content, tool_calls=tool_calls))
                elif msg_type == "tool":
                    loaded_messages.append(ToolMessage(content=content, tool_call_id=msg_data.get("tool_call_id")))
                elif msg_type == "system":
                    loaded_messages.append(SystemMessage(content=content))
            return loaded_messages
        except json.JSONDecodeError as e:
            logger.error(f"Error al decodificar el historial JSON desde {self.history_file_path}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error al cargar el historial desde {self.history_file_path}: {e}")
            return []

    def invoke(self, history: list, system_message: Optional[str] = None, interrupt_queue: Optional[queue.Queue] = None):
        """Invoca el modelo LLM con un historial de conversación y un mensaje de sistema opcional.

        Args:
            history: El historial completo de la conversación en el formato de LangChain.
            system_message: Un mensaje de sistema opcional para guiar al modelo.
            interrupt_queue: Una cola para verificar si se ha solicitado una interrupción.

        Returns:
            La respuesta del modelo, que puede incluir texto o llamadas a herramientas.
        """
        current_time = time.time()
        while self.call_timestamps and self.call_timestamps[0] <= current_time - self.rate_limit_period:
            self.call_timestamps.popleft()

        if len(self.call_timestamps) >= self.rate_limit_calls:
            time_to_wait = self.rate_limit_period - (current_time - self.call_timestamps[0])
            if time_to_wait > 0:
                logger.debug(f"Rate limit hit. Waiting for {time_to_wait:.2f} seconds...")
                time.sleep(time_to_wait)
                current_time = time.time()
                logger.debug("Finished waiting for rate limit.")
                while self.call_timestamps and self.call_timestamps[0] <= current_time - self.rate_limit_period:
                    self.call_timestamps.popleft()

        self.stop_generation_flag = False

        # 1. Construir todos los mensajes de sistema iniciales
        all_initial_system_messages_for_llm = []
        
        # Añadir el contexto dinámico del espacio de trabajo si está disponible
        workspace_context_message = self._build_llm_context_message()
        if workspace_context_message:
            all_initial_system_messages_for_llm.append(self._to_litellm_message(workspace_context_message))

        # Instrucción para el LLM sobre cómo manejar las confirmaciones de herramientas
        tool_confirmation_instruction = (
            "¡ATENCIÓN! Si ya has recibido un ToolMessage con la salida de un comando, ¡ese comando ya se ejecutó! No lo propongas de nuevo. "\
            "Cuando recibas un ToolMessage con un 'status: \"requires_confirmation\"', "\
            "analiza cuidadosamente el 'diff' y la 'action_description'. "\
            "Si la acción es segura y deseada, responde con un ToolMessage que contenga "\
            "el 'tool_name' y los 'args' originales de la herramienta, pero con 'confirm: True'. "\
            "Si la acción no es segura o no es deseada, responde con un mensaje de texto explicando por qué la deniegas. "\
            "Siempre prioriza la seguridad y la intención del usuario. "\
            "**IMPORTANTE:** Si un ToolMessage indica que una herramienta se ejecutó con éxito, considera esa acción como completada y no la anuncies ni la propongas de nuevo en tu siguiente respuesta. Continúa con el siguiente paso de la tarea."
        )

        # Instrucciones para el manejo de memoria
        memory_instructions = (
            "**INSTRUCCIONES DE MEMORIA:**\n"
            "- Al iniciar una nueva sesión, utiliza la herramienta 'memory_read' para leer el contenido de la memoria contextual del proyecto desde 'llm_context.md'. Esto te ayudará a recordar información relevante de sesiones anteriores.\n"
            "- Durante la conversación, identifica información relevante proporcionada por el usuario (como preferencias, decisiones importantes, contexto del proyecto, o datos clave) y guárdala en la memoria utilizando la herramienta 'memory_append' cuando sea pertinente. Asegúrate de que la información sea útil para futuras sesiones.\n"
            "- No guardes información trivial o repetitiva; enfócate en elementos que puedan mejorar la continuidad y eficiencia en interacciones futuras."
        )

        if all_initial_system_messages_for_llm and all_initial_system_messages_for_llm[0]["role"] == "system":
            all_initial_system_messages_for_llm[0]["content"] += f"\n\n{tool_confirmation_instruction}\n\n{memory_instructions}"
        else:
            all_initial_system_messages_for_llm.append({"role": "system", "content": tool_confirmation_instruction + "\n\n" + memory_instructions})

        if system_message:
            # Si ya hay un system_message del workspace_context o la instrucción de confirmación, concatenar el system_message proporcionado
            if all_initial_system_messages_for_llm and all_initial_system_messages_for_llm[0]["role"] == "system":
                all_initial_system_messages_for_llm[0]["content"] += f"\n\n{system_message}"
            else:
                all_initial_system_messages_for_llm.append({"role": "system", "content": system_message})
        
        # 2. Convertir el historial de conversación (sin los mensajes de sistema estáticos/dinámicos)
        litellm_conversation_history = [self._to_litellm_message(msg) for msg in history]

        # 3. Filtrar mensajes de asistente vacíos del historial de conversación
        filtered_conversation_messages = []
        for msg in litellm_conversation_history:
            is_assistant = msg.get("role") == "assistant"
            has_content = msg.get("content") and str(msg.get("content")).strip()
            has_tool_calls = msg.get("tool_calls")
            if is_assistant and not has_content and not has_tool_calls:
                continue
            filtered_conversation_messages.append(msg)
        
        # 4. Combinar todos los mensajes para el LLM
        litellm_messages = all_initial_system_messages_for_llm + filtered_conversation_messages

        # Añadir log de depuración para el system_message final
        final_system_message_content = ""
        for msg in all_initial_system_messages_for_llm:
            if msg["role"] == "system":
                final_system_message_content += msg["content"]
        if final_system_message_content:
            logger.debug(f"System Message final enviado al LLM:\n{final_system_message_content[:1000]}... (truncado para log)")

        # 5. Lógica de truncamiento y resumen del historial
        # Definir un mínimo de mensajes a mantener, que incluya todos los system messages + al menos 1 conversacional
        min_messages_to_keep_in_conversation = 1 # Mínimo de mensajes conversacionales a intentar mantener
        
        # Contar los mensajes actuales en el historial de conversación (excluyendo system messages)
        current_conversation_messages_count = len(filtered_conversation_messages)

        # Truncamiento/Resumen basado en `filtered_conversation_messages`
        # La lógica de resumen debe operar sobre `self.conversation_history` (LangChain messages)
        # y no debe afectar `all_initial_system_messages_for_llm`.
        
        # Calculamos la longitud total de `litellm_messages` para la decisión de resumen/truncamiento
        total_litellm_messages_length = sum(len(json.dumps(m, ensure_ascii=False)) for m in litellm_messages)

        if (len(filtered_conversation_messages) > self.max_history_messages or total_litellm_messages_length > self.max_history_chars) and \
           len(filtered_conversation_messages) > min_messages_to_keep_in_conversation:
            
            if self.console:
                self.console.print("[yellow]El historial de conversación es demasiado largo. Intentando resumir...[/yellow]")
            
            summary = self.summarize_conversation_history() # Opera en self.conversation_history
            if summary:
                # Crear un nuevo historial con el resumen al principio
                summary_message_lc = SystemMessage(content=f"Resumen de la conversación anterior: {summary}")
                new_conversation_history_litellm = [self._to_litellm_message(summary_message_lc)]
                
                # Mantener los mensajes más recientes que no excedan el límite de caracteres
                final_conversational_messages = []
                current_length = len(json.dumps(new_conversation_history_litellm, ensure_ascii=False))

                # Iterar desde el final del historial para conservar los mensajes más recientes
                for msg in reversed(filtered_conversation_messages):
                    # Mantener siempre los pares de tool_calls juntos
                    pair_to_add = []
                    if msg.get("role") == "tool":
                        # Si es un ToolMessage, buscar su AIMessage correspondiente
                        tool_call_id = msg.get("tool_call_id")
                        for prev_msg in reversed(filtered_conversation_messages):
                            if prev_msg.get("role") == "assistant" and prev_msg.get("tool_calls"):
                                if any(tc.get("id") == tool_call_id for tc in prev_msg["tool_calls"]):
                                    pair_to_add = [prev_msg, msg]
                                    break
                    else:
                        pair_to_add = [msg]

                    # Calcular el tamaño del par y añadirlo si cabe
                    pair_length = sum(len(json.dumps(m, ensure_ascii=False)) for m in pair_to_add)
                    if current_length + pair_length > self.max_history_chars or len(final_conversational_messages) >= self.max_history_messages:
                        break

                    # Insertar el par al principio de la lista para mantener el orden
                    final_conversational_messages = pair_to_add + final_conversational_messages
                    current_length += pair_length

                new_conversation_history_litellm.extend(final_conversational_messages)

                # Actualizar `litellm_messages` con los system messages iniciales y el nuevo historial resumido
                litellm_messages = all_initial_system_messages_for_llm + new_conversation_history_litellm

                # Actualizar self.conversation_history para reflejar el resumen (en formato LangChain)
                # Esto es crucial para futuras llamadas a summarize_conversation_history
                # Solo guardamos el historial de conversación real, no los mensajes de contexto dinámicos.
                self.conversation_history = [self._from_litellm_message(msg) for msg in new_conversation_history_litellm]
                self._save_history(self.conversation_history) # Guardar el historial de conversación resumido
                if self.console:
                    self.console.print("[green]Historial resumido y actualizado.[/green]")
            else:
                if self.console:
                    self.console.print("[red]No se pudo resumir el historial. Se procederá con el truncamiento.[/red]")
 
        # Post-procesamiento del historial para asegurar la secuencia AIMessage (tool_calls) -> ToolMessage
        final_litellm_messages = []
        for i, msg in enumerate(litellm_messages):
            if msg.get('role') == 'tool':
                tool_call_id = msg.get('tool_call_id')
                # Buscar si el AIMessage anterior tiene una tool_call con este ID
                found_matching_ai_message = False
                if i > 0 and litellm_messages[i-1].get('role') == 'assistant' and litellm_messages[i-1].get('tool_calls'):
                    for tc in litellm_messages[i-1]['tool_calls']:
                        if tc.get('id') == tool_call_id:
                            found_matching_ai_message = True
                            break
                
                if not found_matching_ai_message:
                    # Si no se encontró un AIMessage coincidente, insertar uno simulado
                    # Intentar inferir el nombre de la herramienta del ToolMessage content si es posible
                    tool_name = "unknown_tool"
                    if "Contenido añadido exitosamente a la memoria" in msg.get("content", ""):
                        tool_name = "memory_append"
                    elif "Archivo escrito con éxito" in msg.get("content", ""):
                        tool_name = "file_operations" # O file_update_tool, dependiendo del contexto
                    
                    simulated_tool_call = {
                        "id": tool_call_id,
                        "function": {
                            "name": tool_name,
                            "arguments": "{}" # Argumentos vacíos o inferidos si es posible
                        }
                    }
                    simulated_ai_message = {"role": "assistant", "content": "", "tool_calls": [simulated_tool_call]}
                    final_litellm_messages.append(simulated_ai_message)
                    logger.debug(f"DEBUG: Insertado AIMessage simulado para ToolMessage huérfano: {simulated_ai_message}")
            final_litellm_messages.append(msg)
        
        litellm_messages = final_litellm_messages

        # Truncamiento estándar si aún es necesario después del resumen
        # Ahora, solo truncamos la parte conversacional, manteniendo los system messages iniciales.
        current_conversational_messages = [msg for msg in litellm_messages if msg.get('role') != 'system']
        
        # Recalcular la longitud total de los mensajes para el truncamiento final
        total_litellm_messages_length = sum(len(json.dumps(msg, ensure_ascii=False)) for msg in (all_initial_system_messages_for_llm + current_conversational_messages))

        # Truncamiento estándar si aún es necesario después del resumen
        # Ahora, solo truncamos la parte conversacional, manteniendo los system messages iniciales.
        # Calculamos la longitud total de los mensajes para el truncamiento final
        current_total_length = sum(len(json.dumps(msg, ensure_ascii=False)) for msg in (all_initial_system_messages_for_llm + current_conversational_messages))

        while (len(current_conversational_messages) > self.max_history_messages or\
               current_total_length > self.max_history_chars) and \
              len(current_conversational_messages) > min_messages_to_keep_in_conversation:
            
            # Remove from the oldest conversational messages
            if current_conversational_messages:
                removed_msg = current_conversational_messages.pop(0)
                current_total_length -= len(json.dumps(removed_msg, ensure_ascii=False))
            else:
                break # No conversational messages left to truncate

        # Reconstruct litellm_messages with the truncated conversational part
        litellm_messages = all_initial_system_messages_for_llm + current_conversational_messages

        # Merge consecutive assistant messages to ensure valid sequence
        merged_messages = []
        for msg in litellm_messages:
            if msg['role'] == 'assistant' and merged_messages and merged_messages[-1]['role'] == 'assistant':
                # Merge consecutive assistant messages
                prev = merged_messages[-1]
                prev['content'] = (prev.get('content', '') or '') + (msg.get('content', '') or '')
                if 'tool_calls' in msg:
                    if 'tool_calls' not in prev:
                        prev['tool_calls'] = []
                    prev['tool_calls'].extend(msg['tool_calls'])
            else:
                merged_messages.append(msg)
        litellm_messages = merged_messages

        # Lógica adicional para asegurar que el último AIMessage con tool_calls y su ToolMessage estén presentes
        if litellm_messages and litellm_messages[-1].get('role') == 'tool':
            last_tool_message = litellm_messages[-1]
            tool_call_id_of_last_tool_message = last_tool_message.get('tool_call_id')
            
            found_ai_message_for_tool = False
            for i in range(len(litellm_messages) - 2, -1, -1): # Buscar hacia atrás desde el penúltimo mensaje
                msg = litellm_messages[i]
                if msg.get('role') == 'assistant' and msg.get('tool_calls'):
                    for tc in msg['tool_calls']:
                        if tc.get('id') == tool_call_id_of_last_tool_message:
                            # Si encontramos el AIMessage correspondiente, nos aseguramos de que esté en la lista
                            # Si ya está, no hacemos nada. Si no, lo insertamos justo antes del ToolMessage.
                            if msg not in litellm_messages:
                                litellm_messages.insert(i + 1, msg) # Insertar antes del ToolMessage
                            found_ai_message_for_tool = True
                            break
                if found_ai_message_for_tool:
                    break

        try:
            completion_kwargs = {
                "model": self.model_name,
                "messages": litellm_messages, # Usar el historial final procesado
                "tools": self.litellm_tools,
                "stream": True,
                "api_key": self.api_key, # Pasar la API Key directamente
                "temperature": self.generation_params.get("temperature", 0.7),
            }
            if "top_p" in self.generation_params:
                completion_kwargs["top_p"] = self.generation_params["top_p"]
            if "top_k" in self.generation_params:
                completion_kwargs["top_k"] = self.generation_params["top_k"]

            logger.debug(f"DEBUG: Mensajes finales ENVIADOS a LiteLLM: {json.dumps(litellm_messages, indent=2, ensure_ascii=False)}") # DEBUG print mejorado
            logger.debug(f"DEBUG: completion_kwargs ENVIADOS a LiteLLM: {json.dumps(completion_kwargs, indent=2, ensure_ascii=False)}") # DEBUG print mejorado
    
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
                    logger.debug("Interrupción detectada desde la cola.") # Para depuración
                    break # Salir del bucle de chunks

                if self.stop_generation_flag:
                    logger.debug("Generación detenida por bandera.")
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
                    # Acumular tool_calls
                    for tc in tool_calls_from_delta:
                        # Asegurarse de que la lista tool_calls tenga el tamaño suficiente
                        while tc.index >= len(tool_calls):
                            tool_calls.append({"id": "", "function": {"name": "", "arguments": ""}})
                        
                        # Actualizar el ID si está presente en el chunk
                        if getattr(tc, 'id', None) is not None:
                            tool_calls[tc.index]["id"] = tc.id
                        
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
                logger.debug(f"DEBUG: invoke - AIMessage final con tool_calls: {formatted_tool_calls}")
                yield AIMessage(content=full_response_content, tool_calls=formatted_tool_calls)
            else:
                # El AIMessage final incluye solo el contenido acumulado
                logger.debug(f"DEBUG: invoke - AIMessage final sin tool_calls: {full_response_content[:100]}...")
                yield AIMessage(content=full_response_content)

        except Exception as e:
            import traceback
            logger.error(f"Error de LiteLLM: {e}")
            traceback.print_exc(file=sys.stderr)
            error_message = f"¡Ups! 😵 Ocurrió un error inesperado al comunicarme con el modelo (LiteLLM): {e}. Por favor, revisa los logs para más detalles. ¡Intentemos de nuevo!"""
            logger.error(f"DEBUG: invoke - Error en LiteLLM: {e}")
            yield AIMessage(content=error_message)

    def summarize_conversation_history(self) -> str:
        """Resume el historial de conversación actual utilizando el modelo LLM a través de LiteLLM."""
        if not self.conversation_history:
            return ""
        
        # Convertir el historial a mensajes de LiteLLM para aplicar la lógica de filtrado
        litellm_history_for_summary = [self._to_litellm_message(msg) for msg in self.conversation_history]
        logger.debug(f"DEBUG: summarize_conversation_history - Historial para resumen (LiteLLM): {json.dumps(litellm_history_for_summary, indent=2, ensure_ascii=False)[:1000]}...")

        # Aplicar la lógica de post-procesamiento para eliminar ToolMessages huérfanos
        processed_litellm_history = []
        tool_call_ids_in_aimessages = set()
        
        for msg in litellm_history_for_summary:
            if msg.get('role') == 'assistant' and msg.get('tool_calls'):
                for tc in msg['tool_calls']:
                    if 'id' in tc:
                        tool_call_ids_in_aimessages.add(tc['id'])
        
        for msg in litellm_history_for_summary:
            if msg.get('role') == 'tool':
                tool_call_id = msg.get('tool_call_id')
                # Solo eliminar si el tool_call_id existe y no está en los AIMessages válidos
                if tool_call_id and tool_call_id not in tool_call_ids_in_aimessages:
                    logger.debug(f"DEBUG: summarize_conversation_history - Eliminando ToolMessage huérfano: {msg}")
                    continue
            processed_litellm_history.append(msg)
        
        logger.debug(f"DEBUG: summarize_conversation_history - Historial procesado (sin huérfanos): {json.dumps(processed_litellm_history, indent=2, ensure_ascii=False)[:1000]}...")

        # Convertir de nuevo a mensajes de LangChain para añadir el summarize_prompt
        langchain_processed_history = [self._from_litellm_message(msg) for msg in processed_litellm_history]

        summarize_prompt = HumanMessage(content="Genera un resumen EXTENSO y DETALLADO de la conversación anterior. Incluye TODOS los puntos clave, decisiones tomadas, tareas pendientes, el contexto esencial para la continuidad y CUALQUIER información relevante que ayude a retomar la conversación sin perder el hilo. Prioriza la fidelidad y la exhaustividad sobre la brevedad. Limita el resumen a 4000 caracteres, pero asegúrate de no omitir detalles críticos.")
        
        temp_history_for_summary = langchain_processed_history + [summarize_prompt]

        try:
            litellm_messages_for_summary = [self._to_litellm_message(msg) for msg in temp_history_for_summary]
            logger.debug(f"DEBUG: summarize_conversation_history - Mensajes finales para LiteLLM (resumen): {json.dumps(litellm_messages_for_summary, indent=2, ensure_ascii=False)[:1000]}...")
            
            litellm_generation_params = self.generation_params

            summary_completion_kwargs = {
                "model": self.model_name,
                "messages": litellm_messages_for_summary,
                "api_key": self.api_key, # Pasar la API Key directamente
                "temperature": litellm_generation_params.get("temperature", 0.7),
                "stream": False,
            }
            if "top_p" in litellm_generation_params:
                summary_completion_kwargs["top_p"] = litellm_generation_params["top_p"]
            if "top_k" in litellm_generation_params:
                summary_completion_kwargs["top_k"] = litellm_generation_params["top_k"]

            response = completion(
                **summary_completion_kwargs
            )
            
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
                                        logger.debug(f"DEBUG: summarize_conversation_history - Resumen generado: {str(content)[:100]}...")
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
                                    logger.debug(f"DEBUG: summarize_conversation_history - Resumen generado: {str(content)[:100]}...")
                                    return str(content)
            except Exception:
                pass
            logger.warning("DEBUG: summarize_conversation_history - No se pudo generar el resumen de la conversación.")
            return "Error: No se pudo generar el resumen de la conversación."
        except Exception as e:
            import traceback
            logger.error(f"Error de LiteLLM al resumir el historial: {e}")
            traceback.print_exc(file=sys.stderr)
            logger.error(f"DEBUG: summarize_conversation_history - Error de LiteLLM: {e}")
            return f"Error: Ocurrió un error inesperado al resumir el historial con LiteLLM: {e}."

    def get_tool(self, tool_name: str) -> BaseTool | None:
        """Encuentra y devuelve una herramienta de LangChain por su nombre."""
        return self.tool_manager.get_tool(tool_name)

    def _invoke_tool_with_interrupt(self, tool: BaseTool, tool_args: dict) -> Any:
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
            if self.active_tool_future is not None and self.active_tool_future.running():
                raise RuntimeError("Ya hay una herramienta en ejecución. No se puede iniciar otra.")
            
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
                        logger.debug("_invoke_tool_with_interrupt - Interrupción detectada en la cola (via TimeoutError).")
                        self.interrupt_queue.get()
                        if future.running():
                            logger.debug("_invoke_tool_with_interrupt - Intentando cancelar la tarea (via TimeoutError).")
                            future.cancel()
                            logger.debug("_invoke_tool_with_interrupt - Lanzando InterruptedError (via TimeoutError).")
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