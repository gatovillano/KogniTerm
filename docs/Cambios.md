---
## 01-11-25 Refactorización del Flujo del Agente para Evitar Explicaciones Redundantes
Descripción general: Se refactorizó el flujo del agente en `kogniterm/core/agents/bash_agent.py` y `kogniterm/core/agent_state_types.py` para evitar que el LLM genere explicaciones redundantes de comandos después de su ejecución, procesando directamente la salida del comando.

- **Punto 1**: Se añadió la bandera `command_output_ready_for_processing: bool = False` al `AgentState` en `kogniterm/core/agent_state_types.py` y se aseguró su reseteo en los métodos `reset` y `reset_temporary_state`.
- **Punto 2**: En `kogniterm/core/agents/bash_agent.py`, se modificó `execute_tool_node` para establecer `state.command_output_ready_for_processing = True` cuando se ejecuta un `execute_command`.
- **Punto 3**: Se modificó `should_continue` para que, si `state.command_output_ready_for_processing` es `True`, el flujo siempre regrese a `call_model`. 
- **Punto 4**: Se añadió una lógica condicional al inicio de `call_model_node` para que, si `state.command_output_ready_for_processing` es `True`, procese directamente el último `ToolMessage` (la salida del comando), genere una respuesta concisa al usuario y resetee la bandera a `False`.
---
## 01-11-25 Corrección de AttributeError en AgentState
Descripción general: Se corrigió un `AttributeError` en la clase `AgentState` al intentar acceder al atributo `command_output_ready_for_processing` antes de que fuera definido.

- **Punto 1**: Se añadió `command_output_ready_for_processing: bool = False` como un campo explícito en la clase `AgentState` en `kogniterm/core/agent_state_types.py` para asegurar su existencia y correcta inicialización.
---
## 01-11-25 Corrección de Duplicación de Explicaciones de Comandos
Descripción general: Se corrigió la duplicación de explicaciones de comandos en la interfaz de confirmación, asegurando que la explicación se genere una sola vez y se almacene correctamente en el estado del agente.

- **Punto 1**: Se añadió `command_explanation: Optional[str] = None` como un campo explícito en la clase `AgentState` en `kogniterm/core/agent_state_types.py`.
- **Punto 2**: En `kogniterm/core/agents/bash_agent.py`, se modificó `execute_tool_node` para generar una explicación concisa del comando `execute_command` y almacenarla en `state.command_explanation`.
- **Punto 3**: Se modificaron los métodos `reset` y `reset_temporary_state` en `kogniterm/core/agent_state_types.py` para asegurar que `command_explanation` se resetee a `None`.
---
## 01-11-25 Corrección de Confirmación de Actualización Redundante
Descripción general: Se solucionó el problema donde el agente generaba respuestas redundantes después de una confirmación exitosa de actualización de archivo, al no reconocer que la acción ya había sido aplicada.

- **Punto 1**: En `kogniterm/core/agents/bash_agent.py`, se modificó la función `handle_tool_confirmation` para que, después de una re-ejecución exitosa de una herramienta que requería confirmación (como `file_update_tool` o `advanced_file_editor`), se elimine el `ToolMessage` original de confirmación del historial de mensajes del agente. Esto evita que el LLM procese nuevamente la solicitud de confirmación y genere respuestas redundantes.
---
## 01-11-25 Mejora en la Visualización del Diff en Confirmaciones de Actualización
Descripción general: Se mejoró la visualización del `diff` en las confirmaciones de actualización de archivos, asegurando que se muestre dentro de un bloque de código Markdown para una mejor legibilidad.

- **Punto 1**: En `kogniterm/core/agents/bash_agent.py`, se modificó la función `execute_tool_node` para que, cuando una herramienta requiera confirmación y proporcione un `diff`, este se envuelva en un bloque de código Markdown (````diff
...
````) antes de ser añadido al `ToolMessage`. Esto asegura que la interfaz de usuario lo renderice correctamente.
---
## 01-11-25 Corrección de Panel de Confirmación Vacío
Descripción general: Se solucionó la aparición de un panel de confirmación vacío debajo del panel principal, asegurando que el estado del agente se limpie completamente después de procesar una confirmación.

