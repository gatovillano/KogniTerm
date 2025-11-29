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

load_dotenv()

# Lógica de fallback para credenciales
openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
litellm_model = os.getenv("LITELLM_MODEL")
litellm_api_base = os.getenv("LITELLM_API_BASE")

google_api_key = os.getenv("GOOGLE_API_KEY")
gemini_model = os.getenv("GEMINI_MODEL")

if openrouter_api_key and litellm_model:
    # Usar OpenRouter
    # Si el modelo no tiene el prefijo openrouter/, añadirlo
    # Esto maneja nombres de modelo directos de la web de OpenRouter como "kwaipilot/kat-coder-pro:free"
    if "/" in litellm_model and not litellm_model.startswith("openrouter/"):
        # El modelo ya tiene un proveedor en su nombre (ej: "kwaipilot/kat-coder-pro:free")
        # LiteLLM necesita "openrouter/" + el nombre completo
        os.environ["LITELLM_MODEL"] = f"openrouter/{litellm_model}"
        model_display = f"openrouter/{litellm_model}"
    elif not litellm_model.startswith("openrouter/"):
        # Modelo simple sin proveedor
        os.environ["LITELLM_MODEL"] = f"openrouter/{litellm_model}"
        model_display = f"openrouter/{litellm_model}"
    else:
        # Ya tiene el prefijo correcto
        os.environ["LITELLM_MODEL"] = litellm_model
        model_display = litellm_model
    
    os.environ["OPENROUTER_API_KEY"] = openrouter_api_key
    litellm.api_base = litellm_api_base if litellm_api_base else "https://openrouter.ai/api/v1"
    print(f"🤖 Configuración activa: OpenRouter ({model_display})")
elif google_api_key and gemini_model:
    # Usar Google AI Studio
    os.environ["LITELLM_MODEL"] = f"gemini/{gemini_model}" # Asegurarse de que sea gemini/gemini-1.5-flash
    os.environ["LITELLM_API_KEY"] = google_api_key
    litellm.api_base = None # Asegurarse de que no haya un api_base de Vertex AI
    print(f"🤖 Configuración activa: Google AI Studio ({gemini_model})")
else:
    print("⚠️  ADVERTENCIA: No se encontraron credenciales válidas para OpenRouter ni Google AI Studio. Asegúrate de configurar OPENROUTER_API_KEY/LITELLM_MODEL o GOOGLE_API_KEY/GEMINI_MODEL en tu archivo .env", file=sys.stderr)

from .exceptions import UserConfirmationRequired # Importar la excepción
from .tools.tool_manager import ToolManager
import tiktoken # Importar tiktoken
from .context.workspace_context import WorkspaceContext # Importar WorkspaceContext
from .history_manager import HistoryManager





