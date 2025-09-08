import time
import threading
import queue
import sys # Añadir esta importación
from jupyter_client import KernelManager
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

class KogniTermKernel:
    def __init__(self):
        self.km = None
        self.kc = None
        self.output_queue = queue.Queue()
        self.listener_thread = None
        self.stop_event = threading.Event()
        self.execution_complete_event = threading.Event() # Evento para señalar la finalización de la ejecución
        self.current_execution_outputs = [] # Para recolectar las salidas de la ejecución actual

    def start_kernel(self):
        print("Iniciando kernel de Python...")
        try:
            self.km = KernelManager(kernel_name='kogniterm_venv')
            self.km.start_kernel()
            self.kc = self.km.client()
            self.kc.start_channels()

            # Esperar a que el kernel esté listo
            self.kc.wait_for_ready()
            print("Kernel de Python iniciado y listo.")

            self.listener_thread = threading.Thread(target=self._iopub_listener)
            self.listener_thread.daemon = True
            self.listener_thread.start()
        except Exception as e:
            print(f"Error al iniciar el kernel: {e}")
            self.stop_kernel() # Intentar limpiar si falla el inicio

    def _iopub_listener(self):
        while not self.stop_event.is_set():
            try:
                # Esperar mensajes del canal iopub
                msg = self.kc.iopub_channel.get_msg(timeout=0.1)
                self.output_queue.put(msg)
                # Si el mensaje es de estado y indica 'idle', señalamos que la ejecución ha terminado
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

        print(f"\nEjecutando código:\n---\n{code}\n---")
        self.execution_complete_event.clear() # Limpiar el evento antes de una nueva ejecución
        self.current_execution_outputs = [] # Limpiar las salidas anteriores
        msg_id = self.kc.execute(code)

        # Esperar hasta que la ejecución esté completa (estado 'idle' capturado por el listener)
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
            self.listener_thread.join(timeout=2) # Esperar a que el hilo termine
        print("Kernel detenido.")

# Definir el esquema de argumentos para la herramienta Python
class PythonToolArgs(BaseModel):
    code: str = Field(description="El código Python a ejecutar.")

class PythonTool(BaseTool):
    name: str = "python_executor"
    description: str = "Ejecuta código Python utilizando un kernel de Jupyter. Mantiene el estado entre ejecuciones."
    args_schema: type[BaseModel] = PythonToolArgs
    last_structured_output: dict = None # Declarar como atributo de clase con tipo y valor por defecto
    auto_approve: bool = False # Nuevo atributo para controlar la aprobación automática

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._kernel = KogniTermKernel()
        self._kernel.start_kernel()

    def _run(self, code: str) -> str:
        """
        Ejecuta un bloque de código Python en el kernel de Jupyter.
        Este método es el que será llamado por LangChain/Gemini.
        La salida se convierte a una cadena para ser procesada por el LLM.
        """
        if not self.auto_approve:
            print(f"\n🚨 Se requiere aprobación para ejecutar el siguiente código Python:\n```python\n{code}\n```")
            response = input("¿Deseas aprobar la ejecución de este código? (s/n): ")
            if response.lower() != 's':
                return "Ejecución de código Python cancelada por el usuario."

        print(f"Ejecutando código Python:\n```python\n{code}\n```")
        raw_output = self._kernel.execute_code(code)
        self.last_structured_output = raw_output # Almacenar la salida estructurada


        # Procesar la salida bruta a un formato más amigable para el LLM
        formatted_output = []
        if "result" in raw_output:
            for item in raw_output["result"]:
                if item['type'] == 'stream':
                    formatted_output.append(f"Output ({item['name']}): {item['text']}")
                elif item['type'] == 'error':
                    formatted_output.append(f"Error ({item['ename']}): {item['evalue']}\nTraceback:\n{'\n'.join(item['traceback'])}")
                elif item['type'] == 'execute_result':
                    # Intentar obtener 'text/plain' primero, si no, usar la representación de los datos
                    data_str = item['data'].get('text/plain', str(item['data']))
                    formatted_output.append(f"Result: {data_str}")
                elif item['type'] == 'display_data':
                    # Podríamos añadir lógica para tipos específicos como imágenes o HTML
                    # Por ahora, una representación simple
                    if 'image/png' in item['data']:
                        formatted_output.append("[IMAGEN PNG GENERADA]")
                    elif 'text/html' in item['data']:
                        formatted_output.append(f"[HTML GENERADO]: {item['data']['text/html'][:100]}...") # Snippet
                    else:
                        formatted_output.append(f"Display Data: {str(item['data'])}")
            return "\n".join(formatted_output)
        elif "error" in raw_output:
            return f"Error en el kernel de Python: {raw_output['error']}"
        return "PythonTool: No se recibió salida discernible."

    def get_last_structured_output(self):
        """Devuelve la última salida estructurada generada por la ejecución del código Python."""
        return self.last_structured_output

    def __del__(self):
        self._kernel.stop_kernel()