- **Punto 1**: En `kogniterm/core/agents/bash_agent.py`, se modificó la función `handle_tool_confirmation` para resetear `state.file_update_diff_pending_confirmation` y `state.command_to_confirm` a `None` inmediatamente después de procesar la confirmación (ya sea aprobada o denegada). Esto evita que la interfaz de usuario muestre un panel de confirmación adicional o vacío.
---
## 01-11-25 Instrucción al LLM para Confirmaciones de Actualización
Descripción general: Se añadió una instrucción explícita en el mensaje del sistema para asegurar que el LLM siempre solicite confirmación para las operaciones de actualización de archivos.

- **Punto 1**: En `kogniterm/core/agents/bash_agent.py`, se modificó el `SYSTEM_MESSAGE` para incluir una directriz clara y concisa que enfatiza la necesidad de solicitar confirmación para cualquier operación de modificación de archivos, especialmente aquellas que utilizan `advanced_file_editor` o `file_update_tool`.
---
## 01-11-25 Eliminación del Truncamiento de Salidas de Terminal
Descripción general: Se eliminó la lógica de truncamiento de las salidas de las herramientas en `execute_tool_node` para asegurar que el LLM siempre reciba la información completa de la terminal, evitando interrupciones o decisiones erróneas basadas en datos incompletos.

- **Punto 1**: En `kogniterm/core/agents/bash_agent.py`, se eliminó la lógica de truncamiento de `processed_tool_output` dentro de la función `execute_tool_node`, asegurando que la salida completa de la herramienta se añada al `ToolMessage`.
---
## 01-11-25 Mejora en la Visualización de Explicaciones de Comandos
Descripción general: Se mejoró la visualización de las explicaciones de comandos en el panel de confirmación, haciéndolas más concisas y evitando duplicaciones.

- **Punto 1**: En `kogniterm/core/agents/bash_agent.py`, se modificó la generación de `state.command_explanation` para que la explicación del comando sea más concisa.
- **Punto 2**: Se reforzó la instrucción en el `SYSTEM_MESSAGE` de `kogniterm/core/agents/bash_agent.py` para que el LLM evite generar explicaciones redundantes de comandos, especialmente cuando ya se muestran en el panel de confirmación.
---
## 01-11-25 Depuración del Truncamiento de Salidas de Terminal
Descripción general: Se añadieron prints de depuración para identificar el punto exacto donde se produce el truncamiento de las salidas de la terminal, y se eliminó un truncamiento residual en los mensajes de éxito.

- **Punto 1**: En `kogniterm/core/agents/bash_agent.py`, se eliminó el truncamiento en el `success_message` dentro de `handle_tool_confirmation`.
- **Punto 2**: Se añadió un `DEBUG` print en `handle_tool_confirmation` para mostrar la longitud de `tool_output_str`.
- **Punto 3**: Se añadió un `DEBUG` print en `execute_tool_node` para mostrar la longitud de `full_tool_output` antes de añadirlo al `ToolMessage`.
---
## 01-11-25 Depuración del Flujo de Comunicación del Agente
Descripción general: Se añadieron prints de depuración en puntos clave del flujo de comunicación del agente para rastrear el estado de los mensajes y las banderas de control, con el fin de identificar por qué el agente no procesa correctamente las salidas de los comandos.

- **Punto 1**: Se añadieron `DEBUG` prints en `handle_tool_confirmation` para rastrear el estado de `state.messages` y las banderas de control después de una re-ejecución exitosa.
- **Punto 2**: Se añadieron `DEBUG` prints en `should_continue` para mostrar los valores de `state.command_to_confirm`, `state.file_update_diff_pending_confirmation`, y `state.command_output_ready_for_processing`.
- **Punto 3**: Se añadieron `DEBUG` prints al inicio de `call_model_node` para mostrar el `last_message` y el valor de `state.command_output_ready_for_processing`.
---
## 01-11-25 Corrección del Flujo de Comunicación del Agente (Eliminación de AIMessage Intermedio)
Descripción general: Se corrigió el problema donde un `AIMessage` intermedio impedía que el LLM procesara correctamente la salida de los comandos, asegurando que el `ToolMessage` con la salida del comando sea el último mensaje relevante en el historial.

