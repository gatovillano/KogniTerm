# Auto-aprobación de Comandos y Ediciones en KogniTerm Desktop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar en el cliente Desktop y en el Servidor Backend de KogniTerm la activación de auto-aprobación de comandos y ediciones mediante el modal de Ajustes, un botón toggle rápido en la cabecera del chat, y la opción "Aceptar siempre" en la notificación de aprobación.

**Architecture:** 
En el backend, se persiste la clave `auto_approve` en `ConfigManager` (global/proyecto) y se sincroniza en vivo con `CommandApprovalHandler` en las `AgentSession` activas. En el frontend Desktop (React/Vite/Tauri), se agrega el control en `SettingsModal.tsx`, un badge conmutador rápido en `App.tsx`, y el botón "Aceptar siempre" en `CommandApproval.tsx`.

**Tech Stack:** Python 3.10+, FastAPI, LangChain/LangGraph, React, TypeScript, TailwindCSS, Lucide Icons.

## Global Constraints

- Sincronización en tiempo real entre la API `/api/config/set` y las sesiones activas en el `SessionPool`.
- Respetar la especificación del schema de configuración (`ConfigManager` en `kogniterm/terminal/config_manager.py`).
- Mantener compatibilidad con la interfaz de WebSocket y los eventos `approval_required`.

---

### Task 1: Backend Sync of `auto_approve` and Unit Tests

**Files:**
- Modify: `kogniterm/terminal/command_approval_handler.py:140-146`
- Modify: `kogniterm/server/app.py:830-845`
- Test: `tests/unit/test_server_auto_approval.py`

**Interfaces:**
- Consumes: `ConfigManager.get_config("auto_approve")`
- Produces: `POST /api/config/set` updating `auto_approve` and syncing active sessions.

- [ ] **Step 1: Write the unit test for auto_approve config sync**

```python
# Append to tests/unit/test_server_auto_approval.py
@pytest.mark.anyio
async def test_command_approval_handler_respects_config_manager_auto_approve():
    """Verifica que CommandApprovalHandler consulte auto_approve de ConfigManager si no está seteado explícitamente."""
    with patch("kogniterm.terminal.config_manager.ConfigManager.get_config", return_value=True):
        handler = CommandApprovalHandler(
            llm_service=MagicMock(),
            command_executor=MagicMock(),
            prompt_session=None,
            terminal_ui=MagicMock(),
            agent_state=MagicMock(),
        )
        assert handler.auto_approve is True
```

- [ ] **Step 2: Run test to verify it fails before modification**

Run: `pytest tests/unit/test_server_auto_approval.py -v`

- [ ] **Step 3: Update `CommandApprovalHandler` and `app.py` to sync `auto_approve`**

In `kogniterm/terminal/command_approval_handler.py`:
```python
        from kogniterm.terminal.config_manager import ConfigManager
        cm = ConfigManager()
        self.auto_approve = bool(cm.get_config("auto_approve"))
```

In `kogniterm/server/app.py` in `set_config_value`:
```python
        if req.key == "auto_approve":
            with pool._lock:
                for session in pool._sessions.values():
                    if session.command_approval_handler:
                        session.command_approval_handler.auto_approve = bool(req.value)
```

- [ ] **Step 4: Run pytest to verify it passes**

Run: `pytest tests/unit/test_server_auto_approval.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add kogniterm/terminal/command_approval_handler.py kogniterm/server/app.py tests/unit/test_server_auto_approval.py
git commit -m "feat(backend): sync auto_approve config across sessions and handler"
```

---

### Task 2: Configuración en Ajustes Avanzados (`SettingsModal.tsx`)

**Files:**
- Modify: `kogniterm-desktop/apps/desktop/src/components/settings/SettingsModal.tsx:540-575`

**Interfaces:**
- Consumes: `getScopeValue('auto_approve', activeScope)`
- Produces: `setScopeValue('auto_approve', boolean, activeScope)` saved via `/api/config/set`

- [ ] **Step 1: Add Auto-Approve Toggle in Advanced Settings Tab**

In `SettingsModal.tsx` under `{activeTab === 'advanced' && (...)}`:
```tsx
                {/* Auto Approve setting */}
                <div className="space-y-2 pt-2 border-t border-slate-100">
                  <div className="flex items-center justify-between">
                    <div>
                      <label className="text-xs font-semibold text-slate-800">Auto-aprobar Comandos y Ediciones</label>
                      <p className="text-[11px] text-slate-500 mt-0.5">
                        Ejecuta automáticamente modificaciones de archivos y comandos bash sin solicitar confirmación manual.
                      </p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer select-none">
                      <input 
                        type="checkbox" 
                        checked={Boolean(getScopeValue('auto_approve', activeScope))} 
                        onChange={(e) => setScopeValue('auto_approve', e.target.checked, activeScope)}
                        className="sr-only peer" 
                      />
                      <div className="w-10 h-5 bg-slate-200 rounded-full peer peer-checked:bg-indigo-600 peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all shadow-xs"></div>
                    </label>
                  </div>
                </div>
```

