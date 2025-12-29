import time
import threading
import queue
import sys

_jupyter_client_available = False
try:
    from jupyter_client import KernelManager
    _jupyter_client_available = True
except ImportError:
    print("Advertencia: jupyter_client no está disponible. La herramienta PythonTool no funcionará.")

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Optional, Any

class KogniTermKernel:
    def __init__(self):
        self.km = None
        self.kc = None
        self.output_queue = queue.Queue()
        self.listener_thread = None
        self.stop_event = threading.Event()
        self.execution_complete_event = threading.Event()
        self.current_execution_outputs = []

    def start_kernel(self):
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
        while not self.stop_event.is_set():
            try:
                msg = self.kc.iopub_channel.get_msg(timeout=0.1)
                self.output_queue.put(msg)
                if msg['header']['msg_type'] == 'status' and msg['content']['execution_state'] == 'idle':
                    self.execution_complete_event.set()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error en el listener iopub: {e}")
                break

    def execute_code(self, code):
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
        if self.kc:
            print("Deteniendo canales del kernel...")
            self.kc.stop_channels()
        if self.km:
            print("Apagando kernel...")
            self.km.shutdown_kernel()
        self.stop_event.set()
        if self.listener_thread and self.listener_thread.is_alive():
            self.listener_thread.join(timeout=2)
        print("Kernel detenido.")

class PythonToolArgs(BaseModel):
    code: str = Field(description="El código Python a ejecutar.")

class PythonTool(BaseTool):
    name: str = "python_executor"
    description: str = "Ejecuta código Python utilizando un kernel de Jupyter. Mantiene el estado entre ejecuciones."
    args_schema: type[BaseModel] = PythonToolArgs
    last_structured_output: dict = None

    def get_action_description(self, **kwargs) -> str:
        return "Ejecutando código Python interactivo"
    # El atributo auto_approve se eliminará de la herramienta, ya que la lógica de confirmación
    # se manejará en el grafo del agente.

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        if _jupyter_client_available:
            self._kernel = KogniTermKernel()
            self._kernel.start_kernel()
        else:
            self._kernel = None # O un objeto dummy que siempre devuelva error

    def _run(self, code: str) -> str:
        """
        Ejecuta un bloque de código Python en el kernel de Jupyter.
        Este método es el que será llamado por LangChain/Gemini.
        La salida se convierte a una cadena para ser procesada por el LLM.
        """
        if not _jupyter_client_available or self._kernel is None:
            return "Error: La herramienta PythonTool no está disponible porque jupyter_client no está instalado o el kernel no pudo iniciarse."
        # Eliminamos la lógica de confirmación directa de la herramienta.
        # Esto será manejado por el grafo del agente.
        raw_output = self._kernel.execute_code(code)
        self.last_structured_output = raw_output

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
            return "\n".join(formatted_output)
        elif "error" in raw_output:
            error_message = f"Error en el kernel de Python: {raw_output['error']}"
            return error_message
        no_output_message = "PythonTool: No se recibió salida discernible."
        return no_output_message

    def get_last_structured_output(self):
        """Devuelve la última salida estructurada generada por la ejecución del código Python."""
        return self.last_structured_output

    def __del__(self):
        if _jupyter_client_available and self._kernel:
            self._kernel.stop_kernel()
