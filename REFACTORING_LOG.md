# 📑 Reporte de Refactorización: Gemini-Interpreter Core
**Estado:** Fase 0 Completada | **Fecha:** 2025-05-22
**Responsable:** KogniTerm

## 🎯 Objetivo General
Eliminar la deuda técnica y la duplicación de código en la capa de agentes, desacoplando la lógica de ejecución de herramientas y llamadas al modelo para preparar el sistema hacia una arquitectura Cliente-Servidor.

---

## ✅ 1. Cambios Realizados (Fase 0: Migración de Agentes)

Se ha implementado una arquitectura de **Herencia y Delegación**. Se crearon dos pilares centrales: `BaseAgentNode` y `ToolExecutor`.

### 🛠️ Componentes Centralizados
- **`BaseAgentNode`**: Centraliza la lógica de `call_model`, la generación de mensajes de sistema y la gestión de prompts.
- **`ToolExecutor`**: Centraliza la ejecución de herramientas, el manejo de `ThreadPoolExecutor`, la gestión de excepciones de confirmación (`UserConfirmationRequired`) y la lógica de `should_continue`.

### 🤖 Agentes Refactorizados
Se procesaron los 4 agentes pesados, eliminando cientos de líneas de código redundante en cada uno:

| Agente | Acción Principal | Resultado |
| :--- | :--- | :--- |
| **Researcher** | Migración a `BaseAgentNode` | Código limpio, delegación total de herramientas. |
| **Code Agent** | Implementación de auto-aprobaciones | Preservada la validación de diffs, eliminada la lógica de hilos manual. |
| **Bash Agent** | Integración de `ToolExecutor` | Eliminada la complejidad de ejecución de shell manual; mantenida la carga dinámica de scripts. |
| **Deep Researcher** | Adaptación de `DeepResearchState` | Flujo de Plan $\rightarrow$ Research $\rightarrow$ Reflection $\rightarrow$ Synthesis ahora usa el núcleo centralizado. |

### 📈 Impacto Técnico
- **Reducción de Código**: Se eliminó la repetición de la lógica de `execute_tool_node` en 4 archivos diferentes.
- **Consistencia**: Todos los agentes ahora implementan el protocolo obligatorio de `task_tracker`.
- **Mantenibilidad**: Cualquier mejora en la ejecución de herramientas ahora se aplica a todos los agentes modificando un solo archivo (`tool_executor.py`).

---

## 🚀 2. Hoja de Ruta: Tareas Pendientes

### ⚡ Fase 1: Descomposición de `LLMService` (Prioridad Alta)
El `LLMService` es actualmente un monolito. Se debe fragmentar en:
- [ ] `provider_config.py`: Gestión de API Keys y configuraciones de modelos.
- [ ] `message_converter.py`: Transformación de mensajes entre formatos (LangChain $\leftrightarrow$ Gemini $\leftrightarrow$ OpenAI).
- [ ] `tool_parser.py`: Lógica de parseo y validación de llamadas a herramientas.
- [ ] `streaming_executor.py`: Manejo de flujos de respuesta en tiempo real.
- [ ] `fallback_handler.py`: Estrategias de reintento y modelos de respaldo.

### 🌐 Fase 2: Desacoplamiento Cliente-Servidor (Arquitectura)
1. **Capa de Interfaz (`kogniterm/ui/`)**: Mover todos los componentes de Rich y TUI a un módulo independiente.
2. **Implementación de API/WebSocket**: Crear un servidor que exponga la lógica de los agentes.
3. **Handshake de Seguridad**: Implementar el sistema de confirmaciones remotas para que la TUI pueda aprobar comandos ejecutados en el servidor.
4. **Sincronización de Estado**: Implementar la persistencia de `AgentState` en una base de datos o caché (Redis) para permitir reconexiones.

### 🧹 Fase 3: Limpieza y Optimización Final
- [ ] Refactorización de `ToolManager` para soportar carga dinámica desde el servidor.
- [ ] Actualización de `pyproject.toml` y `docker-compose.yml` para reflejar la nueva estructura de servicios.
- [ ] Auditoría de seguridad en la ejecución de comandos bash remotos.

---

## ⚠️ Notas para el Tester
Al probar los agentes, verificar específicamente:
1. Que el `task_tracker` se inicialice correctamente en el primer turno.
2. Que las herramientas que requieren confirmación sigan deteniendo el flujo y esperen la respuesta del usuario.
3. Que el `DeepResearcher` mantenga la coherencia de sus hallazgos (`findings`) a través de las iteraciones.
