from abc import ABC, abstractmethod
from typing import List, Optional
# google.genai is lazily imported inside GeminiAdapter to avoid import-time dependency errors
from kogniterm.terminal.config_manager import ConfigManager
import os
import logging

logger = logging.getLogger(__name__)

class EmbeddingAdapter(ABC):
    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        pass

    def embed_query(self, text: str) -> List[float]:
        embeddings = self.embed_documents([text])
        if not embeddings:
            raise ValueError("No se pudo generar embedding para la consulta.")
        return embeddings[0]

class GeminiAdapter(EmbeddingAdapter):
    def __init__(self, api_key: str, model: str = "models/text-embedding-004"):
        try:
            import google.genai as genai
            genai.configure(api_key=api_key)
            self.genai = genai
        except ImportError:
            raise ImportError("google-genai package is not installed. Please install it with `pip install google-genai`.")
        self.model = model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        try:
            # Procesamiento por lotes nativo de Gemini
            # La API de Gemini acepta una lista de strings y devuelve una lista de embeddings
            result = self.genai.embed_content(
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
                    result = self.genai.embed_content(
                        model=self.model,
                        content=text,
                        task_type="retrieval_document"
                    )
                    embeddings.append(result['embedding'])
                except Exception as inner_e:
                    logger.error(f"Error crítico en embedding individual de Gemini: {inner_e}")
                    raise inner_e
            return embeddings

    def embed_query(self, text: str) -> List[float]:
        if not text:
            raise ValueError("La consulta no puede estar vacía.")
        try:
            result = self.genai.embed_content(
                model=self.model,
                content=text,
                task_type="retrieval_query"
            )
            return result['embedding']
        except Exception as e:
            logger.warning(f"Error en query embedding de Gemini, usando fallback de documento: {e}")
            return super().embed_query(text)

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

class SentenceTransformersAdapter(EmbeddingAdapter):
    def __init__(self, model: str | None = None):
        try:
            from sentence_transformers import SentenceTransformer
            import torch
            # Allow overriding default model via env var KOGNITERM_EMBEDDINGS_MODEL
            default_model = os.getenv("KOGNITERM_EMBEDDINGS_MODEL", "paraphrase-MiniLM-L3-v2")
            self.model_name = model or default_model

            # Prepare a project-local cache folder for models to avoid re-downloading
            project_models_dir = os.path.join(os.getcwd(), ".kogniterm", "models")
            os.makedirs(project_models_dir, exist_ok=True)
            # Sanitize model name into a filesystem-friendly directory name
            sanitized = self.model_name.replace("/", "__").replace(":", "__")
            local_model_path = os.path.join(project_models_dir, sanitized)

            # Use CPU by default unless explicitly disabled via KOGNITERM_FORCE_CPU=0
            force_cpu = os.getenv("KOGNITERM_FORCE_CPU", "1") in ("1", "true", "True")

            # If a cached local copy exists, load from there to avoid network download
            if os.path.isdir(local_model_path):
                logger.info(f"Loading SentenceTransformer '{self.model_name}' from local cache {local_model_path}")
                if force_cpu:
                    self.model = SentenceTransformer(local_model_path, device='cpu')
                else:
                    self.model = SentenceTransformer(local_model_path)
            else:
                # Otherwise load normally (may download) and attempt to cache the model for future runs
                logger.info(f"Loading SentenceTransformer '{self.model_name}' (may download) and caching to {local_model_path}")
                if force_cpu:
                    model_obj = SentenceTransformer(self.model_name, device='cpu')
                else:
                    try:
                        model_obj = SentenceTransformer(self.model_name)
                    except RuntimeError as e:
                        # Fallback to CPU on CUDA OOM or related GPU errors
                        if "out of memory" in str(e).lower() or "cuda" in str(e).lower():
                            logger.warning("CUDA OOM or CUDA error loading SentenceTransformer; falling back to CPU")
                            model_obj = SentenceTransformer(self.model_name, device='cpu')
                        else:
                            raise

                # Try to save a local copy for quicker subsequent startups; non-fatal on failure
                try:
                    model_obj.save(local_model_path)
                    logger.info(f"Saved SentenceTransformer model to local cache {local_model_path}")
                except Exception as e:
                    logger.warning(f"Could not cache SentenceTransformer model to {local_model_path}: {e}")

                self.model = model_obj
        except ImportError:
            raise ImportError("sentence-transformers package is not installed. Please install it with `pip install sentence-transformers`.")
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        try:
            embeddings = self.model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
            return [e.tolist() for e in embeddings]
        except Exception as e:
            logger.error(f"Error generating sentence-transformers embeddings: {e}")
            raise e

class FastEmbedAdapter(EmbeddingAdapter):
    def __init__(self, model: str = "BAAI/bge-small-en-v1.5"):
        try:
            from fastembed import TextEmbedding
            self.model_name = model

            # Use project-local cache folder if available (may be a path saved from previous runs)
            project_models_dir = os.path.join(os.getcwd(), ".kogniterm", "models")
            os.makedirs(project_models_dir, exist_ok=True)
            sanitized = self.model_name.replace("/", "__").replace(":", "__")
            local_model_path = os.path.join(project_models_dir, sanitized)

            model_arg = local_model_path if os.path.isdir(local_model_path) else self.model_name

            # TextEmbedding often accepts a model name or local path; prefer local cache when present
            self.client = TextEmbedding(model_name=model_arg)

            if model_arg != self.model_name:
                logger.info(f"FastEmbed: using local cached model at {model_arg}")
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
    _instance: Optional["EmbeddingsService"] = None

    def __init__(self):
        EmbeddingsService._instance = self  # Guardar como singleton
        self.config_manager = ConfigManager()
        self.config = self.config_manager.get_config()
        self.provider = self.config.get("embeddings_provider", "fastembed")
        self.model = self.config.get("embeddings_model")
        self.api_key = self._get_api_key()
        
        # Ollama, FastEmbed and local sentence-transformers don't strictly need an API key
        if self.provider in ["ollama", "fastembed", "sentence_transformers", "sentence-transformers"]:
            self.adapter = self._get_adapter()
        elif self.api_key:
            self.adapter = self._get_adapter()
        else:
            self.adapter = None
            logger.warning(f"No API key found for provider {self.provider}. EmbeddingsService will not function.")

    @classmethod
    def get_instance(cls) -> "EmbeddingsService":
        """Obtiene la instancia singleton, creándola si no existe."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

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
        elif self.provider in ["sentence_transformers", "sentence-transformers"]:
            model = self.model if self.model else "all-MiniLM-L6-v2"
            return SentenceTransformersAdapter(model)
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

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Compatibilidad con llamadas antiguas que esperan una API tipo LangChain."""
        return self.generate_embeddings(texts)

    def embed_query(self, text: str) -> List[float]:
        """Genera un embedding para una única consulta."""
        if not self.adapter:
            raise ValueError("EmbeddingsService is not initialized properly.")
        if not text:
            raise ValueError("La consulta no puede estar vacía.")
        return self.adapter.embed_query(text)
