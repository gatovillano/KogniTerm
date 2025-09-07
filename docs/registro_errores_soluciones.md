# Registro de Errores y Soluciones

---

### 11-08-25: El intérprete intenta ejecutar el comando 'None'

**Error:**
Cuando el modelo de lenguaje devuelve una respuesta puramente conversacional (sin comandos), el sistema intenta ejecutar `None` como un comando de shell, lo que provoca el error: `/bin/sh: 1: None: not found`.

**Causa Raíz:**
En el archivo `gemini_interpreter/core/interpreter.py`, dentro del método `chat`, si no se detectaba un bloque de código en la respuesta del modelo, una variable que contenía el objeto `None` de Python era convertida a la cadena de texto `'None'` a través de `str(None)` justo en la sentencia `return`.

**Solución:**
Se modificó la sentencia `return` en el método `chat`. Se añadió una comprobación para que, si la variable del comando es `None`, se devuelva una cadena vacía (`""`) en su lugar. Esto previene que la cadena `'None'` sea pasada al motor de ejecución de comandos, solucionando el error de raíz.

---

### 11-08-25: Error de Límite de Cuota de API (Rate Limit)

**Error:**
La aplicación fallaba con un error `429 You exceeded your current quota` al realizar llamadas consecutivas y rápidas a la API de Gemini.

**Causa Raíz:**
El sistema carecía de un mecanismo para controlar la frecuencia de las peticiones a la API. Las interacciones rápidas y consecutivas del usuario provocaban que se superara el número de llamadas por minuto permitido por el plan de la API.

**Solución:**
Se implementó un mecanismo de enfriamiento (cooldown) en `gemini_interpreter/core/interpreter.py` para espaciar las llamadas a la API. Se añadieron las propiedades `last_call_time` y `cooldown_period` a la clase `Interpreter`. Antes de cada llamada, el sistema ahora comprueba si ha pasado el tiempo mínimo definido en `cooldown_period` y, si no es así, espera (`time.sleep()`) lo necesario para evitar superar el límite de la API.

---

### 11-08-25: `NameError: name 'time' is not defined`

**Error:**
La aplicación fallaba con un `NameError` indicando que el nombre `time` no estaba definido al intentar usar `time.monotonic()` en `interpreter.py`.

**Causa Raíz:**
El módulo `time` no había sido importado en el archivo `gemini_interpreter/core/interpreter.py`, a pesar de que el código intentaba utilizar funciones de este módulo para el mecanismo de enfriamiento. Esto pudo deberse a que una operación de reemplazo anterior no se aplicó correctamente.

**Solución:**
Se añadió la sentencia `import time` al inicio del archivo `gemini_interpreter/core/interpreter.py` para asegurar que el módulo `time` esté disponible antes de que sus funciones sean invocadas.

---

### 11-08-25: `AttributeError: 'Interpreter' object has no attribute 'last_call_time'`

**Error:**
La aplicación fallaba con un `AttributeError` indicando que el objeto `Interpreter` no tenía el atributo `last_call_time` al intentar acceder a él en el método `chat`.

**Causa Raíz:**
Los atributos `self.last_call_time` y `self.cooldown_period` no estaban siendo inicializados en el método `__init__` de la clase `Interpreter` en `gemini_interpreter/core/interpreter.py`, a pesar de que el código en el método `chat` intentaba acceder a ellos. Esto pudo deberse a que una operación de reemplazo anterior no se aplicó correctamente.

**Solución:**
Se añadieron las líneas de inicialización para `self.last_call_time` y `self.cooldown_period` en el método `__init__` de la clase `Interpreter` en `gemini_interpreter/core/interpreter.py`, asegurando que estos atributos existan antes de ser utilizados.

---

### 11-08-25: Ejecución Consecutiva de Comandos en Modo Directo

**Error:**
El agente Bash no podía ejecutar comandos consecutivos en un solo turno sin que el usuario solicitara explícitamente un "plan".

**Causa Raíz:**
La ruta de ejecución directa en `gemini_interpreter/terminal/terminal.py` solo invocaba la aplicación del agente Bash una vez por turno, limitando las operaciones a un solo paso.

