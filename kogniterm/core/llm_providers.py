from abc import ABC, abstractmethod
import os
import json
import sys
from openai import OpenAI
import google.generativeai as genai
from google.generativeai.client import configure
from google.generativeai.generative_models import GenerativeModel
from google.generativeai import protos, types
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage

class AbstractLLMProvider(ABC):
    @abstractmethod
    def generate_content(self, *args, **kwargs):
        pass

class GeminiService(AbstractLLMProvider):
    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("La variable de entorno GOOGLE_API_KEY no está configurada.")
        configure(api_key=api_key)
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.model = GenerativeModel(self.model_name)

    def generate_content(self, *args, **kwargs):
        # Extraer los mensajes de LangChain de kwargs
        langchain_messages = kwargs.pop('contents', [])
        
        # Convertir mensajes de LangChain a formato Gemini
        gemini_contents = []
        for msg in langchain_messages:
            if isinstance(msg, SystemMessage):
                # Tratar SystemMessage como un HumanMessage para Gemini
                gemini_contents.append(protos.Content(role='user', parts=[protos.Part(text=msg.content)]))
            elif isinstance(msg, HumanMessage):
                gemini_contents.append(protos.Content(role='user', parts=[protos.Part(text=msg.content)]))
            elif isinstance(msg, AIMessage):
                parts = []
                if msg.content:
                    parts.append(protos.Part(text=msg.content))
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        parts.append(protos.Part(function_call=protos.FunctionCall(name=tc['name'], args=tc['args'])))
                gemini_contents.append(protos.Content(role='model', parts=parts))
            elif isinstance(msg, ToolMessage):
                # Asumiendo que tool_call_id es el nombre de la herramienta para la respuesta
                # y content es la respuesta de la herramienta
                tool_response_dict = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
                gemini_contents.append(protos.Content(role='tool', parts=[protos.Part(function_response=protos.FunctionResponse(name=msg.tool_call_id, response=tool_response_dict))]))
            else:
                # Ignorar otros tipos de mensajes o manejar según sea necesario
                print(f"Advertencia: Tipo de mensaje no soportado por Gemini: {type(msg)}", file=sys.stderr)
                continue

        # Obtener y convertir herramientas si existen
        tools = kwargs.get('tools')
        gemini_tools = []
        if tools:
            for tool_instance in tools:
                # Asumiendo que tool_instance es una instancia de LangChain BaseTool
                function_declaration = protos.FunctionDeclaration(
                    name=tool_instance.name,
                    description=tool_instance.description,
                    parameters=self._convert_pydantic_to_gemini_schema(tool_instance.args_schema)
                )
                gemini_tools.append(function_declaration)
        
        # Pasar los contenidos y las herramientas convertidas a la API de Gemini
        return self.model.generate_content(contents=gemini_contents, tools=gemini_tools if gemini_tools else None)

    def _convert_pydantic_to_gemini_schema(self, pydantic_model):
        """Convierte un modelo Pydantic a un protos.Schema compatible con Gemini."""
        pydantic_schema = pydantic_model.schema()

        type_mapping = {
            "string": protos.Type.STRING,
            "integer": protos.Type.INTEGER,
            "number": protos.Type.NUMBER,
            "boolean": protos.Type.BOOLEAN,
            "array": protos.Type.ARRAY,
            "object": protos.Type.OBJECT,
        }

        gemini_properties = {}
        if "properties" in pydantic_schema:
            for prop_name, prop_details in pydantic_schema["properties"].items():
                gemini_properties[prop_name] = protos.Schema(
                    type=type_mapping.get(prop_details.get("type", "string"), protos.Type.STRING),
                    description=prop_details.get("description", "")
                    # TODO: Añadir manejo para 'enum', 'items' para arrays, etc.
                )
        
        return protos.Schema(
            type=protos.Type.OBJECT,
            properties=gemini_properties,
            required=pydantic_schema.get("required", [])
        )

