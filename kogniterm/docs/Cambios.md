
---

## 20-11-2025 Corrección de Error 'Missing corresponding tool call' en LiteLLM

Se ha solucionado un error crítico de conexión con la API (`litellm.APIConnectionError`) causado por inconsistencias en el historial de mensajes, específicamente la presencia de mensajes de herramientas (`ToolMessage`) huérfanos o desconectados de sus llamadas originales (`AIMessage`).

- **Punto 1**: Se mejoró la lógica de truncamiento en `kogniterm/core/history_manager.py` para agrupar atómicamente los mensajes del asistente y sus respuestas de herramientas correspondientes, evitando que se separen o eliminen parcialmente.
- **Punto 2**: Se endureció la validación en `_remove_orphan_tool_messages` (`history_manager.py`) para eliminar estrictamente cualquier mensaje de herramienta cuyo ID no coincida con una llamada válida en el historial, previniendo errores en la API.
- **Punto 3**: Se eliminó lógica redundante y potencialmente conflictiva de filtrado de huérfanos en `kogniterm/core/llm_service.py`, centralizando la responsabilidad en el `HistoryManager`.