- **Punto 1**: En `kogniterm/core/agents/bash_agent.py`, se eliminó la adición del `AIMessage` que pre-procesaba la respuesta del LLM dentro del bloque `if state.command_output_ready_for_processing:` en la función `call_model_node`. Esto permite que el LLM procese directamente el `ToolMessage` con la salida del comando en su siguiente turno.
---
## 01-11-25 Mejora en la Visualización de Explicaciones de Comandos (Concisión)
Descripción general: Se hizo la explicación de comandos aún más concisa para evitar el truncamiento en la interfaz de usuario, dejando solo el comando en sí.

- **Punto 1**: En `kogniterm/core/agents/bash_agent.py`, se modificó la generación de `state.command_explanation` para que sea solo el comando en sí, sin ninguna frase introductoria.
---
## 01-11-25 Mejora en el Procesamiento de Salida de Comandos por el LLM
Descripción general: Se implementaron mejoras para asegurar que el LLM reconozca que un comando ya fue ejecutado y su salida procesada, evitando así la re-ejecución innecesaria y los bucles.

- **Punto 1**: Se modificó la `tool_confirmation_instruction` en `kogniterm/core/llm_service.py` para enfatizar explícitamente que, si un `ToolMessage` ya contiene la salida de un comando, el LLM debe considerarlo ejecutado y no proponerlo de nuevo.
- **Punto 2**: Se modificó la función `call_model_node` en `kogniterm/core/agents/bash_agent.py` para que, cuando `state.command_output_ready_for_processing` sea `True` y el último mensaje sea un `ToolMessage` (salida de un comando), se añada un `AIMessage` al historial que resuma la ejecución del comando y su salida. Esto proporciona al LLM una señal clara de que la acción ya se completó.
---
## 01-11-25 Corrección de Persistencia de Estado en call_model_node
Descripción general: Se corrigió un problema de persistencia de estado en `call_model_node` que impedía que los cambios en el `AgentState` se propagaran correctamente a través del grafo.

- **Punto 1**: Se modificó la línea de retorno de `call_model_node` en `kogniterm/core/agents/bash_agent.py` para que devuelva el objeto `state` completo en lugar de solo `{"messages": state.messages}`. Esto asegura que todos los cambios realizados en el objeto `state` dentro de `call_model_node` (incluido el reseteo de `command_output_ready_for_processing`) se persistan en el estado del grafo.
---
## 01-11-25 Corrección de IndentationError en bash_agent.py
Descripción general: Se corrigió un `IndentationError` en la función `call_model_node` de `kogniterm/core/agents/bash_agent.py` que impedía la ejecución de la aplicación.

- **Punto 1**: Se ajustó la indentación del bloque `else` y se movió la sentencia `return state` para que estuviera correctamente alineada con el bloque `if` principal, resolviendo el error de sintaxis.
---
## 01-11-25 Optimización del Truncamiento del Historial en LLMService
Descripción general: Se optimizó la lógica de truncamiento del historial de conversación en `LLMService` para mejorar la eficiencia y reducir el tiempo de respuesta del LLM.

- **Punto 1**: Se eliminó el método `_truncate_messages` de `kogniterm/core/llm_service.py` ya que no realizaba un truncamiento efectivo y su comentario era engañoso.
- **Punto 2**: Se optimizó el bucle de truncamiento dentro del método `invoke()` en `kogniterm/core/llm_service.py`. Ahora, el cálculo de la longitud total de los mensajes se realiza una vez y se actualiza de forma incremental al eliminar mensajes, evitando recálculos innecesarios en cada iteración.
---
## 01-11-25 Reversión de Optimización de Resumen en LLMService
Descripción general: Se revirtió el cambio de optimización del resumen en `LLMService` para restaurar el comportamiento anterior de generación de resúmenes más extensos.

