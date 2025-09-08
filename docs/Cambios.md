## 07-09-25 Corrección de NameError para deque en LLMService

Descripción general: Se corrigió un `NameError: name 'deque' is not defined` que ocurría en `kogniterm/core/llm_service.py` debido a que `deque` no estaba importado.

- **Punto 1**: Se añadió `from collections import deque` a la lista de importaciones en `kogniterm/core/llm_service.py`.
---
## 07-09-25 Corrección de NameError para configure en LLMService

Descripción general: Se corrigió un `NameError: name 'configure' is not defined` que ocurría en `kogniterm/core/llm_service.py` debido a que la función `configure` no estaba importada.

- **Punto 1**: Se añadió `from google.generativeai import configure` a la lista de importaciones en `kogniterm/core/llm_service.py`.
---
## 07-09-25 Corrección de NameError para os en LLMService

Descripción general: Se corrigió un `NameError: name 'os' is not defined` que ocurría en `kogniterm/core/llm_service.py` debido a que el módulo `os` no estaba importado.

- **Punto 1**: Se añadió `import os` a la lista de importaciones en `kogniterm/core/llm_service.py`.
---
## 07-09-25 Corrección de TypeError y NameError en LLMService

Descripción general: Se corrigió un `TypeError: tool_call() missing 1 required keyword-only argument: 'id'` y un `NameError: name 'sys' is not defined` en `kogniterm/core/llm_service.py`. El `TypeError` se debía a que los `tool_calls` de `AIMessage` ahora requieren un argumento `id`. El `NameError` se resolvió al asegurar que `sys` estuviera correctamente importado y accesible en el contexto de manejo de errores.

- **Punto 1**: Se importó el módulo `uuid` para generar IDs únicos para los `tool_calls`.
- **Punto 2**: Se modificó la lógica de carga del historial en `_load_history` para incluir un `id` único en cada `tool_call` al reconstruir los `AIMessage`. Se añadió `tc.get('id', str(uuid.uuid4()))` para usar un ID existente si lo hay, o generar uno nuevo.
- **Punto 3**: Se actualizó la función `_save_history` para guardar el `id` de los `tool_calls` al serializar el historial, asegurando que la información se preserve correctamente.
---
## 07-09-25 Corrección de IndentationError en LLMService

Descripción general: Se corrigió un `IndentationError: unexpected indent` en `kogniterm/core/llm_service.py` causado por una línea mal indentada al final del archivo.

- **Punto 1**: Se eliminó una `l` solitaria y un `return None` mal indentado al final del archivo `kogniterm/core/llm_service.py`.
---
## 07-09-25 Corrección de TypeError en LLMService (Carga de Historial)

Descripción general: Se corrigió un `TypeError: tool_call() missing 1 required keyword-only argument: 'id'` que persistía al cargar el historial en `kogniterm/core/llm_service.py`. El problema se debía a que los `tool_calls` reconstruidos no siempre incluían el argumento `id` requerido por `langchain_core`.

- **Punto 1**: Se modificó la función `_load_history` para asegurar que cada `tool_call` reconstruido siempre tenga un `id`. Se utiliza `tc.get('id', str(uuid.uuid4()))` para obtener el `id` si existe en el historial serializado, o generar uno nuevo si no está presente.
- **Punto 2**: Se aseguró que el `id` se incluya también en el bloque `except` cuando los argumentos no se pueden parsear, garantizando que el `id` siempre esté presente.
---
## 07-09-25 Corrección de Error de API de Gemini (Orden de Turnos)

Descripción general: Se corrigió el error `400 Please ensure that function call turn comes immediately after a user turn or after a function response turn.` que indicaba un problema con el orden de los mensajes en el historial enviado a la API de Gemini.

- **Punto 1**: Se refactorizó la lógica de truncamiento del historial en la función `invoke` de `LLMService` para asegurar que los pares de mensajes de `function_call` y `function_response` se mantengan juntos y que el orden de los turnos sea siempre el esperado por la API de Gemini.
---
## 07-09-25 Corrección de Prompt de Sistema no Recibido por LLM

