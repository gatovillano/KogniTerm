import os
import sys
import time
import json
from collections import deque
import google.generativeai as genai
from google.generativeai.client import configure
from google.generativeai.generative_models import GenerativeModel
from google.api_core.exceptions import GoogleAPIError
from langchain_core.tools import BaseTool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from litellm import completion, litellm # <--- Modificar esta línea para importar litellm
import uuid # <--- Añadir esta línea

from .tools.tool_manager import get_callable_tools

HISTORY_FILE = os.path.join(os.getcwd(), "kogniterm_history.json")

def _to_gemini_content(message):
    """Convierte un mensaje de LangChain a un objeto Content de Gemini."""
    if isinstance(message, (HumanMessage, SystemMessage)):
        return genai.protos.Content(role='user', parts=[genai.protos.Part(text=message.content)])
    elif isinstance(message, AIMessage):
        if message.tool_calls:
            # Si el AIMessage tiene tool_calls, se convierte a FunctionCall
            function_calls = []
            for tc in message.tool_calls:
                function_calls.append(genai.protos.Part(
                    function_call=genai.protos.FunctionCall(
                        name=tc['name'],
                        args=tc['args']
                    )
                ))
            return genai.protos.Content(role='model', parts=function_calls)
        else:
            return genai.protos.Content(role='model', parts=[genai.protos.Part(text=message.content)])
    elif isinstance(message, ToolMessage):

        # ToolMessage se mapea a un rol 'user' con una function_response
        return genai.protos.Content(
            role='user',
            parts=[
                genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=message.tool_call_id, # Usamos tool_call_id como nombre de la función
                        response={'output': message.content} # La respuesta de la herramienta
                    )
                )
            ]
        )
    else:
        raise ValueError(f"Tipo de mensaje desconocido: {type(message)}")

def _to_litellm_message(message):
    """Convierte un mensaje de LangChain a un formato compatible con LiteLLM."""
    if isinstance(message, HumanMessage):
        return {"role": "user", "content": message.content}
    elif isinstance(message, AIMessage):
        if message.tool_calls:
            # LiteLLM espera tool_calls en un formato específico
            litellm_tool_calls = []
            for tc in message.tool_calls:
                litellm_tool_calls.append({
                    "id": tc.get("id", str(uuid.uuid4())), # Asegurar un ID para LiteLLM
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc["args"]) # Los argumentos deben ser un string JSON
                    }
                })
            # Asegurarse de que el contenido no sea None si hay tool_calls
            content = message.content if message.content is not None else ""
            return {"role": "assistant", "content": content, "tool_calls": litellm_tool_calls}
        else:
            return {"role": "assistant", "content": message.content}
    elif isinstance(message, ToolMessage):
        # LiteLLM espera tool_response en un formato específico
        return {
            "role": "tool",
            "tool_call_id": message.tool_call_id,
            "content": message.content
        }
    elif isinstance(message, SystemMessage):
        return {"role": "system", "content": message.content}
    else:
        raise ValueError(f"Tipo de mensaje desconocido para LiteLLM: {type(message)}")

def _to_json_serializable(obj):
    if isinstance(obj, genai.protos.Part):
        if hasattr(obj, 'text') and obj.text is not None:
            return {'text': obj.text}
        elif hasattr(obj, 'function_call') and obj.function_call is not None:
            return {'function_call': {'name': obj.function_call.name, 'args': dict(obj.function_call.args)}}
        elif hasattr(obj, 'function_response') and obj.function_response is not None:
            return {'function_response': {'name': obj.function_response.name, 'response': dict(obj.function_response.response)}}
    elif hasattr(obj, 'role') and hasattr(obj, 'parts'): # Manejar objetos tipo Content
        return {'role': obj.role, 'parts': [_to_json_serializable(part) for part in obj.parts]}
    elif isinstance(obj, dict):
        return {k: _to_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_to_json_serializable(elem) for elem in obj]
    return obj

