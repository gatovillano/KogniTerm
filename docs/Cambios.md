---                                                                    
## 29-10-25 Corrección de Importación Circular de AgentState
Descripción general: Se resolvió un `ImportError` causado por una importación circular entre `kogniterm.terminal.terminal_ui` y `kogniterm.core.agents.bash_agent` al importar la clase `AgentState`.

- **Punto 1**: Se creó un nuevo archivo `kogniterm/core/agent_state_types.py` para contener la definición de la clase `AgentState`.
- **Punto 2**: Se eliminó la definición de `AgentState` de `kogniterm/core/agents/bash_agent.py` y se actualizó su importación para que apunte a `kogniterm/core/agent_state_types.py`.
- **Punto 3**: Se actualizó la importación de `AgentState` en `kogniterm/terminal/terminal_ui.py` para que apunte a `kogniterm/core/agent_state_types.py`.
- **Punto 4**: Se eliminó la importación de `TerminalUI` de `kogniterm/core/agents/bash_agent.py` ya que no era necesaria directamente en ese módulo, rompiendo así el ciclo de importación.
---
## 29-10-25 Corrección de TypeError y Propagación de TerminalUI
Descripción general: Se corrigió un `TypeError` en la llamada a `create_bash_agent` y se aseguró la correcta propagación de la instancia de `TerminalUI` a través de las capas de la aplicación para habilitar la interactividad de la terminal.

- **Punto 1**: Se modificó `AgentInteractionManager.__init__` en `kogniterm/terminal/agent_interaction_manager.py` para aceptar `terminal_ui` como argumento y pasarlo a `create_bash_agent`.
- **Punto 2**: Se modificó `KogniTermApp.__init__` en `kogniterm/terminal/kogniterm_app.py` para pasar la instancia de `TerminalUI` al constructor de `AgentInteractionManager`.
---
## 29-10-25 Ajuste de Suspensión/Reanudación de prompt_toolkit para Interactividad de Comandos
Descripción general: Se ajustó la lógica de suspensión y reanudación de `prompt_toolkit` para asegurar la correcta interactividad con comandos de terminal que requieren entrada del usuario (ej. `sudo`), moviendo estas operaciones al momento de la ejecución real del comando.

- **Punto 1**: Se modificó `handle_command_approval` en `kogniterm/terminal/command_approval_handler.py`.
- **Punto 2**: La suspensión (`self.prompt_session.app.suspend_to_background()`) y reanudación (`self.prompt_session.app.run_in_terminal(lambda: None)`) de `prompt_toolkit` ahora ocurren *dentro* del bloque `try` donde se ejecuta `self.command_executor.execute()`.
- **Punto 3**: Se añadió `self.terminal_ui.print_stream(output_chunk)` para mostrar la salida del comando en tiempo real.
- **Punto 4**: Se incluyó un bloque `except Exception as e` para asegurar que `prompt_toolkit` se reanude incluso si ocurre un error durante la ejecución del comando.
---
## 29-10-25 Impresión Directa de Salida de Comandos en CommandExecutor
Descripción general: Se modificó `CommandExecutor` para imprimir la salida de los comandos directamente en `sys.stdout` en tiempo real, asegurando la interactividad con comandos que requieren entrada del usuario.

- **Punto 1**: En `kogniterm/core/command_executor.py`, dentro del método `execute`, se añadió `sys.stdout.write(output)` y `sys.stdout.flush()` justo después de leer la salida del PTY.
- **Punto 2**: Esto delega la responsabilidad de la visualización en tiempo real al `CommandExecutor`, que ya maneja el PTY, evitando conflictos con `prompt_toolkit` y permitiendo la interactividad con comandos como `sudo`.
---
## 29-10-25 Consistencia en la Salida de Herramientas para el LLM
Descripción general: Se aseguró que el método `_invoke_tool_with_interrupt` en `LLMService` siempre devuelva un generador, independientemente de si la herramienta subyacente produce una salida generada o un resultado directo. Esto garantiza que el LLM reciba la salida de todas las herramientas de manera consistente.

- **Punto 1**: Se modificó el método `_invoke_tool_with_interrupt` en `kogniterm/core/llm_service.py`.
- **Punto 2**: Si la herramienta invocada devuelve un resultado directo (no un generador), este resultado ahora se envuelve en un generador de un solo elemento (`yield from [result]`), asegurando que el método siempre devuelva un generador.
- **Punto 3**: Esto resuelve el problema donde el LLM no recibía la salida de herramientas que no eran generadores, como `file_operations`, permitiendo que el agente razone correctamente sobre la información proporcionada por todas las herramientas.
---
## 29-10-25 Corrección de Propagación de Salida de file_operations al LLM
Descripción general: Se corrigió un problema donde el LLM no recibía la salida completa de la herramienta `file_operations`, especialmente para archivos de texto plano, debido a una lógica incorrecta en la construcción del `ToolMessage`.

