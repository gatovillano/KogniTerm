
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

---

## 26-01-26 Mejora de Razonamiento y Capacidades de Agentes (CoT y Alcance Ampliado)

Se han implementado mejoras significativas en el razonamiento de los agentes mediante Chain of Thought (CoT), visualización en terminal, y se ha refinado/ampliado el alcance de los agentes de investigación según feedback del usuario.

- **Punto 1**: Implementación de Protocolo de Razonamiento (CoT) obligatorio con bloques `<thinking>` o `__THINKING__:` en `BashAgent`, `CodeAgent`, `CodeCrew` y `ResearcherCrew`.
- **Punto 2**: Mejora en `BashAgent` y `CodeAgent` para visualizar el proceso de pensamiento en la UI de terminal y detección de bucles infinitos en `CodeAgent`.
- **Punto 3**: Ampliación del alcance de `ResearcherCrew`: `CodebaseSpecialist` ahora es genérico para todo código, `DocumentationSpecialist` cubre documentos de negocio/cualitativos, y `WebResearcher` incluye datos cuantitativos/cualitativos.
- **Punto 4**: Refinamiento estricto de `GitHubResearcher` para priorizar búsqueda web previa y evitar clonación destructiva, usando herramientas de exploración remota.

---

## 01-02-2026 Fase 1: Mejoras Incrementales - Multi-Proveedor y Agentes Asíncronos

Se han implementado mejoras incrementales al sistema multi-proveedor y a los agentes asíncronos, enfocándose en robustez, métricas de rendimiento y operaciones I/O no bloqueantes.

### 1. Mejoras al Sistema Multi-Proveedor

- **Punto 1**: Creación de `kogniterm/core/multi_provider_manager.py`: Implementación de sistema de fallback automático entre múltiples proveedores de LLM (OpenRouter, Google, Anthropic, Cohere, OpenAI).
- **Punto 2**: Implementación de métricas de rendimiento detalladas: latencia, tasa de éxito, fallos consecutivos, y estados de salud (HEALTHY/DEGRADED/UNHEALTHY) para cada proveedor.
- **Punto 3**: Integración con `LLMService`: El servicio ahora utiliza `MultiProviderManager` para ejecutar solicitudes con fallback automático cuando un proveedor falla.
- **Punto 4**: Health checks automáticos al inicio y sistema de priorización de proveedores basado en configuración.
- **Punto 5**: Reportes de métricas visuales accesibles mediante `llm_service.print_provider_metrics()`.

### 2. Agentes Asíncronos Parciales

- **Punto 1**: Creación de `kogniterm/core/async_io_manager.py`: Sistema híbrido que permite operaciones I/O asíncronas manteniendo sincronía en estado compartido.
- **Punto 2**: Implementación de `AsyncIOManager`: Loop de eventos dedicado en hilo separado para ejecutar operaciones asíncronas sin bloquear el hilo principal.
- **Punto 3**: Implementación de `HybridStateManager`: Gestor de estado que protege operaciones de estado compartido con locks mientras permite I/O asíncrona.
- **Punto 4**: Actualización de agentes (`bash_agent.py`, `code_agent.py`, `researcher_agent.py`): Importación del sistema async y preparación para ejecución de herramientas en modo asíncrono.
- **Punto 5**: Patrón híbrido establecido: async para operaciones I/O (LLM calls, web requests, file operations), sync protegido para estado compartido (historial de mensajes, estado del agente).
