import os
import sys
import random
import string
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import litellm

logger = logging.getLogger(__name__)


def _normalize_ollama_api_base(api_base: Optional[str]) -> Optional[str]:
    """Normaliza la base de Ollama para evitar duplicar segmentos /api o /v1."""
    if not api_base:
        return api_base

    normalized = api_base.rstrip("/")
    for suffix in ("/api", "/v1"):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]

    return normalized.rstrip("/")

def setup_litellm_global_config():
    """Configura los parámetros globales de LiteLLM."""
    litellm.drop_params = True 
    litellm.modify_params = False 
    litellm.telemetry = False
    os.environ['LITELLM_LOG'] = 'ERROR' 
    litellm.set_verbose = False
    litellm.suppress_debug_info = True
    litellm.add_fastapi_middleware = False

class ProviderConfig:
    def __init__(self, model_name: Optional[str] = None):
        load_dotenv()
        self.model_name = model_name or os.getenv("LITELLM_MODEL") or "google/gemini-1.5-flash"
        self._validate_model_name()
        self.api_key = self._discover_api_key()
        self.api_base = os.getenv("LITELLM_API_BASE")
        self.headers = {}
        self.setup_provider()

    def _validate_model_name(self):
        if self.model_name.startswith("AIza"):
            logger.warning(f"Se detectó una API Key en LITELLM_MODEL ('{self.model_name[:8]}...'). Corrigiendo a 'google/gemini-1.5-flash'.")
            self.model_name = "google/gemini-1.5-flash"

    def _discover_api_key(self) -> Optional[str]:
        if self.model_name.startswith("gemini/"):
            return os.getenv("GOOGLE_API_KEY") or os.getenv("LITELLM_API_KEY")
        elif self.model_name.startswith("openrouter/"):
            return os.getenv("OPENROUTER_API_KEY") or os.getenv("LITELLM_API_KEY")
        elif self.model_name.startswith("ollama/"):
            return os.getenv("OLLAMA_CLOUD_API_KEY") or os.getenv("OLLAMA_API_KEY")
        return os.getenv("LITELLM_API_KEY") or os.getenv("OPENROUTER_API_KEY") or os.getenv("GOOGLE_API_KEY")

    def setup_provider(self):
        """Configura el proveedor y LiteLLM para el modelo actual."""
        model_to_use = self.model_name
        
        # Detectar si es Gemini nativo o OpenRouter
        is_gemini = model_to_use.startswith("gemini/") or ("gemini" in model_to_use.lower() and "openrouter" not in model_to_use.lower())
        
        if is_gemini:
            google_key = os.getenv("GOOGLE_API_KEY")
            if google_key:
                if not model_to_use.startswith("gemini/"):
                    model_to_use = f"gemini/{model_to_use.split('/')[-1]}"
                self.model_name = model_to_use
                self.api_key = google_key
                os.environ["LITELLM_MODEL"] = model_to_use
                os.environ["LITELLM_API_KEY"] = google_key
                litellm.api_base = None
                self.api_base = None
                self.headers = {}
                logger.info(f"🤖 Google AI Studio activo: {model_to_use}")
                return

        # Ollama Local/Cloud
        if model_to_use.startswith("ollama/"):
            ollama_local_base = _normalize_ollama_api_base(
                os.getenv("OLLAMA_API_BASE") or "http://localhost:11434"
            )
            ollama_cloud_base = "https://ollama.com"
            ollama_cloud_key = os.getenv("OLLAMA_CLOUD_API_KEY")
            ollama_local_key = os.getenv("OLLAMA_API_KEY")
            explicit_target = (os.getenv("OLLAMA_PROVIDER_TARGET") or "").strip().lower()

            # Prioridad explícita:
            # 1) OLLAMA_API_BASE => local/custom
            # 2) Si hay key cloud y no hay base local => cloud
            if explicit_target in ["cloud", "ollama_cloud"]:
                use_cloud = bool(ollama_cloud_key)
            elif explicit_target in ["local", "ollama"]:
                use_cloud = False
            elif os.getenv("OLLAMA_API_BASE"):
                use_cloud = False
            else:
                use_cloud = bool(ollama_cloud_key)

            # Si es cloud, quitar el prefijo 'ollama/'
            if use_cloud and model_to_use.startswith("ollama/"):
                self.model_name = model_to_use.replace("ollama/", "", 1)
            else:
                self.model_name = model_to_use
            self.api_key = ollama_cloud_key if use_cloud else ollama_local_key
            self.api_base = ollama_cloud_base if use_cloud else ollama_local_base
            self.headers = {}

            # Usar prefijo estándar 'ollama/' para asegurar compatibilidad con LiteLLM
            if not use_cloud and self.model_name.startswith("ollama/"):
                # Mantenemos 'ollama/' ya que LiteLLM lo maneja correctamente
                pass

            os.environ["LITELLM_MODEL"] = self.model_name
            if self.api_key:
                os.environ["LITELLM_API_KEY"] = self.api_key
            os.environ["LITELLM_API_BASE"] = self.api_base

            litellm.api_base = self.api_base
            logger.info(
                f"🤖 Ollama {'Cloud' if use_cloud else 'Local/Custom'} activo: {self.model_name} (base={self.api_base})"
            )
            return
        
        # OpenRouter o Fallback
        or_key = os.getenv("OPENROUTER_API_KEY")
        if or_key:
            if "/" not in model_to_use and not model_to_use.startswith("openrouter/"):
                model_to_use = f"openrouter/{model_to_use}"
            self.model_name = model_to_use
            self.api_key = or_key
            os.environ["LITELLM_MODEL"] = model_to_use
            os.environ["OPENROUTER_API_KEY"] = or_key
            os.environ["LITELLM_API_KEY"] = or_key
            self.api_base = self.api_base or "https://openrouter.ai/api/v1"
            litellm.api_base = self.api_base
            self.headers = {"HTTP-Referer": "https://github.com/gatovillano/KogniTerm", "X-Title": "KogniTerm"}
            litellm.headers = self.headers
            logger.info(f"🤖 OpenRouter activo: {model_to_use}")
        else:
            logger.warning("No se encontraron credenciales específicas. Usando configuración por defecto.")

    def get_completion_kwargs(self, messages, tools=None, **kwargs) -> Dict[str, Any]:
        params = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
            "api_key": self.api_key,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 8192),
            "num_retries": kwargs.get("num_retries", 3),
            "timeout": kwargs.get("timeout", 120),
        }
        
        if tools:
            params["tools"] = tools
            if any(k in self.model_name.lower() for k in ["gpt", "openai", "gemini"]):
                params["tool_choice"] = "auto"

        if self.model_name.startswith("ollama/"):
            params["custom_llm_provider"] = "ollama"
            if self.api_base:
                params["api_base"] = self.api_base
            if self.api_key and "ollama.com" in (self.api_base or ""):
                params["headers"] = {"Authorization": f"Bearer {self.api_key}"}
                
        if "openrouter" in self.model_name.lower():
            if "extra_body" not in params: params["extra_body"] = {}
            params["extra_body"]["reasoning"] = { "type": "enabled" }
            params["include_reasoning"] = True
            params["user"] = f"user_{generate_id(12)}"
            
        return params

def generate_id(length: int = 12) -> str:
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))
