## 05-09-25 Corrección de Flujo de Herramientas en Terminal

Descripción general: Se corrigió un problema en `kogniterm/terminal/terminal.py` donde las salidas de las herramientas y las respuestas del LLM no se procesaban correctamente, lo que impedía que el agente respondiera adecuadamente después de la ejecución de un comando.

- **Causa del Error**: El `ToolMessage` enviado al agente después de la ejecución de un comando utilizaba un `tool_call_id` genérico ("execute_command") en lugar del `id` específico de la `tool_call` generada por el LLM. Esto impedía que el agente correlacionara la salida del comando con la solicitud original de la herramienta.
- **Solución**:
    - Se añadió una variable `last_command_tool_call_id` en el bucle principal de la terminal para almacenar el `id` de la `tool_call` de "execute_command" cuando el LLM la genera.
    - Se modificaron las instancias de `ToolMessage` para que utilicen este `last_command_tool_call_id` capturado, asegurando que la salida del comando se asocie correctamente con la `tool_call` original.

---
## 05-09-25 Mejora de la Visualización de Mensajes del LLM en la Terminal
Descripcion general: Se mejoró la experiencia de usuario en la terminal al asegurar que los mensajes del LLM se visualicen correctamente, incluso cuando el LLM utiliza herramientas y no genera texto directamente. Esto se logró mostrando mensajes provisionales y asegurando una visualización final informativa.

- **Retroalimentación durante el streaming**: Se modificó `kogniterm/terminal/terminal.py` para que, si el `AIMessage` no tiene contenido de texto pero sí `tool_calls`, el panel de `rich` muestre "El LLM está utilizando herramientas...".
- **Visualización final informativa**: Se ajustó la lógica en `kogniterm/terminal/terminal.py` para que, al finalizar la interacción del LLM, si no hay texto pero sí `tool_calls`, se muestre un mensaje como "El LLM ha finalizado la ejecución de herramientas." en el panel final.

---
## 05-09-25 Limpieza de Logs de Depuración en Terminal

Descripción general: Se eliminaron los mensajes de log de depuración (`print("DEBUG: ...")`) del archivo `kogniterm/terminal/terminal.py` para limpiar la salida de la consola y mejorar la experiencia del usuario.

- **Punto 1**: Se identificaron y eliminaron todas las líneas que contenían `print("DEBUG: ...")` en el archivo `kogniterm/terminal/terminal.py`.
- **Punto 2**: Se eliminaron un total de 8 líneas de depuración.

---
## 05-09-25 Mejora en la Visualización de Salida de Herramientas

Descripción general: Se modificó la interfaz de la terminal para que la salida de las herramientas se visualice fuera del panel del LLM, permitiendo que solo el mensaje del LLM se muestre dentro del panel, mejorando la claridad y la experiencia del usuario.

- **Punto 1**: Se ajustó la lógica de streaming en `kogniterm/terminal/terminal.py` para que la información de las `tool_calls` se imprima directamente en la consola, en lugar de ser acumulada en el contenido del mensaje del LLM.
- **Punto 2**: Se modificó el manejo de la visualización final del panel del LLM para asegurar que solo el contenido textual del LLM se muestre, eliminando mensajes relacionados con la finalización de la ejecución de herramientas cuando no hay texto explícito del LLM.

---
## 05-09-25 Visualización de Código de Herramientas

Descripción general: Se implementó la visualización del código de las herramientas (especialmente `python_executor`) en un bloque formateado antes de su ejecución, mejorando la transparencia y el seguimiento de las acciones del LLM.

- **Punto 1**: Se modificó `kogniterm/terminal/terminal.py` para extraer el argumento `code` de las `tool_calls` de `python_executor`.
- **Punto 2**: El código extraído se muestra en un bloque de Markdown (```python
...
```) directamente en la consola, antes de la ejecución de la herramienta.
- **Punto 3**: Se aseguró que la información de la herramienta (nombre y argumentos) se siga mostrando fuera del panel del LLM, y que el panel del LLM contenga exclusivamente el mensaje textual del LLM.

---
## 06-09-25 Implementación de Kernel de Jupyter y Herramienta de Ejecución de Python

Descripción general: Se introdujo un kernel de Jupyter para Kogniterm, permitiendo la ejecución interactiva de código Python, y se añadió una herramienta de ejecución de Python para expandir las capacidades del agente. Además, se corrigieron problemas críticos en el procesamiento de la salida de herramientas en la terminal y se mejoró la visualización de mensajes del LLM.

- **Implementación del Kernel de Jupyter**: Se integró un kernel de Jupyter para Kogniterm, lo que facilita la ejecución interactiva de código Python y mantiene el estado entre sesiones.
- **Adición de Herramienta de Ejecución de Python**: Se incorporó una nueva herramienta (`python_executor`) que permite a los agentes ejecutar código Python directamente, ampliando su funcionalidad para tareas que requieren procesamiento de datos o lógica compleja.