Descripción general: Se corrigió el problema por el cual el LLM no estaba recibiendo el prompt de sistema, lo que afectaba su capacidad para seguir instrucciones iniciales.

- **Punto 1**: Se modificó la función `invoke` en `kogniterm/core/llm_service.py` para insertar el `system_message` directamente al principio del historial de LangChain (`history`) antes de cualquier procesamiento o truncamiento. Esto asegura que el prompt de sistema siempre sea el primer mensaje enviado al modelo y tenga prioridad.
---
## 07-09-25 Persistencia del Prompt de Sistema después de %reset

Descripción general: Se implementó la persistencia del prompt de sistema para que no se pierda después de un comando `%reset` en el entorno del kernel.

- **Punto 1**: Se añadió un atributo `self.system_message` a la clase `LLMService` para almacenar el prompt de sistema.
- **Punto 2**: Se modificó la función `_save_history` para guardar el `self.system_message` en el archivo `kogniterm_history.json` como un mensaje de tipo 'system'.
- **Punto 3**: Se modificó la función `_load_history` para cargar el `system_message` del archivo de historial y establecerlo en `self.system_message`.
- **Punto 4**: Se ajustó la función `invoke` para que utilice `self.system_message` y lo actualice si se proporciona un nuevo `system_message` en la llamada.
---
## 07-09-25 Corrección de AttributeError: 'LLMService' object has no attribute 'system_message'

Descripción general: Se corrigió el `AttributeError` que ocurría porque la instancia de `LLMService` utilizada en `terminal.py` no tenía el atributo `system_message` inicializado correctamente.

- **Punto 1**: Se modificó la llamada a `_load_history` en `kogniterm/terminal/terminal.py` de `LLMService._load_history(HISTORY_FILE)` a `llm_service._load_history()`, asegurando que se llame como un método de instancia y que `self.system_message` se inicialice correctamente.
- **Punto 2**: Se modificaron las llamadas a `LLMService._save_history(HISTORY_FILE, [])` a `llm_service._save_history([])` en `kogniterm/terminal/terminal.py`, asegurando que también se llamen como métodos de instancia.
- **Punto 3**: Se modificó la llamada a `llm_service.invoke(history)` en `kogniterm/core/agents/bash_agent.py` para pasar explícitamente el `system_message` desde `llm_service.system_message`.
- **Punto 4**: Se eliminó la lógica de añadir el `SYSTEM_MESSAGE` constante al `agent_state.messages` en `kogniterm/terminal/terminal.py`, ya que el `system_message` ahora se maneja directamente por la instancia de `LLMService`.
---
## 07-09-25 Corrección de IndexError: list index out of range en LLMService

Descripción general: Se corrigió un `IndexError: list index out of range` que ocurría en `kogniterm/core/llm_service.py` cuando `response.candidates` estaba vacío, lo que indicaba que el modelo no había generado una respuesta válida.

- **Punto 1**: Se añadió una verificación `if not response.candidates:` después de la llamada a `chat_session.send_message(last_message_for_send)`.
- **Punto 2**: Si `response.candidates` está vacío, se devuelve un `AIMessage` con un mensaje de error amigable para el usuario, evitando el `IndexError` y proporcionando una retroalimentación clara.
---
## 07-09-25 Corrección de PydanticUserError: A non-annotated attribute en FileOperationsTool

Descripción general: Se corrigió un `PydanticUserError` en `kogniterm/core/tools/file_operations_tool.py` debido a que el atributo `ignored_directories` no tenía una anotación de tipo.

- **Punto 1**: Se añadió `ClassVar` a la importación de `typing`.
- **Punto 2**: Se anotó `ignored_directories` como `ClassVar[List[str]]` para indicar que es una variable de clase y no un campo del modelo.
---
## 07-09-25 Corrección de IndexError en LLMService (Manejo de Excepciones)

Descripción general: Se corrigió la reaparición del `IndexError: list index out of range` en `kogniterm/core/llm_service.py` al envolver la llamada a `chat_session.send_message` en un bloque `try-except` más amplio que captura explícitamente `IndexError`.

