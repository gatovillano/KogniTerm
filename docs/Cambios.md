---
## 21-10-25 Implementación de Truncamiento de Salidas Extensas
Descripción general: Se implementó un mecanismo de truncamiento para manejar salidas extensas de comandos y herramientas, evitando el error `litellm.APIConnectionError` causado por el exceso de tokens.

- **Punto 1**: Se modificó `kogniterm/core/command_executor.py` para truncar la salida de los comandos de shell a 4000 caracteres.
    - Se añadió `MAX_OUTPUT_LENGTH = 4000` y `output_buffer = ""` al inicio del método `execute`.
    - Se implementó la lógica para acumular la salida en `output_buffer` y truncarla si excede `MAX_OUTPUT_LENGTH`, añadiendo un mensaje de advertencia.
    - Se aseguró que el contenido final de `output_buffer` se ceda al final de la ejecución del comando.
- **Punto 2**: Se modificó `kogniterm/core/llm_service.py` para truncar la salida de las herramientas a 3000 caracteres antes de enviarlas al LLM.
    - Se eliminó la función global `_to_litellm_message` duplicada.
    - Se añadió `self.max_tool_output_chars = 3000` al método `__init__` de la clase `LLMService`.
    - Se modificó el método `_to_litellm_message` dentro de la clase `LLMService` para truncar el `content` de los `ToolMessage` si excede `self.max_tool_output_chars`, añadiendo un mensaje de advertencia.
---
## 21-10-25 Corrección de NameError en LLMService
Descripción general: Se corrigió un `NameError` en la clase `LLMService` donde se intentaba llamar a la función `_to_litellm_message` como una función global después de haberla movido a un método de clase.

- **Punto 1**: Se reemplazaron todas las llamadas a `_to_litellm_message` por `self._to_litellm_message` dentro de la clase `LLMService` en `kogniterm/core/llm_service.py`. Esto incluyó las llamadas en el método `invoke` (para `workspace_context_message` y `litellm_conversation_history`) y en el método `summarize_conversation_history` (para `litellm_history_for_summary` y `litellm_messages_for_summary`).
---
## 21-10-25 Mejora en el Manejo de Salida de Brave Search
Descripción general: Se mejoró el manejo de la salida de la herramienta `brave_search` para formatear los resultados de manera más concisa, reduciendo la probabilidad de errores `litellm.APIConnectionError` con salidas extensas.

- **Punto 1**: Se modificó el método `_run` en `kogniterm/core/tools/brave_search_tool.py` para:
    - Parsear la cadena JSON de los resultados de Brave Search.
    - Limitar los resultados a los 3 primeros.
    - Extraer y formatear solo los campos relevantes (`title`, `link`, `snippet`) de cada resultado.
    - Unir los resultados formateados en una cadena de texto concisa.
    - Añadir manejo de errores para la decodificación JSON y otros errores inesperados.
---
## 21-10-25 Corrección de NameError en BraveSearchTool
Descripción general: Se corrigió un `NameError` en `kogniterm/core/tools/brave_search_tool.py` debido a la falta de importación del módulo `json`.

- **Punto 1**: Se añadió `import json` al principio del archivo `kogniterm/core/tools/brave_search_tool.py`.
---
## 21-10-25 Corrección de error "Missing corresponding tool call for tool response message" en LiteLLM
Descripción general: Se corrigió un error de `litellm.APIConnectionError` que se manifestaba como "Missing corresponding tool call for tool response message" al usar herramientas, como `brave_search`. Este error ocurría debido a que la lógica de truncamiento del historial de conversación podía separar un `AIMessage` con `tool_calls` de su `ToolMessage` correspondiente, lo que confundía a `litellm`.

- **Modificación de la lógica de historial**: Se ajustó la forma en que se construye el historial de mensajes para `litellm` en [`kogniterm/core/llm_service.py`](kogniterm/core/llm_service.py).
- **Ajuste de inserción de resumen**: Se modificó la inserción del resumen de la conversación y los mensajes de sistema para asegurar que las parejas de `AIMessage` y `ToolMessage` se mantengan adyacentes, evitando que el resumen se inserte entre ellos y cause el error de validación de `litellm`.
---
## 21-10-25 Workaround (revisado) para "Missing corresponding tool call for tool response message" en LiteLLM/Gemini
Descripción general: Se revisó el workaround en `kogniterm/core/llm_service.py` para mitigar el error `litellm.APIConnectionError` ("Missing corresponding tool call for tool response message") que ocurre con Gemini cuando el `ToolMessage` contiene `content` después de un `AIMessage` con `tool_calls`.