def _from_json_serializable(data):
    if isinstance(data, dict):
        if 'text' in data:
            return genai.protos.Part(text=data['text'])
        elif 'function_call' in data:
            return genai.protos.Part(function_call=genai.protos.FunctionCall(name=data['function_call']['name'], args=data['function_call']['args']))
        elif 'function_response' in data:
            return genai.protos.Part(function_response=genai.protos.FunctionResponse(name=data['function_response']['name'], response=data['function_response']['response']))
        elif 'role' in data and 'parts' in data:
            # Al deserializar, creamos un diccionario con objetos Part para el historial
            return genai.protos.Content(role=data['role'], parts=[_from_json_serializable(part) for part in data['parts']])
        return {k: _from_json_serializable(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_from_json_serializable(elem) for elem in data]
    return data

# --- Funciones de Ayuda para Conversión de Herramientas ---

def pydantic_to_genai_type(pydantic_type: str):
    """Convierte un tipo de Pydantic a un tipo de google.generativeai.protos.Type."""
    type_map = {
        'string': genai.protos.Type.STRING,
        'number': genai.protos.Type.NUMBER,
        'integer': genai.protos.Type.INTEGER,
        'boolean': genai.protos.Type.BOOLEAN,
        'array': genai.protos.Type.ARRAY,
        'object': genai.protos.Type.OBJECT,
    }
    return type_map.get(pydantic_type, genai.protos.Type.STRING) # Fallback a STRING

def convert_langchain_tool_to_genai(
    tool: BaseTool
) -> genai.protos.FunctionDeclaration:
    """Convierte una herramienta de LangChain (BaseTool) a una FunctionDeclaration de Google AI."""
    try:
        args_schema = tool.args_schema.schema()
    except AttributeError as e:
        tool_name = getattr(tool, 'name', 'Desconocido') # Obtener el nombre de forma segura
        tool_type = type(tool)
        print(f"ERROR: La herramienta '{tool_name}' de tipo '{tool_type}' no tiene un 'args_schema' válido o no tiene el método '.schema()'. Error: {e}", file=sys.stderr)
        raise # Re-lanza la excepción para que el programa falle y podamos depurar.
    
    properties = {}
    required = args_schema.get('required', [])

    for name, definition in args_schema.get('properties', {}).items():
        properties[name] = genai.protos.Schema(
            type=pydantic_to_genai_type(definition.get('type')),
            description=definition.get('description', '')
        )

    return genai.protos.FunctionDeclaration(
        name=tool.name,
        description=tool.description,
        parameters=genai.protos.Schema(
            type=genai.protos.Type.OBJECT,
            properties=properties,
            required=required
        )
    )

def _convert_langchain_tool_to_litellm(tool: BaseTool) -> dict:
    """Convierte una herramienta de LangChain (BaseTool) a un formato compatible con LiteLLM."""
    try:
        args_schema = tool.args_schema.schema()
    except AttributeError as e:
        tool_name = getattr(tool, 'name', 'Desconocido')
        tool_type = type(tool)
        print(f"ERROR: La herramienta '{tool_name}' de tipo '{tool_type}' no tiene un 'args_schema' válido o no tiene el método '.schema()'. Error: {e}", file=sys.stderr)
        raise

    # LiteLLM espera el esquema de parámetros directamente en 'parameters'
    # y los tipos de Pydantic son generalmente compatibles.
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": args_schema
        }
    }

# --- Clase Principal del Servicio LLM ---