class LLMService:
    def __init__(self, interrupt_queue: Optional[queue.Queue] = None):
        self.model_name = os.environ.get("LITELLM_MODEL", "google/gemini-1.5-flash")
        self.api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("LITELLM_API_KEY")
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
        self.max_history_messages = 20 # Valor por defecto, ajustar según necesidad
        self.max_history_chars = 15000 # Valor por defecto, ajustar según necesidad
        self.workspace_context = WorkspaceContext(root_dir=os.getcwd())
        self.workspace_context_initialized = False
        self.call_timestamps = deque() # Inicializar call_timestamps
        self.rate_limit_period = 60 # Por ejemplo, 60 segundos
        self.rate_limit_calls = 10 # Por ejemplo, 10 llamadas por período
        self.generation_params = {"temperature": 0.7, "top_p": 0.95, "top_k": 40} # Parámetros de generación por defecto
        self.tool_execution_lock = threading.Lock() # Inicializar el lock
        self.active_tool_future = None # Inicializar la referencia a la tarea activa
        self.tool_executor = ThreadPoolExecutor(max_workers=1) # Inicializar el ThreadPoolExecutor
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
                            "id": tc.get("id", str(uuid.uuid4())),
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

    def _to_litellm_message(self, message: Union[HumanMessage, AIMessage, ToolMessage]) -> Dict[str, Any]:
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

                    serialized_tool_calls.append({
                        "id": tc_id,
                        "function": {
                            "name": tc_name,
                            "arguments": json.dumps(tc_args)
                        }
                    })
                return {"role": "assistant", "content": message.content, "tool_calls": serialized_tool_calls}
            return {"role": "assistant", "content": message.content}
        elif isinstance(message, ToolMessage):
            content = message.content
            return {"role": "tool", "content": content, "tool_call_id": message.tool_call_id}
        elif isinstance(message, SystemMessage):
            return {"role": "system", "content": message.content}
        return {"role": "user", "content": str(message)} # Fallback



    def _truncate_messages(self, messages: List[Union[HumanMessage, AIMessage, ToolMessage]]) -> List[Union[HumanMessage, AIMessage, ToolMessage]]:
        # Implementación de truncamiento de mensajes
        # ... (la lógica de truncamiento se mantiene igual)
        return messages

    def _get_token_count(self, text: str) -> int:
        return len(self.tokenizer.encode(text))

    def _save_history(self, history: List[Union[HumanMessage, AIMessage, ToolMessage]]):
        """Método de compatibilidad que delega al history_manager."""
        self.history_manager._save_history(history)

    def _load_history(self) -> List[Union[HumanMessage, AIMessage, ToolMessage]]:
        """Método de compatibilidad que delega al history_manager."""
        return self.history_manager._load_history()

    def invoke(self, messages: List[Union[HumanMessage, AIMessage, ToolMessage]]) -> Generator[str, None, None]:
        # Implementación de invocación del LLM
        # ... (la lógica de invocación se mantiene igual)
        yield ""

    def summarize_conversation_history(self) -> str:
        # Implementación de resumen de historial
        # ... (la lógica de resumen se mantiene igual)
        return ""

    def get_tool(self, tool_name: str) -> BaseTool:
        return self.tool_map.get(tool_name)

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
                memory_init_tool.invoke({"history_file_path": self.history_file_path})
            except Exception as e:
                # print(f"Advertencia: Error al inicializar la memoria: {e}", file=sys.stderr)
                pass # No es crítico si falla la inicialización de memoria



    def invoke(self, history: List[BaseMessage] = None, system_message: str = None, interrupt_queue: Optional[queue.Queue] = None, save_history: bool = True) -> Generator[Union[AIMessage, str], None, None]:
        """
        Invoca al modelo LLM con el historial proporcionado o el interno.
        
        Args:
            history: Historial explícito (opcional).
            system_message: Mensaje de sistema (opcional).
            interrupt_queue: Cola para interrupciones (opcional).
            save_history: Si es True, guarda el historial procesado. Si es False, no modifica el historial persistente.
        """
        # Siempre usar self.conversation_history (el historial persistente) como la fuente de verdad
        # A MENOS que se pase un historial explícito que queramos procesar (aunque idealmente deberían estar sincronizados)
        if history is not None:
             messages_to_process = history
             # Si se pasa un historial explícito, intentamos sincronizar el interno si son diferentes objetos
             if history is not self.conversation_history:
                 # Opción A: Actualizar el interno con el externo (peligroso si el externo es parcial)
                 # Opción B: Usar el externo para este turno pero no persistir si save_history=False
                 # Asumiremos que si se pasa history, es el que se debe usar.
                 pass
        else:
            messages_to_process = self.conversation_history
        
        # Convertir a formato LiteLLM para el procesamiento
        messages_litellm = [self._to_litellm_message(msg) for msg in messages_to_process]
        
        # 1. Procesar historial (resumen, truncamiento, etc.)
        processed_history = self.history_manager.get_processed_history_for_llm(
            llm_service_summarize_method=self.summarize_conversation_history,
            max_history_messages=self.max_conversation_tokens // 100, # Estimación burda
            max_history_chars=self.max_conversation_tokens * 4, # Estimación burda
            console=self.console,
            save_history=save_history, # Propagar flag
            history=messages_to_process # <<--- PASAR EL HISTORIAL EXPLÍCITO
        )
        
        # Logging de diagnóstico para verificar el procesamiento del historial

        
        current_time = time.time()
        while self.call_timestamps and self.call_timestamps[0] <= current_time - self.rate_limit_period:
            self.call_timestamps.popleft()

        if len(self.call_timestamps) >= self.rate_limit_calls:
            time_to_wait = self.rate_limit_period - (current_time - self.call_timestamps[0])
            if time_to_wait > 0:
                print(f"DEBUG: Rate limit hit. Waiting for {time_to_wait:.2f} seconds...", file=sys.stderr)
                time.sleep(time_to_wait)
                current_time = time.time()
                print(f"DEBUG: Finished waiting for rate limit.", file=sys.stderr)
                while self.call_timestamps and self.call_timestamps[0] <= current_time - self.rate_limit_period:
                    self.call_timestamps.popleft()


        self.stop_generation_flag = False

        # 1. Construir todos los mensajes de sistema iniciales
        all_initial_system_messages_for_llm = []
        
        # IMPORTANTE: Extraer SystemMessages del historial procesado primero
        # Esto incluye el SYSTEM_MESSAGE del bash_agent que define la identidad de KogniTerm
        system_messages_from_history = [msg for msg in processed_history if isinstance(msg, SystemMessage)]
        for sys_msg in system_messages_from_history:
            all_initial_system_messages_for_llm.append(self._to_litellm_message(sys_msg))
        
        # Añadir el contexto dinámico del espacio de trabajo si está disponible
        workspace_context_message = self._build_llm_context_message()
        if workspace_context_message:
            all_initial_system_messages_for_llm.append(self._to_litellm_message(workspace_context_message))

        # Instrucción para el LLM sobre cómo manejar las confirmaciones de herramientas
        tool_confirmation_instruction = (
            "Cuando recibas un ToolMessage con un 'status: \"requires_confirmation\"', "
            "analiza cuidadosamente el 'diff' y la 'action_description'. "
            "Si la acción es segura y deseada, responde con un ToolMessage que contenga "
            "el 'tool_name' y los 'args' originales de la herramienta, pero con 'confirm: True'. "
            "Si la acción no es segura o no es deseada, responde con un mensaje de texto explicando por qué la deniegas. "
            "Siempre prioriza la seguridad y la intención del usuario. "
            "**IMPORTANTE:** Si un ToolMessage indica que una herramienta se ejecutó con éxito, considera esa acción como completada y no la anuncies ni la propongas de nuevo en tu siguiente respuesta. Continúa con el siguiente paso de la tarea."
        )

        if all_initial_system_messages_for_llm and all_initial_system_messages_for_llm[0]["role"] == "system":
            all_initial_system_messages_for_llm[0]["content"] += f"\n\n{tool_confirmation_instruction}"
        else:
            all_initial_system_messages_for_llm.append({"role": "system", "content": tool_confirmation_instruction})

        if system_message:
            # Si ya hay un system_message del workspace_context o la instrucción de confirmación, concatenar el system_message proporcionado
            if all_initial_system_messages_for_llm and all_initial_system_messages_for_llm[0]["role"] == "system":
                all_initial_system_messages_for_llm[0]["content"] += f"\n\n{system_message}"
            else:
                all_initial_system_messages_for_llm.append({"role": "system", "content": system_message})
        
        # 2. Convertir el historial de conversación procesado (EXCLUYENDO los SystemMessages ya extraídos)
        # IMPORTANTE: Usar processed_history que ya fue procesado por history_manager
        litellm_conversation_history = [self._to_litellm_message(msg) for msg in processed_history if not isinstance(msg, SystemMessage)]

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

        # NOTA: La siguiente lógica de truncamiento y resumen está COMENTADA porque ahora usamos
        # processed_history que ya fue procesado por history_manager.get_processed_history_for_llm()
        # Esta lógica duplicada causaba que el historial procesado se ignorara.
        # Si se necesita procesamiento adicional en el futuro, debe hacerse en history_manager.
        
        # # 5. Lógica de truncamiento y resumen del historial
        # # Definir un mínimo de mensajes a mantener, que incluya todos los system messages + al menos 1 conversacional
        # min_messages_to_keep_in_conversation = 1 # Mínimo de mensajes conversacionales a intentar mantener
        # 
        # # Contar los mensajes actuales en el historial de conversación (excluyendo system messages)
        # current_conversation_messages_count = len(filtered_conversation_messages)
        #
        # # Truncamiento/Resumen basado en `filtered_conversation_messages`
        # # La lógica de resumen debe operar sobre `self.conversation_history` (LangChain messages)
        # # y no debe afectar `all_initial_system_messages_for_llm`.
        # 
        # # Calculamos la longitud total de `litellm_messages` (incluyendo system messages) para la decisión de resumen/truncamiento
        # total_litellm_messages_length = sum(len(json.dumps(msg, ensure_ascii=False)) for msg in litellm_messages)
        # 
        # if (len(filtered_conversation_messages) > self.max_history_messages or
        #     total_litellm_messages_length > self.max_history_chars) and \
        #    len(filtered_conversation_messages) > min_messages_to_keep_in_conversation:
        #     
        #     if self.console:
        #         self.console.print("[yellow]El historial de conversación es demasiado largo. Intentando resumir...[/yellow]")
        #     
        #     summary = self.summarize_conversation_history() # Opera en self.conversation_history
        #     if summary:
        #         max_summary_length = min(2000, self.max_history_chars // 4)
        #         if len(summary) > max_summary_length:
        #             summary = summary[:max_summary_length] + "... [Resumen truncado para evitar bucles]"
        #
        #         # El nuevo historial de conversación incluirá el resumen y los últimos mensajes relevantes.
        #         new_conversation_history_litellm = []
        #         new_conversation_history_litellm.append(self._to_litellm_message({"role": "system", "content": f"Resumen de la conversación anterior: {summary}"}))
        #         
        #         # Identificar todos los pares AIMessage/ToolMessage en el historial completo
        #         tool_call_pairs = []
        #         for i, msg in enumerate(filtered_conversation_messages):
        #             if msg.get('role') == 'assistant' and msg.get('tool_calls'):
        #                 tool_call_id = msg['tool_calls'][0]['id'] # Asumiendo un solo tool_call por AIMessage
        #                 # Buscar el ToolMessage correspondiente
        #                 for j in range(i + 1, len(filtered_conversation_messages)):
        #                     next_msg = filtered_conversation_messages[j]
        #                     if next_msg.get('role') == 'tool' and next_msg.get('tool_call_id') == tool_call_id:
        #                         tool_call_pairs.append((msg, next_msg))
        #                         break
        #         
        #         # Identificar todos los pares AIMessage/ToolMessage en el historial completo
        #         # y reconstruir el historial para mantenerlos juntos.
        #         temp_filtered_conversation_messages = []
        #         i = 0
        #         while i < len(filtered_conversation_messages):
        #             msg = filtered_conversation_messages[i]
        #             temp_filtered_conversation_messages.append(msg)
        #             if msg.get('role') == 'assistant' and msg.get('tool_calls'):
        #                 tool_call_id = msg['tool_calls'][0]['id'] # Asumiendo un solo tool_call por AIMessage
        #                 # Buscar el ToolMessage correspondiente inmediatamente después
        #                 if i + 1 < len(filtered_conversation_messages) and \
        #                    filtered_conversation_messages[i+1].get('role') == 'tool' and \
        #                    filtered_conversation_messages[i+1].get('tool_call_id') == tool_call_id:
        #                     temp_filtered_conversation_messages.append(filtered_conversation_messages[i+1])
        #                     i += 1 # Saltar el ToolMessage ya añadido
        #             i += 1
        #
        #         # Ahora, `temp_filtered_conversation_messages` contiene los pares de tool_calls juntos.
        #         # Necesitamos truncar esto para que quepa en el historial.
        #         # Priorizamos los mensajes más recientes y los pares de tool_calls.
        #         
        #         # Invertir para procesar desde los más recientes
        #         reversed_temp_filtered_conversation_messages = list(reversed(temp_filtered_conversation_messages))
        #         
        #         final_conversational_messages = []
        #         current_length = 0
        #         
        #         for msg in reversed_temp_filtered_conversation_messages:
        #             msg_len = len(json.dumps(msg, ensure_ascii=False))
        #             
        #             # Si añadir este mensaje excede el límite, y no es un mensaje de tool_call
        #             # o su AIMessage correspondiente ya ha sido añadido, entonces no lo añadimos.
        #             if current_length + msg_len > self.max_history_chars and \
        #                len(final_conversational_messages) >= self.max_history_messages:
        #                 break
        #             
        #             final_conversational_messages.insert(0, msg)
        #             current_length += msg_len
        #             
        #             # Si el mensaje actual es un ToolMessage, asegurarnos de que su AIMessage esté presente
        #             if msg.get('role') == 'tool':
        #                 tool_call_id = msg.get('tool_call_id')
        #                 found_ai_message = False
        #                 for prev_msg in final_conversational_messages[:-1]: # Buscar en los ya añadidos
        #                     if prev_msg.get('role') == 'assistant' and prev_msg.get('tool_calls'):
        #                         for tc in prev_msg['tool_calls']:
        #                             if tc.get('id') == tool_call_id:
        #                                 found_ai_message = True
        #                                 break
        #                     if found_ai_message:
        #                         break
        #                 
        #                 if not found_ai_message:
        #                     # Si el AIMessage no está, buscarlo en el historial original y añadirlo
        #                     for original_msg in reversed_temp_filtered_conversation_messages:
        #                         if original_msg.get('role') == 'assistant' and original_msg.get('tool_calls'):
        #                             for tc in original_msg['tool_calls']:
        #                                 if tc.get('id') == tool_call_id:
        #                                     final_conversational_messages.insert(0, original_msg)
        #                                     current_length += len(json.dumps(original_msg, ensure_ascii=False))
        #                                     break
        #                             break
        #         
        #         new_conversation_history_litellm.extend(final_conversational_messages)
        #
        #         # Actualizar `litellm_messages` con los system messages iniciales y el nuevo historial resumido
        #         litellm_messages = all_initial_system_messages_for_llm + new_conversation_history_litellm
        #
        #         # Actualizar self.conversation_history para reflejar el resumen (en formato LangChain)
        #         # Esto es crucial para futuras llamadas a summarize_conversation_history
        #         # Solo guardamos el historial de conversación real, no los mensajes de contexto dinámicos.
        #         self.conversation_history = [self._from_litellm_message(msg) for msg in new_conversation_history_litellm]
        #         self._save_history(self.conversation_history) # Guardar el historial de conversación resumido
        #         if self.console:
        #             self.console.print("[green]Historial resumido y actualizado.[/green]")
        #     else:
        #         if self.console:
        #             self.console.print("[red]No se pudo resumir el historial. Se procederá con el truncamiento.[/red]")
 
        # Post-procesamiento del historial para eliminar ToolMessages huérfanos
        # ELIMINADO: Esta lógica ahora es manejada por history_manager.get_processed_history_for_llm()
        # Mantener litellm_messages tal cual viene del history_manager
        pass

        # NOTA: El siguiente truncamiento estándar también está COMENTADO porque es redundante.
        # El processed_history ya fue truncado por history_manager.get_processed_history_for_llm()
        
        # # Truncamiento estándar si aún es necesario después del resumen
        # # Ahora, solo truncamos la parte conversacional, manteniendo los system messages iniciales.
        # current_conversational_messages = [msg for msg in litellm_messages if msg.get('role') != 'system']
        # 
        # # Recalcular la longitud total de los mensajes para el truncamiento final
        # total_litellm_messages_length = sum(len(json.dumps(msg, ensure_ascii=False)) for msg in (all_initial_system_messages_for_llm + current_conversational_messages))
        #
        # while (len(current_conversational_messages) > self.max_history_messages or
        #        total_litellm_messages_length > self.max_history_chars) and \
        #       len(current_conversational_messages) > min_messages_to_keep_in_conversation:
        #     
        #     # Remove from the oldest conversational messages
        #     if current_conversational_messages:
        #         removed_msg = current_conversational_messages.pop(0)
        #         # Recalculate total length for the next iteration
        #         total_litellm_messages_length = sum(len(json.dumps(msg, ensure_ascii=False)) for msg in (all_initial_system_messages_for_llm + current_conversational_messages))
        #     else:
        #         break # No conversational messages left to truncate
        #
        # # Reconstruct litellm_messages with the truncated conversational part
        # litellm_messages = all_initial_system_messages_for_llm + current_conversational_messages

        # Lógica adicional para asegurar que el último AIMessage con tool_calls y su ToolMessage estén presentes
        if litellm_messages and litellm_messages[-1].get('role') == 'tool':
            last_tool_message = litellm_messages[-1]
            tool_call_id_of_last_tool_message = last_tool_message.get('tool_call_id')
            
            found_ai_message_for_tool = False
            # Buscar el AIMessage correspondiente en todo el historial
            for msg in reversed(litellm_messages[:-1]):
                if msg.get('role') == 'assistant' and msg.get('tool_calls'):
                    for tc in msg['tool_calls']:
                        if tc.get('id') == tool_call_id_of_last_tool_message:
                            found_ai_message_for_tool = True
                            break
                if found_ai_message_for_tool:
                    break
            
            # Si no se encuentra el AIMessage, es más seguro eliminar el ToolMessage huérfano
            if not found_ai_message_for_tool:
                litellm_messages.pop()


        # Eliminar el último mensaje si es un AIMessage vacío, ya que puede causar problemas.
        if litellm_messages and litellm_messages[-1].get('role') == 'assistant' and not litellm_messages[-1].get('content') and not litellm_messages[-1].get('tool_calls'):
            litellm_messages.pop()

        try:
            completion_kwargs = {
                "model": self.model_name,
                "messages": litellm_messages, # Usar el historial final procesado
                "tools": self.litellm_tools,
                "stream": True,
                "api_key": self.api_key, # Pasar la API Key directamente
                "temperature": self.generation_params.get("temperature", 0.7),
                # Añadir reintentos para errores 503 y otros errores de servidor
                "num_retries": 5,
                "retry_strategy": "exponential_backoff_retry",
            }
            if "top_p" in self.generation_params:
                completion_kwargs["top_p"] = self.generation_params["top_p"]
            if "top_k" in self.generation_params:
                completion_kwargs["top_k"] = self.generation_params["top_k"]

            logger.debug(f"DEBUG: Mensajes finales enviados a LiteLLM: {json.dumps(litellm_messages, indent=2, ensure_ascii=False)}")
    
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
                    print("DEBUG: Generación detenida por bandera.", file=sys.stderr)
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
                        
                        # Actualizar el ID si está presente en el chunk, si no generar uno nuevo si es el inicio
                        if getattr(tc, 'id', None) is not None:
                            tool_calls[tc.index]["id"] = tc.id
                        elif not tool_calls[tc.index]["id"]:
                             tool_calls[tc.index]["id"] = str(uuid.uuid4())
                        
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
                yield AIMessage(content=full_response_content, tool_calls=formatted_tool_calls)
            else:
                # El AIMessage final incluye solo el contenido acumulado
                yield AIMessage(content=full_response_content)

        except Exception as e:
            import traceback
            print(f"Error de LiteLLM: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            error_message = f"¡Ups! 😵 Ocurrió un error inesperado al comunicarme con el modelo (LiteLLM): {e}. Por favor, revisa los logs para más detalles. ¡Intentemos de nuevo!"""
            yield AIMessage(content=error_message)

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

    def get_tool(self, tool_name: str) -> BaseTool | None:
        """Encuentra y devuelve una herramienta de LangChain por su nombre."""
        return self.tool_manager.get_tool(tool_name)

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
                        print("DEBUG: _invoke_tool_with_interrupt - Interrupción detectada en la cola (via TimeoutError).", file=sys.stderr)
                        self.interrupt_queue.get()
                        if future.running():
                            print("DEBUG: _invoke_tool_with_interrupt - Intentando cancelar la tarea (via TimeoutError).", file=sys.stderr)
                            future.cancel()
                            print("DEBUG: _invoke_tool_with_interrupt - Lanzando InterruptedError (via TimeoutError).", file=sys.stderr)
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
