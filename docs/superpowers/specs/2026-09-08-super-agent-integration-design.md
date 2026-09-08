# Diseño de Integración: SuperAgent como Agente Principal en KogniTerm

**Fecha:** 2026-09-08  
**Rama:** `feature/super-agent-bridge`  
**Estado:** Propuesto  

---

## 1. Contexto y Objetivos

KogniTerm cuenta con un submódulo experimental [`kogniterm/core/ai_cli_bridge`](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/ai_cli_bridge) diseñado con el propósito de:
- **Reducir drásticamente la latencia**: Ejecución directa sobre `litellm.acompletion` con streaming de fragmentos y razonamiento nativo (`thinking` / `reasoning`).
- **Simplificar la arquitectura**: Desacoplar la ejecución de grafos complejos (como LangGraph o nodos pesados) y utilizar un registro ágil de herramientas (`ToolRegistry` en [`kogniterm/capabilities/registry.py`](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/capabilities/registry.py)).

El objetivo de esta fase es promover a [`SuperAgent`](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/ai_cli_bridge/super_agent.py) como el agente principal en el flujo normal de la aplicación ([`AgentInteractionManager`](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/terminal/agent_interaction_manager.py)), sustituyendo a [`BashAgent`](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/agents/bash_agent.py), **sin eliminar código previo** para permitir reversibilidad y pruebas rigurosas en la rama `feature/super-agent-bridge`.

---

## 2. Diagnóstico del Estado Actual de `ai_cli_bridge`

### 2.1 Componentes Existentes
- **`ToolRegistryAdapter`**: Normaliza `default_tool_registry` para ejecutar herramientas directamente (`asyncio.to_thread` o corrutinas nativas) sin transformadores de LangChain.
- **`LLMBridge`**: Resuelve proveedores a través de `MultiProviderManager` (`gemini`, `ollama`, `kilocode`, `openrouter`), convierte esquemas de herramientas para LiteLLM y gestiona el streaming de respuestas y llamadas a funciones.
- **`SuperAgent`**: Encapsula `LLMBridge` y expone `execute_stream(task)` y `run(task)`.

### 2.2 Limitaciones a Corregir
1. **Bucle agéntico incompleto en `LLMBridge.chat`**: Actualmente, tras ejecutar las llamadas a herramientas emitidas en el primer turno, `LLMBridge` emite `done` y termina. No reinyecta las respuestas de las herramientas al LLM para que sintetice la respuesta final o encadene herramientas posteriores.
2. **Falta de soporte para conversaciones multi-turno**: `SuperAgent.execute_stream(task)` crea mensajes efímeros `[system, user]` para una sola tarea, perdiendo el historial acumulado en la sesión de terminal.
3. **Ausencia de contexto dinámico y prompt de sistema de KogniTerm**: Se utilizaba un mensaje de sistema fijo y mínimo (`"Eres KogniTerm en modo fast path..."`), ignorando las memorias de `.kogniterm/llm_context.md`, `.kogniterm/instructions.md` y el directorio de trabajo actual.
4. **Manejo de confirmaciones interactivas (Human-in-the-Loop)**: `SuperAgent` ejecutaba herramientas sin pausar para solicitar aprobación en comandos de consola (`execute_command`) o modificaciones de archivos con diff.

---

## 3. Arquitectura Propuesta

```
┌────────────────────────────────────────────────────────┐
│  KogniTermApp / TUI (tui_app.py) / CLI (cli.py)        │
└──────────────────────────┬─────────────────────────────┘
                           │ invoke_agent(user_input)
                           ▼
┌────────────────────────────────────────────────────────┐
│             AgentInteractionManager                    │
│  - Configuración: KOGNITERM_MAIN_AGENT="super_agent"  │
│  - Mantiene AgentState (historial de mensajes)         │
└──────────────────────────┬─────────────────────────────┘
                           │ .invoke(state)
                           ▼
┌────────────────────────────────────────────────────────┐
│                  SuperAgentRunner                      │
│  - Adaptador bidireccional LangChain ↔ LiteLLM Dicts   │
│  - Soporte de streaming en vivo hacia TerminalUI       │
│  - Intercepción de confirmaciones (Human-in-the-Loop)  │
│  - Verificación de sintaxis Python post-edición        │
└──────────────────────────┬─────────────────────────────┘
                           │ execute_stream(history)
                           ▼
┌────────────────────────────────────────────────────────┐
│                     SuperAgent                         │
│  - Bucle de control con historial de conversación     │
│  - Inyección de System Prompt dinámico                 │
└──────────────────────────┬─────────────────────────────┘
                           │ chat(messages) [while loop]
                           ▼
┌────────────────────────────────────────────────────────┐
│                     LLMBridge                          │
│  - Bucle iterativo de herramientas (hasta max_steps)  │
│  - MultiProviderManager (Ollama, Gemini, Kilocode, ...)│
│  - Streaming de Content, Reasoning y Tool events       │
└──────────────────────────┬─────────────────────────────┘
                           │ execute(tool_name, args)
                           ▼
┌────────────────────────────────────────────────────────┐
│                ToolRegistryAdapter                     │
│  - default_tool_registry (Capabilities nativas)        │
│  - Acceso a skills dinámicas (task_tracker, etc.)      │
└────────────────────────────────────────────────────────┘
```

