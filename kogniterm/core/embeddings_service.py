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
        if not texts:
            return []
        try:
            # Procesamiento por lotes nativo de Gemini
            # La API de Gemini acepta una lista de strings y devuelve una lista de embeddings
            result = genai.embed_content(
                model=self.model,
                content=texts,
                task_type="retrieval_document"
            )
            # Si se pasa una lista, 'embedding' contiene la lista de vectores
            return result['embedding']
        except Exception as e:
            logger.warning(f"Error en batch embedding de Gemini, reintentando uno por uno: {e}")
            embeddings = []
            for text in texts:
                try:
                    result = genai.embed_content(
                        model=self.model,
                        content=text,
                        task_type="retrieval_document"
                    )
                    embeddings.append(result['embedding'])
                except Exception as inner_e:
                    logger.error(f"Error crítico en embedding individual de Gemini: {inner_e}")
                    raise inner_e
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
        if not texts:
            return []
        try:
            # Intentar el nuevo endpoint /api/embed de Ollama que soporta lotes
            response = self.requests.post(
                f"{self.base_url}/api/embed",
                json={
                    "model": self.model,
                    "input": texts
                },
                timeout=60
            )
            
            if response.status_code == 200:
                return response.json().get('embeddings', [])
            
            # Fallback al endpoint antiguo /api/embeddings si /api/embed no está disponible
            logger.warning(f"Ollama /api/embed no disponible (status {response.status_code}), usando fallback lento.")
            embeddings = []
            for text in texts:
                resp = self.requests.post(
                    f"{self.base_url}/api/embeddings",
                    json={
                        "model": self.model,
                        "prompt": text
                    }
                )
                resp.raise_for_status()
                embeddings.append(resp.json()['embedding'])
            return embeddings
        except Exception as e:
            logger.error(f"Error generando embeddings con Ollama: {e}")
            raise e

class FastEmbedAdapter(EmbeddingAdapter):
    def __init__(self, model: str = "BAAI/bge-small-en-v1.5"):
        try:
            from fastembed import TextEmbedding
            self.model_name = model
            self.client = TextEmbedding(model_name=self.model_name)
        except ImportError:
            raise ImportError("FastEmbed package is not installed. Please install it with `pip install fastembed`.")
        except Exception as e:
            logger.error(f"Error initializing FastEmbed: {e}")
            raise e

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        try:
            # fastembed devuelve un generador de numpy arrays
            embeddings_generator = self.client.embed(texts)
            return [embedding.tolist() for embedding in embeddings_generator]
        except Exception as e:
            logger.error(f"Error generating FastEmbed embeddings: {e}")
            raise e

class EmbeddingsService:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.config = self.config_manager.get_config()
        self.provider = self.config.get("embeddings_provider", "fastembed")
        self.model = self.config.get("embeddings_model")
        self.api_key = self._get_api_key()
        
        # Ollama and FastEmbed don't strictly need an API key
        if self.provider in ["ollama", "fastembed"]:
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
        elif self.provider == "fastembed":
            model = self.model if self.model else "BAAI/bge-small-en-v1.5"
            return FastEmbedAdapter(model)
        else:
            raise ValueError(f"Unsupported embeddings provider: {self.provider}")

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        if not self.adapter:
             raise ValueError("EmbeddingsService is not initialized properly.")
        
        if not texts:
            return []

        # Implementar procesamiento por lotes para optimizar latencia y respetar límites de API
        # Gemini tiene un límite de 100 por lote, OpenAI de 2048. Usamos 100 como valor seguro y rápido.
        batch_size = 100
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            try:
                batch_embeddings = self.adapter.embed_documents(batch)
                all_embeddings.extend(batch_embeddings)
            except Exception as e:
                logger.error(f"Error en el lote de embeddings {i//batch_size}: {e}")
                raise e
                
        return all_embeddings