class OpenAIService(AbstractLLMProvider):
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("La variable de entorno OPENAI_API_KEY no está configurada.")
        
        base_url = os.getenv("LLM_API_ENDPOINT")
        if base_url:
            self.client = OpenAI(api_key=api_key, base_url=base_url)
        else:
            self.client = OpenAI(api_key=api_key)

        self.model_name = os.getenv("OPENAI_MODEL", "gpt-4o")

    def generate_content(self, *args, **kwargs):
        messages = kwargs.get('contents')
        tools = kwargs.get('tools')
        
        openai_messages = []
        if messages is None:
            messages = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                openai_messages.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                openai_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                if msg.tool_calls:
                    tool_calls = []
                    for tc in msg.tool_calls:
                        tool_calls.append({
                            "id": tc.get('id', f"call_{tc['name']}"),
                            "type": "function",
                            "function": {
                                "name": tc['name'],
                                "arguments": json.dumps(tc['args'])
                            }
                        })
                    openai_messages.append({"role": "assistant", "tool_calls": tool_calls})
                else:
                    openai_messages.append({"role": "assistant", "content": msg.content})
            elif isinstance(msg, ToolMessage):
                 openai_messages.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": json.dumps(msg.content)
                })
        
        openai_tools = []
        if tools:
            for tool in tools:
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.__parameters__[0].schema() if hasattr(tool, '__parameters__') and tool.__parameters__ else {}
                    }
                })
        
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=openai_messages,
            tools=openai_tools if openai_tools else [],
            tool_choice="auto" if openai_tools else "none"
        )
        
        first_choice = response.choices[0]
        if first_choice.message.content:
            return AIMessage(content=first_choice.message.content)
        elif first_choice.message.tool_calls:
            tool_calls = []
            for tc in first_choice.message.tool_calls:
                tool_calls.append({
                    "name": tc.function.name,
                    "args": json.loads(tc.function.arguments),
                    "id": tc.id
                })
            return AIMessage(content="", tool_calls=tool_calls)
        return AIMessage(content="")



class OpenAICompatibleProvider(AbstractLLMProvider):
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("La variable de entorno OPENAI_API_KEY no está configurada.")
        
        base_url = os.getenv("LLM_API_ENDPOINT")
        if not base_url:
            raise ValueError("La variable de entorno LLM_API_ENDPOINT debe configurarse para OpenAICompatibleProvider.")
        
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model_name = os.getenv("OPENAI_MODEL", "gpt-4o")

    def generate_content(self, *args, **kwargs):
        messages = kwargs.get('contents')
        tools = kwargs.get('tools')
        
        openai_messages = []
        if messages is None:
            messages = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                openai_messages.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                openai_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                if msg.tool_calls:
                    tool_calls = []
                    for tc in msg.tool_calls:
                        tool_calls.append({
                            "id": tc.get('id', f"call_{tc['name']}"),
                            "type": "function",
                            "function": {
                                "name": tc['name'],
                                "arguments": json.dumps(tc['args'])
                            }
                        })
                    openai_messages.append({"role": "assistant", "tool_calls": tool_calls})
                else:
                    openai_messages.append({"role": "assistant", "content": msg.content})
            elif isinstance(msg, ToolMessage):
                 openai_messages.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": json.dumps(msg.content)
                })
        
        openai_tools = []
        if tools:
            for tool in tools:
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.__parameters__[0].schema() if hasattr(tool, '__parameters__') and tool.__parameters__ else {}
                    }
                })
        
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=openai_messages,
            tools=openai_tools if openai_tools else [],
            tool_choice="auto" if openai_tools else "none"
        )
        
        first_choice = response.choices[0]
        if first_choice.message.content:
            return AIMessage(content=first_choice.message.content)
        elif first_choice.message.tool_calls:
            tool_calls = []
            for tc in first_choice.message.tool_calls:
                tool_calls.append({
                    "name": tc.function.name,
                    "args": json.loads(tc.function.arguments),
                    "id": tc.id
                })
            return AIMessage(content="", tool_calls=tool_calls)
        return AIMessage(content="")


def get_llm_provider(provider_name: str) -> AbstractLLMProvider:
    if provider_name == "gemini":
        return GeminiService()
    elif provider_name == "openai":
        return OpenAIService()
    elif provider_name == "openai_compatible":
        return OpenAICompatibleProvider()
    else:
        raise ValueError(f"Proveedor de LLM no soportado: {provider_name}. Use 'gemini', 'openai' o 'openai_compatible'.")