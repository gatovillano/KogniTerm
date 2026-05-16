"""
Multi-Provider Manager para KogniTerm.

Este módulo implementa:
1. Sistema de fallback automático entre múltiples proveedores de LLM
2. Métricas de rendimiento y health checks
3. Soporte para proveedores adicionales (Google, Cohere, Anthropic, etc.)
"""

import os
import time
import json
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from collections import deque
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from litellm import completion, litellm

logger = logging.getLogger(__name__)


class ProviderStatus(Enum):
    """Estados posibles de un proveedor."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ProviderMetrics:
    """Métricas de rendimiento para un proveedor."""
    provider_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    last_request_time: Optional[datetime] = None
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None
    consecutive_failures: int = 0
    status: ProviderStatus = ProviderStatus.UNKNOWN
    
    # Historial de latencias (últimas 100)
    latency_history: deque = field(default_factory=lambda: deque(maxlen=100))
    
    def record_success(self, latency_ms: float):
        """Registra una solicitud exitosa."""
        self.total_requests += 1
        self.successful_requests += 1
        self.total_latency_ms += latency_ms
        self.avg_latency_ms = self.total_latency_ms / self.successful_requests
        self.last_request_time = datetime.now()
        self.consecutive_failures = 0
        self.latency_history.append(latency_ms)
        self._update_status()
    
    def record_failure(self, error_msg: str):
        """Registra una solicitud fallida."""
        self.total_requests += 1
        self.failed_requests += 1
        self.last_error = error_msg
        self.last_error_time = datetime.now()
        self.consecutive_failures += 1
        self._update_status()
    
    def _update_status(self):
        """Actualiza el estado basado en métricas recientes."""
        if self.consecutive_failures >= 3:
            self.status = ProviderStatus.UNHEALTHY
        elif self.consecutive_failures >= 1:
            self.status = ProviderStatus.DEGRADED
        elif self.successful_requests > 0:
            self.status = ProviderStatus.HEALTHY
    
    def get_success_rate(self) -> float:
        """Retorna la tasa de éxito (0.0 - 1.0)."""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte las métricas a diccionario."""
        return {
            "provider_name": self.provider_name,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "last_request_time": self.last_request_time.isoformat() if self.last_request_time else None,
            "last_error": self.last_error,
            "last_error_time": self.last_error_time.isoformat() if self.last_error_time else None,
            "consecutive_failures": self.consecutive_failures,
            "status": self.status.value,
            "success_rate": round(self.get_success_rate() * 100, 2),
            "recent_avg_latency_ms": round(sum(self.latency_history) / len(self.latency_history), 2) if self.latency_history else 0
        }


@dataclass
class ProviderConfig:
    """Configuración para un proveedor de LLM."""
    name: str
    model_prefix: str
    api_key_env: str
    api_base: Optional[str] = None
    api_base_env: Optional[str] = None
    priority: int = 100  # Menor = mayor prioridad
    enabled: bool = True
    timeout_seconds: int = 120
    max_retries: int = 3
    fallback_on_error_codes: List[str] = field(default_factory=list)
    
    def get_api_key(self) -> Optional[str]:
        """Obtiene la API key desde variables de entorno."""
        return os.getenv(self.api_key_env)
    
    def get_api_base(self) -> Optional[str]:
        """Obtiene la URL base de la API, priorizando la variable de entorno si existe."""
        if self.api_base_env:
            env_base = os.getenv(self.api_base_env)
            if env_base:
                return env_base
        return self.api_base
    
    def is_configured(self) -> bool:
        """Verifica si el proveedor está configurado."""
        if not self.enabled:
            return False
            
        # Soporte para forzar local o cloud mediante OLLAMA_PROVIDER_TARGET
        target = (os.getenv("OLLAMA_PROVIDER_TARGET") or "").strip().lower()
        if self.name == "ollama_cloud" and target in ["local", "ollama"]:
            return False
        if self.name == "ollama" and target in ["cloud", "ollama_cloud"]:
            return False

        # Para Ollama local o cloud con base personalizada, puede no requerir API Key
        if self.model_prefix == "ollama":
            # Si el target forzó este proveedor, asumimos configurado para evitar fallback silencioso
            if self.name == "ollama_cloud" and target in ["cloud", "ollama_cloud"]:
                return True
            if self.name == "ollama" and target in ["local", "ollama"]:
                return True

            # Si tiene base personalizada (local, proxy o IP privada), se considera configurado
            api_base = self.get_api_base()
            if api_base:
                if any(x in api_base for x in ["localhost", "127.0.0.1", "0.0.0.0", "::1"]):
                    return True
                # Si el usuario configuró OLLAMA_API_BASE manualmente, asumimos que sabe lo que hace
                if os.getenv("OLLAMA_API_BASE") and self.name == "ollama":
                    return True

            # Para Ollama Cloud u otros, requerimos API Key
            key = self.get_api_key() or os.getenv("OLLAMA_API_KEY")
            return key is not None
            
        return self.get_api_key() is not None