- **Punto 1**: Se modificó el bloque `try-except` en la función `invoke` de `LLMService` para incluir la captura de `IndexError`.
- **Punto 2**: Si se captura un `IndexError`, se devuelve un `AIMessage` con un mensaje de error que indica que hubo un problema al procesar la respuesta del modelo, incluyendo el traceback para depuración.
---
## 07-09-25 Instrucción al LLM para priorizar código Python

Descripción general: Se añadió una directriz al `SYSTEM_MESSAGE` del agente para instruir al LLM a priorizar el uso de la herramienta `python_executor` para tareas que puedan ser resueltas eficientemente con código Python.

- **Punto 1**: Se modificó el `SYSTEM_MESSAGE` en `kogniterm/core/agents/bash_agent.py` para incluir la frase: "**Prioriza el uso de la herramienta `python_executor` para tareas que puedan ser resueltas eficientemente con código Python, especialmente para lógica compleja, manipulación de datos o automatización.**"
---
## 07-09-25 Instrucción al LLM para priorizar recuadros Markdown

Descripción general: Se añadió una directriz al `SYSTEM_MESSAGE` del agente para instruir al LLM a priorizar el uso de recuadros Markdown para presentar información estructurada o resultados.

- **Punto 1**: Se modificó el `SYSTEM_MESSAGE` en `kogniterm/core/agents/bash_agent.py` para incluir la frase: "**Para presentar información estructurada o resultados, utiliza siempre recuadros Markdown (```) para mejorar la legibilidad y el orden.**"
---
## 07-09-25 Log de código Python en PythonTool

Descripción general: Se modificó la herramienta `PythonTool` para que el código Python a ejecutar se muestre siempre en la salida, formateado en un recuadro Markdown, en lugar de ser un log de depuración.

- **Punto 1**: Se modificó la línea de `print` en la función `_run` de `PythonTool` en `kogniterm/core/tools/python_executor.py`.
- **Punto 2**: Se eliminó el prefijo `DEBUG:` y el argumento `file=sys.stderr`.
- **Punto 3**: Se envolvió el código en un bloque de código Markdown (````python
{code}
````) para una mejor visualización.
---
## 07-09-25 Persistencia del Historial de Conversación por Directorio

Descripción general: Se modificó la lógica de guardado del historial de conversación del LLM para que sea persistente entre sesiones y se guarde en un archivo `kogniterm_history.json` dentro del directorio de trabajo actual donde se inicia `kogniterm`. Esto asegura que cada directorio tenga su propio historial de chat.

- **Punto 1**: Se modificó la definición de `HISTORY_FILE` en `kogniterm/core/llm_service.py` para que utilice `os.path.join(os.getcwd(), "kogniterm_history.json")`, asegurando una ruta absoluta basada en el directorio de trabajo actual.
- **Punto 2**: Se añadió `import pathlib` en `kogniterm/core/llm_service.py` para un manejo más robusto de rutas, aunque `os.path.join` es suficiente para este caso.
---
## 07-09-25 Corrección de Error al Cargar Historial (ID de Tool Call)

Descripción general: Se corrigió el error `tool_call() missing 1 required keyword-only argument: 'id'` que ocurría al cargar el historial de conversación, asegurando que cada `tool_call` reconstruido tenga un `id` único.

- **Punto 1**: Se modificó la función `_load_history` en `kogniterm/core/llm_service.py` para incluir el `id` en los `formatted_tool_calls` al reconstruir los `AIMessage`. Se utiliza `tc.get('id', str(uuid.uuid4()))` para asignar un `id` existente o generar uno nuevo.
- **Punto 2**: Se añadió `import uuid` al principio del archivo `kogniterm/core/llm_service.py` para permitir la generación de IDs únicos.
---
## 07-09-25 Reversión de Reinicio de Historial en Comandos Meta

Descripción general: Se revirtió el cambio que eliminaba el reinicio del historial de conversación en los comandos `%reset` y `%agentmode` en `kogniterm/terminal/terminal.py`. Esto asegura que estos comandos borren el historial de la sesión actual como es su función esperada.

