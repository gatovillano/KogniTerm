import os
import sys
import time
import json
import queue
from typing import Optional, Any
from collections import deque
from langchain_core.tools import BaseTool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from litellm import completion, litellm
import uuid
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, TimeoutError # Nuevas importaciones
import threading # Nueva importación

load_dotenv()

from .tools.tool_manager import get_callable_tools

def _to_litellm_message(message):
    """Convierte un mensaje de LangChain a un formato compatible con LiteLLM."""
    if isinstance(message, HumanMessage):
        return {"role": "user", "content": message.content}
    elif isinstance(message, AIMessage):
        if message.tool_calls:
            litellm_tool_calls = []
            for tc in message.tool_calls:
                # Asegurarse de que el ID de la herramienta se propague correctamente
                tool_call_id = tc.get("id", str(uuid.uuid4()))
                litellm_tool_calls.append({
                    "id": tool_call_id,
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc["args"])
                    }
                })
            content = message.content if message.content is not None else ""
            return {"role": "assistant", "content": content, "tool_calls": litellm_tool_calls}
        else:
            return {"role": "assistant", "content": message.content}
    elif isinstance(message, ToolMessage):
        tool_call_id = message.tool_call_id if message.tool_call_id is not None else str(uuid.uuid4())
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": message.content
        }
    elif isinstance(message, SystemMessage):
        return {"role": "system", "content": message.content}
    else:
        raise ValueError(f"Tipo de mensaje desconocido para LiteLLM: {type(message)}")

def _convert_langchain_tool_to_litellm(tool: BaseTool) -> dict:
    """Convierte una herramienta de LangChain (BaseTool) a un formato compatible con LiteLLM."""
    args_schema = {"type": "object", "properties": {}}
    if hasattr(tool, 'args_schema') and tool.args_schema is not None:
        if hasattr(tool.args_schema, 'schema'):
            schema_method = getattr(tool.args_schema, 'schema', None)
            if callable(schema_method):
                try:
                    args_schema = schema_method()
                except Exception as e:
                    tool_name = getattr(tool, 'name', 'Desconocido')
                    tool_type = type(tool)
                    print(f"Advertencia: Error al obtener el esquema de la herramienta '{tool_name}' de tipo '{tool_type}': {e}. Se usará un esquema vacío.", file=sys.stderr)
            else:
                tool_name = getattr(tool, 'name', 'Desconocido')
                tool_type = type(tool)
                print(f"Advertencia: 'args_schema' de la herramienta '{tool_name}' de tipo '{tool_type}' no tiene un método 'schema' invocable. Se usará un esquema vacío.", file=sys.stderr)
        elif isinstance(tool.args_schema, dict):
            args_schema = tool.args_schema
        else:
            tool_name = getattr(tool, 'name', 'Desconocido')
            tool_type = type(tool)
            print(f"Advertencia: La herramienta '{tool_name}' de tipo '{tool_type}' tiene un 'args_schema' de tipo inesperado ({type(tool.args_schema)}). Se usará un esquema vacío.", file=sys.stderr)

    # Asegurarse de que cada propiedad en args_schema['properties'] tenga un 'type'
    if 'properties' in args_schema:
        for prop_name, prop_details in args_schema['properties'].items():
            if 'type' not in prop_details:
                # Intentar inferir el tipo o establecer un valor predeterminado
                # Por ahora, estableceremos 'string' como predeterminado si falta
                args_schema['properties'][prop_name]['type'] = 'string'
    
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": args_schema
        }
    }