- **Punto 1**: Se revirtió la modificación del `summarize_prompt` en `kogniterm/core/llm_service.py` a su estado original, pidiendo un resumen "EXTENSO y DETALLADO" con un límite de 4000 caracteres.
---
## 01-11-25 Añadido de Debug Prints para Diagnóstico de LLM
Descripción general: Se añadieron prints de depuración en `LLMService` para diagnosticar por qué el LLM no está generando respuestas o procesando comandos como se espera.

- **Punto 1**: Se añadió un `logger.debug` print en `kogniterm/core/llm_service.py` justo antes de la llamada a `completion` para mostrar los `litellm_messages` y `completion_kwargs` que se están enviando al LLM. Esto ayudará a entender el contexto que recibe el LLM y sus parámetros de invocación.
---
## 01-11-25 Corrección de Flujo del Agente para HumanMessage
Descripción general: Se corrigió el flujo del agente para asegurar que el LLM siempre procese los `HumanMessage` y tenga la oportunidad de generar una respuesta o una llamada a herramienta.

- **Punto 1**: Se modificó la función `should_continue` en `kogniterm/core/agents/bash_agent.py` para que, si el último mensaje en el historial es un `HumanMessage`, el grafo siempre devuelva `"call_model"`. Esto asegura que el LLM reciba la entrada del usuario y pueda actuar en consecuencia.
---
## 01-11-25 Corrección de Duplicación de Explicaciones en Panel de Confirmación
Descripción general: Se corrigió la duplicación de explicaciones de comandos en el panel de confirmación, donde la explicación aparecía cortada y duplicada. El problema estaba en la acumulación de contenido del generador de explicación en `command_approval_handler.py`.

- **Punto 1**: Se modificó el bucle de iteración sobre `explanation_response_generator` en `kogniterm/terminal/command_approval_handler.py` para no añadir el contenido del `AIMessage` al `full_response_content`, ya que este ya se acumula con los chunks de texto. Esto evita la duplicación de la explicación.
- **Punto 2**: Se verificó que no hay problemas de corte en el panel de confirmación, ya que el panel usa `soft_wrap=True` y `overflow="fold"`, lo que permite que el texto se ajuste correctamente sin cortes.
---
---
## 01-11-25 Corrección de Explicación de Comando Mostrando Solo Primera Línea
Descripción general: Se corrigió el problema donde la explicación de comandos en el panel de confirmación solo mostraba la primera línea, truncando el resto del contenido. El problema estaba en cómo se acumulaba el contenido del generador de explicación en `command_approval_handler.py`.

- **Punto 1**: Se modificó el bucle de iteración sobre `explanation_response_generator` para que, cuando se recibe un `AIMessage`, se tome directamente su contenido completo (que ya incluye todos los chunks acumulados) y se salga del bucle, evitando la acumulación parcial de chunks que causaba el truncamiento.
---
---
## 01-11-25 Mejora del Prompt para Explicaciones de Comandos Más Concisas
Descripción general: Se mejoró el prompt utilizado para generar explicaciones de comandos en el panel de confirmación, haciendo que las explicaciones sean más directas y concisas, eliminando texto adicional innecesario.

- **Punto 1**: Se modificó el `explanation_prompt` en `kogniterm/terminal/command_approval_handler.py` para que sea más directo: "Explica brevemente qué hace el comando bash: `{command_to_execute}`. Responde solo con la explicación, sin mencionar el comando ni añadir texto adicional. Máximo 2 frases."
---
---
## 01-11-25 Corrección de Truncamiento de Texto en Panel de Confirmación
Descripción general: Se corrigió el problema de truncamiento de texto en el panel de confirmación, donde la explicación del comando no se mostraba completa. La solución consistió en pre-procesar el texto para que se ajuste al ancho de la terminal antes de renderizarlo en el panel.

