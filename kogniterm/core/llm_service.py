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
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from .tools import get_callable_tools

HISTORY_FILE = "kogniterm_history.json"

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
            return {'role': data['role'], 'parts': [_from_json_serializable(part) for part in data['parts']]}
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
        self.langchain_tools = get_callable_tools()
        
        
        # Convertir herramientas al formato de Google AI
        self.google_ai_tools = [convert_langchain_tool_to_genai(tool) for tool in self.langchain_tools]

        # Configuración para la generación de contenido
        generation_config = genai.types.GenerationConfig(
            temperature=0.7, # Un valor más alto para fomentar la creatividad en la planificación
            # top_p=0.95, # Descomentar si se desea usar nucleous sampling
            # top_k=40,   # Descomentar si se desea usar top-k sampling
        )

        # Inicializar el modelo con las herramientas y la configuración de generación
        self.model = GenerativeModel(
            self.model_name,
            tools=self.google_ai_tools,
            generation_config=generation_config
        )

        # Atributos para el rate limiting
        self.call_timestamps = deque() # Almacena las marcas de tiempo de las llamadas
        self.rate_limit_calls = 10     # Límite de 10 llamadas
        self.rate_limit_period = 60    # En segundos (1 minuto)

        # Atributos para el truncamiento del historial
        self.max_history_chars = 15000 # Aproximación de tokens (ajustar según pruebas)
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
                print("Inicializando memoria...", file=sys.stderr)
                # Invocar la herramienta sin argumentos para usar el valor por defecto de file_path
                memory_init_tool.invoke({})
                print("Memoria inicializada o ya existente. ✅", file=sys.stderr)
            except Exception as e:
                print(f"Error al inicializar la memoria: {e} ❌", file=sys.stderr)
        else:
            print("Advertencia: La herramienta 'memory_init' no se encontró. La memoria no será inicializada automáticamente. ⚠️", file=sys.stderr)

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
                                loaded_history.append(AIMessage(content=item['content'], tool_calls=tool_calls))
                            else:
                                loaded_history.append(AIMessage(content=item['content']))
                        elif item['type'] == 'tool':
                            loaded_history.append(ToolMessage(content=item['content'], tool_call_id=item['tool_call_id']))
                        else:
                            print(f"Advertencia: Tipo de mensaje desconocido en el historial cargado: {item['type']}", file=sys.stderr)
                    print(f"Historial cargado desde {HISTORY_FILE}. ✅", file=sys.stderr)
                    
                    return loaded_history
            except json.JSONDecodeError as e:
                print(f"Error al decodificar JSON del historial: {e} ❌", file=sys.stderr)

                return []
            except Exception as e:
                print(f"Error al cargar el historial: {e} ❌", file=sys.stderr)

                return []
        print(f"No se encontró archivo de historial en {HISTORY_FILE}. Iniciando con historial vacío. 📝", file=sys.stderr)
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
                        serializable_history.append({'type': 'ai', 'content': msg.content, 'tool_calls': [{'name': tc['name'], 'args': tc['args']} for tc in msg.tool_calls]})
                    else:
                        serializable_history.append({'type': 'ai', 'content': msg.content})
                elif isinstance(msg, ToolMessage):
                    serializable_history.append({'type': 'tool', 'content': msg.content, 'tool_call_id': msg.tool_call_id})
                else:
                    print(f"Advertencia: Tipo de mensaje desconocido en el historial: {type(msg)}", file=sys.stderr)
                    continue # Saltar mensajes desconocidos

            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(serializable_history, f, indent=4, ensure_ascii=False)
            print(f"Historial guardado en {HISTORY_FILE}. ✅", file=sys.stderr)
            print(f"DEBUG: Historial guardado exitosamente.", file=sys.stderr)
        except Exception as e:
            print(f"Error al guardar el historial: {e} ❌", file=sys.stderr)
            print(f"DEBUG: Error al guardar historial: {e}", file=sys.stderr)

    def invoke(self, history: list, system_message: str = None):
        print(f"DEBUG: Invocando LLM con historial (longitud: {len(history)}): {history[:2]}...", file=sys.stderr)
        """
        Invoca el modelo Gemini con un historial de conversación y un mensaje de sistema opcional.

        Args:
            history: Una lista de diccionarios que representan el historial de la conversación,
                     en el formato que espera la API de Google AI.
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
                print(f"Rate limit alcanzado. Esperando {time_to_wait:.2f} segundos...", file=sys.stderr)
                time.sleep(time_to_wait)
                current_time = time.time() # Actualizar el tiempo después de esperar
                # Volver a limpiar por si acaso
                while self.call_timestamps and self.call_timestamps[0] <= current_time - self.rate_limit_period:
                    self.call_timestamps.popleft()

        # --- Lógica de Truncamiento del Historial ---
        truncated_history = []
        current_chars = 0
        
        # El último mensaje (el del usuario actual) siempre debe incluirse
        last_message_for_send = history[-1]['parts'][0]
        
        # El historial para start_chat debe excluir el último mensaje (el actual)
        history_for_start_chat = history[:-1]

        # Recorrer el historial de atrás hacia adelante para mantener los mensajes más recientes
        for msg_dict in reversed(history_for_start_chat):
            # Estimar caracteres en el mensaje
            msg_chars = 0
            for part in msg_dict.get('parts', []):
                if hasattr(part, 'text') and part.text is not None:
                    msg_chars += len(part.text)
                elif 'function_call' in part:
                    # Estimar caracteres de llamadas a funciones (nombre + args)
                    msg_chars += len(part['function_call'].get('name', ''))
                    msg_chars += len(str(part['function_call'].get('args', {})))
                elif 'function_response' in part:
                    # Estimar caracteres de respuestas de funciones
                    msg_chars += len(str(part['function_response'].get('response', {})))
            
            if current_chars + msg_chars <= self.max_history_chars:
                truncated_history.insert(0, msg_dict) # Insertar al principio para mantener el orden original
                current_chars += msg_chars
            else:
                # Si añadir este mensaje excede el límite, truncar aquí
                break
        
        # Asegurarse de que el system_message (si existe) esté al principio del historial truncado
        # y que no exceda el límite por sí solo.
        # Nota: El system_message se añade como un mensaje de 'user' en el formato de la API de Google AI
        # y se asume que es el primer mensaje en el historial.
        if history and history[0]['role'] == 'user' and hasattr(history[0]['parts'][0], 'text') and history[0]['parts'][0].text is not None:
            system_message_content = history[0]['parts'][0].text
            system_message_chars = len(system_message_content)
            
            # Si el system_message ya está en truncated_history, no lo añadimos de nuevo.
            # Esto es una heurística, asumiendo que el system_message es el primer elemento.
            if not truncated_history or (truncated_history[0]['role'] == 'user' and hasattr(truncated_history[0]['parts'][0], 'text') and truncated_history[0]['parts'][0].text is not None and truncated_history[0]['parts'][0].text != system_message_content):
                if current_chars + system_message_chars <= self.max_history_chars:
                    truncated_history.insert(0, {'role': 'user', 'parts': [genai.protos.Part(text=system_message_content)]})
                else:
                    # Si el system_message es demasiado grande, lo truncamos si es el único mensaje
                    if not truncated_history:
                        truncated_history.insert(0, {'role': 'user', 'parts': [genai.protos.Part(text=system_message_content[:self.max_history_chars])]})
        
        # Crear una nueva sesión de chat para cada invocación para mantenerla sin estado
        chat_session = self.model.start_chat(history=truncated_history)
        
        try:
            response = chat_session.send_message(last_message_for_send)
            self.call_timestamps.append(time.time()) # Registrar la llamada exitosa
            
            return response
        except GoogleAPIError as e:
            error_message = f"Error de API de Gemini: {e}"
            print(f"ERROR: {error_message}", file=sys.stderr)
            # Devolver un objeto de respuesta simulado con el error en el texto
            return genai.types.GenerateContentResponse(
                candidates=[
                    genai.types.Candidate(
                        content=genai.types.Content(parts=[genai.types.Part(text=error_message)]),
                        finish_reason=genai.types.FinishReason.ERROR,
                    )
                ],
            )
        except Exception as e:
            import traceback
            error_message = f"Ocurrió un error inesperado: {e}\n{traceback.format_exc()}"
            print(f"ERROR: {error_message}", file=sys.stderr)
            return genai.types.GenerateContentResponse(
                candidates=[
                    genai.types.Candidate(
                        content=genai.types.Content(parts=[genai.types.Part(text=error_message)]),
                        finish_reason=genai.types.FinishReason.ERROR,
                    )
                ],
            )

    def get_tool(self, tool_name: str) -> BaseTool | None:
        """Encuentra y devuelve una herramienta de LangChain por su nombre."""
        for tool in self.langchain_tools:
            if tool.name == tool_name:
                return tool
        return None