class LLMService:
    """Un servicio para interactuar con el modelo Gemini de Google AI."""
    def __init__(self):
        
        self.console = None
        
        """Inicializa el servicio, configura la API y prepara las herramientas."""
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("Error: La variable de entorno GOOGLE_API_KEY no está configurada.", file=sys.stderr)
            raise ValueError("La variable de entorno GOOGLE_API_KEY no está configurada.")

        configure(api_key=api_key)

        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        if not self.model_name.startswith("gemini/"):
            self.model_name = f"gemini/{self.model_name}" # <--- Añadir esta línea
        
        # Obtener herramientas de LangChain
        self.langchain_tools = get_callable_tools(llm_service_instance=self)
        
        
        # Convertir herramientas al formato de Google AI
        self.google_ai_tools = [convert_langchain_tool_to_genai(tool) for tool in self.langchain_tools]

        # Convertir herramientas al formato de LiteLLM
        self.litellm_tools = [_convert_langchain_tool_to_litellm(tool) for tool in self.langchain_tools]

        # Configuración para la generación de contenido
        self.generation_config = genai.types.GenerationConfig(
            temperature=0.7, # Un valor más alto para fomentar la creatividad en la planificación
            # top_p=0.95, # Descomentar si se desea usar nucleous sampling
            # top_k=40,   # Descomentar si se desea usar top-k sampling
        )

        # Inicializar el modelo con las herramientas y la configuración de generación
        self.model = GenerativeModel(
            self.model_name,
            tools=self.google_ai_tools,
            generation_config=self.generation_config
        )

        # Atributos para el rate limiting
        self.call_timestamps = deque() # Almacena las marcas de tiempo de las llamadas
        self.rate_limit_calls = 10     # Límite de 10 llamadas
        self.rate_limit_period = 60    # En segundos (1 minuto)

        # Atributos para el truncamiento del historial
        self.max_history_chars = 30000 # Aproximación de tokens (ajustar según pruebas)
        self.max_history_messages = 50 # Límite de mensajes en el historial para evitar que crezca indefinidamente

        # Inicializar la memoria al inicio del servicio
        self._initialize_memory()
        
        # Cargar historial de conversación
        self.conversation_history = self._load_history()

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
            try:
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    serializable_history = json.load(f)
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

    def invoke(self, history: list, system_message: str = None):
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
            # Extraer parámetros de generación para LiteLLM
            litellm_generation_params = {
                "temperature": self.generation_config.temperature,
                "top_p": self.generation_config.top_p if hasattr(self.generation_config, 'top_p') else None,
                "top_k": self.generation_config.top_k if hasattr(self.generation_config, 'top_k') else None,
            }
            # Filtrar None para evitar errores si un parámetro no está establecido
            litellm_generation_params = {k: v for k, v in litellm_generation_params.items() if v is not None}

            start_time = time.perf_counter() # Medir el tiempo de inicio
            response_generator = completion(
                model=self.model_name,
                messages=litellm_messages,
                tools=self.litellm_tools,
                stream=True,
                api_key=os.getenv("GOOGLE_API_KEY"), # <--- Añadir esta línea
                **litellm_generation_params
            )
            end_time = time.perf_counter() # Medir el tiempo de finalización
            self.call_timestamps.append(time.time()) # Registrar la llamada exitosa
            
            # Procesar la respuesta en streaming
            full_response_content = ""
            tool_calls = []
            for chunk in response_generator:
                if chunk.choices and chunk.choices[0].delta:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        # Asegurarse de que delta.content sea un string antes de concatenar
                        full_response_content += str(delta.content)
                        yield str(delta.content) # Devolver el contenido en streaming
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            # LiteLLM puede enviar tool_calls en chunks, necesitamos reconstruirlos
                            if len(tool_calls) <= tc.index:
                                tool_calls.append({"id": "", "function": {"name": "", "arguments": ""}})
                            
                            if tc.id:
                                tool_calls[tc.index]["id"] = tc.id
                            if tc.function.name:
                                tool_calls[tc.index]["function"]["name"] = tc.function.name
                            if tc.function.arguments:
                                tool_calls[tc.index]["function"]["arguments"] += tc.function.arguments
            
            # Si hay tool_calls, devolverlos como AIMessage
            if tool_calls:
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
            error_message = f"¡Ups! 😵 Ocurrió un error inesperado al comunicarme con el modelo (LiteLLM): {e}. Por favor, revisa los logs para más detalles. ¡Intentemos de nuevo!"
            yield AIMessage(content=error_message)

    def summarize_conversation_history(self) -> str:
        """Resume el historial de conversación actual utilizando el modelo LLM a través de LiteLLM."""
        if not self.conversation_history:
            return "No hay historial para resumir."

        # Crear un prompt para el resumen
        summarize_prompt = HumanMessage(content="Por favor, resume la siguiente conversación de manera concisa y detallada, capturando los puntos clave, decisiones tomadas y tareas pendientes. El resumen debe ser útil para retomar la conversación más tarde.")
        
        # Crear un historial temporal para el resumen, incluyendo el prompt de resumen
        temp_history_for_summary = self.conversation_history + [summarize_prompt]

        try:
            # Convertir el historial de LangChain a un formato compatible con LiteLLM
            litellm_messages_for_summary = [_to_litellm_message(msg) for msg in temp_history_for_summary]
            
            # Llamar a LiteLLM para obtener el resumen
            # Extraer parámetros de generación para LiteLLM
            litellm_generation_params = {
                "temperature": self.generation_config.temperature,
                "top_p": self.generation_config.top_p if hasattr(self.generation_config, 'top_p') else None,
                "top_k": self.generation_config.top_k if hasattr(self.generation_config, 'top_k') else None,
            }
            # Filtrar None para evitar errores si un parámetro no está establecido
            litellm_generation_params = {k: v for k, v in litellm_generation_params.items() if v is not None}

            response = completion(
                model=self.model_name,
                messages=litellm_messages_for_summary,
                api_key=os.getenv("GOOGLE_API_KEY"), # <--- Añadir esta línea
                **litellm_generation_params
            )
            
            if response.choices and response.choices[0].message.content:
                summary_text = response.choices[0].message.content
                return summary_text
            else:
                return "No se pudo generar un resumen."
        except Exception as e:
            import traceback
            # Imprimir el traceback completo a stderr para depuración
            print(f"Error de LiteLLM al resumir el historial: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return f"¡Ups! 😵 Ocurrió un error inesperado al resumir el historial con LiteLLM: {e}. Por favor, revisa los logs para más detalles. ¡Intentemos de nuevo!"

    def get_tool(self, tool_name: str) -> BaseTool | None:
        """Encuentra y devuelve una herramienta de LangChain por su nombre."""
        for tool in self.langchain_tools:
            if tool.name == tool_name:
                return tool
        return None
