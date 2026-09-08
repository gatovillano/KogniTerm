# SuperAgent Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrar a `SuperAgent` (`ai_cli_bridge`) como el agente principal en el flujo de KogniTerm (`AgentInteractionManager`), reemplazando la ejecución de `BashAgent` para reducir latencia y simplificar la arquitectura, manteniendo `BashAgent` como opción de fallback sin borrar código.

**Architecture:** Se dota a `LLMBridge` de un bucle agéntico recursivo multi-paso; `SuperAgent` recibe soporte para historial multi-turno y memoria contextual; se implementa `SuperAgentRunner` para transformar bidireccionalmente el `AgentState` de KogniTerm y soportar renderizado en vivo y confirmaciones de usuario (Human-in-the-Loop); finalmente se conecta en `AgentInteractionManager` como agente activo predeterminado.

**Tech Stack:** Python 3.12+, LiteLLM, Asyncio, Pydantic, Rich, Pytest.

## Global Constraints

- No eliminar código existente en `bash_agent.py` ni romper compatibilidad con `AgentState`.
- Respetar la regla de pseudo-terminales sin eco (`##KOGNITERM_DONE_MARKER##`).
- Preservar el flujo de confirmación de seguridad para comandos bash y modificaciones de archivo con diff.
- Todo trabajo se realiza y valida en la rama `feature/super-agent-bridge`.

---

### Task 1: Bucle Agéntico Multi-Paso en `LLMBridge`

**Files:**
- Modify: `kogniterm/core/ai_cli_bridge/llm_bridge.py:89-211`
- Test: `tests/unit/test_llm_bridge_loop.py`

**Interfaces:**
- Consumes: `litellm.acompletion`, `ToolRegistryAdapter.execute`
- Produces: `LLMBridge.chat(messages, tools=None, max_steps=25) -> AsyncGenerator[Dict[str, Any], None]`

- [ ] **Step 1: Escribir el test unitario que falla para el bucle agéntico de LLMBridge**

```python
# tests/unit/test_llm_bridge_loop.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from kogniterm.core.ai_cli_bridge.llm_bridge import LLMBridge

@pytest.mark.asyncio
async def test_llm_bridge_executes_tools_and_loops_for_final_answer():
    bridge = LLMBridge(model="test-model")

    # Simular turno 1: modelo pide herramienta "read_file"
    chunk_t1_tc = MagicMock()
    tc1 = MagicMock()
    tc1.index = 0
    tc1.id = "call_123"
    tc1.function.name = "read_file"
    tc1.function.arguments = '{"path": "test.txt"}'
    chunk_t1_tc.choices = [MagicMock(delta=MagicMock(content=None, reasoning_content=None, thinking=None, reasoning=None, thinking_content=None, tool_calls=[tc1]))]

    # Simular turno 2: modelo genera la respuesta final basada en el resultado
    chunk_t2_text = MagicMock()
    chunk_t2_text.choices = [MagicMock(delta=MagicMock(content="El archivo contiene datos.", reasoning_content=None, thinking=None, reasoning=None, thinking_content=None, tool_calls=None))]

    async def mock_stream_turn1():
        yield chunk_t1_tc

    async def mock_stream_turn2():
        yield chunk_t2_text

    mock_acompletion = AsyncMock(side_effect=[mock_stream_turn1(), mock_stream_turn2()])

    with patch("litellm.acompletion", mock_acompletion), \
         patch.object(bridge, "execute_tool_call", AsyncMock(return_value="contenido de prueba")):
        
        messages = [{"role": "user", "content": "lee test.txt"}]
        events = []
        async for ev in bridge.chat(messages=messages, max_steps=5):
            events.append(ev)

        event_types = [e["type"] for e in events]
        assert "tool_start" in event_types
        assert "tool_result" in event_types
        assert "content" in event_types
        assert "done" in event_types

        # Verificar que acompletion fue llamado dos veces (bucle agéntico)
        assert mock_acompletion.call_count == 2
        # Verificar que el mensaje de tool fue agregado al historial
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        assert len(tool_msgs) == 1
        assert tool_msgs[0]["content"] == '"contenido de prueba"'
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `pytest tests/unit/test_llm_bridge_loop.py -v`  
Expected: FAIL porque `acompletion` solo se llama una vez y no existe el bucle agéntico.

- [ ] **Step 3: Implementar el bucle iterativo multi-paso en `LLMBridge.chat`**

Modificar `kogniterm/core/ai_cli_bridge/llm_bridge.py`:
Envolver la llamada a `litellm.acompletion` y el procesamiento de deltas en un ciclo `while step_count < max_steps:`. Si `not tool_calls_dict`, emitir `done` y salir. Si hay `tool_calls_dict`, ejecutar las herramientas, anexarlas con rol `"tool"` a `messages`, y continuar la siguiente iteración.

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `pytest tests/unit/test_llm_bridge_loop.py -v`  
Expected: PASS

- [ ] **Step 5: Commit de Task 1**

```bash
git add tests/unit/test_llm_bridge_loop.py kogniterm/core/ai_cli_bridge/llm_bridge.py
git commit -m "feat(ai_cli_bridge): implement multi-step agentic loop in LLMBridge"
```

---

### Task 2: Soporte Multi-Turno y Contexto en `SuperAgent`

**Files:**
- Modify: `kogniterm/core/ai_cli_bridge/super_agent.py:1-89`
- Test: `tests/unit/test_super_agent_multiturn.py`

**Interfaces:**
- Consumes: `LLMBridge.chat`
- Produces: `SuperAgent.execute_stream(task: Optional[str] = None, messages: Optional[List[Dict[str, Any]]] = None, system_prompt: Optional[str] = None, max_steps: int = 25) -> AsyncGenerator[Dict[str, Any], None]`

- [ ] **Step 1: Escribir test unitario para historial multi-turno y system prompt en SuperAgent**

```python
# tests/unit/test_super_agent_multiturn.py
import pytest
from unittest.mock import AsyncMock, patch
from kogniterm.core.ai_cli_bridge.super_agent import SuperAgent

