import os
import sys
import time
from collections import deque
import google.generativeai as genai
from google.generativeai.client import configure
from google.generativeai.generative_models import GenerativeModel
from google.api_core.exceptions import GoogleAPIError
from langchain_core.tools import BaseTool

from .tools import get_callable_tools

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
        print("DEBUG: Inicializando instancia de LLMService...", file=sys.stderr)
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

    def invoke(self, history: list, system_message: str = None):
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
                if 'text' in part:
                    msg_chars += len(part['text'])
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
        if history and history[0]['role'] == 'user' and 'text' in history[0]['parts'][0]:
            system_message_content = history[0]['parts'][0]['text']
            system_message_chars = len(system_message_content)
            
            # Si el system_message ya está en truncated_history, no lo añadimos de nuevo.
            # Esto es una heurística, asumiendo que el system_message es el primer elemento.
            if not truncated_history or (truncated_history[0]['role'] == 'user' and 'text' in truncated_history[0]['parts'][0] and truncated_history[0]['parts'][0]['text'] != system_message_content):
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
