# Especificación de Diseño: Recomendaciones de Evolución para KogniTerm

Este documento detalla el diseño de las cinco mejoras de evolución propuestas para robustecer la arquitectura, seguridad y analítica de **KogniTerm**, inspiradas en patrones declarativos de **KiloCode**.

---

## 1. Agentes Declarativos Basados en Configuración (Config-driven Agents)

### Objetivo
Permitir la definición de agentes especializados mediante archivos YAML y Markdown (con frontmatter) de forma externa, reduciendo el acoplamiento directo entre el código del grafo (`create_*_agent`) y la configuración del comportamiento (prompts del sistema, roles y herramientas permitidas).

### Diseño
*   **Búsqueda y Descubrimiento**: Se buscarán archivos `.yaml`, `.yml` y `.md` con prioridad descendente:
    1.  Workspace/Proyecto: `.agents/` (ej. `.agents/custom_agent.md`)
    2.  Configuración de usuario: `~/.kogniterm/agents/`
    3.  Defaults del sistema: `kogniterm/core/agents/config/`
*   **Formato de Configuración**:
    *   **YAML Frontmatter**: Define `name`, `description`, `role` (leaf | orchestrator), `allowed_tools` y opcionalmente `denied_tools`, `max_depth`, `max_concurrent_children`.
    *   **Cuerpo (Markdown)**: Si es un archivo Markdown, el cuerpo del documento representa el `system_prompt` del agente. Si es un archivo YAML, se lee el campo `system_prompt`.
*   **Clase `AgentConfigManager`**:
    *   Descubrimiento e indexación de archivos válidos en el inicio de la sesión.
    *   Expone `get_agent_config(agent_name: str) -> Optional[Dict[str, Any]]`.
*   **Ejecución Dinámica**:
    *   Las herramientas `call_agent` y `call_agents_parallel` resolverán el nombre del agente contra el manager de configuración.
    *   Si se encuentra, se compila un grafo dinámico usando `create_dynamic_agent` parametrizado con el `system_prompt`, las herramientas habilitadas y las restricciones del rol (LEAF / ORCHESTRATOR) especificadas.

---

## 2. Delegación Asíncrona Real (`AgentPool`)

### Objetivo
Sustituir la delegación secuencial y los bloques aninados por un gestor asíncrono formal (`AgentPool`) que ejecute los subgrafos en paralelo mediante llamadas concurrentes verdaderas (`ainvoke`) y control de semáforos, evitando el bloqueo del hilo principal de trabajo.

### Diseño
*   **Clase `AgentPool` (`kogniterm/core/delegation/agent_pool.py`)**:
    *   Administra la cola de ejecución asíncrona de subagentes.
    *   Controla la concurrencia máxima con un `asyncio.Semaphore`.
    *   Permite ejecutar simultáneamente $N$ tareas de agentes mediante `asyncio.gather`.
    *   Expone `execute_parallel(agents_specs: List[Dict[str, Any]]) -> List[Any]`.
*   **Integración**:
    *   Rediseñar la herramienta `call_agents_parallel` para registrar los contextos de delegación correspondientes y coordinar la ejecución a través de la clase `AgentPool`.

---

## 3. Permisos Granulares por Comando (allow/ask/deny)

### Objetivo
Establecer un mapeo declarativo que evalúe comandos bash contra reglas de expresiones regulares, permitiendo la auto-aprobación, la confirmación interactiva obligatoria o el bloqueo inmediato.

### Diseño
*   **Configuración (`command_rules.yaml`)**:
    *   Ubicaciones: `.agents/command_rules.yaml` (workspace) y `~/.kogniterm/command_rules.yaml` (usuario).
    *   Estructura:
        ```yaml
        rules:
          - pattern: "^git status$"
            action: "allow"
          - pattern: "^rm -rf .*$"
            action: "deny"
          - pattern: "^sudo .*$"
            action: "deny"
          - pattern: "^pip install .*$"
            action: "ask"
        ```
*   **Clase `CommandRulesResolver` (`kogniterm/core/delegation/command_rules.py`)**:
    *   Indexa e interpreta las reglas regex en orden secuencial.
    *   Evalúa el comando recibido y retorna la acción correspondiente (`allow`, `ask` o `deny`).
*   **Modificaciones en `CommandApprovalHandler`**:
    *   Llama a `CommandRulesResolver.resolve(command)` antes de pedir aprobación.
    *   Si es `deny`, cancela de inmediato y retorna un `ToolMessage` indicando la denegación por política, sin mostrar confirmaciones interactivas.
    *   Si es `allow`, establece `auto_approve = True` y ejecuta directamente.
    *   Si es `ask`, procede con la lógica interactiva por defecto.

---

## 4. Reducción de Acoplamiento (`AgentInteractionManager`)

### Objetivo
Crear una abstracción para `AgentInteractionManager` para que los componentes del núcleo (`kogniterm/core/` y `session_pool.py`) no importen directamente módulos del paquete de UI/Terminal.

### Diseño
*   **Abstracción (`kogniterm/core/agent_interaction.py`)**:
    *   `BaseAgentInteractionManager`: Clase base abstracta (ABC) con el método abstracto `invoke_agent`.
    *   `AgentInteractionRegistry`: Registro estático de factoría (`register_factory` / `create`).
*   **Desacoplamiento en `session_pool.py`**:
    *   Eliminar el import `from kogniterm.terminal.agent_interaction_manager import AgentInteractionManager`.
    *   Usar `AgentInteractionRegistry.create(...)` en su lugar.
*   **Inyección de la clase**:
    *   `kogniterm/terminal/agent_interaction_manager.py` heredará de `BaseAgentInteractionManager` y llamará a `AgentInteractionRegistry.register_factory` para autoregistrarse.
    *   El entrypoint del servidor (`app.py`) importará el módulo terminal al arrancar para activar el registro.

---

## 5. Telemetría de Sesión (`KiloSession`-like)

### Objetivo
Registrar y exportar de forma detallada y estructurada las trazas de delegación, conteo de tokens consumidos y estimación de costos asociados a la API por sesión.

### Diseño
*   **Ubicación de Salida**: Cada sesión genera un archivo en el workspace actual bajo `.kogniterm/telemetry/session_<id>.json`.
*   **Clase `TelemetryTracker` (`kogniterm/core/delegation/telemetry.py`)**:
    *   Campos: `session_id`, `start_time`, `total_duration`, `total_cost`, `total_tokens` (input/output).
    *   Estructuras internas: `llm_calls` (modelo, tokens, costo, timestamp) y `delegations` (subagente, tarea, profundidad, estado, entregable, duración).
*   **Estimación de Costos**:
    *   Se definirá una tabla de precios de referencia para los modelos principales (ej: Gemini, OpenAI, Antrophic) y se multiplicará por el número de tokens reportados en la respuesta de LLMService.
*   **Integración**:
    *   Registrar llamadas en `LLMService.invoke()` tras completar el streaming de un mensaje de IA.
    *   Registrar delegaciones en `call_agent_skill` y `call_agents_parallel` capturando inicio, fin, estado y el resultado final.