@pytest.mark.asyncio
async def test_super_agent_preserves_multiturn_history():
    agent = SuperAgent(model="test-model")

    async def fake_chat(messages, tools=None, max_steps=25):
        yield {"type": "content", "text": "Respuesta al turno 2"}
        yield {"type": "done", "content": "Respuesta al turno 2"}

    with patch.object(agent.llm_bridge, "chat", side_effect=fake_chat):
        existing_history = [
            {"role": "system", "content": "Eres KogniTerm."},
            {"role": "user", "content": "Hola"},
            {"role": "assistant", "content": "Hola, ¿en qué ayudo?"}
        ]
        events = []
        async for ev in agent.execute_stream(task="¿Qué hora es?", messages=existing_history):
            events.append(ev)

        assert any(e.get("type") == "done" for e in events)
        # Verificar que el mensaje nuevo se añadió a la historia
        assert len(existing_history) == 4
        assert existing_history[-1]["content"] == "¿Qué hora es?"
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `pytest tests/unit/test_super_agent_multiturn.py -v`  
Expected: FAIL porque `execute_stream` solo toma `task: str` y sobrescribe `messages`.

- [ ] **Step 3: Modificar `SuperAgent` para soportar `messages`, `system_prompt` y streaming extendido**

Actualizar `kogniterm/core/ai_cli_bridge/super_agent.py`:
- Modificar firma de `execute_stream` a:
  ```python
  async def execute_stream(
      self,
      task: Optional[str] = None,
      messages: Optional[List[Dict[str, Any]]] = None,
      system_prompt: Optional[str] = None,
      max_steps: int = 25,
  ) -> AsyncGenerator[Dict[str, Any], None]:
  ```
- Inicializar o preservar `messages`.
- Inyectar o actualizar el mensaje `"system"` si se pasa `system_prompt`.
- Agregar `task` al historial como `"user"` si se proporciona.
- Capturar razonamiento (`reasoning`) y deltas de contenido.

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `pytest tests/unit/test_super_agent_multiturn.py -v`  
Expected: PASS

- [ ] **Step 5: Commit de Task 2**

```bash
git add tests/unit/test_super_agent_multiturn.py kogniterm/core/ai_cli_bridge/super_agent.py
git commit -m "feat(ai_cli_bridge): add multi-turn conversation and system prompt support to SuperAgent"
```

---

### Task 3: Adaptar `ToolRegistryAdapter` para Soporte Extendido de Herramientas y Confirmaciones

**Files:**
- Modify: `kogniterm/core/ai_cli_bridge/tool_registry_adapter.py:1-43`
- Test: `tests/unit/test_tool_adapter_extended.py`

**Interfaces:**
- Consumes: `default_tool_registry`, `LLMService` (opcional), `UserConfirmationRequired`
- Produces: `ToolRegistryAdapter.execute(name: str, args: Dict[str, Any], confirmation_callback=None)`