---

## 4. Especificación Detallada de Componentes

### 4.1 Bucle Agéntico en `LLMBridge`
- Se introduce un bucle `while step_count < max_steps` (límite de 30 iteraciones) dentro de `LLMBridge.chat()`.
- En cada iteración:
  - Invoca `litellm.acompletion(stream=True)`.
  - Transmite deltas de texto, pensamiento (`reasoning_content` / `thinking`) y acumula llamadas a herramientas.
  - Si no hay `tool_calls`, concluye la respuesta y emite `{"type": "done", "content": accumulated_content}`.
  - Si hay `tool_calls`:
    - Emite `{"type": "tool_start", "name": t_name, "args": t_args}`.
    - Ejecuta las herramientas (respetando pausas si se requiere confirmación del usuario).
    - Agrega los resultados con rol `"tool"` a `messages`.
    - Itera de nuevo para que el LLM procese las salidas y decida si llamar a otra herramienta o finalizar.

### 4.2 Soporte Multi-Turno y Contexto en `SuperAgent`
- Se adapta `SuperAgent.execute_stream(task, messages=None, system_prompt=None)`:
  - Si se proporciona una lista previa de `messages`, se continúa la conversación.
  - Si se suministra un `system_prompt`, se establece o actualiza el mensaje de rol `"system"`.
  - Si se proporciona un nuevo `task`, se añade como `{"role": "user", "content": task}`.

### 4.3 `SuperAgentRunner` e Integración con `AgentInteractionManager`
- `SuperAgentRunner` encapsula la lógica para:
  1. Recibir `AgentState` con mensajes LangChain (`SystemMessage`, `HumanMessage`, `AIMessage`, `ToolMessage`).
  2. Mapearlos eficientemente a la estructura de diccionarios que consume LiteLLM.
  3. Ejecutar el generador `execute_stream` en el event loop asíncrono.
  4. Renderizar texto y pensamiento (`reasoning`) en tiempo real en `terminal_ui` (tanto para TUI como CLI).
  5. Manejar confirmaciones: Si `execute_command` o una edición de archivo requiere aprobación del usuario (según el estado de `command_approval_handler` o las reglas de confirmación), pausar el ciclo y retornar el diccionario de estado con `command_to_confirm` o `tool_pending_confirmation`.
  6. Al completarse la respuesta del modelo, convertir los nuevos mensajes a formato `AIMessage` / `ToolMessage` y sincronizarlos con `state.messages`.
  7. Ejecutar `verification_node` para validar la sintaxis de cualquier archivo Python modificado.

### 4.4 Coexistencia y Conmutación (Fallback)
- En [`kogniterm/terminal/agent_interaction_manager.py`](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/terminal/agent_interaction_manager.py):
  - Se añade un parámetro o bandera de entorno:
    ```python
    main_agent_type = os.environ.get("KOGNITERM_MAIN_AGENT", "super_agent").lower()
    if main_agent_type == "super_agent":
        self.active_agent_app = create_super_agent(...)
    else:
        self.active_agent_app = create_bash_agent(...)
    ```
  - Se conserva `self.bash_agent_app = create_bash_agent(...)` completamente disponible y sin modificaciones destructivas en [`kogniterm/core/agents/bash_agent.py`](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/agents/bash_agent.py).

---

## 5. Pruebas y Plan de Verificación

1. **Pruebas Unitarias de Componentes**:
   - `test_llm_bridge_loop.py`: Verificar que `LLMBridge.chat` realiza el bucle iterativo cuando el modelo emite `tool_calls`.
   - `test_super_agent_runner.py`: Verificar conversión bidireccional de `AgentState`, manejo de historial multi-turno y emisión de eventos.
   - `test_super_agent_confirmation.py`: Probar la interrupción y reanudación en confirmaciones de comandos y diffs.
2. **Pruebas de Regresión Existentes**:
   - Ejecución de la suite completa de tests de la aplicación con `pytest`.
3. **Verificación Manual en CLI y TUI**:
   - Probar consultas simples, ejecución de comandos bash, edición de archivos y streaming de pensamiento en `kogniterm` CLI y TUI.
