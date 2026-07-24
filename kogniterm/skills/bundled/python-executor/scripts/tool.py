"""
Python Executor Skill - Ejecución interactiva de código Python.

Esta es una skill migrada desde python_executor.py.
Provee funcionalidad para ejecutar código Python de forma interactiva con kernel de Jupyter.
"""

import time
import threading
import queue
import logging
import json
from typing import Generator, Optional, Any

logger = logging.getLogger(__name__)

_jupyter_client_available = False
try:
    from jupyter_client import KernelManager
    _jupyter_client_available = True
except ImportError:
    print("Advertencia: jupyter_client no está disponible. La herramienta PythonTool no funcionará.")

# Metadata de la herramienta
name = "python_executor"
description = "Ejecuta código Python utilizando un kernel de Jupyter. Mantiene el estado entre ejecuciones."


class KogniTermKernel:
    """Kernel de Jupyter para ejecución de código Python."""
    
    def __init__(self):
        self.km = None
        self.kc = None
        self.output_queue = queue.Queue()
        self.listener_thread = None
        self.stop_event = threading.Event()
        self.execution_complete_event = threading.Event()
        self.current_execution_outputs = []

    def start_kernel(self):
        """Inicia el kernel de Jupyter."""
        if not _jupyter_client_available:
            print("Error: No se puede iniciar el kernel. jupyter_client no está disponible.")
            return
        try:
            try:
                self.km = KernelManager(kernel_name='kogniterm_venv')
                self.km.start_kernel()
            except Exception as e:
                print(f"Kernel 'kogniterm_venv' no disponible ({e}), usando kernel por defecto...")
                self.km = KernelManager()
                self.km.start_kernel()
                
            self.kc = self.km.client()
            self.kc.start_channels()

            # Añadir timeout para evitar bloqueo indefinido si el kernel muere al arrancar
            self.kc.wait_for_ready(timeout=5.0)

            self.listener_thread = threading.Thread(target=self._iopub_listener)
            self.listener_thread.daemon = True
            self.listener_thread.start()
        except Exception as e:
            print(f"Error al iniciar el kernel: {e}")
            self.stop_kernel()

    def _iopub_listener(self):
        """Listener para mensajes del kernel."""
        while not self.stop_event.is_set():
            try:
                msg = self.kc.iopub_channel.get_msg(timeout=0.1)
                self.output_queue.put(msg)
                if msg['header']['msg_type'] == 'status' and msg['content']['execution_state'] == 'idle':
                    self.execution_complete_event.set()
            except queue.Empty:
                continue
            except Exception as e:
                if not self.stop_event.is_set():
                    print(f"Error en el listener iopub: {e}")
                break

    def execute_code(self, code, terminal_ui=None, command_title="python"):
        """Ejecuta código en el kernel de forma síncrona manteniendo retrocompatibilidad."""
        outputs = []
        for _ in self.execute_code_stream(code, terminal_ui=terminal_ui, command_title=command_title):
            pass
        return {"result": self.current_execution_outputs}

    def execute_code_stream(self, code: str, terminal_ui: Any = None, command_title: str = "python") -> Generator[str, None, None]:
        """Ejecuta código en el kernel y produce fragmentos formateados en tiempo real."""
        if not self.kc:
            yield "Error: El kernel no está iniciado o falló al arrancar.\n"
            return

        if not self.listener_thread or not self.listener_thread.is_alive():
            yield "Error: El hilo de escucha del kernel no está activo. ¿Está instalado 'ipykernel'?\n"
            return

        self.current_execution_outputs = []
        self.execution_complete_event.clear()

        try:
            msg_id = self.kc.execute(code)
            logger.info(f"Código enviado al kernel con msg_id: {msg_id}")
        except Exception as e:
            yield f"Error al enviar código al kernel: {e}"
            return

        start_wait = time.time()
        max_wait = 300
        accumulated_text = ""

        def _format_msg(msg_type, content):
            if msg_type == 'stream':
                return content['text']
            elif msg_type == 'execute_result':
                data = content.get('data', {})
                return data.get('text/plain', '')
            elif msg_type == 'error':
                return '\n'.join(content.get('traceback', []))
            elif msg_type == 'display_data':
                data = content.get('data', {})
                return data.get('text/plain', '')
            return ""

        while not self.execution_complete_event.is_set():
            if not self.listener_thread or not self.listener_thread.is_alive():
                err_msg = "\nError: El kernel se detuvo inesperadamente durante la ejecución.\n"
                self.current_execution_outputs.append({"type": "error", "ename": "DeadKernel", "evalue": err_msg, "traceback": []})
                yield err_msg
                break

            if time.time() - start_wait > max_wait:
                err_msg = f"\nTimeout: El kernel de Jupyter no respondió después de {max_wait} segundos.\n"
                self.current_execution_outputs.append({"type": "error", "ename": "Timeout", "evalue": err_msg, "traceback": []})
                accumulated_text += err_msg
                if terminal_ui and hasattr(terminal_ui, "update_terminal_output"):
                    try:
                        terminal_ui.update_terminal_output("python_executor", accumulated_text, command=command_title)
                    except Exception:
                        pass
                yield err_msg
                break

            try:
                msg = self.output_queue.get(timeout=0.1)
                msg_type = msg['header']['msg_type']
                content = msg['content']

                if msg_type in ('stream', 'error', 'execute_result', 'display_data'):
                    if msg_type == 'stream':
                        self.current_execution_outputs.append({'type': 'stream', 'name': content['name'], 'text': content['text']})
                    elif msg_type == 'error':
                        self.current_execution_outputs.append({'type': 'error', 'ename': content.get('ename'), 'evalue': content.get('evalue'), 'traceback': content.get('traceback', [])})
                    elif msg_type == 'execute_result':
                        self.current_execution_outputs.append({'type': 'execute_result', 'data': content.get('data')})
                    elif msg_type == 'display_data':
                        self.current_execution_outputs.append({'type': 'display_data', 'data': content.get('data')})

                    chunk = _format_msg(msg_type, content)
                    if chunk:
                        accumulated_text += chunk
                        if terminal_ui and hasattr(terminal_ui, "update_terminal_output"):
                            try:
                                terminal_ui.update_terminal_output("python_executor", accumulated_text, command=command_title)
                            except Exception:
                                pass
                        yield chunk
            except queue.Empty:
                continue
            except Exception as e:
                err = f"Error al procesar mensaje de salida: {e}\n"
                accumulated_text += err
                yield err
                break
        


    def stop_kernel(self):
        """Detiene el kernel de forma segura."""
        # 1. Avisar al hilo que debe detenerse
        self.stop_event.set()
        
        # 2. Esperar a que el hilo termine antes de cerrar los canales
        if self.listener_thread and self.listener_thread.is_alive():
            self.listener_thread.join(timeout=1.0)
            
        # 3. Ahora que el hilo está detenido, cerrar canales con seguridad
        if self.kc:
            try:
                self.kc.stop_channels()
            except Exception:
                pass
            self.kc = None
                
        # 4. Apagar el kernel físico
        if self.km:
            try:
                self.km.shutdown_kernel()
            except Exception:
                pass
            self.km = None