- [ ] **Step 1: Escribir test unitario para ToolRegistryAdapter con interceptor de confirmaciones**

```python
# tests/unit/test_tool_adapter_extended.py
import pytest
from unittest.mock import MagicMock
from kogniterm.core.ai_cli_bridge.tool_registry_adapter import ToolRegistryAdapter

@pytest.mark.asyncio
async def test_tool_registry_adapter_executes_registered_tool():
    adapter = ToolRegistryAdapter()
    result = await adapter.execute("read_file", {"path": "pyproject.toml", "limit": 1})
    assert isinstance(result, str) or isinstance(result, dict)

@pytest.mark.asyncio
async def test_tool_registry_adapter_unregistered_raises_key_error():
    adapter = ToolRegistryAdapter()
    with pytest.raises(KeyError):
        await adapter.execute("herramienta_inexistente", {})
```

- [ ] **Step 2: Ejecutar test para verificar comportamiento inicial**

Run: `pytest tests/unit/test_tool_adapter_extended.py -v`  
Expected: PASS o FAIL según disponibilidad.

- [ ] **Step 3: Enriquecer `ToolRegistryAdapter`**

Actualizar `kogniterm/core/ai_cli_bridge/tool_registry_adapter.py`:
- Añadir método `register_tool_provider(provider_fn)` o soporte para buscar herramientas en `SkillManager` / `LLMService` si no están en `default_tool_registry` (ej. `task_tracker`).
- Manejar la ejecución garantizando argumentos limpios y control de excepciones descriptivas.

- [ ] **Step 4: Ejecutar test para verificar**

Run: `pytest tests/unit/test_tool_adapter_extended.py -v`  
Expected: PASS

- [ ] **Step 5: Commit de Task 3**

```bash
git add tests/unit/test_tool_adapter_extended.py kogniterm/core/ai_cli_bridge/tool_registry_adapter.py
git commit -m "feat(ai_cli_bridge): enhance ToolRegistryAdapter with dynamic tool resolution"
```

---

### Task 4: Implementar `SuperAgentRunner`

**Files:**
- Create: `kogniterm/core/ai_cli_bridge/super_agent_runner.py`
- Modify: `kogniterm/core/ai_cli_bridge/__init__.py`
- Test: `tests/unit/test_super_agent_runner.py`

**Interfaces:**
- Consumes: `SuperAgent`, `AgentState`, `LLMService`, `TerminalUI`, `command_approval_handler`
- Produces: `SuperAgentRunner.invoke(state: AgentState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]`

- [ ] **Step 1: Escribir test unitario para `SuperAgentRunner.invoke`**

```python
# tests/unit/test_super_agent_runner.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from langchain_core.messages import HumanMessage, AIMessage
from kogniterm.core.agent_state import AgentState
from kogniterm.core.ai_cli_bridge.super_agent_runner import SuperAgentRunner, create_super_agent

def test_super_agent_runner_invoke_converts_messages_and_returns_dict():
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    runner = create_super_agent(llm_service=llm_service)

    state = AgentState(messages=[HumanMessage(content="Hola")])

    async def fake_stream(task=None, messages=None, system_prompt=None, max_steps=25):
        yield {"type": "content", "text": "¡Hola! ¿Cómo estás?"}
        yield {
            "type": "done",
            "output": "¡Hola! ¿Cómo estás?",
            "tools_used": [],
            "success": True,
            "error": None,
        }

    with patch.object(runner.agent, "execute_stream", side_effect=fake_stream):
        result = runner.invoke(state)
        assert "messages" in result
        assert len(result["messages"]) == 2
        assert isinstance(result["messages"][-1], AIMessage)
        assert result["messages"][-1].content == "¡Hola! ¿Cómo estás?"
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `pytest tests/unit/test_super_agent_runner.py -v`  
Expected: FAIL porque `super_agent_runner.py` aún no existe.

- [ ] **Step 3: Implementar `SuperAgentRunner`**

Crear `kogniterm/core/ai_cli_bridge/super_agent_runner.py`:
- Implementar clase `SuperAgentRunner` con `__init__(llm_service, terminal_ui, interrupt_queue, command_approval_handler)`.
- Mapeo de `AgentState.messages` (LangChain) a LiteLLM OpenAI dict format (`system`, `user`, `assistant`, `tool`).
- Construcción dinámica del `system_prompt` aprovechando `get_system_message` de KogniTerm y el directorio actual.
- Detección de herramientas que requieren confirmación (`execute_command` o modificaciones de archivo) para pausar la ejecución y devolver `command_to_confirm` / `tool_pending_confirmation`.
- Renderizado de streaming de razonamiento y texto en `terminal_ui` (tanto TUI como CLI).
- Verificación sintáctica con `verification_node`.
- Función factory `create_super_agent(...)`.

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `pytest tests/unit/test_super_agent_runner.py -v`  
Expected: PASS

- [ ] **Step 5: Commit de Task 4**

```bash
git add kogniterm/core/ai_cli_bridge/super_agent_runner.py tests/unit/test_super_agent_runner.py kogniterm/core/ai_cli_bridge/__init__.py
git commit -m "feat(ai_cli_bridge): implement SuperAgentRunner compatible with AgentInteractionManager"
```

---

### Task 5: Conectar `SuperAgent` en `AgentInteractionManager` como Agente Principal

**Files:**
- Modify: `kogniterm/terminal/agent_interaction_manager.py:27-58, 110-120`
- Test: `tests/unit/test_agent_interaction_super_agent.py`

**Interfaces:**
- Consumes: `create_super_agent`, `create_bash_agent`, `AgentInteractionManager`
- Produces: Inicialización dinámica de `active_agent_app` gobernada por `KOGNITERM_MAIN_AGENT` (por defecto `"super_agent"`).

- [ ] **Step 1: Escribir test unitario para AgentInteractionManager con SuperAgent**

```python
# tests/unit/test_agent_interaction_super_agent.py
import pytest
import os
from unittest.mock import MagicMock, patch
from kogniterm.terminal.agent_interaction_manager import AgentInteractionManager
from kogniterm.core.agent_state import AgentState