- **Corrección de Procesamiento de Salida de Herramientas**: Se resolvió un problema crítico donde los IDs de llamada a herramienta no se asociaban correctamente, garantizando que los agentes reciban y procesen adecuadamente la salida de los comandos ejecutados.
- **Mejora de Visualización de Mensajes del LLM**: Se optimizó la forma en que se muestran los mensajes generados por el LLM en la terminal, mejorando la experiencia del usuario incluso cuando el LLM interactúa con herramientas y no produce texto directo.

---
## 06-09-25 Mejora en la Visualización de Salida de Python Executor

Descripción general: Se modificó `kogniterm/terminal/terminal.py` para formatear y mostrar la salida de la herramienta `python_executor` de manera estructurada y por trozos, mejorando la legibilidad y la experiencia del usuario.

- **Punto 1**: Se añadió la importación de `PythonTool` en `kogniterm/terminal/terminal.py` para acceder a la salida estructurada del ejecutor de Python.
- **Punto 2**: Se implementó una lógica en `kogniterm/terminal/terminal.py` para detectar `ToolMessage` provenientes de `python_executor`.
- **Punto 3**: La salida estructurada de `python_executor` (stream, error, execute_result, display_data) se itera y se imprime de forma formateada, utilizando `rich` para una mejor visualización si está disponible.
- **Punto 4**: Se aseguró que esta nueva visualización no interfiera con la salida de `command_executor` ni con el orden general de la interfaz.

---
## 06-09-25 Ocultar Argumentos de Herramientas en Logs

Descripción general: Se modificó `kogniterm/core/agents/bash_agent.py` para evitar la impresión de los argumentos de las herramientas en los logs de ejecución, mejorando la limpieza de la salida de la consola.

- **Punto 1**: Se eliminó la línea `console.print(f"[bold blue]⚙️ Argumentos:[/bold blue] [cyan]{tool_args}[/cyan]")` del archivo `kogniterm/core/agents/bash_agent.py`.

---
## 06-09-25 Corrección de Persistencia de Historial

Descripción general: Se implementaron cambios para asegurar la correcta persistencia del historial de conversación entre sesiones de KogniTerm, abordando el problema de que el historial se borraba al iniciar una nueva sesión.

- **Punto 1**: Se modificó `kogniterm/core/llm_service.py` para que las funciones `_load_history` y `_save_history` impriman errores en lugar de silenciarlos, facilitando la depuración de problemas de carga/guardado.
- **Punto 2**: Se modificó `kogniterm/core/agents/bash_agent.py` para que la clase `AgentState` inicialice su atributo `messages` como una lista vacía, en lugar de incluir el `SYSTEM_MESSAGE` por defecto.
- **Punto 3**: Se modificó `kogniterm/terminal/terminal.py` para importar `SYSTEM_MESSAGE` y ajustar la lógica de inicialización del `agent_state` y carga del historial. Ahora, el `SYSTEM_MESSAGE` se añade explícitamente una única vez al principio del historial del agente, evitando duplicados y asegurando su correcta presencia.
---
## 07-09-25 Corrección de Orden de Turnos en Llamadas a la API de Gemini

Descripción general: Se resolvió un error de la API de Gemini ("400 Please ensure that function call turn comes immediately after a user turn or after a function response turn") causado por una incorrecta conversión y manejo del historial de mensajes entre LangChain y el formato de la API de Gemini.

- **Punto 1**: Se modificó `kogniterm/core/agents/bash_agent.py` para que la propiedad `history_for_api` devuelva directamente los objetos `BaseMessage` de LangChain, eliminando una doble conversión innecesaria.
- **Punto 2**: Se ajustó `kogniterm/core/llm_service.py` para asegurar que la función `_to_gemini_content` maneje correctamente los `HumanMessage` como turnos de usuario simples, eliminando la lógica que los trataba incorrectamente como respuestas de función si tenían un `tool_call_id`. Esto garantiza que la secuencia de turnos de la API de Gemini se respete adecuadamente.
---
## 07-09-25 Corrección de Tipo de Mensaje Desconocido en LLMService

Descripción general: Se corrigió un `ValueError: Tipo de mensaje desconocido: <class 'dict'>` que ocurría en `kogniterm/core/llm_service.py` debido a que un diccionario se estaba pasando como un mensaje de LangChain en el historial de la conversación.

- **Punto 1**: Se modificó `kogniterm/core/agents/bash_agent.py` en la función `explain_command_node` para que, al construir el historial temporal (`temp_history`), se añada un objeto `HumanMessage` en lugar de un diccionario al historial. Esto asegura que todos los elementos del historial sean instancias de `BaseMessage` de LangChain, como espera `llm_service.py`.
---
## 07-09-25 Corrección de NameError para SystemMessage en LLMService

Descripción general: Se corrigió un `NameError: name 'SystemMessage' is not defined` que ocurría en `kogniterm/core/llm_service.py` debido a que la clase `SystemMessage` no estaba importada.

- **Punto 1**: Se añadió `SystemMessage` a la importación de `langchain_core.messages` en `kogniterm/core/llm_service.py`.