# Instancia global del kernel
_kernel_instance = None


def _get_kernel_instance() -> Optional[KogniTermKernel]:
    """Obtiene o crea la instancia del kernel."""
    global _kernel_instance
    if _kernel_instance is None:
        if _jupyter_client_available:
            _kernel_instance = KogniTermKernel()
            _kernel_instance.start_kernel()
        else:
            _kernel_instance = None
    return _kernel_instance


def python_executor(code: str, terminal_ui: Any = None, auto_confirm: bool = False, confirm: bool = False) -> Generator[str, None, None]:
    """
    Ejecuta código Python en un kernel de Jupyter.

    Args:
        code: El código Python a ejecutar
        terminal_ui: Interfaz de terminal para mostrar mensajes
        auto_confirm: Si True, ejecuta sin pedir confirmación
        confirm: Alias de auto_confirm

    Yields:
        str: Resultados de la ejecución formateados

    Raises:
        Exception: Errores durante la ejecución
    """
    global _kernel_instance
    
    if not _jupyter_client_available:
        yield "Error: La herramienta PythonExecutor no está disponible porque jupyter_client no está instalado."
        return

    # Siempre usar el flujo de confirmación estándar como otras herramientas
    # El sistema de aprobación se encarga de verificar auto_approve_mode
    if not auto_confirm and not confirm:
        # Devolver estado de confirmación requerida para que el sistema lo maneje
        yield json.dumps({
            "status": "requires_confirmation",
            "operation": "python_executor",
            "action_description": "¿Ejecutar código Python?",
            "code_preview": code
        })
        return

    kernel = _get_kernel_instance()
    if kernel is None:
        yield "Error: No se pudo iniciar el kernel de Jupyter."
        return

    cmd_title = "python"
    for chunk in kernel.execute_code_stream(code, terminal_ui=terminal_ui, command_title=cmd_title):
        yield chunk


# Función alternativa para ejecución síncrona
def _python_executor_sync(code: str) -> str:
    """
    Versión síncrona de python_executor.
    Retorna el resultado completo como string.
    """
    output = []
    for chunk in python_executor(code):
        output.append(chunk)
    return "".join(output)


# Función para obtener la última salida estructurada
def _get_last_structured_output() -> Optional[dict]:
    """
    Devuelve la última salida estructurada generada por la ejecución del código Python.
    """
    global _kernel_instance
    if _kernel_instance:
        return _kernel_instance.current_execution_outputs
    return None


# Función de limpieza
def _cleanup():
    """Limpia recursos del kernel."""
    global _kernel_instance
    if _kernel_instance:
        _kernel_instance.stop_kernel()
        _kernel_instance = None


# Schema de parámetros para el LLM
parameters_schema = {
    "type": "object",
    "properties": {
        "code": {
            "type": "string",
            "description": "El código Python a ejecutar"
        }
    },
    "required": ["code"]
}