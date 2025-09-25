---
### 17-09-25: `APIConnectionError` con `JSONDecodeError` en Streaming

**Error:**
La aplicación falla con un `litellm.APIConnectionError` que contiene un `json.decoder.JSONDecodeError` con el mensaje `Expecting property name enclosed in double quotes: line 1 column 2 (char 1), Received chunk: {`. Esto ocurre durante el streaming de respuestas del LLM, específicamente al interactuar con modelos de Gemini/Vertex AI a través de LiteLLM.

**Causa Raíz:**
Este error indica que el proveedor del modelo (Gemini/Vertex AI) está enviando chunks de datos durante el streaming que no son JSON válidos, o que LiteLLM está interpretando incorrectamente estos chunks. El problema no reside en el código de `kogniterm`, sino en la comunicación entre LiteLLM y la API externa.

**Solución Propuesta:**
1.  **Manejo de Errores en `kogniterm`:** Se implementó un manejo de errores más específico en `LLMService.invoke` (`kogniterm/core/llm_service.py`) para capturar `litellm.exceptions.APIConnectionError` y mostrar un mensaje más amigable al usuario, sin romper la aplicación. Esto no soluciona la causa raíz del JSON mal formado, pero mejora la robustez de la aplicación.
2.  **Verificar Versión de LiteLLM:** Asegurarse de que se está utilizando la última versión de LiteLLM, ya que estos errores de parsing a menudo se corrigen en nuevas versiones.
3.  **Reportar a LiteLLM/Proveedor:** Si el problema persiste con la última versión de LiteLLM, se recomienda reportarlo a los desarrolladores de LiteLLM o al soporte de Google/Vertex AI para que investiguen por qué están enviando chunks mal formados.

---
## 24-09-2025 Solución a NameError: name 'tempfile' is not defined en ignore_pattern_manager.py

**Descripción del error:** Al refactorizar la creación y gestión del archivo temporal en `ignore_pattern_manager.py` para usar `tempfile`, se introdujo un `NameError` porque el módulo `tempfile` no estaba importado.

**Solución propuesta:**
Se añadió la línea `import tempfile` al inicio de `kogniterm/core/context/ignore_pattern_manager.py`.

**Resultado:** El `NameError` ha sido resuelto, permitiendo que la lógica de manejo de archivos temporales funcione correctamente.

---
## 24-09-2025 Solución a TypeError: object of type 'KeyBindings' has no len() en kogniterm_app.py

**Descripción del error:** Al intentar combinar múltiples objetos `KeyBindings` en `kogniterm/terminal/kogniterm_app.py` usando el método `add()` de `KeyBindings`, se produjo un `TypeError` (`object of type 'KeyBindings' has no len()`). Esto se debe a que el método `add()` espera secuencias de teclas (cadenas), no otros objetos `KeyBindings`.

**Solución propuesta:**
Se corrigió la combinación de `KeyBindings` utilizando el operador `+` (que es el método correcto para combinar objetos `KeyBindings` en `prompt_toolkit`) en lugar del método `add()`.

**Resultado:** El `TypeError` ha sido resuelto, permitiendo que los `KeyBindings` se combinen correctamente y la funcionalidad de interrupción por `Esc` funcione como se espera.

---
## 24-09-2025 Solución a TypeError: unsupported operand type(s) for +: 'KeyBindings' and 'KeyBindings' en kogniterm_app.py

**Descripción del error:** Al intentar combinar múltiples objetos `KeyBindings` en `kogniterm/terminal/kogniterm_app.py` utilizando el operador `+`, se produjo un `TypeError` (`unsupported operand type(s) for +: 'KeyBindings' and 'KeyBindings'`). Esto se debe a que el operador `+` no es el método correcto para combinar objetos `KeyBindings` en `prompt_toolkit`.

**Solución propuesta:**
Se corrigió la combinación de `KeyBindings` utilizando la función `merge_key_bindings` de `prompt_toolkit.key_binding.key_bindings`, que es el método adecuado para esta tarea.

**Resultado:** El `TypeError` ha sido resuelto, permitiendo que los `KeyBindings` se combinen correctamente y la funcionalidad de interrupción por `Esc` funcione como se espera.
