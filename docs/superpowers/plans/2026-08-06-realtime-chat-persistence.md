# Realtime Chat Persistence & Live Streaming Re-attachment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist every chat message immediately to disk message-by-message and enable seamless live streaming re-attachment when switching threads in KogniTerm Desktop.

**Architecture:** In `AgentSession`, save human and AI messages immediately on creation to `ThreadManager` (`messages.json`), and store active streaming state (`current_thinking`, `current_response`, `active_terminal_entries`). In `app.py`, send `live_state` on WebSocket `connected` event if `session.is_running`. In `useChat.ts`, handle initial live state re-attachment and preserve local message cache on thread switching.

**Tech Stack:** Python (FastAPI, asyncio, LangChain messages), TypeScript (React hooks, WebSocket, Tauri Desktop).

## Global Constraints

- Preserve all existing WebSocket message protocol types (`chunk`, `live_update`, `terminal_output`, `done`, `connected`).
- Ensure no data loss when switching threads or when reloading the desktop application.
- Ensure thread disk writes are atomic using existing `ThreadManager.save_thread_messages`.

---

### Task 1: Backend Real-Time Persistence & Live State Buffer (`session_pool.py`)

**Files:**
- Modify: `kogniterm/server/session_pool.py:530-900`
- Test: `tests/test_server_session_persistence.py`

**Interfaces:**
- Consumes: `ThreadManager.save_thread_messages(thread_id, messages)`
- Produces: `AgentSession.live_state()` dictionary containing `thinking`, `response`, `terminal_entries`

- [ ] **Step 1: Write unit test for immediate message saving & live state buffering**

Create `tests/test_server_session_persistence.py`:

```python
import pytest
import asyncio
from unittest.mock import MagicMock
from langchain_core.messages import HumanMessage, AIMessage
from kogniterm.server.session_pool import AgentSession, ServerUI

def test_agent_session_live_state_buffer():
    ui = ServerUI(loop=asyncio.get_event_loop(), session_id="test_sess")
    ui._push("live_update", {"thinking": "Pensando en la solución...", "response": "Procesando respuesta"})
    
    assert ui.current_thinking == "Pensando en la solución..."
    assert ui.current_response == "Procesando respuesta"
    
    ui.reset_live_buffer()
    assert ui.current_thinking == ""
    assert ui.current_response == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_server_session_persistence.py -v`
Expected: FAIL (ServerUI attributes missing)

- [ ] **Step 3: Update `ServerUI` and `AgentSession` in `session_pool.py`**

In `kogniterm/server/session_pool.py`:
Add live streaming buffer attributes to `ServerUI`:
```python
    def __init__(self, loop: asyncio.AbstractEventLoop, session_id: str):
        self._loop = loop
        self.session_id = session_id
        self._queues: list = []
        self._queues_lock = threading.Lock()
        self._pending_approvals: dict = {}
        self._pending_approvals_async: dict = {}
        self._pending_lock = threading.Lock()
        self.current_thinking: str = ""
        self.current_response: str = ""
        self.active_terminal_entries: list = []

    def reset_live_buffer(self):
        self.current_thinking = ""
        self.current_response = ""
        self.active_terminal_entries.clear()
```
Update `ServerUI._push` or live update handling so `current_thinking`, `current_response`, and `active_terminal_entries` capture streaming chunks.
In `AgentSession.send(...)`:
Immediately after `self.agent_state.add_message(HumanMessage(content=message))` (around line 851):
```python
if self.thread_manager:
    self.thread_manager.save_thread_messages(
        self.session_id, self.agent_state.messages
    )
```
And inside `_run_agent_loop` or after step completions, ensure `save_thread_messages` is called to sync all AI/Tool messages immediately to disk.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_server_session_persistence.py -v`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add tests/test_server_session_persistence.py kogniterm/server/session_pool.py
git commit -m "feat: add immediate message persistence and live streaming buffer to AgentSession"
```

---

