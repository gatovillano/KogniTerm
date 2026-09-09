# Auto Thread Naming on Chat Start Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Nombrar automáticamente los hilos de chat con un título preliminar inmediato y un título descriptivo generado por LLM en segundo plano al iniciar una conversación.

**Architecture:** 
Implementa un modelo híbrido en dos etapas: (1) Asignación inmediata de un título heurístico preliminar limpio desde el primer mensaje del usuario (0ms de latencia), y (2) Invocación asíncrona no bloqueante al LLM en segundo plano para refinar el título a una frase concisa (3-6 palabras), actualizando el hilo si el usuario no lo renombró manualmente. Corrige el bloqueo en `ThreadManager.generate_title_if_needed` para permitir la generación cuando `title_source in ("default", "fallback")` y requiere únicamente el mensaje inicial del usuario.

**Tech Stack:** Python 3.12, LangChain Core messages (`HumanMessage`, `AIMessage`), LiteLLM / MultiProviderManager, asyncio, pytest.

## Global Constraints
- No romper retrocompatibilidad de metadatos existentes en `.kogniterm/threads/`.
- No alterar hilos donde `title_source == "manual"`.
- Operaciones de I/O de archivos deben ser atómicas (`.tmp` + `os.replace`).
- La llamada al LLM para generar títulos debe ser no bloqueante y nunca debe propagar excepciones que interfieran con el chat.

---

### Task 1: ChatThread Data Model and ThreadManager `_fallback_title` Heuristics

**Files:**
- Modify: `kogniterm/core/chat_thread.py:20-25`
- Modify: `kogniterm/core/thread_manager.py:600-608`
- Test: `tests/unit/test_thread_manager.py`

**Interfaces:**
- Produces: `ChatThread.title_source` defaulting to `"default"`.
- Produces: `ThreadManager._fallback_title(first_user_message: str) -> str` returning sanitized, capitalized title without greetings, markdown or punctuation.

- [ ] **Step 1: Write failing unit tests for `_fallback_title` and default `title_source`**

Add tests to `tests/unit/test_thread_manager.py`:
```python
def test_chat_thread_default_title_source():
    from kogniterm.core.chat_thread import ChatThread
    thread = ChatThread()
    assert thread.title_source == "default"


def test_thread_manager_fallback_title_cleaning():
    from kogniterm.core.thread_manager import ThreadManager

    # Saludos iniciales removidos
    assert ThreadManager._fallback_title("Hola, necesito crear un script de bash") == "Crear un script de bash"
    assert ThreadManager._fallback_title("Buenas! Podrías ayudarme a refactorizar el código?") == "Refactorizar el código"
    assert ThreadManager._fallback_title("Hello, please fix the database query") == "Fix the database query"

    # Markdown y código
    assert ThreadManager._fallback_title("```python\ndef test(): pass\n```") == "Código python"
    assert ThreadManager._fallback_title("Revisa https://github.com/repo y dime qué opinas") == "Revisa y dime qué opinas"

    # Mensajes cortos o vacíos
    assert ThreadManager._fallback_title("") == "Nueva conversación"
    assert ThreadManager._fallback_title("   ") == "Nueva conversación"
    assert ThreadManager._fallback_title("hola") == "Nueva conversación"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_thread_manager.py -k "test_chat_thread_default_title_source or test_thread_manager_fallback_title_cleaning" -v`
Expected: FAIL (assertion errors on `title_source` and `_fallback_title`).

- [ ] **Step 3: Implement minimal changes in `chat_thread.py` and `thread_manager.py`**

In `kogniterm/core/chat_thread.py`:
Change `title_source: str = "manual"` to `title_source: str = "default"`.

