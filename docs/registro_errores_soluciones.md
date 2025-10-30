## 29-09-25 - AttributeError: 'LLMService' object has no attribute 'history_file_path'

### Descripción del Error
El error `AttributeError: 'LLMService' object has no attribute 'history_file_path'` ocurría porque el atributo `self.history_file_path` no estaba siendo inicializado en el método `__init__` de la clase `LLMService` antes de ser utilizado en el método `_load_history`.

Además, se identificó que `self.console`, `self.max_history_messages` y `self.max_history_chars` también se utilizaban sin inicialización, lo que podría generar errores futuros. También se detectó una llamada duplicada a `self._load_history()` en `__init__`.

### Solución Propuesta
Se inicializaron los atributos `self.history_file_path`, `self.console`, `self.max_history_messages` y `self.max_history_chars` en el método `__init__` de la clase `LLMService`. Se eliminó la llamada duplicada a `self._load_history()`.

### Archivos Modificados
- `kogniterm/core/llm_service.py`

### Detalles de los Cambios
- En `kogniterm/core/llm_service.py`, dentro del método `__init__` de la clase `LLMService`:
    - Se añadió la línea `self.history_file_path = os.path.join(os.getcwd(), ".kogniterm", "history.json")` para inicializar la ruta del archivo de historial.
    - Se añadió la línea `self.console = None` para inicializar el atributo `console`.
    - Se añadió la línea `self.max_history_messages = 100` para inicializar el número máximo de mensajes en el historial.
    - Se añadió la línea `self.max_history_chars = 100000` para inicializar el número máximo de caracteres en el historial.
    - Se eliminó una de las dos llamadas a `self._load_history()` para evitar redundancia.
---
## 30-10-25 - litellm.APIConnectionError: Missing corresponding tool call for tool response message

### Descripción del Error
El error `litellm.APIConnectionError: Missing corresponding tool call for tool response message` ocurrió durante la ejecución de la herramienta `file_search`. Este error indica que el modelo no pudo encontrar una llamada a la herramienta correspondiente para el mensaje de respuesta que recibió, lo que sugiere un problema en la comunicación o el formato de los mensajes entre el modelo y las herramientas.

### Solución Propuesta
Se registrará este error para su seguimiento. La solución inmediata es investigar la causa raíz de por qué el modelo no está reconociendo la respuesta de la herramienta `file_search` y ajustar la lógica de manejo de herramientas o la configuración de `litellm` si es necesario.

### Archivos Modificados
- Ninguno directamente en esta fase, solo el registro de errores.

### Detalles de los Cambios
- Se añadió una nueva entrada en `docs/registro_errores_soluciones.md` para documentar este error.