- **Punto 1**: Se modificó la lógica en el método `invoke` de `LLMService` para iterar sobre `litellm_messages` justo antes de la llamada a `completion`.
- **Punto 2**: Si se identifica un `ToolMessage` que sigue a un `AIMessage` con `tool_calls` (basado en `tool_call_id`), **ese `ToolMessage` se omite completamente del historial** para evitar el error de `litellm`.
---
## 22-10-25 Corrección de NameError en bash_agent.py
Descripción general: Se corrigió un `NameError` en `kogniterm/core/agents/bash_agent.py` debido a que la clase `LLMService` no estaba definida. Esto se solucionó importando `LLMService` desde `kogniterm/core/llm_service`.

- **Punto 1**: Se añadió la importación `from ..llm_service import LLMService` al archivo `kogniterm/core/agents/bash_agent.py` para asegurar que `LLMService` esté disponible cuando se defina la función `create_bash_agent`.
---
## 22-10-25 Solución de Importación Circular y Refactorización de AgentState
Descripción general: Se resolvió un problema de importación circular entre `bash_agent.py`, `llm_service.py` y `search_memory_tool.py` moviendo la clase `AgentState` a su propio módulo (`agent_state.py`) y actualizando las importaciones en los archivos afectados.

- **Punto 1**: Se movió la definición de la clase `AgentState` de `kogniterm/core/agents/bash_agent.py` a un nuevo archivo `kogniterm/core/agent_state.py`.
- **Punto 2**: Se actualizó `kogniterm/core/agents/bash_agent.py` para importar `AgentState` desde `kogniterm/core/agent_state.py` y se eliminó la importación directa de `LLMService` ya que se pasa como argumento.
- **Punto 3**: Se actualizó `kogniterm/core/tools/search_memory_tool.py` para importar `AgentState` desde `kogniterm/core/agent_state.py`.
---
## 22-10-25 Eliminación de Importación Redundante de LLMService en bash_agent.py
Descripción general: Se eliminó una importación redundante de `LLMService` en `kogniterm/core/agents/bash_agent.py` que contribuía a un problema de importación circular. `LLMService` se pasa como argumento a la función `create_bash_agent`, por lo que no necesita ser importado directamente en el módulo.

- **Punto 1**: Se eliminó la línea `from ..llm_service import LLMService` del archivo `kogniterm/core/agents/bash_agent.py`.
---
## 22-10-25 Corrección de NameError para LLMService en bash_agent.py
Descripción general: Se corrigió un `NameError` en `kogniterm/core/agents/bash_agent.py` al usar `LLMService` como anotación de tipo en la función `create_bash_agent`. Para evitar reintroducir un ciclo de importación, la anotación de tipo se cambió a una cadena de texto.

- **Punto 1**: Se modificó la anotación de tipo `LLMService` a `'LLMService'` en la definición de la función `create_bash_agent` en `kogniterm/core/agents/bash_agent.py`.
---
## 22-10-25 Corrección de ValidationError en SearchMemoryTool
Descripción general: Se resolvió un `ValidationError` en `SearchMemoryTool` causado por la inicialización incorrecta del campo `agent_state`. La solución implicó inicializar `AgentState` antes que `LLMService` y pasar la instancia de `AgentState` a `LLMService`, además de corregir la ruta de importación de `AgentState` en `kogniterm/terminal/terminal.py`.

- **Punto 1**: Se corrigió la importación de `AgentState` en `kogniterm/terminal/terminal.py` para que apunte a `kogniterm/core/agent_state.py`.
- **Punto 2**: Se modificó la función `_main_async` en `kogniterm/terminal/terminal.py` para inicializar `agent_state_instance` antes que `llm_service_instance`.
- **Punto 3**: Se pasó `agent_state_instance` como argumento a la inicialización de `LLMService`.
- **Punto 4**: Se actualizó `agent_state_instance.messages` con el historial de conversación cargado por `llm_service_instance` después de su inicialización.
---
## 22-10-25 Asegurar Inicialización de AgentState en LLMService
Descripción general: Se corrigió el `ValidationError` persistente en `SearchMemoryTool` asegurando que el `agent_state` siempre sea una instancia válida de `AgentState` al inicializar `LLMService`. Esto se logró importando `AgentState` en `llm_service.py` y creando una nueva instancia de `AgentState` si no se proporciona una al constructor de `LLMService`.

