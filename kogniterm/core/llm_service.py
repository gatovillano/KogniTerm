import os
import sys
import json
from typing import List, Dict, Any, Union, cast
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage, FunctionMessage, ToolMessage, ToolCall
from google.generativeai.protos import Part, FunctionCall, FunctionResponse # Importar Part y FunctionCall

from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam
from openai.types.chat.completion_create_params import Function
from google.generativeai.types import GenerationConfig
from google.generativeai.types.content_types import FunctionCallingConfigDict, ToolConfigDict as GenaiToolConfigDict


from langchain_core.tools import BaseTool
from pydantic import BaseModel

from .tools import get_callable_tools

# --- Funciones de Ayuda para Conversión de Herramientas ---

def pydantic_to_json_schema(pydantic_model: BaseModel) -> Dict[str, Any]:
    """Convierte un modelo Pydantic a un esquema JSON compatible con OpenAI."""
    schema = pydantic_model.schema()
    # OpenAI espera el esquema de parámetros dentro de un objeto 'parameters'
    return {
        "type": "function",
        "function": {
            "name": schema.get("title", "UnknownFunction"),
            "description": schema.get("description", "No description available."),
            "parameters": {
                "type": "object",
                "properties": schema.get("properties", {}),
                "required": schema.get("required", []),
            },
        },
    }

# --- Clase Principal del Servicio LLM ---