- **Punto 1**: En `kogniterm/terminal/command_approval_handler.py`, se modificó la lógica de renderizado del panel. Ahora, el contenido Markdown se convierte a un objeto `Text` de `rich`, se trunca con `overflow="fold"` al ancho de la terminal (menos un margen) y luego se pasa al `Panel`. Esto asegura que el texto se ajuste correctamente sin ser cortado.
---
---
## 01-11-25 Corrección del Reconocimiento de Ejecución de Herramientas por el LLM
Descripción general: Se corrigió el problema donde el LLM no reconocía que la herramienta `execute_command` ya había sido ejecutada, intentando re-ejecutarla o generando respuestas inconsistentes. Se implementaron cambios en `execute_tool_node` y `execute_command_tool.py` para asegurar que el `ToolMessage` se añada correctamente al historial y que la salida incluya una indicación clara de ejecución exitosa.

- **Punto 1**: En `kogniterm/core/agents/bash_agent.py`, se modificó `execute_tool_node` para asegurar que el `ToolMessage` con la salida completa de la herramienta se añada al historial para todas las herramientas, incluyendo `execute_command`, después de procesar la lógica de confirmación. Esto evita que el LLM no vea la salida en el historial.
- **Punto 2**: En `kogniterm/core/tools/execute_command_tool.py`, se añadió una línea al final del método `_run` para ceder un mensaje que indica que el comando se ejecutó exitosamente, proporcionando una señal clara al LLM de que la acción se completó.
---
## 02-11-25 Corrección del Bucle Infinito del LLM Después de Ejecutar Herramientas
Descripción general: Se corrigió el bucle infinito donde el LLM repetía "El agente continúa automáticamente..." y generaba explicaciones redundantes de comandos después de su ejecución. Se ajustó el flujo del grafo y la lógica de continuación para detener el bucle cuando el último mensaje es un ToolMessage o AIMessage sin tool_calls.

- **Punto 1**: En `kogniterm/core/agents/bash_agent.py`, se eliminó el `AIMessage` conciso que se añadía después de los `ToolMessage` en `execute_tool_node`, ya que contribuía al bucle.
- **Punto 2**: Se modificó `call_model_node` para evitar llamar al LLM si el último mensaje es un `ToolMessage`, previniendo bucles innecesarios.
- **Punto 3**: Se ajustó `should_continue` para terminar el grafo cuando el último mensaje es un `AIMessage` sin `tool_calls`.
- **Punto 4**: En `kogniterm/terminal/kogniterm_app.py`, se modificó el bucle de continuación automática para detenerse if the last message is a `ToolMessage` or an `AIMessage` without `tool_calls`.
- **Punto 5**: Se eliminó la invocación redundante del agente después de añadir el `ToolMessage` en el manejo de confirmaciones de comandos, dejando que el flujo automático lo procese.
---
---
## 02-11-25 Corrección de Duplicación de ToolMessages en el Historial del LLM
Descripción general: Se corrigió la duplicación de ToolMessages en el historial enviado al LLM, que causaba pérdida de contexto y respuestas inconsistentes. Se eliminaron ToolMessages huérfanos y se aseguró que el historial incluya al menos un HumanMessage para mantener el contexto completo.

- **Punto 1**: En `kogniterm/terminal/kogniterm_app.py`, se modificó el manejo de confirmaciones de comandos y archivos para eliminar el ToolMessage anterior de "requires_confirmation" antes de añadir el nuevo ToolMessage con la salida real, evitando duplicaciones.
- **Punto 2**: En `kogniterm/core/llm_service.py`, se modificó la lógica de truncamiento del historial para asegurar que siempre se incluya al menos un HumanMessage en el historial truncado, manteniendo el contexto completo para el LLM.
- **Punto 3**: En `kogniterm/terminal/command_approval_handler.py`, se restauró la impresión en tiempo real de la salida del comando durante la ejecución para mantener la visibilidad del usuario, ya que la eliminación previa causaba que la salida no se mostrara.
---
---
## 02-11-25 Refactorización de la Gestión del Historial y Corrección de Contexto del LLM
Descripción general: Se refactorizó la gestión del historial de conversación para centralizarlo en `AgentState`, eliminando la gestión duplicada en `LLMService` y asegurando que el `SYSTEM_MESSAGE` y los `AIMessage` se incluyan correctamente en el historial enviado al LLM. Esto resuelve los problemas de falta de contexto y duplicación de mensajes.