class LLMService:
    """Un servicio para interactuar con el modelo LLM a través de LiteLLM."""
    def __init__(self, interrupt_queue: Optional[queue.Queue] = None):
        self.console = None
        self.api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            print("Error: Ninguna de las variables de entorno OPENROUTER_API_KEY o GOOGLE_API_KEY está configurada.", file=sys.stderr)
            raise ValueError("Ninguna de las variables de entorno OPENROUTER_API_KEY o GOOGLE_API_KEY está configurada.")
        
        self.interrupt_queue = interrupt_queue # Guardar la cola de interrupción
        self.tool_executor = ThreadPoolExecutor(max_workers=1) # Ejecutor para herramientas
        self.active_tool_future = None # Para rastrear la ejecución de la herramienta activa
        self.tool_execution_lock = threading.Lock() # Para sincronizar el acceso a active_tool_future

        litellm_api_base = os.getenv("LITELLM_API_BASE")
        if litellm_api_base:
            litellm.api_base = litellm_api_base

        configured_model = os.getenv("LITELLM_MODEL")
        if not configured_model:
            configured_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
            if not configured_model.startswith("gemini/"):
                configured_model = f"gemini/{configured_model}"
        else:
            # Si LITELLM_MODEL está configurado, verificar si ya tiene un prefijo de proveedor
            known_prefixes = ("gemini/", "openai/", "openrouter/", "ollama/", "azure/", "anthropic/", "cohere/", "huggingface/")
            if not configured_model.startswith(known_prefixes):
                # Si no tiene un prefijo conocido, y el error sugiere OpenRouter, añadirlo.
                configured_model = f"openrouter/{configured_model}"
        self.model_name = configured_model

        self.langchain_tools = get_callable_tools(llm_service_instance=self, interrupt_queue=self.interrupt_queue)

        self.litellm_tools = [_convert_langchain_tool_to_litellm(tool) for tool in self.langchain_tools]

        self.generation_params = {
            "temperature": 0.4,
            # "top_p": 0.95, # Descomentar si se desea usar nucleous sampling
            # "top_k": 40,   # Descomentar si se desea usar top-k sampling
        }

        self.call_timestamps = deque()
        self.rate_limit_calls = 10
        self.rate_limit_period = 60

        self.max_history_chars = 120000 # Aumentado para permitir más historial antes de resumir
        self.max_history_messages = 200 # Aumentado para permitir más mensajes antes de resumir
        self.stop_generation_flag = False # Bandera para detener la generación
        self.history_file_path: Optional[str] = None # Se inicializará con set_cwd_for_history
        self.conversation_history = [] # Inicializar vacío, se cargará con set_cwd_for_history

        # No llamar a _initialize_memory o _load_history aquí, se hará en set_cwd_for_history

    def set_console(self, console):
        """Establece la consola para el streaming de salida."""
        self.console = console

    def set_cwd_for_history(self, cwd: str):
        """
        Establece el directorio de trabajo actual y actualiza la ruta del archivo de historial.
        Carga el historial específico para este directorio.
        """
        kogniterm_dir = os.path.join(cwd, ".kogniterm")
        os.makedirs(kogniterm_dir, exist_ok=True)
        self.history_file_path = os.path.join(kogniterm_dir, "kogniterm_history.json")
        self._initialize_memory() # Inicializar memoria para el nuevo directorio
        self.conversation_history = self._load_history() # Cargar historial para el nuevo directorio
        if self.console:
            self.console.print(f"[dim]Historial cargado desde: {self.history_file_path}[/dim]")

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

    def _load_history(self) -> list:
        """Carga el historial de conversación desde un archivo JSON."""
        if not self.history_file_path:
            return [] # No hay ruta de historial configurada

        if os.path.exists(self.history_file_path):
            try:
                with open(self.history_file_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()
                    if not file_content.strip():
                        return []
                    serializable_history = json.loads(file_content)
                    loaded_history = []
                    for item in serializable_history:
                        if item['type'] == 'human':
                            loaded_history.append(HumanMessage(content=item['content']))
                        elif item['type'] == 'ai':
                            tool_calls = item.get('tool_calls', [])
                            if tool_calls:
                                formatted_tool_calls = []
                                for tc in tool_calls:
                                    if isinstance(tc['args'], dict):
                                        formatted_tool_calls.append({'name': tc['name'], 'args': tc['args'], 'id': tc.get('id')})
                                    else:
                                        try:
                                            parsed_args = json.loads(tc['args'])
                                            formatted_tool_calls.append({'name': tc['name'], 'args': parsed_args, 'id': tc.get('id')})
                                        except (json.JSONDecodeError, TypeError):
                                            print(f"Advertencia: No se pudieron parsear los argumentos de la herramienta: {tc['args']}", file=sys.stderr)
                                            formatted_tool_calls.append({'name': tc['name'], 'args': {}, 'id': tc.get('id')})
                                loaded_history.append(AIMessage(content=item['content'], tool_calls=formatted_tool_calls))
                            else:
                                loaded_history.append(AIMessage(content=item['content']))
                        elif item['type'] == 'tool':
                            loaded_history.append(ToolMessage(content=item['content'], tool_call_id=item['tool_call_id']))
                        elif item['type'] == 'system':
                            loaded_history.append(SystemMessage(content=item['content']))
                        else:
                            pass
                    
                    return loaded_history
            except json.JSONDecodeError as e:
                print(f"Error al decodificar el historial JSON desde {self.history_file_path}: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)
            except Exception as e:
                print(f"Error inesperado al cargar el historial desde {self.history_file_path}: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)
        return []

    def _save_history(self, history: list):
        """Guarda el historial de conversación en un archivo JSON."""
        if not self.history_file_path:
            return # No hay ruta de historial configurada

        try:
            serializable_history = []
            for msg in history:
                if isinstance(msg, HumanMessage):
                    serializable_history.append({'type': 'human', 'content': msg.content})
                elif isinstance(msg, AIMessage):
                    if msg.tool_calls:
                        serializable_history.append({'type': 'ai', 'content': msg.content, 'tool_calls': [{'name': tc['name'], 'args': tc['args'], 'id': tc.get('id')} for tc in msg.tool_calls]})
                    else:
                        serializable_history.append({'type': 'ai', 'content': msg.content})
                elif isinstance(msg, ToolMessage):
                    serializable_history.append({'type': 'tool', 'content': msg.content, 'tool_call_id': msg.tool_call_id})
                elif isinstance(msg, SystemMessage):
                    serializable_history.append({'type': 'system', 'content': msg.content})
                else:
                    continue # Saltar mensajes desconocidos

            with open(self.history_file_path, 'w', encoding='utf-8') as f:
                json.dump(serializable_history, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error al guardar el historial en {self.history_file_path}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)

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
                print(f"DEBUG: Rate limit hit. Waiting for {time_to_wait:.2f} seconds...", file=sys.stderr)
                time.sleep(time_to_wait)
                current_time = time.time()
                print(f"DEBUG: Finished waiting for rate limit.", file=sys.stderr)
                while self.call_timestamps and self.call_timestamps[0] <= current_time - self.rate_limit_period:
                    self.call_timestamps.popleft()

        self.stop_generation_flag = False

        litellm_messages = [_to_litellm_message(msg) for msg in history]

        filtered_messages = []
        for msg in litellm_messages:
            is_assistant = msg.get("role") == "assistant"
            has_content = msg.get("content") and str(msg.get("content")).strip()
            has_tool_calls = msg.get("tool_calls")
            if is_assistant and not has_content and not has_tool_calls:
                continue
            filtered_messages.append(msg)
        litellm_messages = filtered_messages

        if system_message:
            litellm_messages.insert(0, {"role": "system", "content": system_message})

        min_messages_to_keep = 1
        if len(litellm_messages) > min_messages_to_keep:
            if litellm_messages[-1].get('role') == 'tool' and len(litellm_messages) > 1:
                min_messages_to_keep += 2
            else:
                min_messages_to_keep += 1

        # Lógica de truncamiento de historial
        # Nuevo: Intentar resumir el historial si es demasiado largo antes de truncar
        if (len(litellm_messages) > self.max_history_messages or
            sum(len(json.dumps(msg)) for msg in litellm_messages) > self.max_history_chars) and \
           len(litellm_messages) > min_messages_to_keep: # Asegurarse de que haya suficientes mensajes para resumir
            
            if self.console:
                self.console.print("[yellow]El historial es demasiado largo. Intentando resumir...[/yellow]")
            
            summary = self.summarize_conversation_history()
            if summary:
                # Mantener el system message inicial (si existe) y los últimos N mensajes (ej. 5)
                # para no perder el contexto inmediato.
                
                # Identificar el system message inicial
                initial_system_message = None
                if litellm_messages and litellm_messages[0].get('role') == 'system':
                    initial_system_message = litellm_messages[0]
                    # Eliminar el system message del resto de mensajes para la selección de los últimos
                    temp_litellm_messages = litellm_messages[1:]
                else:
                    temp_litellm_messages = litellm_messages
                
                # Seleccionar los últimos 5 mensajes (o menos si no hay tantos)
                messages_to_keep = temp_litellm_messages[-5:] if len(temp_litellm_messages) > 5 else temp_litellm_messages
                
                # Construir el nuevo historial con el system message original, el resumen y los últimos mensajes
                new_litellm_messages = []
                if initial_system_message:
                    new_litellm_messages.append(initial_system_message)
                
                new_litellm_messages.append({"role": "system", "content": f"Resumen de la conversación anterior: {summary}"})
                new_litellm_messages.extend(messages_to_keep)
                litellm_messages = new_litellm_messages
                
                if self.console:
                    self.console.print("[green]Historial resumido y actualizado.[/green]")
            else:
                if self.console:
                    self.console.print("[red]No se pudo resumir el historial. Se procederá con el truncamiento.[/red]")
 
        # Post-procesamiento del historial para eliminar ToolMessages huérfanos
        # Esto es crucial para evitar el error "Missing corresponding tool call" de LiteLLM
        # cuando el resumen elimina el AIMessage que invoca la herramienta.
        processed_litellm_messages = []
        tool_call_ids_in_aimessages = set()
        for i, msg in enumerate(litellm_messages):
            if msg.get('role') == 'assistant' and msg.get('tool_calls'):
                for tc in msg['tool_calls']:
                    if 'id' in tc:
                        tool_call_ids_in_aimessages.add(tc['id'])
            
            if msg.get('role') == 'tool':
                tool_call_id = msg.get('tool_call_id')
                if tool_call_id and tool_call_id not in tool_call_ids_in_aimessages:
                    continue # Eliminar ToolMessage huérfano
            
            processed_litellm_messages.append(msg)
        litellm_messages = processed_litellm_messages

        # Truncamiento estándar si aún es necesario después del resumen
        while len(litellm_messages) > self.max_history_messages and len(litellm_messages) > min_messages_to_keep:
            if litellm_messages[0].get('role') == 'system' and len(litellm_messages) > 1:
                litellm_messages.pop(1)
            else:
                litellm_messages.pop(0)

        current_chars = sum(len(json.dumps(msg)) for msg in litellm_messages)
        while current_chars > self.max_history_chars and len(litellm_messages) > min_messages_to_keep:
            if litellm_messages[0].get('role') == 'system' and len(litellm_messages) > 1:
                removed_msg = litellm_messages.pop(1)
            else:
                removed_msg = litellm_messages.pop(0)
            current_chars -= len(json.dumps(removed_msg))

        try:
            completion_kwargs = {
                "model": self.model_name,
                "messages": litellm_messages,
                "tools": self.litellm_tools,
                "stream": True,
                "api_key": self.api_key,
                "temperature": self.generation_params.get("temperature", 0.7),
            }
            if "top_p" in self.generation_params:
                completion_kwargs["top_p"] = self.generation_params["top_p"]
            if "top_k" in self.generation_params:
                completion_kwargs["top_k"] = self.generation_params["top_k"]

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
                    print(f"DEBUG: Tool calls from delta: {tool_calls_from_delta}", file=sys.stderr)
                    # Acumular tool_calls, no emitir AIMessage aquí
                    for tc in tool_calls_from_delta:
                        if tc.index >= len(tool_calls):
                            tool_calls.extend([{"id": "", "function": {"name": "", "arguments": ""}}] * (tc.index - len(tool_calls) + 1))
                        
                        # Solo actualizar el ID si no está vacío y es diferente, o si es la primera vez que se asigna
                        if getattr(tc, 'id', None) is not None and (not tool_calls[tc.index]["id"] or tool_calls[tc.index]["id"] != tc.id):
                            tool_calls[tc.index]["id"] = tc.id
                        if getattr(tc, 'function', None) is not None:
                            if getattr(tc.function, 'name', None) is not None:
                                tool_calls[tc.index]["function"]["name"] = tc.function.name
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

    def summarize_conversation_history(self) -> Optional[str]:
        """Resume el historial de conversación actual utilizando el modelo LLM a través de LiteLLM."""
        if not self.conversation_history:
            return None
 
        summarize_prompt = HumanMessage(content="Por favor, resume la siguiente conversación de manera EXHAUSTIVA, DETALLADA y EXTENSA. Captura todos los puntos clave, decisiones tomadas, tareas pendientes y cualquier información relevante que pueda ser útil para retomar la conversación con el contexto completo. El resumen debe ser lo más completo posible y actuar como un reemplazo fiel del historial para la comprensión del LLM en el futuro.")
        
        temp_history_for_summary = self.conversation_history + [summarize_prompt]

        try:
            litellm_messages_for_summary = [_to_litellm_message(msg) for msg in temp_history_for_summary]
            
            litellm_generation_params = self.generation_params

            summary_completion_kwargs = {
                "model": self.model_name,
                "messages": litellm_messages_for_summary,
                "api_key": self.api_key,
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
            if hasattr(response, 'choices') and response.choices and len(response.choices) > 0:
                # Acceder directamente al atributo 'choices' una vez que se ha verificado su existencia
                choices = response.choices
                if isinstance(choices, list) and len(choices) > 0:
                    first_choice = choices[0]
                    # Verificar si 'message' es un atributo y si tiene 'content'
                    if hasattr(first_choice, 'message') and hasattr(first_choice.message, 'content'):
                        summary_text = first_choice.message.content
                        return summary_text
            return None
        except Exception as e:
            import traceback
            print(f"Error de LiteLLM al resumir el historial: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return f"¡Ups! 😵 Ocurrió un error inesperado al resumir el historial con LiteLLM: {e}. Por favor, revisa los logs para más detalles. ¡Intentemos de nuevo!"""

    def get_tool(self, tool_name: str) -> BaseTool | None:
        """Encuentra y devuelve una herramienta de LangChain por su nombre."""
        for tool in self.langchain_tools:
            if tool.name == tool_name:
                return tool
        return None

    def _invoke_tool_with_interrupt(self, tool: BaseTool, tool_args: dict) -> Any:
        """Invoca una herramienta en un hilo separado, permitiendo la interrupción."""
        with self.tool_execution_lock:
            if self.active_tool_future is not None and self.active_tool_future.running():
                raise RuntimeError("Ya hay una herramienta en ejecución. No se puede iniciar otra.")
            
            # Usar functools.partial para pasar los argumentos a tool.invoke
            # Esto asegura que la función que se ejecuta en el hilo sea simple y reciba los args correctos
            future = self.tool_executor.submit(tool.invoke, tool_args)
            self.active_tool_future = future

        try:
            while True:
                try:
                    # Esperar el resultado de la tarea con un timeout corto
                    return future.result(timeout=0.01) 
                except TimeoutError:
                    # Si hay un timeout, verificar la cola de interrupción
                    if self.interrupt_queue and not self.interrupt_queue.empty():
                        print("DEBUG: _invoke_tool_with_interrupt - Interrupción detectada en la cola (via TimeoutError).", file=sys.stderr)
                        self.interrupt_queue.get() # Consumir la señal
                        if future.running():
                            print("DEBUG: _invoke_tool_with_interrupt - Intentando cancelar la tarea (via TimeoutError).", file=sys.stderr)
                            future.cancel() # Intentar cancelar la tarea
                            print("DEBUG: _invoke_tool_with_interrupt - Lanzando InterruptedError (via TimeoutError).", file=sys.stderr)
                            raise InterruptedError("Ejecución de herramienta interrumpida por el usuario.")
                except InterruptedError:
                    raise # Re-lanzar la excepción de interrupción
                except Exception as e:
                    # Capturar cualquier otra excepción de la herramienta
                    raise e
        except InterruptedError:
            raise # Re-lanzar la excepción de interrupción
        except Exception as e:
            # Capturar cualquier otra excepción de la herramienta
            raise e
        finally:
            with self.tool_execution_lock:
                if self.active_tool_future is future:
                    self.active_tool_future = None # Limpiar la referencia a la tarea activa