- **Punto 1**: Se reintrodujo la línea `llm_service.conversation_history = []` en el bloque del comando `%reset` en `kogniterm/terminal/terminal.py`.
- **Punto 2**: Se reintrodujo la línea `llm_service.conversation_history = []` en el bloque del comando `%agentmode` en `kogniterm/terminal/terminal.py`.
---
## 08-09-25 Corrección de AttributeError en terminal.py (Manejo de Streamed State)

Descripción general: Se corrigió un `AttributeError: 'dict' object has no attribute 'messages'` que ocurría en `kogniterm/terminal/terminal.py` en la línea 226. El error se debía a que `streamed_state` se estaba tratando como un objeto con un atributo `messages`, cuando en el contexto de streaming de `langgraph` y `rich.Live`, se recibía como un diccionario que contenía el estado.

- **Punto 1**: Se modificó la línea 226 en `kogniterm/terminal/terminal.py` de `agent_state.messages = streamed_state.messages` a `agent_state.messages = streamed_state['messages']` para acceder correctamente a los mensajes como una clave de diccionario.
---
## 08-09-25 Corrección de KeyError en terminal.py (Manejo de Streamed State Anidado)

Descripción general: Se corrigió un `KeyError: 'messages'` que ocurría en `kogniterm/terminal/terminal.py` en la línea 227. El error se debía a que `streamed_state` era un diccionario que contenía el estado anidado bajo la clave `'call_model'`, y se estaba intentando acceder a `'messages'` directamente en el nivel superior.

- **Punto 1**: Se modificó la línea 227 en `kogniterm/terminal/terminal.py` de `agent_state.messages = streamed_state['messages']` a `agent_state.messages = streamed_state['call_model']['messages']` para acceder correctamente a los mensajes anidados.

---
## 08-09-25 Corrección de Lógica de Streaming en terminal.py (Manejo de command_to_confirm y final_streamed_state)

Descripción general: Se corrigió el problema donde KogniTerm se quedaba "pensando" indefinidamente debido a un manejo incorrecto de la estructura anidada del `streamed_state` y `final_streamed_state` en el contexto de streaming con `langgraph` y `rich.Live`.

- **Punto 1**: Se modificó la línea 228 en `kogniterm/terminal/terminal.py` de `agent_state.command_to_confirm = streamed_state.command_to_confirm` a `agent_state.command_to_confirm = streamed_state['call_model'].get('command_to_confirm')` para acceder correctamente al `command_to_confirm` anidado.
- **Punto 2**: Se modificó la línea 234 en `kogniterm/terminal/terminal.py` de `agent_state.messages = final_streamed_state['messages']` a `agent_state.messages = final_streamed_state['call_model']['messages']` para asegurar la correcta asignación de los mensajes del estado final.
- **Punto 3**: Se modificó la línea 235 en `kogniterm/terminal/terminal.py` de `agent_state.command_to_confirm = final_streamed_state.get('command_to_confirm')` a `agent_state.command_to_confirm = final_streamed_state['call_model'].get('command_to_confirm')` para asegurar la correcta asignación del `command_to_confirm` del estado final.

---
## 08-09-25 Corrección de Contexto de Historial en terminal.py (Manejo de SYSTEM_MESSAGE)

Descripción general: Se corrigió el problema donde KogniTerm parecía entender el historial como si fuese solo el último mensaje, debido a un manejo inconsistente del `SYSTEM_MESSAGE` al inicio y reinicio de la conversación.

- **Punto 1**: Se modificó la inicialización del `agent_state` en `kogniterm/terminal/terminal.py` para asegurar que el `SYSTEM_MESSAGE` se añada al `agent_state.messages` al inicio, evitando duplicados si ya está presente en el historial cargado.
- **Punto 2**: Se modificó el bloque del comando `%reset` en `kogniterm/terminal/terminal.py` para añadir el `SYSTEM_MESSAGE` al `agent_state.messages` al reiniciar la conversación.
- **Punto 3**: Se modificó el bloque del comando `%agentmode` en `kogniterm/terminal/terminal.py` para añadir el `SYSTEM_MESSAGE` al `agent_state.messages` al cambiar de modo.
---
## 08-09-25 Corrección de Error al Cargar Historial (ID de Tool Call)