# Configuraciones predefinidas de proveedores
DEFAULT_PROVIDERS = [
    ProviderConfig(
        name="openrouter",
        model_prefix="openrouter",
        api_key_env="OPENROUTER_API_KEY",
        api_base="https://openrouter.ai/api/v1",
        priority=10,
        fallback_on_error_codes=["429", "503", "504", "timeout"]
    ),
    ProviderConfig(
        name="google",
        model_prefix="gemini",
        api_key_env="GOOGLE_API_KEY",
        priority=80,
        fallback_on_error_codes=["429", "503", "500"]
    ),
    ProviderConfig(
        name="anthropic",
        model_prefix="anthropic",
        api_key_env="ANTHROPIC_API_KEY",
        priority=30,
        fallback_on_error_codes=["429", "529", "503"]
    ),
    ProviderConfig(
        name="cohere",
        model_prefix="cohere",
        api_key_env="COHERE_API_KEY",
        priority=40,
        fallback_on_error_codes=["429", "503"]
    ),
    ProviderConfig(
        name="openai",
        model_prefix="openai",
        api_key_env="OPENAI_API_KEY",
        priority=50,
        fallback_on_error_codes=["429", "503", "500"]
    ),
    ProviderConfig(
        name="ollama",
        model_prefix="ollama",
        api_key_env="OLLAMA_API_KEY",
        api_base="http://localhost:11434/v1",
        api_base_env="OLLAMA_API_BASE",
        priority=20,
        fallback_on_error_codes=["429", "503"]
    ),
    ProviderConfig(
        name="ollama_cloud",
        model_prefix="ollama",
        api_key_env="OLLAMA_CLOUD_API_KEY",
        api_base="https://ollama.com/v1",
        api_base_env="OLLAMA_CLOUD_API_BASE",
        priority=65,
        fallback_on_error_codes=["429", "503"]
    ),
    ProviderConfig(
        name="zhipuai",
        model_prefix="zhipuai",
        api_key_env="ZHIPUAI_API_KEY",
        api_base="https://open.bigmodel.cn/api/paas/v4/",
        api_base_env="ZHIPUAI_API_BASE",
        priority=70,
        fallback_on_error_codes=["429", "503"]
    ),
    ProviderConfig(
        name="kilocode",
        # Kilo Gateway es OpenAI-compatible → LiteLLM requiere prefijo 'openai'
        model_prefix="openai",
        api_key_env="KILOCODE_API_KEY",
        # La URL debe terminar en /v1 para que LiteLLM añada /chat/completions correctamente
        api_base="https://api.kilo.ai/api/gateway/v1",
        priority=15,
        fallback_on_error_codes=["429", "503", "timeout"]
    ),
]


