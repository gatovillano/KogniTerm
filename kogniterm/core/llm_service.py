import os
import sys
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
    args_schema = tool.args_schema.schema()
    
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
        # Crear una nueva sesión de chat para cada invocación para mantenerla sin estado
        chat_session = self.model.start_chat(history=history)
        
        # El último mensaje del historial es el que se envía
        last_message = history[-1]['parts'][0]

        try:
            response = chat_session.send_message(last_message)
            return response
        except GoogleAPIError as e:
            error_message = f"Error de API de Gemini: {e}"
            print(f"ERROR: {error_message}", file=sys.stderr)
            # Devolver un objeto de respuesta simulado con el error en el texto
            return genai.types.GenerateContentResponse(
                candidates=[
                    genai.types.generation_types.Candidate(
                        content=genai.types.generation_types.Content(parts=[genai.types.generation_types.Part(text=error_message)]),
                        finish_reason=genai.types.generation_types.FinishReason.ERROR,
                    )
                ],
            )
        except Exception as e:
            import traceback
            error_message = f"Ocurrió un error inesperado: {e}\n{traceback.format_exc()}"
            print(f"ERROR: {error_message}", file=sys.stderr)
            return genai.types.GenerateContentResponse(
                candidates=[
                    genai.types.generation_types.Candidate(
                        content=genai.types.generation_types.Content(parts=[genai.types.generation_types.Part(text=error_message)]),
                        finish_reason=genai.types.generation_types.FinishReason.ERROR,
                    )
                ],
            )

    def get_tool(self, tool_name: str) -> BaseTool | None:
        """Encuentra y devuelve una herramienta de LangChain por su nombre."""
        for tool in self.langchain_tools:
            if tool.name == tool_name:
                return tool
        return None