- **Punto 1**: En `kogniterm/core/llm_service.py`, se eliminó la gestión interna de `self.conversation_history`. Los métodos `_load_history` y `_save_history` se convirtieron en `@staticmethod` para ser utilizados por `AgentState`.
- **Punto 2**: En `kogniterm/core/agent_state.py`, se añadieron los métodos `load_history(system_message: SystemMessage)` y `save_history()`. `load_history` ahora asegura que el `SYSTEM_MESSAGE` esté siempre al principio del historial y maneja la deduplicación.
- **Punto 3**: En `kogniterm/terminal/kogniterm_app.py`, se modificó el `__init__` para llamar a `self.agent_state.load_history(SYSTEM_MESSAGE)` al inicio y `self.agent_state.save_history()` en el bloque `finally`. También se importó `SYSTEM_MESSAGE` de `kogniterm.core.agents.bash_agent`.
- **Punto 4**: En `kogniterm/terminal/kogniterm_app.py`, se eliminaron las asignaciones redundantes de `self.agent_state.messages = self.llm_service.conversation_history` que causaban duplicaciones.
- **Punto 5**: En `kogniterm/terminal/agent_interaction_manager.py`, se eliminó la lógica duplicada de añadir el `SYSTEM_MESSAGE` en `__init__` y se eliminó la actualización redundante del `agent_state.messages` con `llm_service.conversation_history`, ya que `AgentState` es ahora la fuente de verdad. Se aseguró que `self.agent_state.messages = final_state_dict['messages']` se realice después de cada invocación.
- **Punto 6**: En `kogniterm/core/agents/bash_agent.py`, `call_model_node` ahora pasa `state.messages` directamente a `llm_service.invoke`, ya que `AgentState` garantiza que el `SYSTEM_MESSAGE` esté presente.
- **Punto 7**: En `kogniterm/terminal/command_approval_handler.py`, se restauró la impresión en tiempo real de la salida del comando durante la ejecución para mantener la visibilidad del usuario.
---
## 02-11-25 Corrección de AttributeError en kogniterm/terminal/terminal.py
Descripción general: Se corrigió un `AttributeError` en `kogniterm/terminal/terminal.py` que ocurría porque la clase `AgentState` se importaba de una ubicación incorrecta, lo que resultaba en una instancia sin el método `load_history`.

- **Punto 1**: Se modificó la importación de `AgentState` en `kogniterm/terminal/terminal.py` de `from kogniterm.core.agents.bash_agent import AgentState` a `from kogniterm.core.agent_state import AgentState`. Esto asegura que la instancia de `AgentState` utilizada en `terminal.py` sea la que contiene el método `load_history`.
---
## 02-11-25 Corrección de AttributeError en kogniterm/core/llm_service.py
Descripción general: Se corrigió un `AttributeError: 'str' object has no attribute 'history_file_path'` en `kogniterm/core/llm_service.py` que ocurría porque los métodos `_load_history` y `_save_history` se estaban llamando como métodos estáticos pero no estaban definidos como tales, y esperaban una instancia `self`.

- **Punto 1**: Se añadieron los decoradores `@staticmethod` a los métodos `_load_history` y `_save_history` en `kogniterm/core/llm_service.py`.
- **Punto 2**: Se ajustaron las firmas de `_load_history` y `_save_history` para que aceptaran `history_file_path: str` como un argumento explícito, en lugar de depender de `self.history_file_path`.
- **Punto 3**: Se reemplazaron todas las ocurrencias de `self.history_file_path` dentro de `_load_history` y `_save_history` con el argumento `history_file_path`.
- **Punto 4**: Se modificó la llamada a `_load_history` en el constructor `__init__` de `LLMService` para que utilizara el método estático correctamente: `self.conversation_history = LLMService._load_history(self.history_file_path)`.
---
## 02-11-25 Corrección de TypeError en kogniterm/terminal/command_approval_handler.py
Descripción general: Se corrigió un `TypeError: LLMService._save_history() missing 1 required positional argument: 'history'` en `kogniterm/terminal/command_approval_handler.py` que ocurría porque la llamada al método estático `LLMService._save_history` no incluía todos los argumentos requeridos.

