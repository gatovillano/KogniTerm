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

# --- Clase Principal del Servicio LLM ---

class LLMService:
    """Un servicio para interactuar con el modelo Gemini de Google AI."""
    def __init__(self):
        
        """Inicializa el servicio, configura la API y prepara las herramientas."""
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("Error: La variable de entorno GOOGLE_API_KEY no está configurada.", file=sys.stderr)
            raise ValueError("La variable de entorno GOOGLE_API_KEY no está configurada.")

        configure(api_key=api_key)

        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        
        # Obtener herramientas de LangChain
        self.langchain_tools = get_callable_tools(llm_service_instance=self)
        
        
        # Convertir herramientas al formato de Google AI
        self.google_ai_tools = [convert_langchain_tool_to_genai(tool) for tool in self.langchain_tools]

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
                                      # 250,000 tokens/minuto es un límite alto,
                                      # 15,000 caracteres por historial debería ser seguro.
                                      # Un token es aproximadamente 4 caracteres para inglés.
                                      # Para español, puede variar.

        # Inicializar la memoria al inicio del servicio
        self._initialize_memory()
        
        # Cargar historial de conversación
        self.conversation_history = self._load_history()

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
                            # Reconstruir tool_calls si existen
                            tool_calls = item.get('tool_calls', [])
                            if tool_calls:
                                # Asegurarse de que los args sean diccionarios
                                formatted_tool_calls = []
                                for tc in tool_calls:
                                    tool_call_id = tc.get('id') # Obtener el id de forma segura
                                    if isinstance(tc['args'], dict):
                                        formatted_tool_calls.append({'name': tc['name'], 'args': tc['args'], 'id': tool_call_id})
                                    else:
                                        # Si args no es un dict, intentar parsearlo
                                        try:
                                            parsed_args = json.loads(tc['args'])
                                            formatted_tool_calls.append({'name': tc['name'], 'args': parsed_args, 'id': tool_call_id})
                                        except (json.JSONDecodeError, TypeError):
                                            print(f"Advertencia: No se pudieron parsear los argumentos de la herramienta: {tc['args']}", file=sys.stderr)
                                            formatted_tool_calls.append({'name': tc['name'], 'args': {}, 'id': tool_call_id})
                                loaded_history.append(AIMessage(content=item['content'], tool_calls=formatted_tool_calls))
                            else:
                                loaded_history.append(AIMessage(content=item['content']))
                        elif item['type'] == 'tool':
                            loaded_history.append(ToolMessage(content=item['content'], tool_call_id=item['tool_call_id']))
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
                    # Incluir tool_calls si existen
                    if msg.tool_calls:
                        serializable_history.append({'type': 'ai', 'content': msg.content, 'tool_calls': [{'name': tc['name'], 'args': tc['args'], 'id': tc['id']} for tc in msg.tool_calls]})
                    else:
                        serializable_history.append({'type': 'ai', 'content': msg.content})
                elif isinstance(msg, ToolMessage):
                    serializable_history.append({'type': 'tool', 'content': msg.content, 'tool_call_id': msg.tool_call_id})
                else:
                    continue # Saltar mensajes desconocidos

            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(serializable_history, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error al guardar el historial: {e}", file=sys.stderr)

    def invoke(self, history: list, system_message: str = None):
        """Invoca el modelo Gemini con un historial de conversación y un mensaje de sistema opcional.

        Args:
            history: El historial completo de la conversación en el formato de la API de Google AI.
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
                time.sleep(time_to_wait)
                current_time = time.time() # Actualizar el tiempo después de esperar
                # Volver a limpiar por si acaso
                while self.call_timestamps and self.call_timestamps[0] <= current_time - self.rate_limit_period:
                    self.call_timestamps.popleft()

        # Convertir el historial de LangChain a objetos Content de Gemini
        gemini_history = [_to_gemini_content(msg) for msg in history]

        last_message_for_send = gemini_history[-1]
        history_for_start_chat = gemini_history[:-1]

        # Iterar el historial de atrás hacia adelante
        truncated_history = []
        current_chars = 0
        
        # Recorrer el historial de atrás hacia adelante para truncar
        i = len(history_for_start_chat) - 1
        while i >= 0:
            msg_content = history_for_start_chat[i]
            msg_chars = 0

            # Estimar caracteres del mensaje actual
            for part in msg_content.parts:
                if hasattr(part, 'text') and part.text is not None:
                    msg_chars += len(part.text)
                elif hasattr(part, 'function_call') and part.function_call is not None:
                    msg_chars += len(part.function_call.name)
                    msg_chars += len(str(part.function_call.args))
                elif hasattr(part, 'function_response') and part.function_response is not None:
                    msg_chars += len(part.function_response.name)
                    msg_chars += len(str(part.function_response.response))
            
            # Verificar si el mensaje actual es un AIMessage con tool_calls
            is_tool_call_message = False
            if msg_content.role == 'model':
                for part in msg_content.parts:
                    if hasattr(part, 'function_call') and part.function_call is not None:
                        is_tool_call_message = True
                        break
            
            # Si es un AIMessage con tool_calls, intentar incluir el siguiente ToolMessage (respuesta)
            # para mantener el par tool_call/tool_response junto.
            if is_tool_call_message and i + 1 < len(history_for_start_chat):
                next_msg_content = history_for_start_chat[i + 1]
                is_tool_response_message = False
                if next_msg_content.role == 'user': # La respuesta de la herramienta es un mensaje de usuario
                    for part in next_msg_content.parts:
                        if hasattr(part, 'function_response') and part.function_response is not None:
                            is_tool_response_message = True
                            break
                
                if is_tool_response_message:
                    # Calcular caracteres del ToolMessage
                    next_msg_chars = 0
                    for part in next_msg_content.parts:
                        if hasattr(part, 'text') and part.text is not None:
                            next_msg_chars += len(part.text)
                        elif hasattr(part, 'function_call') and part.function_call is not None:
                            next_msg_chars += len(part.function_call.name)
                            next_msg_chars += len(str(part.function_call.args))
                        elif hasattr(part, 'function_response') and part.function_response is not None:
                            next_msg_chars += len(part.function_response.name)
                            next_msg_chars += len(str(part.function_response.response))
                    
                    # Si ambos mensajes (llamada y respuesta de herramienta) caben, añadirlos como una unidad
                    if current_chars + msg_chars + next_msg_chars <= self.max_history_chars:
                        truncated_history.insert(0, next_msg_content) # Añadir ToolMessage primero
                        truncated_history.insert(0, msg_content)      # Luego AIMessage
                        current_chars += msg_chars + next_msg_chars
                        i -= 1 # Saltar el ToolMessage ya que lo hemos procesado junto con el AIMessage
                    else:
                        break # No caben, truncar aquí
                else: # No es un ToolMessage de respuesta, procesar solo el mensaje actual
                    if current_chars + msg_chars <= self.max_history_chars:
                        truncated_history.insert(0, msg_content)
                        current_chars += msg_chars
                    else:
                        break # No cabe, truncar aquí
            else: # No es un AIMessage con tool_calls, procesar solo el mensaje actual
                if current_chars + msg_chars <= self.max_history_chars:
                    truncated_history.insert(0, msg_content)
                    current_chars += msg_chars
                else:
                    break # No cabe, truncar aquí
            
            i -= 1 # Mover al mensaje anterior
        
        # Asegurarse de que el system_message (si existe) esté al principio del historial truncado
        # y que no exceda el límite por sí solo.
        if system_message:
            system_message_content = genai.protos.Content(role='user', parts=[genai.protos.Part(text=system_message)])
            system_message_chars = 0
            for part in system_message_content.parts:
                if hasattr(part, 'text') and part.text is not None:
                    system_message_chars += len(part.text)

            # Si el system_message ya está en truncated_history, no lo añadimos de nuevo.
            # Esto es una heurística, asumiendo que el system_message es el primer elemento.
            if not truncated_history or not (truncated_history[0].role == 'user' and len(truncated_history[0].parts) > 0 and hasattr(truncated_history[0].parts[0], 'text') and truncated_history[0].parts[0].text == system_message):
                if current_chars + system_message_chars <= self.max_history_chars:
                    truncated_history.insert(0, system_message_content)
                else:
                    # Si el system_message es demasiado grande, lo truncamos si es el único mensaje
                    if not truncated_history:
                        truncated_history.insert(0, genai.protos.Content(role='user', parts=[genai.protos.Part(text=system_message[:self.max_history_chars])]))
        
        # --- Lógica de alternancia de roles para el historial de start_chat ---
        # La API de Gemini espera que el historial de start_chat alterne roles.
        # Si el historial no está vacío, el último mensaje debe tener el rol opuesto al
        # primer mensaje que se enviará con send_message (last_message_for_send).
        
        # Si el historial truncado no está vacío y el rol del último mensaje
        # es el mismo que el rol del mensaje que se va a enviar,
        # entonces necesitamos ajustar el historial.
        if truncated_history and truncated_history[-1].role == last_message_for_send.role:
            # Si el último mensaje del historial truncado es un 'user' y el mensaje a enviar también es 'user',
            # o si ambos son 'model', esto rompe la alternancia.
            # En este caso, eliminamos el último mensaje del historial truncado.
            # Esto es un último recurso para forzar la alternancia, asumiendo que
            # los pares tool_call/tool_response ya se manejaron.
            truncated_history.pop()
        # --- FIN LÓGICA DE ALTERNANCIA ---

        # Crear una nueva sesión de chat para cada invocación para mantenerla sin estado
        chat_session = self.model.start_chat(history=truncated_history)
        
        try:
            response = chat_session.send_message(last_message_for_send)
            self.call_timestamps.append(time.time()) # Registrar la llamada exitosa
            
            return response
        except GoogleAPIError as e:
            error_message = f"Error de API de Gemini: {e}"
            # Devolver un objeto de respuesta simulado con el error en el texto
            return AIMessage(content=error_message)
        except Exception as e:
            import traceback
            error_message = f"Ocurrió un error inesperado: {e}\n{traceback.format_exc()}"
            # Devolver un diccionario simple con el mensaje de error
            return AIMessage(content=error_message)

    def summarize_conversation_history(self) -> str:
        """Resume el historial de conversación actual utilizando el modelo LLM."""
        if not self.conversation_history:
            return "No hay historial para resumir."

        # Crear un prompt para el resumen
        summarize_prompt = HumanMessage(content="Por favor, resume la siguiente conversación de manera concisa y detallada, capturando los puntos clave, decisiones tomadas y tareas pendientes. El resumen debe ser útil para retomar la conversación más tarde.")
        
        # Crear un historial temporal para el resumen, incluyendo el prompt de resumen
        # y excluyendo el SYSTEM_MESSAGE inicial para evitar que el modelo lo resuma
        temp_history_for_summary = self.conversation_history[1:] + [summarize_prompt]

        try:
            # Convertir el historial de LangChain a objetos Content de Gemini
            gemini_history_for_summary = [_to_gemini_content(msg) for msg in temp_history_for_summary]
            
            # Iniciar un chat con el historial para el resumen
            # No pasamos herramientas aquí porque queremos que el modelo genere texto, no llamadas a herramientas
            summary_model = GenerativeModel(self.model_name, generation_config=self.generation_config)
            chat_session = summary_model.start_chat(history=gemini_history_for_summary[:-1]) # Excluir el último mensaje (el prompt de resumen)
            
            response = chat_session.send_message(gemini_history_for_summary[-1]) # Enviar el prompt de resumen
            
            if response.candidates and response.candidates[0].content.parts:
                summary_text = response.candidates[0].content.parts[0].text
                return summary_text
            else:
                return "No se pudo generar un resumen."
        except GoogleAPIError as e:
            return f"Error de API al intentar resumir el historial: {e}"
        except Exception as e:
            return f"Ocurrió un un error inesperado al resumir el historial: {e}"

    def get_tool(self, tool_name: str) -> BaseTool | None:
        """Encuentra y devuelve una herramienta de LangChain por su nombre."""
        for tool in self.langchain_tools:
            if tool.name == tool_name:
                return tool
        return None