Descripción general: Se corrigió el `TypeError: tool_call() missing 1 required keyword-only argument: 'id'` que ocurría al cargar el historial. El problema se debía a que los `tool_calls` de `AIMessage` ahora requieren un argumento `id`, el cual no se estaba incluyendo consistentemente al reconstruir el historial.

- **Punto 1**: Se importó el módulo `uuid` para generar IDs únicos para los `tool_calls`.
- **Punto 2**: Se modificó la función `_load_history` en `kogniterm/core/llm_service.py` para asegurar que cada `tool_call` reconstruido siempre tenga un `id`. Se utiliza `tc.get('id', str(uuid.uuid4()))` para obtener el `id` si existe en el historial serializado, o generar uno nuevo si no está presente. Esto se aplicó a todos los casos de reconstrucción de `tool_calls` (cuando los argumentos son un diccionario, cuando se parsean, y cuando se usa un diccionario vacío).
- **Punto 3**: Se actualizó la función `_save_history` en `kogniterm/core/llm_service.py` para guardar el `id` de los `tool_calls` al serializar el historial, asegurando que la información se preserve correctamente para futuras cargas.
---
## 08-09-25 Corrección de AttributeError: 'dict' object has no attribute 'id' al guardar historial.
Descripción general: Se corrigió un `AttributeError` que ocurría al intentar guardar el historial de conversación en `kogniterm/core/llm_service.py`. El error se debía a que se intentaba acceder a un atributo `id` de un diccionario (`tool_call`) con notación de punto, cuando debería ser con notación de corchetes.

- **Punto 1**: Se modificó la función `_save_history` en `kogniterm/core/llm_service.py` para acceder al `id` de los `tool_calls` usando `tc['id']` en lugar de `tc.id`.
- **Punto 2**: Se mejoró la robustez al guardar el `id` de los `tool_calls` utilizando `tc.get('id', str(uuid.uuid4()))` para asegurar que siempre se guarde un `id` válido, incluso si no está presente en el diccionario original.
---
## 08-09-25 Corrección de AttributeError: 'AIMessage' object has no attribute 'candidates' en bash_agent.py.
Descripción general: Se corrigió un `AttributeError` que ocurría en `kogniterm/core/agents/bash_agent.py` dentro de la función `explain_command_node`. El error se debía a que se intentaba acceder al atributo `candidates` de un objeto `AIMessage`, cuando los objetos `AIMessage` de LangChain no tienen este atributo.

- **Punto 1**: Se modificó la función `explain_command_node` en `kogniterm/core/agents/bash_agent.py` para verificar si la respuesta (`response`) de `llm_service.invoke` es una instancia de `AIMessage`.
- **Punto 2**: Si `response` es un `AIMessage`, se extrae el texto de la explicación directamente de `response.content`.
- **Punto 3**: Si `response` no es un `AIMessage` (asumiendo que es el formato nativo de Gemini), se mantiene la lógica original de acceder a `response.candidates[0].content.parts[0].text`.
---
## 08-09-25 Corrección de error al cargar historial de ToolMessage

Se ha corregido un error inesperado (`tool_call() missing 1 required keyword-only argument: 'id'`) que ocurría al cargar el historial de conversación, específicamente al reconstruir los objetos `ToolMessage`. Este error se debía a que el atributo `id` de `ToolMessage` no se estaba persistiendo ni cargando correctamente.

- **Punto 1**: Se modificó la función `_save_history` en `kogniterm/core/llm_service.py` para incluir el atributo `id` de los objetos `ToolMessage` al serializar el historial en `kogniterm_history.json`.
- **Punto 2**: Se modificó la función `_load_history` en `kogniterm/core/llm_service.py` para leer el atributo `id` del historial serializado y pasarlo al constructor de `ToolMessage` al reconstruir los mensajes. Se utilizó `.get('id')` para asegurar compatibilidad con historiales antiguos que no contengan este campo.