- **Punto 1**: Se modificó el método `execute_tool_node` en `kogniterm/core/agents/bash_agent.py`.
- **Punto 2**: Se reestructuró la lógica para la construcción del `ToolMessage` para `file_operations`, asegurando que `full_tool_output` (que contiene el contenido completo del archivo) se utilice directamente como contenido del `ToolMessage`.
- **Punto 3**: La lógica de procesamiento de JSON y mensajes descriptivos ahora se aplica solo a otras herramientas, garantizando que la salida de `file_operations` no sea alterada antes de ser enviada al LLM.
---
## 29-10-25 Corrección de IndentationError y Propagación de Salida de file_operations al LLM
Descripción general: Se corrigió un `IndentationError` en `kogniterm/core/agents/bash_agent.py` y se ajustó la lógica para asegurar que el LLM reciba la salida completa de la herramienta `file_operations`.

- **Punto 1**: Se corrigió el `IndentationError` en la línea 248 de `kogniterm/core/agents/bash_agent.py`.
- **Punto 2**: Se reestructuró la lógica en `execute_tool_node` para la construcción del `ToolMessage` para `file_operations`, asegurando que `full_tool_output` (que contiene el contenido completo del archivo) se utilice directamente como contenido del `ToolMessage`.
- **Punto 3**: La lógica de procesamiento de JSON y mensajes descriptivos ahora se aplica solo a otras herramientas, garantizando que la salida de `file_operations` no sea alterada antes de ser enviada al LLM.
---
## 30-10-25 Mejora en la Acumulación de Tool Calls en LLMService
Descripción general: Se mejoró la robustez en la acumulación de `tool_calls` dentro de la función `invoke` de `LLMService` para mitigar el error `litellm.APIConnectionError: Missing corresponding tool call for tool response message`.

- **Punto 1**: Se modificó la lógica de acumulación de `tool_calls` en `kogniterm/core/llm_service.py`, dentro de la función `invoke`.
- **Punto 2**: Se aseguró que la lista `tool_calls` se expanda dinámicamente para acomodar nuevos índices (`tc.index`).
- **Punto 3**: Se implementó una lógica para que el `id` de cada `tool_call` se establezca de forma más robusta tan pronto como esté disponible en cualquier `chunk` de la respuesta del modelo.
- **Punto 4**: Se ajustó la actualización del nombre de la función para que no sobrescriba un nombre ya establecido si el `delta` no lo proporciona.
---
## 30-10-25 Mejora en la Visualización de Diff en Confirmaciones de Actualización
Descripción general: Se modificó la forma en que se presenta el `diff` en las confirmaciones de actualización de archivos para que se muestre dentro de un bloque de código Markdown con resaltado de sintaxis `diff`, mejorando la legibilidad.