- **Punto 1**: Se modificó la llamada a `self.llm_service._save_history` en `kogniterm/terminal/command_approval_handler.py` para incluir `self.llm_service.history_file_path` como el primer argumento y `self.agent_state.messages` como el segundo, de acuerdo con la firma del método estático.
---
## 02-11-25 Corrección de la Coherencia del Historial y el Manejo de ToolMessages en LLMService
Descripción general: Se abordó el problema de la falta de correspondencia entre los `AIMessage` y `ToolMessage` en el historial, que podía llevar a un `APIConnectionError`. Se mejoró la lógica de resumen y truncamiento para garantizar que estos pares de mensajes se mantengan siempre juntos.

- **Punto 1**: En `kogniterm/core/llm_service.py`, se modificó la lógica dentro del bloque de resumen del historial para asegurar que los pares `AIMessage` con `tool_calls` y sus correspondientes `ToolMessage` se traten como una unidad indivisible durante el truncamiento. Esto evita que un `ToolMessage` se quede "huérfano" sin su `AIMessage` de origen.
- **Punto 2**: Se eliminó el truncamiento de `max_summary_length` para asegurar que el resumen sea lo más completo posible y se integre de forma coherente en el historial.
- **Punto 3**: Se ajustó la forma en que se construye el `new_conversation_history_litellm` para que el resumen se añada al principio, seguido por los mensajes conversacionales más recientes, manteniendo la coherencia del flujo.
- **Punto 4**: Se corrigió la llamada a `_save_history` dentro del bloque de resumen para usar `LLMService._save_history` como método estático, asegurando la consistencia con las refactorizaciones previ
---
## 02-11-25 Mejora en el Truncamiento de ToolMessages en LLMService
Descripción general: Se implementó un truncamiento explícito del contenido de los `ToolMessage` antes de enviarlos al LLM, para asegurar que el modelo pueda procesar salidas largas de comandos sin perder contexto debido a limitaciones de tokens.

- **Punto 1**: En `kogniterm/core/llm_service.py`, se añadió una lógica de truncamiento dentro del método `_to_litellm_message` para los mensajes de tipo `ToolMessage`. Si el contenido excede `self.MAX_TOOL_MESSAGE_CONTENT_LENGTH`, se trunca y se añade una indicación de que el contenido ha sido truncado.
---
## 02-11-25 Desactivación de Prints de Depuración en LLMService
Descripción general: Se reemplazaron los `print` de depuración directos con llamadas a `logger.debug` y `logger.warning` en `kogniterm/core/llm_service.py` para centralizar y controlar el nivel de logging de forma más efectiva.

- **Punto 1**: Se eliminaron los `print(f"DEBUG: ...")` directos relacionados con las credenciales de la API y la configuración de LiteLLM.
- **Punto 2**: Se cambiaron los `print(f"DEBUG: ...")` de carga y guardado de historial a `logger.debug`.
- **Punto 3**: Se cambió el `print(f"DEBUG: Rate limit hit...")` a `logger.debug`.
- **Punto 4**: Se cambiaron los `print("DEBUG: Interrupción detectada...")` y `print("DEBUG: Generación detenida...")` a `logger.debug`.
- **Punto 5**: Se cambiaron los `print(f"Error de LiteLLM: {e}")` a `logger.error`.
---
## 02-11-25 Desactivación de Prints de Depuración en BashAgent
Descripción general: Se reemplazaron los `console.print(f"DEBUG: ...")` directos con llamadas a `logger.debug` en `kogniterm/core/agents/bash_agent.py` para centralizar y controlar el nivel de logging de forma más efectiva.

- **Punto 1**: Se reemplazaron todas las ocurrencias de `console.print(f"DEBUG: ...")` con `logger.debug(f"...")` en las funciones `handle_tool_confirmation`, `call_model_node`, `execute_tool_node` y `should_continue`.