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