**Solución:**
Se refactorizó el bloque `else` (ruta de ejecución directa) en `gemini_interpreter/terminal/terminal.py` para incluir un bucle `while`. Este bucle ahora invoca continuamente la aplicación del agente Bash hasta que el `execution_status` indique la finalización, el fallo o la cancelación, lo que permite la ejecución consecutiva de comandos sin necesidad de planificación explícita.

---

### 11-08-25: `SyntaxError: unterminated f-string literal` en `terminal.py`

**Error:**
La aplicación fallaba con un `SyntaxError` indicando una f-string no terminada en la línea 269 de `gemini_interpreter/terminal/terminal.py`.

**Causa Raíz:**
Durante una refactorización previa de `terminal.py`, la f-string utilizada para `summary_prompt` fue formateada incorrectamente, lo que llevó a un error de sintaxis. Esto se debió a un manejo inadecuado de las comillas y los saltos de línea dentro de la f-string.

**Solución:**
Se corrigió la f-string de `summary_prompt` en `gemini_interpreter/terminal/terminal.py` para utilizar comillas triples (`""") de forma adecuada, lo que permite un formato multilínea correcto y resuelve el `SyntaxError`. Se sobrescribió toda la función `start_terminal_interface` para asegurar la integridad estructural del archivo.

---

### 11-08-25: `AttributeError: 'dict' object has no attribute 'gemini_response_text'` en `terminal.py`

**Error:**
La aplicación fallaba con un `AttributeError` indicando que un objeto de tipo `dict` no tenía el atributo `gemini_response_text`. Esto ocurría porque el código intentaba acceder a las claves de un diccionario (`current_state`) usando la notación de punto (ej. `current_state.gemini_response_text`) en lugar de la notación de corchetes (ej. `current_state['gemini_response_text']`).

**Causa Raíz:**
El método `bash_agent_app.invoke()` devuelve un diccionario, pero el código en `terminal/terminal.py` esperaba un objeto con atributos, lo que llevó a un acceso incorrecto a los datos.

**Solución:**
Se modificaron todas las instancias en `gemini_interpreter/terminal/terminal.py` donde se accedía a las propiedades de `current_state` (y `final_state` en un caso) usando la notación de punto. Se reemplazó `current_state.<atributo>` por `current_state['<atributo>']` para asegurar un acceso correcto a los elementos del diccionario.

---

### 11-08-25: `AttributeError: 'dict' object has no attribute 'execution_status'` en `terminal.py`

**Error:**
La aplicación fallaba con un `AttributeError` indicando que un objeto de tipo `dict` no tenía el atributo `execution_status`. Esto ocurría porque el código intentaba acceder a las claves de un diccionario (`final_state`) usando la notación de punto (ej. `final_state.execution_status`) en lugar de la notación de corchetes (ej. `final_state['execution_status']`).

**Causa Raíz:**
El método `bash_agent_app.invoke()` devuelve un diccionario, pero el código en `terminal/terminal.py` esperaba un objeto con atributos, lo que llevó a un acceso incorrecto a los datos en el bloque de manejo de planes.

**Solución:**
Se modificaron todas las instancias en `gemini_interpreter/terminal/terminal.py` dentro del bloque `if user_input.lower().startswith("plan:")` donde se accedía a las propiedades de `final_state` (y `current_state` en el bucle de ejecución del plan) usando la notación de punto. Se reemplazó `final_state.<atributo>` por `final_state['<atributo>']` y `current_state.<atributo>` por `current_state['<atributo>']` para asegurar un acceso correcto a los elementos del diccionario.

---

### 11-08-25: `ValueError: Found edge ending at unknown node` en `bash_agent.py`

**Error:**
La aplicación fallaba con un `ValueError` indicando que se encontró un borde que terminaba en un nodo desconocido, específicamente `<function route_entry_point at 0x...>`.

**Causa Raíz:**
LangGraph espera que el punto de entrada sea el nombre de un nodo ya añadido al grafo, o un callable que sea un nodo en sí mismo. Al pasar la función `route_entry_point` directamente, el grafo no la reconocía como un nodo válido para establecer un borde.

**Solución:**
Se añadió explícitamente la función `route_entry_point` como un nodo al grafo (`workflow.add_node("route_entry_point", route_entry_point)`). Luego, se estableció este nodo como el punto de entrada utilizando su nombre (`workflow.set_entry_point("route_entry_point")`). Finalmente, se definieron los bordes condicionales desde este nuevo nodo de entrada para dirigir el flujo a los nodos `generate_initial_plan` o `call_model` según la lógica de enrutamiento.

---

### 11-08-25: El plan no se presenta para aprobación en `terminal.py`

**Error:**
Cuando el usuario solicitaba un plan (ej. `plan: ...`), el sistema no presentaba el plan para aprobación y no esperaba la entrada del usuario (s/n). En su lugar, el `final_state` devuelto por `bash_agent_app.invoke` tenía `plan_steps` vacío y `execution_status` como `finished`, lo que impedía que la lógica de presentación del plan en `terminal.py` se activara.

**Causa Raíz:**
La función `generate_initial_plan_node` en `bash_agent.py` estaba utilizando `plan_text` (la respuesta conversacional del LLM) para poblar `plan_steps`. Sin embargo, el LLM a menudo devolvía el comando sugerido en el `result` (la parte de la respuesta que contiene comandos o llamadas a herramientas), no en la `gemini_response_text` (la parte conversacional). Esto resultaba en un `plan_steps` vacío si el LLM solo sugería un comando.

**Solución:**
Se modificó la función `generate_initial_plan_node` en `bash_agent.py`. Ahora, después de intentar extraer los pasos del plan de la `gemini_response_text`, se verifica si `plan_steps` está vacío y si el `result` (comando sugerido) no está vacío. Si ambas condiciones son verdaderas, el `result` se añade como un único paso a `plan_steps`. Además, se asegura que el `gemini_response_text` también se propague en el estado de retorno para que el terminal pueda mostrar la respuesta conversacional del LLM.

---

### 22-08-25: Modelo genera `FunctionCall` con `name` vacío

**Error:**
El modelo Gemini, al intentar realizar una llamada a una herramienta (`FunctionCall`), genera un objeto donde el atributo `name` de la herramienta está presente pero su valor es una cadena vacía. Esto provoca un error en el intérprete al intentar procesar una herramienta sin nombre.

**Causa Raíz:**
Aunque las herramientas se declaran correctamente al modelo con sus nombres, el modelo, en ciertas circunstancias, no está rellenando el atributo `name` de la `FunctionCall` que devuelve. Esto puede ser un comportamiento inesperado del modelo o una desalineación interna en cómo interpreta las declaraciones de herramientas y genera las llamadas.

**Solución Propuesta:**
Se ha añadido una medida de robustez en `kogniterm/core/interpreter.py` para asegurar que el `tool_name` siempre sea tratado como una cadena, incluso si `tool_call.name` fuera `None`. Sin embargo, la causa raíz del problema reside en la generación del modelo, y esta solución es una mitigación. Se recomienda monitorear el comportamiento del modelo y, si el problema persiste, considerar reportarlo a los desarrolladores del modelo.

---
### 06-09-25: `SyntaxError: f-string: single '}' is not allowed` en `terminal.py`

**Error:**
La aplicación fallaba con un `SyntaxError` indicando `f-string: single '}' is not allowed` en la línea donde se intentaba imprimir el traceback de un error de Python en `kogniterm/terminal/terminal.py`.

**Causa Raíz:**
Durante la implementación de la visualización formateada de la salida de `python_executor`, se introdujo un error de sintaxis en un f-string. Específicamente, la expresión `{''}.join(item['traceback'])}` fue escrita incorrectamente como `{''}\n.join(item['traceback'])}`, lo que causó que el intérprete de Python detectara un cierre de llave (`}`) inesperado dentro del f-string.

**Solución:**
Se corrigió la sintaxis del f-string en `kogniterm/terminal/terminal.py`. La línea `console.print(f"[red]TRACEBACK:[/red]\n{''}\n.join(item['traceback'])}`")` fue reemplazada por `console.print(f"[red]TRACEBACK:[/red]\n{''.join(item['traceback'])}`")` para asegurar que la expresión `join` se evalúe correctamente dentro del f-string.
---
### 07-09-25: Error de API de Gemini: "400 Please ensure that function call turn comes immediately after a user turn or after a function response turn"

**Error:**
La aplicación fallaba con un error de la API de Gemini indicando que el turno de llamada a función no seguía inmediatamente a un turno de usuario o a un turno de respuesta de función. Esto ocurría después de una cierta cantidad de mensajes en la conversación.

**Causa Raíz:**
La causa principal fue una doble conversión y un manejo incorrecto del historial de mensajes entre el formato de LangChain y el formato esperado por la API de Gemini.
1.  La propiedad `history_for_api` en `kogniterm/core/agents/bash_agent.py` estaba convirtiendo los objetos `BaseMessage` de LangChain a un formato de diccionario, que luego era procesado nuevamente por la función `_to_gemini_content` en `kogniterm/core/llm_service.py`. Esto resultaba en que `_to_gemini_content` no recibía los tipos de objetos `BaseMessage` esperados, lo que llevaba a una interpretación incorrecta de los turnos de conversación.
2.  Adicionalmente, la función `_to_gemini_content` en `kogniterm/core/llm_service.py` tenía una lógica que trataba incorrectamente a los `HumanMessage` como respuestas de función si estos contenían un `tool_call_id`, lo cual es una desviación del uso estándar de los tipos de mensajes de LangChain (donde `ToolMessage` es el tipo correcto para respuestas de función).

**Solución:**
1.  Se modificó `kogniterm/core/agents/bash_agent.py`: La propiedad `history_for_api` ahora devuelve directamente la lista de objetos `BaseMessage` (`self.messages`), eliminando la doble conversión y asegurando que `_to_gemini_content` reciba los tipos de objetos correctos.
2.  Se modificó `kogniterm/core/llm_service.py`: La función `_to_gemini_content` fue ajustada para que los `HumanMessage` siempre sean tratados como mensajes de texto de usuario simples, eliminando la lógica que los convertía incorrectamente en respuestas de función. Esto garantiza que la secuencia de turnos de la API de Gemini se respete adecuadamente, donde un `HumanMessage` es un turno de usuario y un `ToolMessage` es una respuesta de función.
---
### 07-09-25: `ValueError: Tipo de mensaje desconocido: <class 'dict'>` en LLMService

**Error:**
La aplicación fallaba con un `ValueError` en `kogniterm/core/llm_service.py`, indicando que la función `_to_gemini_content` estaba recibiendo un objeto de tipo `dict` en lugar de un mensaje de LangChain (`BaseMessage`). Esto ocurría al intentar procesar el historial de la conversación.

**Causa Raíz:**
El problema se originó en la función `explain_command_node` dentro de `kogniterm/core/agents/bash_agent.py`. Al construir un historial temporal (`temp_history`) para una llamada al LLM, se estaba añadiendo un diccionario (`{'role': 'user', 'parts': [explanation_prompt]}`) directamente a esta lista. Aunque el resto del historial consistía en objetos `BaseMessage`, la presencia de este diccionario causaba que `llm_service.invoke` (y posteriormente `_to_gemini_content`) encontrara un tipo de mensaje inesperado, lo que resultaba en el `ValueError`.

**Solución:**
Se modificó `kogniterm/core/agents/bash_agent.py`: En la función `explain_command_node`, la línea que añadía el prompt de explicación al historial temporal fue cambiada para que, en lugar de un diccionario, se añada un objeto `HumanMessage` (`HumanMessage(content=explanation_prompt)`). Esto asegura que todos los elementos en el historial de mensajes sean instancias válidas de `BaseMessage` de LangChain, resolviendo así el `ValueError` y manteniendo la consistencia en el tipo de datos esperados por el servicio LLM.
