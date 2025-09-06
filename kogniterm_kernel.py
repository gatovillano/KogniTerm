import time
import threading
import queue
from jupyter_client import KernelManager

class KogniTermKernel:
    def __init__(self):
        self.km = None
        self.kc = None
        self.output_queue = queue.Queue()
        self.listener_thread = None
        self.stop_event = threading.Event()

    def start_kernel(self):
        print("Iniciando kernel de Python...")
        self.km = KernelManager(kernel_name='python3')
        self.km.start_kernel()
        self.kc = self.km.client()
        self.kc.start_channels()

        # Esperar a que el kernel esté listo
        self.kc.wait_for_ready()
        print("Kernel de Python iniciado y listo.")

        self.listener_thread = threading.Thread(target=self._iopub_listener)
        self.listener_thread.daemon = True
        self.listener_thread.start()

    def _iopub_listener(self):
        while not self.stop_event.is_set():
            try:
                # Esperar mensajes del canal iopub
                msg = self.kc.iopub_channel.get_msg(timeout=0.1)
                self.output_queue.put(msg)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error en el listener iopub: {e}")
                break

    def execute_code(self, code):
        if not self.kc:
            print("Error: El kernel no está iniciado.")
            return

        print(f"\nEjecutando código:\n---\n{code}\n---")
        msg_id = self.kc.execute(code)

        # Esperar hasta que la ejecución esté completa (estado 'idle')
        # o hasta que se reciba un mensaje de 'execute_reply' para el msg_id
        while True:
            try:
                msg = self.output_queue.get(timeout=0.1)
                msg_type = msg['header']['msg_type']
                content = msg['content']

                if msg_type == 'stream':
                    print(f"OUTPUT: {content['text']}", end='')
                elif msg_type == 'error':
                    print(f"ERROR:\n{content['traceback']}", end='')
                elif msg_type == 'execute_result':
                    print(f"RESULT: {content['data'].get('text/plain', 'No plain text result')}")
                elif msg_type == 'status' and content['execution_state'] == 'idle':
                    # El kernel ha terminado de ejecutar
                    break
                elif msg_type == 'display_data':
                    if 'image/png' in content['data']:
                        print("[IMAGEN PNG GENERADA]")
                        # Aquí KogniTerm podría guardar/mostrar la imagen
                    elif 'text/html' in content['data']:
                        print(f"[HTML GENERADO]: {content['data']['text/html']}")
                        # Aquí KogniTerm podría renderizar el HTML
                    else:
                        print(f"DISPLAY_DATA: {content['data'].get('text/plain', 'Rich data')}")

            except queue.Empty:
                # Si no hay mensajes, verificar si el kernel está inactivo
                status_msg = self.kc.shell_channel.get_msg(timeout=0.1)
                if status_msg and status_msg['header']['msg_type'] == 'status' and status_msg['content']['execution_state'] == 'idle':
                    break
                continue
            except Exception as e:
                print(f"Error al procesar mensaje de salida: {e}")
                break

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