- **Punto 1**: Se modificó la función `handle_file_update_confirmation` en `kogniterm/terminal/terminal_ui.py`.
- **Punto 2**: Se simplificó la construcción de la variable `formatted_diff` para que contenga directamente el contenido del `diff` en texto plano, eliminando los estilos `rich` (`[green]`, `[red]`).
- **Punto 3**: El bloque de código Markdown (` ```diff `) ahora es el encargado de aplicar el resaltado de sintaxis al `diff` en la interfaz de usuario.
---
## 30-10-25 Mejora en la Interpretación de ToolMessages por el LLM
Descripción general: Se añadió una instrucción al sistema del LLM para que interprete correctamente los `ToolMessage`s de ejecución exitosa, evitando la redundancia en los anuncios de ejecución de herramientas.

- **Punto 1**: Se modificó la variable `tool_confirmation_instruction` en `kogniterm/core/llm_service.py`.
- **Punto 2**: Se añadió una instrucción explícita al LLM para que, al recibir un `ToolMessage` que indica una ejecución exitosa, considere esa acción como completada y no la anuncie ni la proponga de nuevo en su siguiente respuesta, sino que continúe con el siguiente paso de la tarea.
---
## 30-10-25 Corrección de `AttributeError` en `summarize_conversation_history`
Descripción general: Se corrigió un `AttributeError: 'NoneType' object has no attribute 'startswith'` que ocurría cuando la función `summarize_conversation_history()` en `kogniterm/core/llm_service.py` devolvía `None`, lo que causaba un fallo en `kogniterm/terminal/meta_command_processor.py`.
- **Punto 1**: Se modificó la firma de la función `summarize_conversation_history()` en `kogniterm/core/llm_service.py` para que siempre devuelva una cadena (`str`) en lugar de `Optional[str]`.
- **Punto 2**: Se añadió una condición para que, si el historial de conversación está vacío, la función devuelva una cadena vacía (`""`) en lugar de `None`.
- **Punto 3**: Se ajustó el manejo de errores en la función para que, en caso de fallo al generar el resumen, se devuelva un mensaje de error como cadena de texto, asegurando que `summary` nunca sea `None`.
---
## 30-10-25 Mejora en el Manejo de Contexto del Espacio de Trabajo para el LLM
Descripción general: Se mejoró el manejo del contexto del espacio de trabajo en `WorkspaceContext` para evitar errores de decodificación y mensajes de herramientas excesivamente largos que causaban `litellm.BadRequestError`.

- **Punto 1**: Se modificó la función `_get_file_contents` en `kogniterm/core/context/workspace_context.py`.
- **Punto 2**: Ahora se aplica `_should_ignore` de forma más estricta antes de intentar leer un archivo, verificando tanto el nombre del elemento como la ruta completa.
- **Punto 3**: Se implementó una lógica para detectar y marcar archivos binarios como "(Contenido binario no legible)", evitando intentos de decodificación `utf-8` en ellos.
- **Punto 4**: Se añadió un truncamiento para el contenido de archivos de texto extensos (`MAX_FILE_CONTENT_LENGTH = 5000`) para asegurar que la salida del `ToolMessage` no exceda los límites de la API del LLM.
---
## 30-10-25 Mejora en el Truncamiento y Formateo de Salidas de Herramientas para el LLM
Descripción general: Se implementó una lógica de truncamiento y formateo más robusta para las salidas de herramientas en `kogniterm/core/agents/bash_agent.py` antes de que se conviertan en `ToolMessage`s. Esto resuelve el `litellm.BadRequestError` causado por mensajes de herramientas excesivamente largos o mal formateados.

- **Punto 1**: Se modificó la función `execute_tool_node` en `kogniterm/core/agents/bash_agent.py`.
- **Punto 2**: Se añadió una lógica para detectar si la salida de la herramienta es un JSON que contiene `file_path` y `content` (como las salidas de lectura de archivos). En este caso, el `content` se trunca a `MAX_TOOL_OUTPUT_CONTENT_LENGTH` (2000 caracteres) antes de ser serializado nuevamente a JSON.
- **Punto 3**: Si la salida es una lista de JSONs (como en `read_many_files`), cada `content` individual dentro de la lista se trunca a `MAX_TOOL_OUTPUT_CONTENT_LENGTH` (500 caracteres).
- **Punto 4**: Para otras salidas JSON, la representación de cadena del JSON se trunca a `MAX_GENERIC_JSON_LENGTH` (2000 caracteres).
- **Punto 5**: Si la salida no es JSON, la cadena completa se trunca a `MAX_GENERIC_OUTPUT_LENGTH` (2000 caracteres).
- **Punto 6**: Estos truncamientos aseguran que el `ToolMessage` final sea conciso y esté correctamente formateado antes de ser enviado a `litellm`, evitando errores de `BadRequestError` y mejorando la comunicación con el LLM.
---
## 30-10-25 Manejo de Errores en AdvancedFileEditorTool
Descripción general: Se mejoró el manejo de errores en `advanced_file_editor_tool.py` para evitar `litellm.APIConnectionError` cuando se intenta editar un archivo no existente. La herramienta ahora devuelve un mensaje de error estructurado en lugar de lanzar una excepción.

- **Punto 1**: Se modificó la función `_read_file_content` en `kogniterm/core/tools/advanced_file_editor_tool.py` para que devuelva un diccionario con `status` y `content` (si es exitoso) o `status` y `message` (si hay un error), en lugar de lanzar excepciones.
- **Punto 2**: Se ajustó la función `_run` en `kogniterm/core/tools/advanced_file_editor_tool.py` para que verifique el `status` del resultado de `_read_file_content`. Si el `status` es `error`, `_run` devuelve un diccionario con el mensaje de error, lo que permite que `litellm` procese la respuesta correctamente.
---
## 19-11-25 Solución a Errores de LiteLLM: Missing Tool Call y 503 Service Unavailable
Descripción general: Se implementaron mejoras en `kogniterm/core/llm_service.py` para solucionar el error `Missing corresponding tool call for tool response message` y para manejar de forma robusta los errores 503 (`Service Unavailable`) del modelo.

- **Consistencia del historial de mensajes**: Se ajustó la lógica en la función `invoke` para asegurar que cada `ToolMessage` tenga un `AIMessage` con la `tool_call` correspondiente en el historial que se envía a `litellm`. Esto evita que se envíen `ToolMessage`s huérfanos que causaban el error `Missing corresponding tool call for tool response message`.
- **Manejo de errores 503 con reintentos**: Se añadió una lógica de reintentos con backoff exponencial a las llamadas de `litellm.completion` (tanto para la invocación principal como para el resumen del historial). Esto permite que la aplicación espere y reintente automáticamente si el modelo devuelve un error 503 debido a sobrecarga, mejorando la robustez de la aplicación.
- **Mensajes AIMessage vacíos**: Se añadió una verificación para eliminar `AIMessage`s vacíos al final del historial, lo cual también puede causar problemas con `litellm`.