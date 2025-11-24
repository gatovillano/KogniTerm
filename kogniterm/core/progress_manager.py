"""
Módulo para gestionar el progreso de tareas en segundo plano.
Permite reportar el progreso de operaciones largas como la indexación del codebase.
"""

import asyncio
from typing import Dict, Any, Optional, Callable
from datetime import datetime


class ProgressManager:
    """
    Gestiona el estado del progreso de múltiples tareas en segundo plano.
    Permite iniciar, actualizar, completar y reportar errores de tareas.
    """
    
    def __init__(self, ui_callback: Optional[Callable] = None):
        """
        Inicializa el ProgressManager.
        
        Args:
            ui_callback: Función callback para actualizar la UI. 
                        Recibe (event_type, task_id, data)
        """
        self.active_tasks: Dict[str, Dict[str, Any]] = {}
        self.ui_callback = ui_callback
        self._lock = asyncio.Lock()
    
    async def start_task(self, task_id: str, total_items: int, description: str):
        """
        Inicia una nueva tarea de progreso.
        
        Args:
            task_id: Identificador único de la tarea
            total_items: Número total de items a procesar
            description: Descripción de la tarea
        """
        async with self._lock:
            self.active_tasks[task_id] = {
                'status': 'started',
                'total': total_items,
                'current': 0,
                'description': description,
                'message': description,
                'start_time': datetime.now(),
                'percentage': 0
            }
        
        if self.ui_callback:
            await self._notify_ui('started', task_id)
    
    async def update_progress(self, task_id: str, current: int, message: str = ""):
        """
        Actualiza el progreso de una tarea existente.
        
        Args:
            task_id: Identificador de la tarea
            current: Número actual de items procesados
            message: Mensaje descriptivo del estado actual
        """
        async with self._lock:
            if task_id not in self.active_tasks:
                return
            
            task = self.active_tasks[task_id]
            task['current'] = current
            task['message'] = message or task['description']
            task['status'] = 'progress'
            
            # Calcular porcentaje
            if task['total'] > 0:
                task['percentage'] = int((current / task['total']) * 100)
            else:
                task['percentage'] = 0
        
        if self.ui_callback:
            await self._notify_ui('progress', task_id)
    
    async def complete_task(self, task_id: str, message: str = ""):
        """
        Marca una tarea como completada.
        
        Args:
            task_id: Identificador de la tarea
            message: Mensaje de finalización
        """
        async with self._lock:
            if task_id not in self.active_tasks:
                return
            
            task = self.active_tasks[task_id]
            task['status'] = 'completed'
            task['message'] = message or f"{task['description']} - Completado"
            task['percentage'] = 100
            task['end_time'] = datetime.now()
        
        if self.ui_callback:
            await self._notify_ui('completed', task_id)
        
        # Limpiar la tarea después de un breve delay
        await asyncio.sleep(0.5)
        async with self._lock:
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]
    
    async def error_task(self, task_id: str, error_message: str):
        """
        Marca una tarea como fallida.
        
        Args:
            task_id: Identificador de la tarea
            error_message: Mensaje de error
        """
        async with self._lock:
            if task_id not in self.active_tasks:
                return
            
            task = self.active_tasks[task_id]
            task['status'] = 'error'
            task['message'] = error_message
            task['end_time'] = datetime.now()
        
        if self.ui_callback:
            await self._notify_ui('error', task_id)
        
        # Limpiar la tarea después de un breve delay
        await asyncio.sleep(0.5)
        async with self._lock:
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]
    
    async def _notify_ui(self, event_type: str, task_id: str):
        """
        Notifica a la UI sobre cambios en el progreso.
        
        Args:
            event_type: Tipo de evento ('started', 'progress', 'completed', 'error')
            task_id: Identificador de la tarea
        """
        if not self.ui_callback:
            return
        
        task_data = self.active_tasks.get(task_id)
        if task_data:
            try:
                await self.ui_callback(event_type, task_id, task_data.copy())
            except Exception as e:
                # No queremos que errores en la UI rompan el progreso
                print(f"Error notificando UI: {e}")
    
    def get_task_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene información sobre una tarea específica.
        
        Args:
            task_id: Identificador de la tarea
            
        Returns:
            Diccionario con información de la tarea o None si no existe
        """
        return self.active_tasks.get(task_id)
    
    def get_all_tasks(self) -> Dict[str, Dict[str, Any]]:
        """
        Obtiene información sobre todas las tareas activas.
        
        Returns:
            Diccionario con todas las tareas activas
        """
        return self.active_tasks.copy()
