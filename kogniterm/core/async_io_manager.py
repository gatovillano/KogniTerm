"""
Async I/O Manager para KogniTerm.

Este módulo implementa:
1. Ejecución asíncrona de operaciones I/O (LLM calls, web requests, file operations)
2. Mantenimiento de sincronía en operaciones que requieren estado compartido
3. Patrón híbrido: async para I/O, sync para estado compartido
"""

import asyncio
import threading
from typing import Any, Callable, Coroutine, Dict, List, Optional, TypeVar, Generic
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
import time
import logging
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class AsyncTaskResult:
    """Resultado de una tarea asíncrona."""
    success: bool
    result: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    task_id: str = ""


class AsyncIOManager:
    """
    Gestor de operaciones I/O asíncronas.
    
    Mantiene un loop de eventos dedicado en un hilo separado para ejecutar
    operaciones asíncronas sin bloquear el hilo principal.
    """
    
    def __init__(self, max_workers: int = 10):
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._lock = threading.RLock()
        self._running = False
        self._task_count = 0
        
    def start(self):
        """Inicia el loop de eventos en un hilo separado."""
        if self._running:
            return
            
        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._running = True
            self._loop.run_forever()
        
        self._thread = threading.Thread(target=run_loop, daemon=True)
        self._thread.start()
        logger.info("AsyncIOManager iniciado")
    
    def stop(self):
        """Detiene el loop de eventos."""
        if not self._running:
            return
            
        self._running = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=5)
        self._executor.shutdown(wait=False)
        logger.info("AsyncIOManager detenido")
    
    def run_async(self, coro: Coroutine, timeout: Optional[float] = None) -> AsyncTaskResult:
        """
        Ejecuta una corrutina de forma asíncrona y retorna el resultado.
        
        Args:
            coro: La corrutina a ejecutar
            timeout: Timeout en segundos
            
        Returns:
            AsyncTaskResult con el resultado o error
        """
        if not self._running or not self._loop:
            self.start()
        
        task_id = f"task_{self._task_count}"
        self._task_count += 1
        start_time = time.time()
        
        try:
            # Enviar la corrutina al loop en el otro hilo
            future = asyncio.run_coroutine_threadsafe(coro, self._loop)
            
            # Esperar el resultado con timeout
            result = future.result(timeout=timeout)
            
            execution_time = (time.time() - start_time) * 1000
            
            return AsyncTaskResult(
                success=True,
                result=result,
                execution_time_ms=execution_time,
                task_id=task_id
            )
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            return AsyncTaskResult(
                success=False,
                error=str(e),
                execution_time_ms=execution_time,
                task_id=task_id
            )
    
    def run_in_executor(self, func: Callable[..., T], *args, **kwargs) -> AsyncTaskResult:
        """
        Ejecuta una función bloqueante en el executor sin bloquear el hilo principal.
        
        Args:
            func: Función a ejecutar
            *args, **kwargs: Argumentos para la función
            
        Returns:
            AsyncTaskResult con el resultado
        """
        task_id = f"sync_task_{self._task_count}"
        self._task_count += 1
        start_time = time.time()
        
        try:
            future = self._executor.submit(func, *args, **kwargs)
            result = future.result()
            
            execution_time = (time.time() - start_time) * 1000
            
            return AsyncTaskResult(
                success=True,
                result=result,
                execution_time_ms=execution_time,
                task_id=task_id
            )
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            return AsyncTaskResult(
                success=False,
                error=str(e),
                execution_time_ms=execution_time,
                task_id=task_id
            )


# Instancia global
_io_manager: Optional[AsyncIOManager] = None


def get_io_manager() -> AsyncIOManager:
    """Obtiene la instancia global del AsyncIOManager."""
    global _io_manager
    if _io_manager is None:
        _io_manager = AsyncIOManager()
        _io_manager.start()
    return _io_manager


def reset_io_manager():
    """Reinicia la instancia global."""
    global _io_manager
    if _io_manager:
        _io_manager.stop()
    _io_manager = None


class HybridStateManager:
    """
    Gestor de estado híbrido que permite:
    - Operaciones I/O asíncronas (LLM calls, web requests)
    - Operaciones de estado compartido síncronas (protegidas por locks)
    """
    
    def __init__(self):
        self._state_lock = threading.RLock()
        self._state: Dict[str, Any] = {}
        self._io_manager = get_io_manager()
    
    def get_state(self, key: str, default: Any = None) -> Any:
        """Obtiene un valor del estado de forma segura."""
        with self._state_lock:
            return self._state.get(key, default)
    
    def set_state(self, key: str, value: Any):
        """Establece un valor en el estado de forma segura."""
        with self._state_lock:
            self._state[key] = value
    
    def update_state(self, updates: Dict[str, Any]):
        """Actualiza múltiples valores en el estado de forma segura."""
        with self._state_lock:
            self._state.update(updates)
    
    def execute_io_async(self, coro: Coroutine, timeout: Optional[float] = None) -> AsyncTaskResult:
        """
        Ejecuta una operación I/O de forma asíncrona.
        El estado compartido no se modifica durante esta operación.
        """
        return self._io_manager.run_async(coro, timeout)
    
    def execute_sync_with_state(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Ejecuta una función que modifica el estado compartido.
        Esta operación es síncrona y protegida por locks.
        """
        with self._state_lock:
            return func(*args, **kwargs)


def async_io_operation(timeout: Optional[float] = None):
    """
    Decorador para marcar funciones que realizan operaciones I/O asíncronas.
    
    La función decorada debe ser una corrutina (async def).
    
    Ejemplo:
        @async_io_operation(timeout=30)
        async def fetch_web_data(url: str) -> dict:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    return await response.json()
    """
    def decorator(func: Callable[..., Coroutine]) -> Callable[..., AsyncTaskResult]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> AsyncTaskResult:
            manager = get_io_manager()
            coro = func(*args, **kwargs)
            return manager.run_async(coro, timeout)
        return wrapper
    return decorator


def sync_state_operation(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorador para marcar funciones que modifican estado compartido.
    Estas funciones se ejecutan de forma síncrona y protegida.
    
    Ejemplo:
        @sync_state_operation
        def update_conversation_history(state: dict, message: dict) -> None:
            state['messages'].append(message)
    """
    @wraps(func)
    def wrapper(*args, **kwargs) -> T:
        # Usar el lock global del HybridStateManager
        state_manager = get_hybrid_state_manager()
        return state_manager.execute_sync_with_state(func, *args, **kwargs)
    return wrapper


# Instancia global del gestor de estado híbrido
_state_manager: Optional[HybridStateManager] = None


def get_hybrid_state_manager() -> HybridStateManager:
    """Obtiene la instancia global del HybridStateManager."""
    global _state_manager
    if _state_manager is None:
        _state_manager = HybridStateManager()
    return _state_manager


def reset_hybrid_state_manager():
    """Reinicia la instancia global."""
    global _state_manager
    _state_manager = None
