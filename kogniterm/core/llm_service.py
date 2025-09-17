import os
import sys
import time
import json
from typing import Optional
from collections import deque
from langchain_core.tools import BaseTool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from litellm import completion, litellm
import uuid

from .tools.tool_manager import get_callable_tools

KOGNITERM_DIR = os.path.join(os.getcwd(), ".kogniterm")
HISTORY_FILE = os.path.join(KOGNITERM_DIR, "kogniterm_history.json")

def _to_litellm_message(message):
    """Convierte un mensaje de LangChain a un formato compatible con LiteLLM."""
    if isinstance(message, HumanMessage):
        return {"role": "user", "content": message.content}
    elif isinstance(message, AIMessage):
        if message.tool_calls:
            litellm_tool_calls = []
            for tc in message.tool_calls:
                litellm_tool_calls.append({
                    "id": tc.get("id", str(uuid.uuid4())),
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
        # Asegurarse de que tool_call_id es una cadena. Si es None, usar una cadena vacía o generar una.
        # El error "Missing corresponding tool call for tool response message" sugiere que el tool_call_id
        # en el ToolMessage no está siendo reconocido por LiteLLM. Esto puede ser porque no coincide
        # con un ID de tool_call generado por LiteLLM previamente.
        # La forma correcta es que el ToolMessage.tool_call_id sea el ID de la tool_call
        # que LiteLLM generó en el AIMessage anterior.
        # Si message.tool_call_id es None o no es válido, LiteLLM no puede emparejarlo.
        tool_call_id = message.tool_call_id if message.tool_call_id is not None else ""
        return {
            "role": "tool",
            "tool_call_id": str(tool_call_id),
            "content": message.content
        }
    elif isinstance(message, SystemMessage):
        return {"role": "system", "content": message.content}
    else:
        raise ValueError(f"Tipo de mensaje desconocido para LiteLLM: {type(message)}")

def _convert_langchain_tool_to_litellm(tool: BaseTool) -> dict:
    """Convierte una herramienta de LangChain (BaseTool) a un formato compatible con LiteLLM."""
    # Intentar obtener el esquema de argumentos. Algunas herramientas pueden no tener un args_schema
    # o su args_schema puede no tener un método .schema().
    args_schema = {"type": "object", "properties": {}} # Esquema predeterminado vacío
    if hasattr(tool, 'args_schema') and tool.args_schema is not None:
        if hasattr(tool.args_schema, 'schema'):
            try:
                args_schema = tool.args_schema.schema()
            except Exception as e:
                tool_name = getattr(tool, 'name', 'Desconocido')
                tool_type = type(tool)
                print(f"Advertencia: Error al obtener el esquema de la herramienta '{tool_name}' de tipo '{tool_type}': {e}. Se usará un esquema vacío.", file=sys.stderr)
        elif isinstance(tool.args_schema, dict):
            # Si args_schema ya es un diccionario, usarlo directamente
            args_schema = tool.args_schema
        else:
            tool_name = getattr(tool, 'name', 'Desconocido')
            tool_type = type(tool)
            print(f"Advertencia: La herramienta '{tool_name}' de tipo '{tool_type}' tiene un 'args_schema' de tipo inesperado ({type(tool.args_schema)}). Se usará un esquema vacío.", file=sys.stderr)

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
    def __init__(self):
        self.console = None
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("Error: La variable de entorno GOOGLE_API_KEY no está configurada.", file=sys.stderr)
            raise ValueError("La variable de entorno GOOGLE_API_KEY no está configurada.")

        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        if not self.model_name.startswith("gemini/"):
            self.model_name = f"gemini/{self.model_name}"

        self.langchain_tools = get_callable_tools(llm_service_instance=self)

        self.litellm_tools = [_convert_langchain_tool_to_litellm(tool) for tool in self.langchain_tools]

        self.generation_params = {
            "temperature": 0.4,
            # "top_p": 0.95, # Descomentar si se desea usar nucleous sampling
            # "top_k": 40,   # Descomentar si se desea usar top-k sampling
        }

        self.call_timestamps = deque()
        self.rate_limit_calls = 10
        self.rate_limit_period = 60

        self.max_history_chars = 60000
        self.max_history_messages = 100
        self.stop_generation_flag = False # Bandera para detener la generación

        # Asegurarse de que el directorio .kogniterm exista
        os.makedirs(KOGNITERM_DIR, exist_ok=True)

        self._initialize_memory()
        self.conversation_history = self._load_history()
        print(f"DEBUG: LLMService.__init__ - Historial cargado inicialmente: {len(self.conversation_history)} mensajes")

    def set_console(self, console):
        """Establece la consola para el streaming de salida."""
        self.console = console

    def _initialize_memory(self):
        """Inicializa la memoria si no existe."""
        memory_init_tool = self.get_tool("memory_init")
        if memory_init_tool:
            try:
                memory_init_tool.invoke({})
            except Exception as e:
                pass

    def _load_history(self) -> list:
        """Carga el historial de conversación desde un archivo JSON."""
        
        if os.path.exists(HISTORY_FILE):
            print(f"DEBUG: _load_history - Archivo de historial encontrado: {HISTORY_FILE}", file=sys.stderr)
            try:
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    file_content = f.read()
                    if not file_content.strip():
                        print(f"DEBUG: _load_history - Archivo de historial vacío o solo con espacios en blanco.", file=sys.stderr)
                        return []
                    serializable_history = json.loads(file_content)
                    print(f"DEBUG: _load_history - Historial serializado cargado: {len(serializable_history)} elementos", file=sys.stderr)
                    loaded_history = []
                    for item in serializable_history:
                        if item['type'] == 'human':
                            loaded_history.append(HumanMessage(content=item['content']))
                        elif item['type'] == 'ai':
                            tool_calls = item.get('tool_calls', [])
                            if tool_calls:
                                formatted_tool_calls = []
                                for tc in tool_calls:
                                    # Asegurarse de que los args sean diccionarios
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
                print(f"DEBUG: _load_history - Historial de LangChain reconstruido: {len(loaded_history)} mensajes", file=sys.stderr)
                print(f"Error al decodificar el historial JSON: {e}", file=sys.stderr)
            except Exception as e:
                print(f"Error inesperado al cargar el historial: {e}", file=sys.stderr)
        return []

    def _save_history(self, history: list):
        """Guarda el historial de conversación en un archivo JSON."""
        
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

            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(serializable_history, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error al guardar el historial: {e}", file=sys.stderr)

    def invoke(self, history: list, system_message: Optional[str] = None):
        """Invoca el modelo LLM con un historial de conversación y un mensaje de sistema opcional.

        Args:
            history: El historial completo de la conversación en el formato de LangChain.
            system_message: Un mensaje de sistema opcional para guiar al modelo.

        Returns:
            La respuesta del modelo, que puede incluir texto o llamadas a herramientas.
        """
        # Lógica de Rate Limiting
        current_time = time.time()
        # Eliminar marcas de tiempo antiguas
        while self.call_timestamps and self.call_timestamps[0] <= current_time - self.rate_limit_period:
            self.call_timestamps.popleft()

        # Si se excede el límite, esperar
        if len(self.call_timestamps) >= self.rate_limit_calls:
            time_to_wait = self.rate_limit_period - (current_time - self.call_timestamps[0])
            if time_to_wait > 0:
                print(f"DEBUG: Rate limit hit. Waiting for {time_to_wait:.2f} seconds...", file=sys.stderr)
                time.sleep(time_to_wait)
                current_time = time.time() # Actualizar el tiempo después de esperar
                print(f"DEBUG: Finished waiting for rate limit.", file=sys.stderr)
                # Volver a limpiar por si acaso
                while self.call_timestamps and self.call_timestamps[0] <= current_time - self.rate_limit_period:
                    self.call_timestamps.popleft()

        self.stop_generation_flag = False # Resetear la bandera al inicio de cada invocación

        # Convertir el historial de LangChain a un formato compatible con LiteLLM
        litellm_messages = [_to_litellm_message(msg) for msg in history]

        # Filtrar mensajes de asistente vacíos que no tengan llamadas a herramientas
        # para evitar enviar contenido vacío al modelo, lo que puede causar respuestas inesperadas.
        filtered_messages = []
        for msg in litellm_messages:
            is_assistant = msg.get("role") == "assistant"
            has_content = msg.get("content") and str(msg.get("content")).strip()
            has_tool_calls = msg.get("tool_calls")
            if is_assistant and not has_content and not has_tool_calls:
                continue
            filtered_messages.append(msg)
        litellm_messages = filtered_messages

        # Añadir el system_message al principio si existe
        if system_message:
            litellm_messages.insert(0, {"role": "system", "content": system_message})

        # Lógica de truncamiento del historial para evitar exceder el límite de tokens y mensajes.
        # Asegurarse de que el mensaje del sistema (si existe) y el último mensaje del usuario
        # (y su posible respuesta de herramienta) siempre se mantengan.

        # Primero, truncar por número de mensajes si es necesario
        # Mantener al menos el mensaje del sistema + el último par de interacción (usuario + AI/herramienta)
        min_messages_to_keep = 1 # Para el mensaje del sistema
        if len(litellm_messages) > min_messages_to_keep:
            # Si el último mensaje es una respuesta de herramienta, necesitamos mantener el AIMessage anterior
            if litellm_messages[-1].get('role') == 'tool' and len(litellm_messages) > 1:
                min_messages_to_keep += 2 # Usuario + AI + Herramienta
            else:
                min_messages_to_keep += 1 # Usuario + AI

        while len(litellm_messages) > self.max_history_messages and len(litellm_messages) > min_messages_to_keep:
            # Asegurarse de no eliminar el mensaje del sistema si es el primero
            if litellm_messages[0].get('role') == 'system' and len(litellm_messages) > 1:
                litellm_messages.pop(1) # Eliminar el siguiente mensaje más antiguo
            else:
                litellm_messages.pop(0) # Eliminar el mensaje más antiguo

        # Luego, truncar por caracteres si es necesario
        current_chars = sum(len(json.dumps(msg)) for msg in litellm_messages)
        while current_chars > self.max_history_chars and len(litellm_messages) > min_messages_to_keep:
            if litellm_messages[0].get('role') == 'system' and len(litellm_messages) > 1:
                removed_msg = litellm_messages.pop(1)
            else:
                removed_msg = litellm_messages.pop(0)
            current_chars -= len(json.dumps(removed_msg)) # Restar el tamaño del mensaje eliminado

        try:
            # Extraer parámetros de generación para LiteLLM y filtrar los no válidos
            litellm_generation_params = self.generation_params.copy()
            # Eliminar 'temperature' si no es un parámetro aceptado directamente por completion en este contexto
            # Si LiteLLM maneja 'temperature' directamente, esto puede no ser necesario.
            # Sin embargo, los errores de Pylance sugieren que los tipos no coinciden.
            # Es mejor pasar solo los parámetros que LiteLLM espera explícitamente, o asegurarse de que los tipos sean correctos.
            # Para este caso, solo 'temperature' debería ser un float.
            # Otros parámetros como 'top_p', 'top_k' se manejan por separado o se asume que son correctos.
            
            # Se asume que 'temperature' es el único float que se pasa directamente y que los errores de Pylance
            # se refieren a que otros parámetros (como n, stream_options, etc.) no deberían recibir un float.
            # La solución más robusta es no pasar **litellm_generation_params si no se sabe qué contiene.
            # Sin embargo, si se espera que contenga solo 'temperature', se puede filtrar.
            # Por ahora, se asume que los errores de tipado se deben a que parámetros como 'n' o 'max_tokens'
            # están recibiendo el valor float de 'temperature' a través del desempaquetado.
            # La forma correcta es pasar `temperature` directamente y no desempaquetar `generation_params` si contiene
            # otros valores que no son para `completion`.

            # Si self.generation_params solo contiene 'temperature', podemos pasarlo directamente.
            # Si contiene más, debemos filtrarlos o pasarlos explícitamente.
            
            # Para solucionar los errores de Pylance, vamos a crear un diccionario con los parámetros
            # que sabemos que son aceptados por `completion` y tienen el tipo correcto.
            # Por ejemplo, 'temperature' es un float, y completion lo acepta.
            # Los errores de Pylance indican que otros parámetros están recibiendo 'float'.
            # Esto sugiere que se están pasando parámetros inesperados a `completion` a través de `**litellm_generation_params`.
            # La solución es pasar solo los parámetros esperados.
            
            # Opción 1: Pasar solo los parámetros conocidos y con tipos correctos.
            # Esto requiere conocer la firma exacta de `completion`.
            # Por simplicidad, asumiremos que `temperature` es el único parámetro de `generation_params`
            # que debe ser pasado directamente y que los otros errores son falsos positivos o que LiteLLM
            # los maneja internamente. Si `completion` espera un `int` para `n` o `max_tokens`,
            # y `litellm_generation_params` tiene un `float` llamado `temperature`,
            # entonces `temperature` se está pasando como `n` o `max_tokens` (por el orden de los argumentos o por cómo LiteLLM los maneja).
            # La solución más segura es:
            
            completion_kwargs = {
                "model": self.model_name,
                "messages": litellm_messages,
                "tools": self.litellm_tools,
                "stream": True,
                "api_key": os.getenv("GOOGLE_API_KEY"),
                "temperature": litellm_generation_params.get("temperature", 0.7), # Default si no está
            }
            # Añadir otros parámetros si existen y son válidos
            if "top_p" in litellm_generation_params:
                completion_kwargs["top_p"] = litellm_generation_params["top_p"]
            if "top_k" in litellm_generation_params:
                completion_kwargs["top_k"] = litellm_generation_params["top_k"]

            start_time = time.perf_counter() # Medir el tiempo de inicio
            response_generator = completion(
                **completion_kwargs
            )
            end_time = time.perf_counter() # Medir el tiempo de finalización
            self.call_timestamps.append(time.time()) # Registrar la llamada exitosa
            
            # Procesar la respuesta en streaming
            full_response_content = ""
            tool_calls = []
            for chunk in response_generator:
                if self.stop_generation_flag:
                    print("DEBUG: Generación detenida por bandera.", file=sys.stderr)
                    break

                # Se espera que 'chunk' sea un objeto con un atributo 'choices'
                # Acceso seguro a chunk.choices y chunk.choices[0].delta
                choices = getattr(chunk, 'choices', None)
                if not choices or not isinstance(choices, list) or not choices[0]:
                    continue
                
                choice = choices[0]
                delta = getattr(choice, 'delta', None)
                if not delta:
                    continue
                
                if getattr(delta, 'content', None) is not None:
                    full_response_content += str(delta.content)
                    yield str(delta.content) # Devolver el contenido en streaming
                
                tool_calls_from_delta = getattr(delta, 'tool_calls', None)
                if tool_calls_from_delta is not None:
                    for tc in tool_calls_from_delta:
                        # Asegurar que tc.index es válido para tool_calls
                        if tc.index >= len(tool_calls):
                            # Extender la lista si el índice es mayor que la longitud actual
                            tool_calls.extend([{"id": "", "function": {"name": "", "arguments": ""}}] * (tc.index - len(tool_calls) + 1))
                        
                        # Actualizar tool_calls de forma segura
                        if getattr(tc, 'id', None) is not None:
                            tool_calls[tc.index]["id"] = tc.id
                            print(f"DEBUG: Capturando tool_call ID: {tc.id}", file=sys.stderr)
                        if getattr(tc, 'function', None) is not None:
                            if getattr(tc.function, 'name', None) is not None:
                                tool_calls[tc.index]["function"]["name"] = tc.function.name
                            if getattr(tc.function, 'arguments', None) is not None:
                                tool_calls[tc.index]["function"]["arguments"] += tc.function.arguments
            
            # Si la generación fue detenida, devolver un mensaje de interrupción
            if self.stop_generation_flag:
                yield AIMessage(content="Generación de respuesta interrumpida por el usuario. 🛑")
            # Si hay tool_calls, devolverlos como AIMessage
            elif tool_calls:
                # Convertir los argumentos de string JSON a dict
                formatted_tool_calls = []
                for tc in tool_calls:
                    try:
                        args = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError:
                        args = {} # Fallback si no es un JSON válido
                    formatted_tool_calls.append({
                        "id": tc["id"],
                        "name": tc["function"]["name"],
                        "args": args
                    })
                yield AIMessage(content=full_response_content, tool_calls=formatted_tool_calls)
            else:
                yield AIMessage(content=full_response_content)

        except Exception as e:
            import traceback
            # Imprimir el traceback completo a stderr para depuración
            print(f"Error de LiteLLM: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            error_message = f"¡Ups! 😵 Ocurrió un error inesperado al comunicarme con el modelo (LiteLLM): {e}. Por favor, revisa los logs para más detalles. ¡Intentemos de nuevo!\""
            yield AIMessage(content=error_message)

    def summarize_conversation_history(self) -> Optional[str]:
        """Resume el historial de conversación actual utilizando el modelo LLM a través de LiteLLM."""
        if not self.conversation_history:
            return None # Retorna None si no hay historial para resumir.

        # Crear un prompt para el resumen
        summarize_prompt = HumanMessage(content="Por favor, resume la siguiente conversación de manera concisa y detallada, capturando los puntos clave, decisiones tomadas y tareas pendientes. El resumen debe ser útil para retomar la conversación más tarde.")
        
        # Crear un historial temporal para el resumen, incluyendo el prompt de resumen
        temp_history_for_summary = self.conversation_history + [summarize_prompt]

        try:
            # Convertir el historial de LangChain a un formato compatible con LiteLLM
            litellm_messages_for_summary = [_to_litellm_message(msg) for msg in temp_history_for_summary]
            
            # Llamar a LiteLLM para obtener el resumen
            # Extraer parámetros de generación para LiteLLM
            litellm_generation_params = self.generation_params

            summary_completion_kwargs = {
                "model": self.model_name,
                "messages": litellm_messages_for_summary,
                "api_key": os.getenv("GOOGLE_API_KEY"),
                "temperature": litellm_generation_params.get("temperature", 0.7),
                "stream": False, # Asegurar que no sea streaming para el resumen
            }
            if "top_p" in litellm_generation_params:
                summary_completion_kwargs["top_p"] = litellm_generation_params["top_p"]
            if "top_k" in litellm_generation_params:
                summary_completion_kwargs["top_k"] = litellm_generation_params["top_k"]

            response = completion(
                **summary_completion_kwargs
            )
            
            if getattr(response, 'choices', None) and response.choices and len(response.choices) > 0:
                # Acceso seguro a response.choices y response.choices[0].message
                choices = getattr(response, 'choices', None)
                if choices and isinstance(choices, list) and len(choices) > 0:
                    first_choice = choices[0]
                    message = getattr(first_choice, 'message', None)
                    if message and getattr(message, 'content', None) is not None:
                        summary_text = message.content
                        return summary_text
            return None # Retorna None si no se pudo generar un resumen.
        except Exception as e:
            import traceback
            # Imprimir el traceback completo a stderr para depuración
            print(f"Error de LiteLLM al resumir el historial: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return f"¡Ups! 😵 Ocurrió un error inesperado al resumir el historial con LiteLLM: {e}. Por favor, revisa los logs para más detalles. ¡Intentemos de nuevo!\""

    def get_tool(self, tool_name: str) -> BaseTool | None:
        """Encuentra y devuelve una herramienta de LangChain por su nombre."""
        for tool in self.langchain_tools:
            if tool.name == tool_name:
                return tool
        return None