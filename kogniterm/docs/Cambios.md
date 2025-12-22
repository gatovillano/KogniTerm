
---

## 20-11-2025 Corrección de Error 'Missing corresponding tool call' en LiteLLM

Se ha solucionado un error crítico de conexión con la API (`litellm.APIConnectionError`) causado por inconsistencias en el historial de mensajes, específicamente la presencia de mensajes de herramientas (`ToolMessage`) huérfanos o desconectados de sus llamadas originales (`AIMessage`).

- **Punto 1**: Se mejoró la lógica de truncamiento en `kogniterm/core/history_manager.py` para agrupar atómicamente los mensajes del asistente y sus respuestas de herramientas correspondientes, evitando que se separen o eliminen parcialmente.
- **Punto 2**: Se endureció la validación en `_remove_orphan_tool_messages` (`history_manager.py`) para eliminar estrictamente cualquier mensaje de herramienta cuyo ID no coincida con una llamada válida en el historial, previniendo errores en la API.
- **Punto 3**: Se eliminó lógica redundante y potencialmente conflictiva de filtrado de huérfanos en `kogniterm/core/llm_service.py`, centralizando la responsabilidad en el `HistoryManager`.

---

## 20-12-2025 Implementación de Agentes Especializados (CodeAgent y ResearcherAgent)

Se han creado e integrado dos nuevos agentes especializados para potenciar las capacidades de KogniTerm en desarrollo e investigación de software, junto con una herramienta para invocarlos.

- **Punto 1**: Creación de `kogniterm/core/agents/code_agent.py`: Agente experto en código con enfoque "Trust but Verify", priorizando calidad y consistencia.
- **Punto 2**: Creación de `kogniterm/core/agents/researcher_agent.py`: Agente investigador que utiliza búsqueda vectorial (`codebase_search_tool`) y textual para comprensión profunda de arquitectura.
- **Punto 3**: Implementación de `kogniterm/core/tools/call_agent_tool.py`: Herramienta puente que permite delegar tareas a estos agentes especializados.
- **Punto 4**: Actualización de `kogniterm/core/tools/tool_manager.py`: Registro de la nueva herramienta y mejora en la inyección de dependencias (`terminal_ui`).
