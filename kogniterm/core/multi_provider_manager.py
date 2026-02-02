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
    priority: int = 100  # Menor = mayor prioridad
    enabled: bool = True
    timeout_seconds: int = 120
    max_retries: int = 3
    fallback_on_error_codes: List[str] = field(default_factory=list)
    
    def get_api_key(self) -> Optional[str]:
        """Obtiene la API key desde variables de entorno."""
        return os.getenv(self.api_key_env)
    
    def is_configured(self) -> bool:
        """Verifica si el proveedor está configurado."""
        return self.enabled and self.get_api_key() is not None


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
        priority=20,
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
        """Retorna lista de proveedores configurados y disponibles."""
        available = []
        for provider in sorted(self.providers, key=lambda p: p.priority):
            if provider.is_configured():
                metrics = self.metrics.get(provider.name)
                # No incluir proveedores en estado UNHEALTHY
                if metrics and metrics.status == ProviderStatus.UNHEALTHY:
                    logger.debug(f"Proveedor {provider.name} omitido por estado UNHEALTHY")
                    continue
                available.append(provider)
        return available
    
    def get_primary_provider(self) -> Optional[ProviderConfig]:
        """Retorna el proveedor primario (de mayor prioridad disponible)."""
        available = self.get_available_providers()
        return available[0] if available else None
    
    def get_fallback_chain(self) -> List[ProviderConfig]:
        """Retorna la cadena de fallback ordenada por prioridad."""
        return self.get_available_providers()
    
    def execute(
        self,
        model_name: str,
        messages: List[Dict[str, Any]],
        stream: bool = True,
        temperature: float = 0.7,
        max_tokens: int = 8192,
        tools: Optional[List[Dict]] = None,
        **kwargs
    ):
        """
        Ejecuta una solicitud con el proveedor primario.
        Sin fallback automático a otros proveedores.
        """
        provider = self.get_primary_provider()
        
        if not provider:
            raise ValueError("No hay proveedores configurados disponibles. Revisa tus API Keys.")
        
        try:
            logger.info(f"Usando proveedor: {provider.name}")
            
            # Construir nombre completo del modelo
            full_model_name = self._build_model_name(provider, model_name)
            
            # Preparar kwargs para LiteLLM
            completion_kwargs = {
                "model": full_model_name,
                "messages": messages,
                "stream": stream,
                "api_key": provider.get_api_key(),
                "temperature": temperature,
                "max_tokens": max_tokens,
                "timeout": provider.timeout_seconds,
                "num_retries": provider.max_retries,
            }
            
            if tools:
                completion_kwargs["tools"] = tools
            
            if provider.api_base:
                completion_kwargs["api_base"] = provider.api_base
            
            if provider.name == "openrouter":
                completion_kwargs["headers"] = {
                    "HTTP-Referer": "https://github.com/gatovillano/KogniTerm",
                    "X-Title": "KogniTerm"
                }
            
            start_time = time.time()
            response = completion(**completion_kwargs)
            latency_ms = (time.time() - start_time) * 1000
            
            with self._lock:
                self.metrics[provider.name].record_success(latency_ms)
            
            logger.info(f"✅ Solicitud exitosa con {provider.name} ({latency_ms:.2f}ms)")
            
            for chunk in response:
                yield chunk
                
        except Exception as e:
            error_msg = self._clean_error_message(e)
            logger.error(f"❌ Error crítico con {provider.name}: {error_msg}")
            
            with self._lock:
                self.metrics[provider.name].record_failure(error_msg)
            
            raise e

    def execute_with_fallback(self, *args, **kwargs):
        """Alias para mantener compatibilidad con el resto del código."""
        return self.execute(*args, **kwargs)
        
        # Si llegamos aquí, todos los proveedores fallaron
        logger.error(f"Todos los proveedores fallaron. Último error: {last_error}")
        raise last_error or Exception("No se pudo completar la solicitud con ningún proveedor")
    
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
                
                if provider.api_base:
                    test_kwargs["api_base"] = provider.api_base
                
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
    """Reinicia la instancia global (útil para tests)."""
    global _provider_manager
    if _provider_manager:
        _provider_manager.close()
    _provider_manager = None
