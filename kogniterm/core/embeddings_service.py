from abc import ABC, abstractmethod
from typing import List
import google.genai as genai
from kogniterm.terminal.config_manager import ConfigManager
import os
import logging

logger = logging.getLogger(__name__)

class EmbeddingAdapter(ABC):
    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        pass

class GeminiAdapter(EmbeddingAdapter):
    def __init__(self, api_key: str, model: str = "models/text-embedding-004"):
        genai.configure(api_key=api_key)
        self.model = model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        embeddings = []
        for text in texts:
            try:
                result = genai.embed_content(
                    model=self.model,
                    content=text,
                    task_type="retrieval_document"
                )
                embeddings.append(result['embedding'])
            except Exception as e:
                logger.error(f"Error generating embedding for text with Gemini: {e}")
                raise e
        return embeddings

class OpenAIAdapter(EmbeddingAdapter):
    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key)
            self.model = model
        except ImportError:
            raise ImportError("OpenAI package is not installed. Please install it with `pip install openai`.")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        try:
            data = self.client.embeddings.create(input=texts, model=self.model).data
            return [d.embedding for d in data]
        except Exception as e:
            logger.error(f"Error generating OpenAI embeddings: {e}")
            raise e

class OllamaAdapter(EmbeddingAdapter):
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "nomic-embed-text"):
        self.base_url = base_url
        self.model = model
        import requests
        self.requests = requests

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        embeddings = []
        for text in texts:
            try:
                response = self.requests.post(
                    f"{self.base_url}/api/embeddings",
                    json={
                        "model": self.model,
                        "prompt": text
                    }
                )
                response.raise_for_status()
                result = response.json()
                embeddings.append(result['embedding'])
            except Exception as e:
                logger.error(f"Error generating embedding for text with Ollama: {e}")
                raise e
        return embeddings

class EmbeddingsService:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.config = self.config_manager.get_config()
        self.provider = self.config.get("embeddings_provider", "gemini")
        self.model = self.config.get("embeddings_model")
        self.api_key = self._get_api_key()
        
        # Ollama doesn't strictly need an API key, so we handle it separately or allow None
        if self.provider == "ollama":
             self.adapter = self._get_adapter()
        elif self.api_key:
             self.adapter = self._get_adapter()
        else:
            self.adapter = None
            logger.warning(f"No API key found for provider {self.provider}. EmbeddingsService will not function.")

    def _get_api_key(self):
        key = self.config.get(f"{self.provider}_api_key")
        if not key:
            if self.provider == "gemini":
                key = os.getenv("GOOGLE_API_KEY")
            elif self.provider == "openai":
                key = os.getenv("OPENAI_API_KEY")
        return key

    def _get_adapter(self) -> EmbeddingAdapter:
        if self.provider == "gemini":
            model = self.model if self.model else "models/text-embedding-004"
            return GeminiAdapter(self.api_key, model)
        elif self.provider == "openai":
            model = self.model if self.model else "text-embedding-3-small"
            return OpenAIAdapter(self.api_key, model)
        elif self.provider == "ollama":
            model = self.model if self.model else "nomic-embed-text"
            base_url = self.config.get("ollama_base_url", "http://localhost:11434")
            return OllamaAdapter(base_url, model)
        else:
            raise ValueError(f"Unsupported embeddings provider: {self.provider}")

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        if not self.adapter:
             raise ValueError("EmbeddingsService is not initialized properly.")
        return self.adapter.embed_documents(texts)