In `kogniterm/core/thread_manager.py`:
Implement enhanced `_fallback_title(first_user_message: str) -> str` that:
1. Strips markdown code fences (```...```) or converts code snippets into generic label.
2. Removes URLs (http/https).
3. Strips punctuation and leading greetings ("hola", "buenas", "buenos días", "buenas tardes", "por favor", "puedes", "podrías", "ayúdame a", "hello", "hi", "please", "can you", "help me").
4. Takes first 5-7 meaningful words (max 50 chars).
5. Capitalizes the result. If empty or generic, returns `"Nueva conversación"`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/test_thread_manager.py -k "test_chat_thread_default_title_source or test_thread_manager_fallback_title_cleaning" -v`
Expected: PASS.

- [ ] **Step 5: Commit changes**

```bash
git add kogniterm/core/chat_thread.py kogniterm/core/thread_manager.py tests/unit/test_thread_manager.py
git commit -m "feat(core): set default title_source to default and improve fallback title cleaning"
```

---

### Task 2: Refactor ThreadManager Title Generation (`generate_title_if_needed` and `_generate_title`)

**Files:**
- Modify: `kogniterm/core/thread_manager.py:448-535`
- Test: `tests/unit/test_thread_manager.py`

**Interfaces:**
- Consumes: `ChatThread.title_source`, `ThreadManager._fallback_title`
- Produces: `ThreadManager.generate_title_if_needed(thread_id, messages, llm_service) -> Optional[str]`
- Produces: `ThreadManager._generate_title(thread_id, messages, llm_service) -> Optional[str]`

- [ ] **Step 1: Write failing unit tests for title generation logic**

Add tests to `tests/unit/test_thread_manager.py`:
```python
import pytest
from unittest.mock import MagicMock, AsyncMock

@pytest.mark.asyncio
async def test_generate_title_if_needed_with_fallback_source(temp_workspace):
    tm = ThreadManager(workspace_dir=temp_workspace)
    thread = tm.create_thread(title="Script de bash")
    thread.title_source = "fallback"
    tm.save_thread(thread)

    mock_llm = MagicMock()
    tm._call_llm_for_title = AsyncMock(return_value="Automatización de scripts")

    # Requiere únicamente HumanMessage
    messages = [HumanMessage(content="Crea un script para backup")]
    new_title = await tm.generate_title_if_needed(thread.id, messages, mock_llm)

    assert new_title == "Automatización de scripts"
    updated = tm.get_thread(thread.id)
    assert updated.title == "Automatización de scripts"
    assert updated.title_source == "llm"


@pytest.mark.asyncio
async def test_generate_title_if_needed_ignores_manual_source(temp_workspace):
    tm = ThreadManager(workspace_dir=temp_workspace)
    thread = tm.create_thread(title="Mi Título Manual")
    thread.title_source = "manual"
    tm.save_thread(thread)

    mock_llm = MagicMock()
    tm._call_llm_for_title = AsyncMock(return_value="Otro título")

    messages = [HumanMessage(content="Crea un script")]
    new_title = await tm.generate_title_if_needed(thread.id, messages, mock_llm)

    assert new_title is None
    updated = tm.get_thread(thread.id)
    assert updated.title == "Mi Título Manual"
    assert updated.title_source == "manual"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_thread_manager.py -k "test_generate_title_if_needed" -v`
Expected: FAIL (fails because `title_source == "fallback"` currently returns `None`).

- [ ] **Step 3: Implement refactored title generation in `thread_manager.py`**

In `kogniterm/core/thread_manager.py`:
1. In `generate_title_if_needed`:
   - Check if `metadata.get("title_source") == "manual"` or `metadata.get("title_source") == "llm"`. If so, return `None`.
   - Allow generation if `title_source in ("default", "fallback", None)` or if `is_generic`.
   - Require only at least one `HumanMessage` with non-empty content (no longer require `AIMessage`).
2. In `_generate_title`:
   - Extract `human_msgs`. If none, return `None`.
   - Build prompt:
     ```python
     if ai_msgs:
         prompt = (
             "Genera un título conciso (máximo 4 a 6 palabras) para este tema de conversación. "
             "Solo responde con el título, sin comillas, markdown ni explicaciones.\n\n"
             f"Usuario: {human_msgs[0][:300]}\n"
             f"Asistente: {ai_msgs[0][:300]}"
         )
     else:
         prompt = (
             "Genera un título conciso (máximo 4 a 6 palabras) para una conversación que inicia con este mensaje. "
             "Solo responde con el título, sin comillas, markdown ni explicaciones.\n\n"
             f"Mensaje: {human_msgs[0][:300]}"
         )
     ```
   - Strip quotes, markdown, trailing dots and prefixes (`título:`, etc.).
   - Call `self.rename_thread(thread_id, title, source="llm")`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/test_thread_manager.py -k "test_generate_title_if_needed" -v`
