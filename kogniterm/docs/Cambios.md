
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

---

## 01-05-2026 Refinamiento Estético de la Interfaz TUI

Se ha mejorado la coherencia visual del área de entrada de texto en la interfaz Textual (TUI) para evitar contrastes innecesarios y mejorar la legibilidad.

- **Punto 1**: Actualización de los estilos CSS en `kogniterm/terminal/tui/tui_app.py` para asegurar la transparencia total de `ChatInput`.
- **Punto 2**: Eliminación de colores de fondo redundantes en el input del splash screen para mantener la consistencia estética en toda la aplicación.
- **Punto 3**: Desactivación definitiva del resaltado de la línea del cursor (`show_cursor_line = False`), eliminando la franja horizontal que causaba el contraste visual en el área de escritura.
- **Punto 4**: Eliminación de temas personalizados en el `TextArea` para permitir que el fondo transparente funcione correctamente y coincida siempre con el contenedor.

---

## 07-05-2026 Mejora de Input Bar Extensible en TUI

Se modificaron los estilos en la interfaz TUI para permitir que la barra de entrada de texto (`ChatInput` y su contenedor `#input_container`) crezca automáticamente en altura a medida que se ingresa más texto, mejorando la experiencia de usuario con mensajes largos.

- **Punto 1**: Se actualizó `kogniterm/terminal/tui/tui_app.py` modificando el CSS para asignar `height: auto` a `#input_container` y `ChatInput`.
- **Punto 2**: Se definieron `max-height` y `min-height` en el contenedor para asegurar que la caja de texto no crezca desproporcionadamente.



---

## 02-02-2026 Corrección: Spinner infinito en DeepResearcher después de finalizar investigación

Se ha solucionado un bug visual en la TUI donde el spinner animado del `DeepResearcher` permanecía visible y animándose infinitamente después de que la investigación finalizaba.

- **Punto 1**: Identificación de la causa raíz en `kogniterm/terminal/tui/components/chat_log.py`: el método `stop_stream()` solo limpiaba la referencia `_active_message_widget` pero no eliminaba el widget `AnimatedSpinnerWidget` del DOM, dejando su timer de animación (`set_interval(0.1, self.tick)`) activo indefinidamente.
- **Punto 2**: Modificación de `ChatLogWidget.stop_stream()` para eliminar explícitamente el widget activo del DOM antes de poner la referencia a `None`, asegurando que el spinner se detenga completamente cuando finaliza el streaming.

---