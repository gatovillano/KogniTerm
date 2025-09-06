# Propuesta: Integración de Ejecución de Código Python basada en Kernel de Jupyter para KogniTerm

## 1. Introducción

La ejecución de código Python en KogniTerm se beneficiará enormemente de la adopción de un modelo basado en un kernel de Jupyter. Este enfoque, similar al de OpenInterpreter, permitirá una interactividad avanzada, mantenimiento del estado entre ejecuciones, y la capacidad de manejar una amplia gama de tipos de salida (texto, errores, imágenes, HTML, etc.). Esto transformará KogniTerm en una herramienta mucho más potente y flexible para la interacción con código.

## 2. Componentes Clave de `jupyter_client`

La biblioteca `jupyter_client` proporciona las herramientas necesarias para interactuar con kernels de Jupyter. Los componentes principales que utilizaremos son:

*   **`KernelManager`**: Responsable de iniciar, detener y gestionar el ciclo de vida de un kernel. En nuestro caso, lo usaremos para iniciar un kernel de `python3`.
*   **`KernelClient`**: Una vez que el `KernelManager` ha iniciado un kernel, el `KernelClient` se conecta a sus diferentes canales de comunicación (`shell`, `iopub`, `stdin`). Este cliente es el que utilizaremos para enviar código y recibir la salida.

## 3. Ciclo de Vida de la Ejecución con Jupyter Kernel

El proceso para ejecutar código Python en KogniTerm utilizando un kernel de Jupyter seguiría estos pasos:

### 3.1. Inicialización del Kernel:

1.  **Instanciar `KernelManager`**: Se creará una instancia de `KernelManager` especificando el nombre del kernel (ej. `python3`).
2.  **Iniciar el Kernel**: `km.start_kernel()` iniciará el proceso del kernel de Python en segundo plano. Esto puede tomar unos segundos.
3.  **Instanciar `KernelClient`**: Se creará una instancia de `KernelClient` a partir del `KernelManager`.
4.  **Conectar Canales**: `kc.start_channels()` establecerá la conexión con los canales de comunicación del kernel. Es importante esperar a que el kernel esté vivo y los canales conectados antes de intentar enviar código.

### 3.2. Ejecución de Código:

1.  **Enviar Código**: El código Python se enviará al kernel utilizando `kc.execute(code)`. Este método devuelve un `msg_id` que puede usarse para rastrear la ejecución.
2.  **Hilo de Escucha (Asíncrono)**: Para procesar la salida de forma asíncrona y en tiempo real, se lanzará un hilo separado que escuchará continuamente el canal `iopub` del `KernelClient`. Este canal es donde el kernel envía todos los mensajes de salida (stdout, stderr, resultados, etc.).
3.  **Procesamiento de Mensajes**: El hilo de escucha leerá los mensajes del canal `iopub` y los pondrá en una cola interna. KogniTerm leerá de esta cola para mostrar la salida al usuario.

### 3.3. Procesamiento de la Salida del Kernel:

Los mensajes del canal `iopub` tendrán un `msg_type` que indicará el tipo de contenido. KogniTerm deberá manejar los siguientes tipos principales:

*   **`stream`**: Contiene la salida estándar (`stdout`) y los errores estándar (`stderr`). Se mostrará al usuario como texto.
*   **`error`**: Contiene información de errores y tracebacks. Se mostrará de forma clara al usuario, posiblemente resaltando el traceback.
*   **`execute_result`**: Contiene el resultado de la última expresión evaluada en una celda de código (similar a lo que se ve en un cuaderno de Jupyter).
*   **`display_data`**: Contiene datos enriquecidos como imágenes (PNG, JPEG en base64), HTML, JavaScript, etc. KogniTerm podría renderizar estos contenidos si la interfaz lo permite (por ejemplo, mostrando una imagen o incrustando HTML).

### 3.4. Finalización y Gestión del Kernel:

1.  **Detección de Inactividad**: El hilo de escucha detectará cuando el kernel vuelve a un estado "idle" (inactivo) después de una ejecución, indicando que el código ha terminado de ejecutarse.
2.  **Interrupción del Kernel**: Se debe implementar una forma de interrumpir la ejecución del código si el usuario lo solicita (similar a CTRL-C). Esto se puede lograr con `km.interrupt_kernel()`.
3.  **Apagado del Kernel**: Cuando KogniTerm ya no necesite el kernel, o al cerrar la aplicación, se debe apagar limpiamente con `kc.stop_channels()` y `km.shutdown_kernel()`.

## 4. Ejemplo de Código Conceptual (Python)

```python
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

        print(f"
Ejecutando código:
---
{code}
---")
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
                    print(f"ERROR:
{content['traceback']}", end='')
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

# Ejemplo de uso:
# kernel_manager = KogniTermKernel()
# kernel_manager.start_kernel()
# kernel_manager.execute_code("a = 10
b = 20
print(a + b)")
# kernel_manager.execute_code("import matplotlib.pyplot as plt
plt.plot([1,2,3])
plt.show()")
# kernel_manager.execute_code("raise ValueError('Esto es un error')")
# kernel_manager.stop_kernel()
```

## 5. Beneficios para KogniTerm

*   **Estado Persistente**: Las variables y funciones definidas en una ejecución se mantienen disponibles para las siguientes, lo que permite interacciones de código más complejas y de varias "celdas".
*   **Salida Enriquecida**: Soporte nativo para imágenes, gráficos, HTML y otros tipos de datos que mejorarán significativamente la experiencia del usuario.
*   **Retroalimentación en Tiempo Real**: La arquitectura asíncrona permitirá mostrar la salida a medida que se genera, no solo al final de la ejecución.
*   **Depuración Mejorada**: Los tracebacks se presentarán de manera más estructurada y completa.
*   **Compatibilidad**: Al usar un estándar de Jupyter, KogniTerm sería compatible con las herramientas y bibliotecas existentes del ecosistema Jupyter.

## 6. Desafíos y Consideraciones

*   **Gestión de Recursos**: Un kernel de Python consume memoria y CPU. KogniTerm necesitará una estrategia para iniciar y detener kernels eficientemente, quizás un solo kernel por sesión de usuario.
*   **Manejo de Errores Robustos**: Es crucial manejar correctamente las excepciones y los errores de comunicación con el kernel para evitar bloqueos.
*   **Asincronía y Concurrencia**: La implementación de hilos para el listener de `iopub` requiere una gestión cuidadosa para evitar condiciones de carrera y garantizar la finalización limpia.
*   **Interfaz de Usuario**: La interfaz de KogniTerm necesitará adaptarse para mostrar los diferentes tipos de salida de manera efectiva (ej. un visor de imágenes, un renderizador de HTML).
*   **Instalación de Dependencias**: Asegurarse de que `jupyter_client` e `ipykernel` estén correctamente instalados en el entorno de KogniTerm.

## 7. Próximos Pasos

1.  **Implementación del `KogniTermKernel`**: Desarrollar la clase `KogniTermKernel` (o similar) basada en el concepto propuesto, integrándola en la arquitectura de KogniTerm.
2.  **Manejo de la Interfaz de Usuario**: Adaptar la capa de presentación de KogniTerm para consumir la salida de `KogniTermKernel` y renderizar los diferentes tipos de mensajes (texto, errores, imágenes, etc.).
3.  **Pruebas Exhaustivas**: Realizar pruebas rigurosas para asegurar la estabilidad, el rendimiento y el manejo correcto de errores en diversas situaciones.
4.  **Optimización**: Considerar optimizaciones para el inicio y apagado del kernel, así como para el procesamiento de grandes volúmenes de salida.