### Task 2: Backend WebSocket Handshake Update (`app.py`)

**Files:**
- Modify: `kogniterm/server/app.py:1480-1510`
- Test: `tests/test_websocket_handshake_live_state.py`

**Interfaces:**
- Consumes: `session.is_running`, `session.ui.current_thinking`, `session.ui.current_response`, `session.ui.active_terminal_entries`
- Produces: `connected` event with `is_running` and `live_state` object

- [ ] **Step 1: Write test for WebSocket connected payload containing live state**

Create `tests/test_websocket_handshake_live_state.py`:

```python
import pytest

def test_websocket_connected_payload_structure():
    payload = {
        "type": "connected",
        "data": {
            "session_id": "test-123",
            "is_running": True,
            "live_state": {
                "thinking": "Analizando...",
                "response": "Hola",
                "terminal_entries": []
            }
        }
    }
    assert payload["data"]["is_running"] is True
    assert payload["data"]["live_state"]["thinking"] == "Analizando..."
```

- [ ] **Step 2: Run test to verify it passes structural checks**

Run: `pytest tests/test_websocket_handshake_live_state.py -v`
Expected: PASS

- [ ] **Step 3: Update `websocket_chat` in `app.py`**

In `kogniterm/server/app.py` around line 1481:
```python
await websocket.send_json(
    {
        "type": "connected",
        "data": {
            **session.to_dict(),
            "config": current_config,
            "is_new": is_new,
            "persistent": True,
            "is_running": session.is_running,
            "live_state": {
                "thinking": getattr(session.ui, "current_thinking", ""),
                "response": getattr(session.ui, "current_response", ""),
                "terminal_entries": getattr(session.ui, "active_terminal_entries", []),
            },
        },
    }
)
```

- [ ] **Step 4: Commit changes**

```bash
git add tests/test_websocket_handshake_live_state.py kogniterm/server/app.py
git commit -m "feat: include is_running and live_state buffer in websocket connected event"
```

---

### Task 3: Frontend Desktop Live Re-attachment & Thread Switching (`useChat.ts`)

**Files:**
- Modify: `kogniterm-desktop/apps/desktop/src/hooks/useChat.ts:280-550`

**Interfaces:**
- Consumes: WebSocket `connected` event data with `is_running` & `live_state`
- Produces: Seamless UI restoration of `isGenerating`, streaming `reasoning`/`content`, and `terminalEntries`

- [ ] **Step 1: Update `useChat.ts` to handle live state re-attachment on connect**

In `kogniterm-desktop/apps/desktop/src/hooks/useChat.ts`:
Inside `ws.onmessage`:
```typescript
if (data.type === 'connected') {
    const payload = data.data || data;
    if (payload.is_running && payload.live_state) {
        setIsGenerating(true);
        const { thinking, response, terminal_entries } = payload.live_state;
        if (thinking || response) {
            setMessages((prev) => {
                if (prev.length > 0 && prev[prev.length - 1].role === 'assistant') {
                    return prev;
                }
                return [
                    ...prev,
                    {
                        id: Date.now().toString(),
                        role: 'assistant',
                        content: response || '',
                        reasoning: thinking || '',
                        timestamp: Date.now(),
                    },
                ];
            });
        }
        if (terminal_entries && terminal_entries.length > 0) {
            setTerminalEntries(terminal_entries);
        }
    }
}
```

- [ ] **Step 2: Update message fetching to prevent overwriting active streaming messages**

In `useEffect` for `threadId` in `useChat.ts`:
When `fetch("/api/threads/${threadId}/messages")` resolves:
Check if `data.messages` contains messages. If local `messages` state already has active/newer messages for the current thread, merge or update intelligently so streaming AI responses are not wiped out.

- [ ] **Step 3: Commit changes**

```bash
git add kogniterm-desktop/apps/desktop/src/hooks/useChat.ts
git commit -m "feat: restore live streaming state and terminal entries on websocket reconnect in desktop client"
```