Expected: PASS.

- [ ] **Step 5: Commit changes**

```bash
git add kogniterm/core/thread_manager.py tests/unit/test_thread_manager.py
git commit -m "feat(core): enable single-message auto-titling and allow fallback source in generate_title_if_needed"
```

---

### Task 3: Integrate Server Auto-Titling in `session_pool.py`

**Files:**
- Modify: `kogniterm/server/session_pool.py:1115-1160, 1340-1352`
- Test: `tests/unit/test_thread_manager.py`

**Interfaces:**
- Consumes: `ThreadManager._fallback_title`, `ThreadManager.generate_title_if_needed`, `AgentSession.ui._push`
- Produces: Immediate `thread_title_updated` event push + asynchronous `_try_generate_title` task at chat start.

- [ ] **Step 1: Write test for server session auto-naming flow**

Add test in `tests/unit/test_thread_manager.py`:
```python
@pytest.mark.asyncio
async def test_session_pool_auto_naming_trigger(temp_workspace):
    from kogniterm.server.session_pool import AgentSession
    from kogniterm.terminal.tui.tui_ui import TuiUI

    tm = ThreadManager(workspace_dir=temp_workspace)
    thread = tm.create_thread(thread_id="test-session-1")
    
    mock_llm = MagicMock()
    mock_llm.model_name = "test-model"
    tm._call_llm_for_title = AsyncMock(return_value="Título Generado por IA")

    session = AgentSession(session_id="test-session-1", workspace_dir=temp_workspace)
    session.thread_manager = tm
    session.llm_service = mock_llm

    # Simular ejecución de _try_generate_title
    await session._try_generate_title()

    updated = tm.get_thread("test-session-1")
    # Si no hay mensajes aún, no genera
    assert updated.title == "Nueva conversación"

    # Con mensaje de usuario
    from langchain_core.messages import HumanMessage
    session.agent_state.add_message(HumanMessage(content="¿Cómo configurar Nginx?"))
    await session._try_generate_title()

    updated = tm.get_thread("test-session-1")
    assert updated.title == "Título Generado por IA"
    assert updated.title_source == "llm"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_thread_manager.py -k "test_session_pool_auto_naming_trigger" -v`
Expected: Verify behavior or failure.

- [ ] **Step 3: Update `AgentSession.send` in `session_pool.py`**