class LLMService:
    """
    Un servicio para interactuar con un LLM, soportando proveedores compatibles con OpenAI y Google Gemini.
    La selección del proveedor se hace a través de la variable de entorno LLM_PROVIDER.
    - 'openai' (o no definida): Usa un endpoint compatible con OpenAI.
    - 'google': Usa la API de Google Gemini.
    """
    def __init__(self):
        """Inicializa el servicio, configura la API y prepara las herramientas."""
        self.provider = os.getenv("LLM_PROVIDER", "openai").lower()
        self.langchain_tools = get_callable_tools()

        if self.provider == "openai":
            self._init_openai()
        elif self.provider == "google":
            self._init_google()
        else:
            raise ValueError(f"Proveedor LLM no soportado: '{self.provider}'. Use 'openai' o 'google'.")

    def _init_openai(self):
        """Inicializa el cliente para un proveedor compatible con OpenAI."""
        try:
            from openai import AsyncOpenAI
        except ImportError:
            print("Error: La librería 'openai' no está instalada. Por favor, ejecute 'pip install openai'.", file=sys.stderr)
            raise

        self.api_key = os.getenv("LLM_API_KEY")
        self.base_url = os.getenv("LLM_API_ENDPOINT")
        self.model_name = os.getenv("LLM_MODEL") or "gpt-3.5-turbo" # Default to avoid None

        if not self.api_key or not self.model_name:
            raise ValueError("Para el proveedor 'openai', las variables de entorno LLM_API_KEY y LLM_MODEL son obligatorias.")

        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        # Ensure model_name is not None for Pylance
        assert self.model_name is not None

        # Convert tools for OpenAI format
        self.openai_tools: List[ChatCompletionToolParam] = [
            ChatCompletionToolParam(type="function", function=pydantic_to_json_schema(tool.args_schema)["function"])
            for tool in self.langchain_tools if tool.args_schema
        ]

    def _init_google(self):
        """Inicializa el cliente para Google Gemini."""
        try:
            from google.generativeai.client import configure
            from google.generativeai.generative_models import GenerativeModel
            from google.generativeai.types import GenerationConfig
            from .google_tools_converter import convert_langchain_tool_to_genai # Helper refactorizado
        except ImportError:
            print("Error: La librería 'google-generativeai' no está instalada.", file=sys.stderr)
            raise

        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("La variable de entorno GOOGLE_API_KEY no está configurada.")

        configure(api_key=api_key)
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        self.google_ai_tools = [convert_langchain_tool_to_genai(tool) for tool in self.langchain_tools]

        self.model = GenerativeModel(
            self.model_name,
            tools=self.google_ai_tools,
            generation_config=GenerationConfig(temperature=0.7)
        )

    async def ainvoke(self, history: List[BaseMessage]) -> Any:
        """Invoca el modelo LLM de forma asíncrona con un historial de conversación."""
        if self.provider == "openai":
            return await self._ainvoke_openai(history)
        else: # google
            return await self._ainvoke_google(history)

    async def _ainvoke_openai(self, history: List[BaseMessage]):
        """Invoca un modelo compatible con OpenAI."""
        openai_messages = []
        for msg in history:
            if isinstance(msg, HumanMessage):
                openai_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                if msg.tool_calls:
                    openai_messages.append({
                        "role": "assistant",
                        "tool_calls": [
                            {"id": tc['id'], "type": "function", "function": {"name": tc['name'], "arguments": json.dumps(tc['args'])}}
                            for tc in msg.tool_calls
                        ]
                    })
                elif msg.content:
                    openai_messages.append({"role": "assistant", "content": msg.content})
            elif isinstance(msg, SystemMessage):
                openai_messages.append({"role": "system", "content": msg.content})
            elif isinstance(msg, ToolMessage):
                openai_messages.append({"role": "tool", "tool_call_id": msg.tool_call_id, "content": msg.content})
            else:
                raise ValueError(f"Tipo de mensaje no soportado para conversión a OpenAI: {type(msg)}")
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=openai_messages,
                tools=self.openai_tools,
                tool_choice="auto"
            )
            return response
        except Exception as e:
            print(f"Error de API compatible con OpenAI: {e}", file=sys.stderr)
            raise

    async def _ainvoke_google(self, history: List[BaseMessage]):
        """Invoca el modelo Gemini de Google de forma stateless."""
        try:
            from google.api_core.exceptions import GoogleAPIError
        except ImportError:
            raise ImportError("Se requiere 'google-api-core' para el proveedor de Google.")

        try:
            gemini_contents = []
            for msg in history:
                if isinstance(msg, HumanMessage):
                    gemini_contents.append({"role": "user", "parts": [Part(text=msg.content)]})
                elif isinstance(msg, AIMessage):
                    parts = []
                    if msg.content:
                        parts.append(Part(text=msg.content))
                    if msg.tool_calls:
                        for tc in msg.tool_calls:
                            parts.append(Part(function_call=FunctionCall(name=tc['name'], args=tc['args'])))
                    gemini_contents.append({"role": "model", "parts": parts})
                elif isinstance(msg, SystemMessage):
                    # Gemini does not have a direct system message role in generate_content,
                    # so we prepend it to the first user message or handle it as a user message.
                    # For simplicity, we'll convert it to a user message here.
                    gemini_contents.append({"role": "user", "parts": [Part(text=msg.content)]})
                elif isinstance(msg, ToolMessage):
                    # Tool messages in Gemini are typically responses to function calls
                    gemini_contents.append({"role": "user", "parts": [Part(function_response=FunctionResponse(name=msg.tool_call_id, response={"content": msg.content}))]})
                else:
                    raise ValueError(f"Tipo de mensaje no soportado para conversión a Gemini: {type(msg)}")

            response = await self.model.generate_content_async(
                contents=gemini_contents, # Usar los contenidos convertidos
                generation_config=cast(GenerationConfig, self.model._generation_config),
                tools=self.google_ai_tools,
                tool_config=cast(GenaiToolConfigDict, {"function_calling_config": {"mode": "AUTO"}})
            )
            return response
        except GoogleAPIError as e:
            print(f"Error de API de Gemini: {e}", file=sys.stderr)
            raise
        except Exception as e:
            import traceback
            print(f"Ocurrió un error inesperado: {e}\n{traceback.format_exc()}", file=sys.stderr)
            raise

    def get_tool(self, tool_name: str) -> Union[BaseTool, None]:
        """Encuentra y devuelve una herramienta de LangChain por su nombre."""
        return next((tool for tool in self.langchain_tools if tool.name == tool_name), None)

llm_service = LLMService()