- [ ] **Step 2: Commit**

```bash
git add kogniterm-desktop/apps/desktop/src/components/settings/SettingsModal.tsx
git commit -m "feat(desktop): add auto-approve toggle in Advanced Settings modal"
```

---

### Task 3: Interruptor Rápido en la Cabecera del Chat (`App.tsx`)

**Files:**
- Modify: `kogniterm-desktop/apps/desktop/src/App.tsx`

**Interfaces:**
- Consumes: `http://localhost:8765/api/config/all`
- Produces: Quick toggle for `auto_approve` state calling `POST /api/config/set`

- [ ] **Step 1: Add state and fetch for `autoApprove` in `App.tsx`**

Fetch initial status of `auto_approve` from `/api/config/all` and add state:
```tsx
const [autoApprove, setAutoApprove] = useState<boolean>(false);

useEffect(() => {
  fetch('http://localhost:8765/api/config/all')
    .then(res => res.ok ? res.json() : null)
    .then(data => {
      if (data?.merged?.auto_approve !== undefined) {
        setAutoApprove(Boolean(data.merged.auto_approve));
      }
    })
    .catch(err => console.error(err));
}, []);

const toggleAutoApprove = async () => {
  const nextVal = !autoApprove;
  setAutoApprove(nextVal);
  try {
    await fetch('http://localhost:8765/api/config/set', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key: 'auto_approve', value: nextVal, scope: 'project' }),
    });
  } catch (err) {
    console.error('Error toggling auto_approve:', err);
  }
};
```

- [ ] **Step 2: Render Quick Toggle Badge in Header**

In the top navigation header bar:
```tsx
<button
  type="button"
  onClick={toggleAutoApprove}
  title={autoApprove ? "Auto-aprobación activa (Clic para desactivar)" : "Auto-aprobación inactiva (Clic para activar)"}
  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium transition-all ${
    autoApprove 
      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20' 
      : 'bg-zinc-800/60 text-zinc-400 border border-zinc-700/50 hover:bg-zinc-800 hover:text-zinc-200'
  }`}
>
  {autoApprove ? <Zap size={13} className="text-emerald-400 fill-emerald-400/20" /> : <Shield size={13} />}
  <span>{autoApprove ? "Auto-aprobación ON" : "Auto-aprobación OFF"}</span>
</button>
```

- [ ] **Step 3: Commit**

```bash
git add kogniterm-desktop/apps/desktop/src/App.tsx
git commit -m "feat(desktop): add quick auto-approve toggle badge in chat header"
```

---

### Task 4: Opción "Aceptar siempre" en Notificación Pendiente (`CommandApproval.tsx`)

**Files:**
- Modify: `kogniterm-desktop/apps/desktop/src/components/chat/CommandApproval.tsx`

**Interfaces:**
- Consumes: `request: ApprovalRequest`
- Produces: Triggers `onApprove(request.id)` and sets `auto_approve: true` on server via API.

- [ ] **Step 1: Add "Aceptar siempre" button and keyboard shortcut `a`/`A`**

In `CommandApproval.tsx`:
```tsx
    const handleApproveAlways = async () => {
        try {
            await fetch('http://localhost:8765/api/config/set', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ key: 'auto_approve', value: true, scope: 'project' }),
            });
        } catch (e) {
            console.error("Error setting auto_approve:", e);
        }
        onApprove(request.id);
    };
```
In the keypress handler:
```tsx
            } else if (e.key === 'a' || e.key === 'A') {
                e.preventDefault();
                handleApproveAlways();
            }
```
In the actions footer:
```tsx
                <div className="flex items-center justify-between w-full">
                    <button
                        onClick={handleApproveAlways}
                        title="Aprobar este y todos los siguientes (A)"
                        className="px-3 py-1.5 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20 hover:bg-amber-500/20 text-xs font-medium transition-colors flex items-center gap-1.5"
                    >
                        <Zap size={13} />
                        <span>Aceptar siempre (A)</span>
                    </button>
                    <div className="flex items-center gap-2">
                        <button onClick={() => onReject(request.id)} ... >...</button>
                        <button onClick={() => onApprove(request.id)} ... >...</button>
                    </div>
                </div>
```

- [ ] **Step 2: Commit**

```bash
git add kogniterm-desktop/apps/desktop/src/components/chat/CommandApproval.tsx
git commit -m "feat(desktop): add Accept Always button and key shortcut to approval modal"
```

---

## Plan Self-Review
- **Spec Coverage:** Completo (backend `ConfigManager` / `session_pool`, `SettingsModal`, header quick toggle, `CommandApproval` accept-always).
- **Placeholder scan:** Sin TODOs ni TBDs.
- **Type consistency:** Rutas y funciones validadas.