- **Punto 1**: Se añadió la importación `from ..agent_state import AgentState` al archivo `kogniterm/core/llm_service.py`.
- **Punto 2**: Se modificó el método `__init__` de `LLMService` para que, si `agent_state` es `None`, se cree una nueva instancia de `AgentState()` antes de pasarlo a `ToolManager`.
---
## 22-10-25 Manejo Robusto de args_schema en LLMService
Descripción general: Se corrigió un `AttributeError: 'NoneType' object has no attribute 'schema'` en `kogniterm/core/llm_service.py` que ocurría cuando una herramienta no tenía un `args_schema` definido o no exponía el método `schema()`. La solución asegura que la inicialización de `self.tool_schemas` sea más tolerante a estas situaciones.

- **Punto 1**: Se modificó la línea de inicialización de `self.tool_schemas` en el método `__init__` de la clase `LLMService` en `kogniterm/core/llm_service.py`.
- **Punto 2**: Se añadió una verificación `hasattr(tool, 'args_schema') and tool.args_schema and hasattr(tool.args_schema, 'schema')` para asegurar que solo se intente llamar a `.schema()` si `args_schema` existe y tiene ese método.
- **Punto 3**: Si `args_schema` es `None` o no tiene el método `schema()`, se utiliza un diccionario vacío (`{}`) como esquema de la herramienta, evitando así el `AttributeError`.
---
## 22-10-25 Corrección de NameError para KogniTermApp
Descripción general: Se corrigió un `NameError: name 'KogniTermApp' is not defined` en `kogniterm/terminal/terminal.py` que ocurría porque la clase `KogniTermApp` no había sido importada explícitamente antes de ser utilizada.

- **Punto 1**: Se añadió la importación `from .kogniterm_app import KogniTermApp` al archivo `kogniterm/terminal/terminal.py` para asegurar que la clase `KogniTermApp` esté disponible cuando se intente instanciarla.
---
## 22-10-25 Corrección de UnboundLocalError en LLMService
Descripción general: Se corrigió un `UnboundLocalError: cannot access local variable 'initial_system_messages' where it is not associated with a value` en `kogniterm/core/llm_service.py`. Este error ocurría porque la variable `initial_system_messages` no siempre se inicializaba en todos los caminos de ejecución de la función `invoke`.

- **Punto 1**: Se inicializó `initial_system_messages = []` al principio de la función `invoke` en `kogniterm/core/llm_service.py`.
- **Punto 2**: Se modificó la lógica para añadir mensajes a `initial_system_messages` cuando `workspace_context_message` o `system_message` están presentes, asegurando que la variable siempre tenga un valor asignado.
---
## 22-10-25 Implementación de Truncamiento en WebFetchTool
Descripción general: Se implementó una lógica de truncamiento en la herramienta `web_fetch` para limitar la longitud de la salida y evitar errores por contenido excesivamente extenso al interactuar con el LLM.

- **Punto 1**: Se modificó el método `_run` en `kogniterm/core/tools/web_fetch_tool.py`.
- **Punto 2**: Se definió una constante `MAX_OUTPUT_LENGTH` con un valor de 10000 caracteres.
- **Punto 3**: Se añadió una condición para verificar si la longitud del contenido obtenido excede `MAX_OUTPUT_LENGTH`. Si es así, el contenido se trunca y se añade un mensaje indicando que la salida ha sido truncada, junto con la longitud original.
---
## 22-10-25 Implementación de Truncamiento en CommandExecutor
Descripción general: Se implementó una lógica de truncamiento en la clase `CommandExecutor` para limitar la longitud de la salida de los comandos y evitar errores por contenido excesivamente extenso al interactuar con el LLM.

- **Punto 1**: Se modificó el método `execute` en `kogniterm/core/command_executor.py`.
- **Punto 2**: Se definió una constante `MAX_OUTPUT_LENGTH` con un valor de 4000 caracteres y se inicializó un `output_buffer` para acumular la salida.
- **Punto 3**: Se añadió una condición dentro del bucle de lectura de salida para verificar si la longitud del `output_buffer` más la nueva salida excede `MAX_OUTPUT_LENGTH`. Si es así, el contenido se trunca, se añade un mensaje indicando el truncamiento, se cede la salida truncada, se termina el proceso y se rompe el bucle.
- **Punto 4**: Se añadió una sección `finally` para ceder cualquier contenido restante en el `output_buffer` si el comando termina antes de alcanzar el límite de truncamiento.