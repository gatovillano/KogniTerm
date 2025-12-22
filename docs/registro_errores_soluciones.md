# Registro de Errores y Soluciones

## 20-12-2025 ValueError: "FileOperationsTool" object has no field "git_ignore_patterns"

**Error:** Al intentar iniciar la aplicación, Pydantic lanzaba un `ValueError` porque se intentaba asignar el atributo `git_ignore_patterns` a la clase `FileOperationsTool` (que hereda de `BaseTool`/Pydantic) sin haberlo definido como un campo del modelo.

**Causa:** Pydantic no permite la asignación de atributos arbitrarios en sus modelos a menos que se configure explícitamente o se usen atributos privados (empezando con `_`).

**Solución:** Se renombró el atributo `git_ignore_patterns` a `_git_ignore_patterns` en `kogniterm/core/tools/file_operations_tool.py` para que Pydantic lo ignore durante su validación interna de campos.

---

## 20-12-2025 litellm.exceptions.APIError: Upstream error from OpenInference

**Error:** Durante el streaming de una respuesta, OpenRouter devolvió un error de proveedor ("Upstream error from OpenInference"). Esto causó que KogniTerm imprimiera un traceback completo en la terminal y se quedara en un estado inconsistente.

**Causa:** Errores temporales en los proveedores de modelos externos que no estaban siendo capturados de forma amigable por el sistema de streaming.

**Solución:** Se mejoró el bloque `try-except` en `LLMService.invoke` para capturar errores de LiteLLM y proveedores. Ahora se muestra un mensaje amigable al usuario, se oculta el traceback técnico de la terminal principal (se mantiene en logs) y se asegura que la aplicación continúe funcionando.