In `kogniterm/server/session_pool.py`:
In `AgentSession.send`:
```python
            # Nombrado inmediato del hilo si aún no tiene título definitivo
            if self.thread_manager:
                try:
                    current = self.thread_manager.get_thread(self.session_id)
                    can_auto_title = current and (
                        current.title_source in ("default", "fallback", None)
                        or current.title in ("Nueva conversación", "Nueva Conversación", "Conversación sin título", "Conversación", self.session_id, "")
                    ) and current.title_source != "manual"
                    
                    if can_auto_title:
                        immediate_title = ThreadManager._fallback_title(message)
                        if immediate_title and immediate_title != "Nueva conversación":
                            self.thread_manager.rename_thread(
                                self.session_id, immediate_title, source="fallback"
                            )
                            self.ui._push(
                                "thread_title_updated",
                                {"thread_id": self.session_id, "title": immediate_title},
                            )
                        # Lanzar en segundo plano la generación con LLM de inmediato
                        asyncio.create_task(self._try_generate_title())
                except Exception as exc:
                    logger.debug(f"[Session:{self.session_id}] Error en auto-nombrado inicial: {exc}")
```
And in `_try_generate_title()`:
Ensure it verifies `thread.title_source != "manual"` before applying, and pushes `"thread_title_updated"`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/test_thread_manager.py -k "test_session_pool_auto_naming_trigger" -v`
Expected: PASS.

- [ ] **Step 5: Commit changes**

```bash
git add kogniterm/server/session_pool.py tests/unit/test_thread_manager.py
git commit -m "feat(server): trigger immediate fallback titling and parallel LLM titling on chat start"
```

---

### Task 4: Connect LLM Service and Auto-Titling in TUI

**Files:**
- Modify: `kogniterm/core/history_manager.py:201-208`
- Modify: `kogniterm/core/llm_service.py:341-347`
- Modify: `kogniterm/terminal/tui/tui_app.py:1053-1060, 2668-2671`
- Test: `tests/unit/test_thread_manager.py`

**Interfaces:**
- Consumes: `LLMService.set_thread_manager`, `HistoryManager.set_llm_service`
- Produces: Full wiring of `llm_service` in `HistoryManager` and immediate title fallback in TUI on first user message.

- [ ] **Step 1: Write test for HistoryManager LLMService wiring**

Add test in `tests/unit/test_thread_manager.py`:
```python
def test_llm_service_set_thread_manager_wires_llm_service():
    from kogniterm.core.llm_service import LLMService
    from kogniterm.core.thread_manager import ThreadManager
    from unittest.mock import MagicMock

    llm = LLMService(model_name="test-model")
    mock_tm = MagicMock()
    llm.set_thread_manager(mock_tm)

    assert llm.history_manager._thread_manager == mock_tm
    assert llm.history_manager._llm_service == llm
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_thread_manager.py -k "test_llm_service_set_thread_manager_wires_llm_service" -v`
Expected: FAIL (because `_llm_service` is currently not set).

- [ ] **Step 3: Implement wiring in `llm_service.py` and TUI integration in `tui_app.py`**

In `kogniterm/core/llm_service.py`:
```python
    def set_thread_manager(self, thread_manager) -> None:
        """Inyecta el ThreadManager en el HistoryManager."""
        if self.history_manager:
            self.history_manager.set_thread_manager(thread_manager)
            self.history_manager.set_llm_service(self)
```

In `kogniterm/terminal/tui/tui_app.py`:
In `process_agent_request`:
When adding the first user message, check if active thread in `self.thread_manager` has `title_source in ("default", "fallback", None)`:
If so, apply `_fallback_title(user_input)` with `source="fallback"`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/test_thread_manager.py -k "test_llm_service_set_thread_manager_wires_llm_service" -v`
Expected: PASS.

- [ ] **Step 5: Commit changes**

```bash
git add kogniterm/core/llm_service.py kogniterm/terminal/tui/tui_app.py tests/unit/test_thread_manager.py
git commit -m "feat(tui): wire llm_service to history_manager and enable auto-titling in TUI"
```

---

### Task 5: Full Test Suite Verification and Regression Run

**Files:**
- Test: `tests/unit/test_thread_manager.py`
- Test: full unit test suite

- [ ] **Step 1: Run all unit tests for thread management**

Run: `.venv/bin/pytest tests/unit/test_thread_manager.py -v`
Expected: ALL PASS.

- [ ] **Step 2: Run full unit test suite**

Run: `.venv/bin/pytest tests/unit/ -v`
Expected: Verify all tests pass or maintain existing passing state without regressions.

- [ ] **Step 3: Final commit and cleanup**

```bash
git commit --allow-empty -m "chore: verify auto-titling on chat start passes full test suite"
```
