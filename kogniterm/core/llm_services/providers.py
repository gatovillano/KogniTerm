"""
Gestión de proveedores LLM.
"""
from typing import Dict, Optional

from kogniterm.core.llm_services.config import LLMConfig
from kogniterm.core.llm_services.errors import LLMError


class LLMProvider:
    """Proveedor base LLM."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self._client = None

    def initialize(self):
        """Inicializa el cliente del proveedor."""
        raise NotImplementedError

    def get_client(self):
        """Obtiene el cliente, inicializándolo si es necesario."""
        if self._client is None:
            self.initialize()
        return self._client

    def generate(self, prompt: str, **kwargs) -> str:
        """Genera texto a partir de un prompt."""
        raise NotImplementedError

    def generate_with_tools(self, prompt: str, tools: list, **kwargs) -> Dict:
        """Genera texto con invocación de herramientas."""
        raise NotImplementedError


class GeminiProvider(LLMProvider):
    """Proveedor para Google Gemini."""

    def __init__(self, config: LLMConfig, api_key: Optional[str] = None):
        super().__init__(config)
        self.api_key = api_key

    def initialize(self):
        """Inicializa el cliente Gemini."""
        try:
            import google.generativeai as genai
        except ImportError:
            raise LLMError(
                "google-generativeai no está instalado. "
                "Instálalo con: pip install google-generativeai"
            )
        if self.api_key:
            genai.configure(api_key=self.api_key)
        self._client = genai

    def generate(self, prompt: str, **kwargs) -> str:
        """Genera texto con Gemini."""
        client = self.get_client()
        model_name = kwargs.get("model", self.config.model)
        temperature = kwargs.get("temperature", self.config.temperature)
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)

        model = client.GenerativeModel(model_name)
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            },
        )
        return response.text

    def generate_with_tools(self, prompt: str, tools: list, **kwargs) -> Dict:
        """Genera texto con herramientas."""
        client = self.get_client()
        model_name = kwargs.get("model", self.config.model)
        temperature = kwargs.get("temperature", self.config.temperature)
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)

        model = client.GenerativeModel(
            model_name,
            tools=tools,
        )
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            },
        )
        return {
            "text": response.text,
            "prompt_feedback": response.prompt_feedback,
            "candidates": response.candidates,
        }


class OpenAIProvider(LLMProvider):
    """Proveedor para OpenAI."""

    def __init__(self, config: LLMConfig, api_key: Optional[str] = None):
        super().__init__(config)
        self.api_key = api_key

    def initialize(self):
        """Inicializa el cliente OpenAI."""
        try:
            import openai
        except ImportError:
            raise LLMError(
                "openai no está instalado. "
                "Instálalo con: pip install openai"
            )
        if self.api_key:
            openai.api_key = self.api_key
        self._client = openai

    def generate(self, prompt: str, **kwargs) -> str:
        """Genera texto con OpenAI."""
        client = self.get_client()
        model = kwargs.get("model", self.config.model)
        temperature = kwargs.get("temperature", self.config.temperature)
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)

        response = client.ChatCompletion.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content
