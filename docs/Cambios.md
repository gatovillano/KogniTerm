---
## 17-09-2025 Corrección de Error "Missing corresponding tool call" en LiteLLM
**Descripción general:** Se corrigió el `APIConnectionError` (`Missing corresponding tool call for tool response message`) que ocurría al denegar la ejecución de un comando, especialmente con modelos de Google a través de LiteLLM.

-   **Punto 1**: Se modificó `CommandApprovalHandler` en `kogniterm/terminal/command_approval_handler.py` para que, al denegar un comando, se genere un `AIMessage` en lugar de un `ToolMessage`. Esto evita que LiteLLM busque un `tool_call` correspondiente que no existe en ese escenario.
-   **Punto 2**: Se reintrodujeron las líneas para guardar el historial y devolver el estado actualizado en `CommandApprovalHandler` que fueron eliminadas accidentalmente durante una refactorización previa.

---
## 18-09-2025 Corrección de SyntaxError en FileUpdateTool

**Descripción general:** Se corrigió un `SyntaxError` en la f-string de la herramienta `FileUpdateTool` que causaba un error de terminación de cadena.

-   **Punto 1**: Se modificó la línea 62 de [`kogniterm/core/tools/file_update_tool.py`](kogniterm/core/tools/file_update_tool.py:62) para asegurar que la f-string esté correctamente terminada, añadiendo `\n{colorized_diff_output}` dentro de la misma.
---
## 19-09-2025 Mejora de la Persistencia del Historial de Conversación

**Descripción general:** Se implementaron mejoras en el manejo del historial de conversación para asegurar su persistencia ante errores inesperados o cierres de la aplicación, evitando la pérdida de contexto.

-   **Manejo de Errores en Carga/Guardado ([`kogniterm/core/llm_service.py`](kogniterm/core/llm_service.py)):**
    -   Se añadió `traceback.print_exc()` en los bloques `except` de `_load_history` y `_save_history` para un registro más detallado de los errores de JSON y otras excepciones, facilitando la depuración sin alterar el comportamiento de retorno de historial vacío.
-   **Guardado Seguro al Salir ([`kogniterm/terminal/kogniterm_app.py`](kogniterm/terminal/kogniterm_app.py)):**
    -   Se implementó un bloque `finally` en el método `run()` de `KogniTermApp`. Esto garantiza que el historial (`self.llm_service._save_history(self.agent_state.messages)`) se guarde siempre antes de que la aplicación finalice, ya sea por una salida normal (ej. `Ctrl+D`), una `KeyboardInterrupt`, o cualquier excepción no manejada.
---
## 19-09-2025 Corrección de SyntaxError en KogniTermApp

**Descripción general:** Se corrigió un `SyntaxError` en el archivo [`kogniterm/terminal/kogniterm_app.py`](kogniterm/terminal/kogniterm_app.py) causado por un bloque `finally` mal posicionado.

-   **Reubicación de `finally`:** El bloque `finally` fue movido para envolver el bucle principal de la aplicación en el método `run()`, asegurando que el guardado del historial se ejecute correctamente al salir de la aplicación, independientemente de cómo termine la ejecución.
---
## 19-09-2025 Mejora de la Persistencia del Historial del LLM y Truncamiento con Resumen

**Descripción general:** Se implementaron mejoras en la persistencia del historial del LLM para soportar un historial por directorio de trabajo y se mejoró la estrategia de truncamiento para mantener un contexto más relevante.

-   **Persistencia por Directorio:**
    -   En [`kogniterm/core/llm_service.py`](kogniterm/core/llm_service.py), se eliminaron las constantes `KOGNITERM_DIR` y `HISTORY_FILE` y se introdujo `self.history_file_path` como atributo de instancia.
    -   Se añadió el método `set_cwd_for_history(cwd: str)` en `LLMService` para establecer dinámicamente la ruta del archivo de historial basado en el directorio de trabajo actual y cargar/inicializar el historial correspondiente.
    -   En [`kogniterm/terminal/kogniterm_app.py`](kogniterm/terminal/kogniterm_app.py), se modificó el método `run()` para llamar a `self.llm_service.set_cwd_for_history(cwd)` cada vez que el directorio de trabajo cambia, asegurando que el historial cargado sea el correcto para la sesión actual.
    -   Se ajustó la inicialización de `self.agent_state.messages` en `KogniTermApp` para que siempre apunte a `self.llm_service.conversation_history`, manteniendo la coherencia.
