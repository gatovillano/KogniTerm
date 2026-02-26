"""
Python Executor Skill - Ejecución interactiva de código Python.

Esta es una skill migrada desde python_executor.py.
Provee funcionalidad para ejecutar código Python de forma interactiva con kernel de Jupyter.
"""

import time
import threading
import queue
import sys
from typing import Generator, Optional, Any

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
            self.km = KernelManager(kernel_name='kogniterm_venv')
            self.km.start_kernel()
            self.kc = self.km.client()
            self.kc.start_channels()

            self.kc.wait_for_ready()

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

    def execute_code(self, code):
        """Ejecuta código en el kernel."""
        if not self.kc:
            return {"error": "El kernel no está iniciado."}

        self.execution_complete_event.clear()
        self.current_execution_outputs = []
        msg_id = self.kc.execute(code)

        while not self.execution_complete_event.is_set():
            try:
                msg = self.output_queue.get(timeout=0.1)
                msg_type = msg['header']['msg_type']
                content = msg['content']

                if msg_type == 'stream':
                    self.current_execution_outputs.append({'type': 'stream', 'name': content['name'], 'text': content['text']})
                elif msg_type == 'error':
                    self.current_execution_outputs.append({'type': 'error', 'ename': content['ename'], 'evalue': content['evalue'], 'traceback': content['traceback']})
                elif msg_type == 'execute_result':
                    self.current_execution_outputs.append({'type': 'execute_result', 'data': content['data']})
                elif msg_type == 'display_data':
                    self.current_execution_outputs.append({'type': 'display_data', 'data': content['data']})

            except queue.Empty:
                continue
            except Exception as e:
                self.current_execution_outputs.append({"error": f"Error al procesar mensaje de salida: {e}"})
                break
        print("Ejecución de código completada.")
        return {"result": self.current_execution_outputs}

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
                
        # 4. Apagar el kernel físico
        if self.km:
            try:
                self.km.shutdown_kernel()
            except Exception:
                pass


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


def python_executor(code: str, terminal_ui: Any = None) -> Generator[str, None, None]:
    """
    Ejecuta código Python en un kernel de Jupyter.

    Args:
        code: El código Python a ejecutar

    Yields:
        str: Resultados de la ejecución formateados

    Raises:
        Exception: Errores durante la ejecución
    """
    global _kernel_instance
    
    if not _jupyter_client_available:
        yield "Error: La herramienta PythonExecutor no está disponible porque jupyter_client no está instalado."
        return

    kernel = _get_kernel_instance()
    if kernel is None:
        yield "Error: No se pudo iniciar el kernel de Jupyter."
        return

    # Ejecutar el código
    raw_output = kernel.execute_code(code)
    
    # Formatear la salida
    formatted_output = []
    if "result" in raw_output:
        for item in raw_output["result"]:
            if item['type'] == 'stream':
                output_line = f"Output ({item['name']}): {item['text']}"
                formatted_output.append(output_line)
            elif item['type'] == 'error':
                traceback_str = '\n'.join(item['traceback'])
                error_line = f"Error ({item['ename']}): {item['evalue']}\nTraceback:\n{traceback_str}"
                formatted_output.append(error_line)
            elif item['type'] == 'execute_result':
                data_str = item['data'].get('text/plain', str(item['data']))
                result_line = f"Result: {data_str}"
                formatted_output.append(result_line)
            elif item['type'] == 'display_data':
                if 'image/png' in item['data']:
                    display_line = "[IMAGEN PNG GENERADA]"
                    formatted_output.append(display_line)
                elif 'text/html' in item['data']:
                    display_line = f"[HTML GENERADO]: {item['data']['text/html'][:100]}..."
                    formatted_output.append(display_line)
                else:
                    display_line = f"Display Data: {str(item['data'])}"
                    formatted_output.append(display_line)
        
        if formatted_output:
            final_output = "\n".join(formatted_output)
            
            if terminal_ui:
                from rich.panel import Panel
                from kogniterm.terminal.themes import ColorPalette
                terminal_ui.console.print(Panel(
                    final_output,
                    title=f"[bold {ColorPalette.SECONDARY}]🐍 Salida de Python[/]",
                    border_style=ColorPalette.SECONDARY,
                    expand=False
                ))
            
            yield final_output
        else:
            if terminal_ui:
                from rich.panel import Panel
                from kogniterm.terminal.themes import ColorPalette
                terminal_ui.console.print(Panel(
                    "Sin salida discernible.",
                    title=f"[bold {ColorPalette.SECONDARY}]🐍 Salida de Python[/]",
                    border_style=ColorPalette.SECONDARY,
                    expand=False
                ))
            yield "PythonExecutor: No se recibió salida discernible."
    elif "error" in raw_output:
        if terminal_ui:
            from rich.panel import Panel
            terminal_ui.console.print(Panel(
                raw_output['error'],
                title=f"[bold red]🐍 Error de Python[/]",
                border_style="red",
                expand=False
            ))
        yield f"Error en el kernel de Python: {raw_output['error']}"
    else:
        if terminal_ui:
            from rich.panel import Panel
            terminal_ui.console.print(Panel(
                "Sin salida discernible.",
                title=f"[bold yellow]🐍 Salida de Python[/]",
                border_style="yellow",
                expand=False
            ))
        yield "PythonExecutor: No se recibió salida discernible."


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