def test_agent_interaction_manager_defaults_to_super_agent():
    llm_service = MagicMock()
    terminal_ui = MagicMock()
    interrupt_queue = MagicMock()
    state = AgentState()

    with patch.dict(os.environ, {"KOGNITERM_MAIN_AGENT": "super_agent"}):
        aim = AgentInteractionManager(llm_service, state, terminal_ui, interrupt_queue)
        from kogniterm.core.ai_cli_bridge.super_agent_runner import SuperAgentRunner
        assert isinstance(aim.active_agent_app, SuperAgentRunner)
        # Verificar que bash_agent_app sigue existiendo como fallback
        assert hasattr(aim, "bash_agent_app")
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `pytest tests/unit/test_agent_interaction_super_agent.py -v`  
Expected: FAIL porque `aim.active_agent_app` no está implementado aún.

- [ ] **Step 3: Actualizar `AgentInteractionManager` para usar `active_agent_app`**

Modificar `kogniterm/terminal/agent_interaction_manager.py`:
- Importar `create_super_agent` de `kogniterm.core.ai_cli_bridge.super_agent_runner`.
- Crear `self.bash_agent_app = create_bash_agent(...)` (se conserva intacto).
- Crear `self.super_agent_app = create_super_agent(...)`.
- Definir `self.active_agent_app = self.super_agent_app` si `os.environ.get("KOGNITERM_MAIN_AGENT", "super_agent").lower() == "super_agent"`, o `self.bash_agent_app` en caso contrario.
- En `invoke_agent(...)`: invocar `self.active_agent_app.invoke(self.agent_state, ...)`.

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `pytest tests/unit/test_agent_interaction_super_agent.py -v`  
Expected: PASS

- [ ] **Step 5: Commit de Task 5**

```bash
git add kogniterm/terminal/agent_interaction_manager.py tests/unit/test_agent_interaction_super_agent.py
git commit -m "feat(terminal): integrate SuperAgent as default active agent in AgentInteractionManager"
```

---

### Task 6: Verificación Integral y Suite de Pruebas

**Files:**
- All modified and new files.

- [ ] **Step 1: Ejecutar la suite completa de pruebas unitarias**

Run: `pytest tests/unit/ -v`  
Expected: Todos los tests deben pasar sin regresiones.

- [ ] **Step 2: Probar ejecución en modo CLI no interactivo**

Run: `python3 -m kogniterm --help` y `python3 -c "import kogniterm.terminal.agent_interaction_manager; print('Import OK')"`  
Expected: Importaciones y ejecución de comandos limpias sin errores de sintaxis ni import loops.

- [ ] **Step 3: Documentar y confirmar commit final en la rama de pruebas**

```bash
git status
git log -n 5 --oneline
```