class MultiProviderManager:
    """
    Gestor de múltiples proveedores de LLM con fallback automático y métricas.
    """
    
    def __init__(self, providers: Optional[List[ProviderConfig]] = None):
        self.providers = providers or DEFAULT_PROVIDERS.copy()
        self.metrics: Dict[str, ProviderMetrics] = {}
        self._lock = threading.RLock()
        self._health_check_executor = ThreadPoolExecutor(max_workers=5)
        self.preferred_provider: Optional[str] = None  # Proveedor preferido (global, por el usuario)
        
        # Inicializar métricas para cada proveedor
        for provider in self.providers:
            self.metrics[provider.name] = ProviderMetrics(provider_name=provider.name)
        
        # Configuración global de LiteLLM
        litellm.drop_params = True
        litellm.modify_params = False
        litellm.telemetry = False
        litellm.set_verbose = False
        litellm.suppress_debug_info = True
        
        logger.info(f"MultiProviderManager inicializado con {len(self.providers)} proveedores")
    
    def _clean_error_message(self, e: Exception) -> str:
        """Limpia y simplifica los mensajes de error de LiteLLM."""
        error_msg = str(e)
        
        # Si el mensaje contiene HTML, es basura visual para el usuario
        if "<!DOCTYPE html>" in error_msg or "<html>" in error_msg.lower():
            if "Model Not Found" in error_msg:
                return "Modelo no encontrado en el proveedor (404)"
            return "El proveedor devolvió una página de error (posiblemente un error 404 o 500)"
            
        # Simplificar errores de autenticación
        if "AuthenticationError" in error_msg or "401" in error_msg:
            if "User not found" in error_msg:
                return "API Key no válida o cuenta no encontrada en el proveedor"
            return "Error de autenticación: Verifica tu API Key"
            
        # Si es un error de Rate Limit
        if "429" in error_msg or "rate limit" in error_msg.lower():
            return "Límite de velocidad excedido (Rate Limit)"
            
        # Recortar mensajes excesivamente largos si no se filtraron antes
        if len(error_msg) > 200:
            return error_msg[:197] + "..."
            
        return error_msg
    
    def get_available_providers(self) -> List[ProviderConfig]:
        """Retorna lista de proveedores configurados y disponibles, priorizando Ollama."""
        available = []
        
        # Sort by priority, but ensure 'preferred_provider' comes first if available
        def provider_key(p):
            if self.preferred_provider and p.name == self.preferred_provider:
                return (0, 0)  # Preferido tiene prioridad máxima
            if p.name == "ollama":
                return (0, 1)  # Ollama tiene prioridad especial si no hay preferido
            return (1, p.priority)  # Resto por prioridad
        
        sorted_providers = sorted(self.providers, key=provider_key)
        
        for provider in sorted_providers:
            is_conf = provider.is_configured()
            if is_conf:
                metrics = self.metrics.get(provider.name)
                # No incluir proveedores en estado UNHEALTHY, EXCEPTO si es el preferido
                if metrics and metrics.status == ProviderStatus.UNHEALTHY:
                    if self.preferred_provider != provider.name:
                        logger.debug(f"Proveedor {provider.name} omitido por estado UNHEALTHY")
                        continue
                available.append(provider)
            else:
                logger.debug(f"💡 Proveedor {provider.name} no disponible (no configurado). Env var: {provider.api_key_env}")
        return available
    
    def get_primary_provider(self) -> Optional[ProviderConfig]:
        """Retorna el proveedor primario (de mayor prioridad disponible)."""
        available = self.get_available_providers()
        return available[0] if available else None
    
    def get_fallback_chain(self) -> List[ProviderConfig]:
        """Retorna la cadena de fallback ordenada por prioridad."""
        return self.get_available_providers()
    
    def _determine_ideal_provider(self, model_name: str, force_provider: Optional[ProviderConfig] = None) -> Optional[ProviderConfig]:
        if force_provider:
            return force_provider
            
        if not model_name:
            return self.get_primary_provider()
            
        available = self.get_available_providers()
        explicit_target = (os.getenv("OLLAMA_PROVIDER_TARGET") or "").strip().lower()
        
        # 1. Priorizar el proveedor preferido si está disponible
        if self.preferred_provider:
            pref_p = next((p for p in available if p.name == self.preferred_provider), None)
            if pref_p:
                model_prefix = model_name.split("/")[0] if "/" in model_name else None
                if model_prefix:
                    # Si el prefijo coincide con el preferido, o ambos son ollama
                    if model_prefix == pref_p.name or model_prefix == pref_p.model_prefix or model_prefix.replace("-", "_") == pref_p.name:
                        return pref_p
                    elif pref_p.name.startswith("ollama") and model_prefix == "ollama":
                        return pref_p
                    # Si el prefijo NO coincide, permitimos que siga la lógica normal
                else:
                    # Modelo sin prefijo (ej. gpt-4o), forzamos al proveedor preferido
                    return pref_p

        # 2. Si no se resolvió por preferido, intentar por prefijo de Ollama
        if model_name.startswith("ollama/"):
            if explicit_target in ["cloud", "ollama_cloud"]:
                provider = next((p for p in available if p.name == "ollama_cloud"), None)
                if provider:
                    return provider
            provider = next((p for p in available if p.name == "ollama"), None)
            if provider: return provider
            provider = next((p for p in available if p.name == "ollama_cloud"), None)
            if provider: return provider
        
        # 3. Lógica basada en prefijo genérico
        if "/" in model_name:
            parts = model_name.split("/", 1)
            prefix = parts[0]
            provider = next((p for p in available if p.name == prefix or p.name == prefix.replace("-", "_") or p.model_prefix == prefix), None)
            if provider: return provider
        
        # 4. Inferencia por nombre del modelo
        lower_model = model_name.lower()
        if lower_model.startswith("gemini"):
            provider = next((p for p in available if p.name == "google"), None)
            if provider: return provider
        elif "gpt" in lower_model:
            provider = next((p for p in available if p.name == "openai"), None)
            if provider: return provider
        elif "claude" in lower_model:
            provider = next((p for p in available if p.name == "anthropic"), None)
            if provider: return provider

        # 5. Fallback final al proveedor primario
        return self.get_primary_provider()

    def execute(
        self,
        model_name: str,
        messages: List[Dict[str, Any]],
        stream: bool = True,
        temperature: float = 0.7,
        max_tokens: int = 8192,
        tools: Optional[List[Dict]] = None,
        force_provider: Optional[ProviderConfig] = None,
        **kwargs
    ):
        """
        Ejecuta una solicitud con el proveedor adecuado.
        """
        provider = self._determine_ideal_provider(model_name, force_provider)
        
        if not provider:
            raise ValueError("No hay proveedores configurados disponibles. Revisa tus API Keys.")

        
        try:
            logger.info(f"Usando proveedor: {provider.name}")
            
            # Construir nombre completo del modelo
            if "/" in model_name:
                # Si el modelo ya tiene prefijo, asegurarse de usarlo
                actual_model = model_name.split("/", 1)[1]
            else:
                actual_model = model_name

            # ESTRATEGIA: Si el proveedor es ollama, el modelo debe ser solo el nombre del modelo
            # LiteLLM se encarga de prefijarlo correctamente si custom_llm_provider está puesto
            if provider.name.startswith("ollama"):
                full_model_name = actual_model
            else:
                full_model_name = f"{provider.model_prefix}/{actual_model}"
            
            logger.debug(f"Llamando a completion con modelo: {full_model_name}, proveedor: {provider.name}")

            completion_kwargs = {
                "model": full_model_name,
                "messages": messages,
                "stream": stream,
                "api_key": kwargs.get("api_key") or provider.get_api_key(),
                "temperature": temperature,
                "max_tokens": max_tokens,
                "timeout": provider.timeout_seconds,
                "num_retries": provider.max_retries,
            }

            if kwargs.get("reasoning_effort"):
                completion_kwargs["reasoning_effort"] = kwargs.get("reasoning_effort")

            if kwargs.get("tool_choice"):
                completion_kwargs["tool_choice"] = kwargs.get("tool_choice")

            if provider.model_prefix == "ollama":
                completion_kwargs["custom_llm_provider"] = "ollama"
            elif provider.name == "kilocode":
                completion_kwargs["custom_llm_provider"] = "openai"
            
            if tools:
                completion_kwargs["tools"] = tools
            
            # Limpiar headers totalmente antes de decidir
            completion_kwargs["headers"] = {}
            
            if provider.name.startswith("ollama"):
                api_base = kwargs.get("api_base") or provider.get_api_base()
                if api_base:
                    completion_kwargs["api_base"] = api_base
                
                # Para ollama local, no requiere headers (o usa los definidos en config)
                if provider.name == "ollama_cloud":
                    cloud_key = kwargs.get("api_key") or provider.get_api_key()
                    if cloud_key:
                        completion_kwargs["headers"] = {"Authorization": f"Bearer {cloud_key}"}
            else:
                api_base = kwargs.get("api_base") or provider.get_api_base()
                if api_base:
                    completion_kwargs["api_base"] = api_base
                
                if provider.name == "openrouter":
                    completion_kwargs["headers"] = {"HTTP-Referer": "https://github.com/gatovillano/KogniTerm", "X-Title": "KogniTerm"}

            # Permitir sobrescribir headers explícitamente desde el llamador
            explicit_headers = kwargs.get("headers")
            if explicit_headers and isinstance(explicit_headers, dict):
                completion_kwargs["headers"] = explicit_headers
            
            # Si headers sigue vacío, eliminarlo para no enviar un dict vacío que pudiera molestar a LiteLLM
            if not completion_kwargs["headers"]:
                del completion_kwargs["headers"]
            
            start_time = time.time()
            logger.debug(f"Completion kwargs: {json.dumps({k: v for k, v in completion_kwargs.items() if k != 'messages'}, indent=2)}")
            response = completion(**completion_kwargs)
            latency_ms = (time.time() - start_time) * 1000
            
            with self._lock:
                self.metrics[provider.name].record_success(latency_ms)
            
            logger.info(f"✅ Solicitud exitosa con {provider.name} ({latency_ms:.2f}ms)")
            
            if stream:
                for chunk in response:
                    yield chunk
            else:
                yield response
                
        except Exception as e:
            error_msg = self._clean_error_message(e)
            logger.error(f"❌ Error crítico con {provider.name}: {error_msg}")
            
            with self._lock:
                self.metrics[provider.name].record_failure(error_msg)
            
            raise e

    def execute_with_fallback(self, *args, **kwargs):
        """Ejecuta una solicitud intentando proveedores en cascada si hay error."""
        model_name = kwargs.get("model_name")
        if not model_name and len(args) > 0:
            model_name = args[0]
            
        force_provider_arg = kwargs.get("force_provider")
        
        ideal_provider = self._determine_ideal_provider(model_name, force_provider_arg)
        base_chain = self.get_fallback_chain()
        
        # Construir nueva cadena poniendo el ideal primero
        chain = []
        if ideal_provider:
            chain.append(ideal_provider)
            
        for p in base_chain:
            if p != ideal_provider:
                chain.append(p)
                
        if not chain:
            raise ValueError("No hay proveedores disponibles para fallback.")
            
        last_exception = None
        for provider in chain:
            try:
                # Pasar explícitamente el proveedor actual
                return self.execute(*args, force_provider=provider, **kwargs)
            except Exception as e:
                error_msg = str(e).lower()
                should_fallback = False
                
                # Check explicit fallback codes
                for code in provider.fallback_on_error_codes:
                    if code.lower() in error_msg:
                        should_fallback = True
                        break
                
                # Also fallback on timeouts or connection errors implicitly
                if "timeout" in error_msg or "connection" in error_msg or "502" in error_msg or "504" in error_msg:
                    should_fallback = True
                    
                # Do NOT fallback for Auth (401), Payment Required (402), or Not Found (404/model not found)
                if not should_fallback:
                    logger.error(f"❌ Error irrecuperable con {provider.name}: {e}. Abortando fallback.")
                    raise e
                    
                logger.warning(f"⚠️ Fallo recuperable con {provider.name}, intentando siguiente en cadena. Error: {e}")
                last_exception = e
                continue
                
        logger.error("❌ Todos los proveedores fallaron en la cadena de fallback.")
        raise last_exception or Exception("Fallback fallido")
    
    def _build_model_name(self, provider: ProviderConfig, model_name: str) -> str:
        """Construye el nombre completo del modelo para un proveedor."""
        # Si el modelo ya tiene el prefijo correcto, usarlo tal cual
        if model_name.startswith(f"{provider.model_prefix}/"):
            return model_name
        
        # Para OpenRouter, mantener el formato especial
        if provider.name == "openrouter":
            if not model_name.startswith("openrouter/"):
                return f"openrouter/{model_name}"
            return model_name
        
        # Para otros proveedores, añadir prefijo
        return f"{provider.model_prefix}/{model_name}"
    
    
    def get_metrics_report(self) -> Dict[str, Any]:
        """Genera un reporte completo de métricas."""
        with self._lock:
            report = {
                "timestamp": datetime.now().isoformat(),
                "providers": {},
                "summary": {
                    "total_providers": len(self.providers),
                    "available_providers": len(self.get_available_providers()),
                    "healthy_providers": sum(1 for m in self.metrics.values() if m.status == ProviderStatus.HEALTHY),
                    "degraded_providers": sum(1 for m in self.metrics.values() if m.status == ProviderStatus.DEGRADED),
                    "unhealthy_providers": sum(1 for m in self.metrics.values() if m.status == ProviderStatus.UNHEALTHY),
                }
            }
            
            for name, metrics in self.metrics.items():
                report["providers"][name] = metrics.to_dict()
            
            return report
    
    def print_metrics_report(self):
        """Imprime un reporte de métricas formateado."""
        report = self.get_metrics_report()
        
        print("\n" + "=" * 60)
        print("📊 REPORTE DE MÉTRICAS DE PROVEEDORES")
        print("=" * 60)
        
        summary = report["summary"]
        print(f"\n📋 Resumen:")
        print(f"   Total de proveedores: {summary['total_providers']}")
        print(f"   Disponibles: {summary['available_providers']}")
        print(f"   ✅ Saludables: {summary['healthy_providers']}")
        print(f"   ⚠️  Degradados: {summary['degraded_providers']}")
        print(f"   ❌ No saludables: {summary['unhealthy_providers']}")
        
        print(f"\n📈 Métricas por proveedor:")
        for name, metrics in report["providers"].items():
            status_icon = "✅" if metrics["status"] == "healthy" else "⚠️" if metrics["status"] == "degraded" else "❌" if metrics["status"] == "unhealthy" else "❓"
            print(f"\n   {status_icon} {name.upper()}")
            print(f"      Estado: {metrics['status']}")
            print(f"      Solicitudes: {metrics['total_requests']} (✓{metrics['successful_requests']} ✗{metrics['failed_requests']})")
            print(f"      Tasa de éxito: {metrics['success_rate']}%")
            print(f"      Latencia promedio: {metrics['avg_latency_ms']}ms")
            print(f"      Latencia reciente: {metrics['recent_avg_latency_ms']}ms")
            if metrics['last_error']:
                print(f"      Último error: {metrics['last_error'][:50]}...")
        
        print("\n" + "=" * 60 + "\n")
    
    def health_check(self, provider_name: Optional[str] = None) -> Dict[str, ProviderStatus]:
        """
        Realiza health checks a los proveedores.
        
        Args:
            provider_name: Si se especifica, solo verifica ese proveedor
        
        Returns:
            Dict con el estado de cada proveedor verificado
        """
        results = {}
        providers_to_check = []
        
        if provider_name:
            provider = next((p for p in self.providers if p.name == provider_name), None)
            if provider:
                providers_to_check.append(provider)
        else:
            providers_to_check = [p for p in self.providers if p.is_configured()]
        
        def check_provider(provider: ProviderConfig) -> tuple:
            """Función interna para verificar un proveedor."""
            try:
                start_time = time.time()
                
                # Solicitud simple de health check
                test_kwargs = {
                    "model": self._build_model_name(provider, "gpt-3.5-turbo" if provider.name != "google" else "gemini-1.5-flash"),
                    "messages": [{"role": "user", "content": "Hi"}],
                    "max_tokens": 5,
                    "timeout": 10,
                    "api_key": provider.get_api_key(),
                }
                
                api_base = provider.get_api_base()
                if api_base:
                    test_kwargs["api_base"] = api_base
                
                response = completion(**test_kwargs)
                # Consumir respuesta
                _ = list(response)
                
                latency_ms = (time.time() - start_time) * 1000
                
                with self._lock:
                    self.metrics[provider.name].record_success(latency_ms)
                
                return provider.name, ProviderStatus.HEALTHY
                
            except Exception as e:
                clean_msg = self._clean_error_message(e)
                # logger.warning(f"⚠️ Health check falló para {provider.name}: {clean_msg}")
                with self._lock:
                    self.metrics[provider.name].record_failure(clean_msg)
                return provider.name, ProviderStatus.UNHEALTHY
        
        # Ejecutar checks en paralelo
        futures = [self._health_check_executor.submit(check_provider, p) for p in providers_to_check]
        
        for future in as_completed(futures):
            name, status = future.result()
            results[name] = status
        
        return results
    
    def reset_metrics(self, provider_name: Optional[str] = None):
        """Reinicia las métricas de uno o todos los proveedores."""
        with self._lock:
            if provider_name:
                if provider_name in self.metrics:
                    self.metrics[provider_name] = ProviderMetrics(provider_name=provider_name)
                    logger.info(f"Métricas reiniciadas para {provider_name}")
            else:
                for name in self.metrics:
                    self.metrics[name] = ProviderMetrics(provider_name=name)
                logger.info("Métricas reiniciadas para todos los proveedores")
    
    def add_provider(self, provider: ProviderConfig):
        """Añade un nuevo proveedor dinámicamente."""
        with self._lock:
            # Eliminar si ya existe
            self.providers = [p for p in self.providers if p.name != provider.name]
            self.providers.append(provider)
            self.metrics[provider.name] = ProviderMetrics(provider_name=provider.name)
        logger.info(f"Proveedor añadido: {provider.name}")
    
    def remove_provider(self, provider_name: str):
        """Elimina un proveedor."""
        with self._lock:
            self.providers = [p for p in self.providers if p.name != provider_name]
            self.metrics.pop(provider_name, None)
        logger.info(f"Proveedor eliminado: {provider_name}")
    
    def close(self):
        """Libera recursos."""
        self._health_check_executor.shutdown(wait=False)
        logger.info("MultiProviderManager cerrado")


# Instancia global del manager
_provider_manager: Optional[MultiProviderManager] = None


def get_provider_manager() -> MultiProviderManager:
    """Obtiene la instancia global del MultiProviderManager."""
    global _provider_manager
    if _provider_manager is None:
        _provider_manager = MultiProviderManager()
    return _provider_manager


def reset_provider_manager():
    """Reinicia la instancia global (útil para tests o cuando cambia el proveedor)."""
    global _provider_manager
    if _provider_manager:
        _provider_manager.close()
    _provider_manager = None


def set_preferred_provider(name: str):
    """Establece un proveedor preferido que será prioritario en get_available_providers()."""
    global _provider_manager
    if _provider_manager:
        _provider_manager.preferred_provider = name
        # Reiniciar métricas para evitar que esté marcado como UNHEALTHY y se omita
        _provider_manager.reset_metrics(name)