-   **Truncamiento Inteligente con Resumen:**
    -   En [`kogniterm/core/llm_service.py`](kogniterm/core/llm_service.py), se modificó el método `invoke` para que, antes de truncar el historial debido a límites de tamaño o mensajes, intente resumir la conversación utilizando `summarize_conversation_history()`. El resumen se inserta como un `SystemMessage` en el historial, manteniendo los mensajes más recientes para un contexto inmediato.
-   **Optimización del Guardado del Historial:**
    -   Se eliminó la llamada redundante a `self.llm_service._save_history(self.agent_state.messages)` de [`kogniterm/terminal/agent_interaction_manager.py`](kogniterm/terminal/agent_interaction_manager.py), ya que el guardado final y seguro se realiza en el bloque `finally` de `KogniTermApp.run()`.
---
## 19-09-2025 Corrección de "Missing corresponding tool call for tool response message" tras resumen de historial

**Descripción general:** Se abordó el error `litellm.APIConnectionError: Missing corresponding tool call for tool response message` que ocurría después del resumen del historial, causado por `ToolMessage`s huérfanos sin su `AIMessage` de invocación correspondiente.

-   **Filtrado de ToolMessages Huérfanos:**
    -   Se implementó una lógica de post-procesamiento en el método `invoke` de [`kogniterm/core/llm_service.py`](kogniterm/core/llm_service.py). Esta lógica identifica y elimina `ToolMessage`s del historial que no tienen un `AIMessage` previo que haya solicitado esa herramienta (`tool_call`) en el historial reducido. Esto asegura la integridad del historial para `litellm` y evita el error.
---
## 19-09-2025 Persistencia del Historial entre Sesiones
52 | 
53 | **Descripción general:** Se aseguró que el historial de conversación del LLM persista entre diferentes sesiones de la aplicación, cargando el historial al inicio para el directorio de trabajo actual.
54 | 
55 | -   **Carga de Historial al Inicio:**
56 |     -   En el constructor de `KogniTermApp` en [`kogniterm/terminal/kogniterm_app.py`](kogniterm/terminal/kogniterm_app.py), se añadió una llamada inicial a `self.llm_service.set_cwd_for_history(initial_cwd)` para cargar el historial específico del directorio de trabajo actual al iniciar la aplicación.
57 |     -   Se modificó la inicialización de `self.agent_state = AgentState(messages=self.llm_service.conversation_history)` para que el estado del agente comience con el historial cargado, garantizando la continuidad de la conversación.
58 |     -   Se eliminó la lógica de detección de cambio de directorio dentro del bucle `run()` de `KogniTermApp`, ya que la carga del historial ahora se maneja al inicio de la sesión para el directorio de trabajo actual.
---
## 19-09-2025 Ajuste de Frecuencia de Resumen del Historial

**Descripción general:** Se ajustaron los límites del historial para reducir la frecuencia de los resúmenes, permitiendo conversaciones más largas antes de que se active la lógica de resumen.

-   **Aumento de Límites de Historial:**
    -   En [`kogniterm/core/llm_service.py`](kogniterm/core/llm_service.py), se aumentaron los valores de `self.max_history_chars` de `60000` a `120000` y `self.max_history_messages` de `100` a `200`. Esto permite que el historial contenga más mensajes y caracteres antes de que se considere "demasiado largo" y se active el proceso de resumen.
---
## 19-09-2025 Mejora de la Calidad del Resumen del Historial

**Descripción general:** Se mejoró la calidad del resumen del historial, solicitando al modelo LLM un resumen más exhaustivo y detallado.

-   **Modificación del Prompt de Resumen:**
    -   En [`kogniterm/core/llm_service.py`](kogniterm/core/llm_service.py), se modificó el `summarize_prompt` en el método `summarize_conversation_history()` para incluir instrucciones más explícitas al LLM, solicitando un resumen "EXHAUSTIVA, DETALLADA y EXTENSA" que capture todos los puntos clave, decisiones tomadas, tareas pendientes y cualquier información relevante, actuando como un reemplazo fiel del historial para la comprensión futura del LLM.