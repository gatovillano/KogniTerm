# Desktop FileCompleter and Skills Autocompletion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement workspace file autocompletion (`@`) and skills autocompletion (`#`) in `kogniterm-desktop`, connecting the React frontend to FastAPI backend endpoints.

**Architecture:** Add a `GET /api/workspace/files` endpoint in `kogniterm/server/app.py` utilizing Python's `fuzzy_match_files` engine from `file_completer.py`. In `kogniterm-desktop`'s `ChatInput.tsx`, parse the active cursor token for `#` (skills), `@` (files), and `/` or `%` (commands), fetch data dynamically, and render an interactive autocomplete dropdown menu with keyboard navigation.

**Tech Stack:** Python 3.12 (FastAPI, pytest), React 19, TypeScript, Lucide React icons, TailwindCSS.

## Global Constraints

- Backend endpoints must handle optional `session_id` and return clean JSON error responses if workspace scanning fails.
- Exclude virtual environments, `.git`, `node_modules`, `dist`, `__pycache__` from file completion results.
- Keep `ChatInput.tsx` UI responsive with debounced network calls for file searches.
- Preserve existing `%` and `/` command autocompletion functionality.

---

### Task 1: Backend API Endpoint `GET /api/workspace/files`

**Files:**
- Modify: `kogniterm/server/app.py:910-950`
- Test: `tests/test_server_api.py`

**Interfaces:**
- Produces: `GET /api/workspace/files?query=...&session_id=...&max_results=20` returning `{"query": string, "results": [{"path": string, "display": string, "is_dir": bool, "meta": string}]}`

- [ ] **Step 1: Write failing unit test for `/api/workspace/files` endpoint**

In `tests/test_server_api.py`:
```python
import pytest
from fastapi.testclient import TestClient
from kogniterm.server.app import create_app

def test_workspace_files_endpoint(tmp_path, monkeypatch):
    # Setup mock workspace files
    (tmp_path / "main.py").write_text("print('hello')")
    (tmp_path / "app_spec.tsx").write_text("export default App")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "ignored.js").write_text("// ignore")
    
    monkeypatch.chdir(tmp_path)
    app = create_app()
    client = TestClient(app)
    
    response = client.get("/api/workspace/files?query=app_spec")
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    paths = [item["path"] for item in data["results"]]
    assert "app_spec.tsx" in paths
    assert "node_modules/ignored.js" not in paths
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_server_api.py -k test_workspace_files_endpoint -v`
Expected: FAIL (404 Not Found)

- [ ] **Step 3: Implement `GET /api/workspace/files` endpoint in `kogniterm/server/app.py`**

Add to `kogniterm/server/app.py`:
```python
    @application.get("/api/workspace/files", tags=["Desktop"])
    async def search_workspace_files(
        query: str = "",
        session_id: Optional[str] = None,
        max_results: int = 20
    ):
        """Busca archivos del workspace utilizando la búsqueda difusa de file_completer."""
        try:
            workspace_path = os.getcwd()
            if session_id:
                s = pool.get(session_id)
                if s and getattr(s, "workspace_dir", None):
                    workspace_path = s.workspace_dir

            from kogniterm.terminal.file_completer import is_ignored_path, fuzzy_match_files

            exclude_extensions = {'.pyc', '.tmp', '.log', '.swp', '.bak', '.old', '.pyfly'}
            items = []

            for root, dirs, files in os.walk(workspace_path):
                dirs[:] = [d for d in dirs if not is_ignored_path(d)]
                try:
                    rel_root = os.path.relpath(root, workspace_path)
                except ValueError:
                    continue

                for d in dirs:
                    rel_dir = os.path.join(rel_root, d) + '/' if rel_root != '.' else d + '/'
                    items.append(rel_dir)

                for f in files:
                    if f.startswith('.') or any(f.endswith(ext) for ext in exclude_extensions):
                        continue
                    rel_path = os.path.join(rel_root, f) if rel_root != '.' else f
                    items.append(rel_path)

                    if len(items) > 3000:
                        break
                if len(items) > 3000:
                    break

            if query and query.strip():
                matches = fuzzy_match_files(query, items, workspace_path, max_results=max_results)
                results = []
                for score, path_str, meta in matches:
                    is_dir = path_str.endswith('/') or os.path.isdir(os.path.join(workspace_path, path_str))
                    results.append({
                        "path": path_str,
                        "display": path_str,
                        "is_dir": is_dir,
                        "meta": meta
                    })
            else:
                results = []
                for item in items[:max_results]:
                    is_dir = item.endswith('/') or os.path.isdir(os.path.join(workspace_path, item))
                    ext = os.path.splitext(item)[1]
                    from kogniterm.terminal.file_completer import _get_file_meta_icon
                    meta = "📁 dir" if is_dir else _get_file_meta_icon(ext)
                    results.append({
                        "path": item,
                        "display": item,
                        "is_dir": is_dir,
                        "meta": meta
                    })

            return {"query": query, "results": results}
        except Exception as e:
            logger.error(f"Error buscando archivos del workspace: {e}")
            return {"query": query, "results": [], "error": str(e)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_server_api.py -k test_workspace_files_endpoint -v`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add kogniterm/server/app.py tests/test_server_api.py
git commit -m "feat(server): add /api/workspace/files endpoint for fuzzy file search"
```

---

### Task 2: Multi-trigger Autocomplete Logic in `ChatInput.tsx`

**Files:**
- Modify: `kogniterm-desktop/apps/desktop/src/components/chat/ChatInput.tsx:50-200`

**Interfaces:**
- Consumes: `GET http://localhost:8765/api/skills` and `GET http://localhost:8765/api/workspace/files?query=...`
- Produces: State management for `@` (files), `#` (skills), `/` or `%` (commands) in `ChatInput`.

- [ ] **Step 1: Add types and multi-trigger state in `ChatInput.tsx`**

Update state interfaces and declarations in `ChatInput.tsx`:
```typescript
interface SuggestionItem {
    id: string;
    label: string;
    desc: string;
    type: 'command' | 'skill' | 'file';
    scope?: string;
    meta?: string;
    insertValue: string;
}

// Inside ChatInput component:
const [showSuggestions, setShowSuggestions] = useState(false);
const [suggestions, setSuggestions] = useState<SuggestionItem[]>([]);
const [selectedIndex, setSelectedIndex] = useState(0);
const [activeTrigger, setActiveTrigger] = useState<'@' | '#' | '/' | '%' | null>(null);
const [cachedSkills, setCachedSkills] = useState<SuggestionItem[]>([]);
```

- [ ] **Step 2: Add skills fetching effect and debounced file search logic**

In `ChatInput.tsx`:
```typescript
// Fetch skills on mount
useEffect(() => {
    const fetchSkills = async () => {
        try {
            const res = await fetch('http://localhost:8765/api/skills');
            if (res.ok) {
                const data = await res.json();
                const items: SuggestionItem[] = (data.skills || []).map((s: any) => ({
                    id: `skill-${s.name}`,
                    label: `#${s.name}`,
                    desc: s.description || 'Skill personalizada',
                    type: 'skill',
                    scope: s.scope || 'global',
                    insertValue: `#${s.name} `
                }));
                setCachedSkills(items);
            }
        } catch (err) {
            console.error('Error cargando skills para autocompletado:', err);
        }
    };
    fetchSkills();
}, []);
```

- [ ] **Step 3: Update `handleInputChange` for `@`, `#`, `/`, `%` triggers**

In `ChatInput.tsx`:
```typescript
const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    setInput(value);

    const cursorPosition = e.target.selectionStart;
    const textBeforeCursor = value.substring(0, cursorPosition);

    // 1. Skill trigger: #
    const skillMatch = textBeforeCursor.match(/#([a-zA-Z0-9_-]*)$/);
    if (skillMatch) {
        const query = skillMatch[1].toLowerCase();
        const filtered = cachedSkills.filter(s =>
            s.label.toLowerCase().includes(query) ||
            s.desc.toLowerCase().includes(query)
        );
        if (filtered.length > 0) {
            setSuggestions(filtered);
            setShowSuggestions(true);
            setActiveTrigger('#');
            setSelectedIndex(0);
            requestAnimationFrame(updateCursorPosition);
            return;
        }
    }

    // 2. File trigger: @
    const fileMatch = textBeforeCursor.match(/@([^\s@]*)$/);
    if (fileMatch) {
        const query = fileMatch[1];
        setActiveTrigger('@');
        setShowSuggestions(true);
        setSelectedIndex(0);
        requestAnimationFrame(updateCursorPosition);

        // Fetch matching files from server
        fetch(`http://localhost:8765/api/workspace/files?query=${encodeURIComponent(query)}`)
            .then(res => res.ok ? res.json() : { results: [] })
            .then(data => {
                const items: SuggestionItem[] = (data.results || []).map((f: any) => ({
                    id: `file-${f.path}`,
                    label: `@${f.path}`,
                    desc: f.is_dir ? 'Carpeta' : f.meta || 'Archivo',
                    type: 'file',
                    meta: f.meta,
                    insertValue: `@${f.path} `
                }));
                setSuggestions(items);
            })
            .catch(err => console.error('Error buscando archivos:', err));
        return;
    }

    // 3. Command trigger: % or /
    const cmdMatch = textBeforeCursor.match(/([%/])(\w*)$/);
    if (cmdMatch) {
        const triggerChar = cmdMatch[1];
        const query = cmdMatch[2].toLowerCase();
        const items: SuggestionItem[] = COMMANDS.map(c => ({
            id: `cmd-${c.command}`,
            label: c.command,
            desc: c.desc,
            type: 'command',
            insertValue: `${c.command} `
        })).filter(c =>
            c.label.toLowerCase().includes(query) ||
            c.desc.toLowerCase().includes(query)
        );

        if (items.length > 0) {
            setSuggestions(items);
            setShowSuggestions(true);
            setActiveTrigger(triggerChar as '%' | '/');
            setSelectedIndex(0);
            requestAnimationFrame(updateCursorPosition);
            return;
        }
    }

    setShowSuggestions(false);
    setActiveTrigger(null);
};
```

- [ ] **Step 4: Update `handleSelectCommand` to replace trigger sequence cleanly**

```typescript
const handleSelectSuggestion = (item: SuggestionItem) => {
    const cursorPosition = textareaRef.current?.selectionStart || 0;
    const textBeforeCursor = input.substring(0, cursorPosition);
    const textAfterCursor = input.substring(cursorPosition);

    let regex: RegExp;
    if (activeTrigger === '#') {
        regex = /#([a-zA-Z0-9_-]*)$/;
    } else if (activeTrigger === '@') {
        regex = /@([^\s@]*)$/;
    } else {
        regex = /([%/])(\w*)$/;
    }

    const newTextBefore = textBeforeCursor.replace(regex, item.insertValue);
    const newValue = newTextBefore + textAfterCursor;
    setInput(newValue);
    setShowSuggestions(false);
    setActiveTrigger(null);

    setTimeout(() => {
        if (textareaRef.current) {
            textareaRef.current.focus();
            const newPos = newTextBefore.length;
            textareaRef.current.setSelectionRange(newPos, newPos);
        }
    }, 0);
};
```

- [ ] **Step 5: Commit changes**

```bash
git add kogniterm-desktop/apps/desktop/src/components/chat/ChatInput.tsx
git commit -m "feat(desktop): add multi-trigger autocompletion logic for # (skills) and @ (files)"
```

---

### Task 3: Render Categorized Autocomplete Dropdown in UI

**Files:**
- Modify: `kogniterm-desktop/apps/desktop/src/components/chat/ChatInput.tsx:280-315`

**Interfaces:**
- Produces: Enhanced UI dropdown component with icons (`Zap`, `FileText`, `Terminal`), scope badges, and keyboard accessibility.

- [ ] **Step 1: Import Lucide icons and render autocomplete dropdown**

Update imports in `ChatInput.tsx`:
```typescript
import { Folder, Sparkles, Paperclip, Square, ChevronDown, ChevronUp, X, ArrowUp, Zap, Box, FileText, Terminal } from 'lucide-react';
```

Update suggestions dropdown template in `ChatInput.tsx`:
```tsx
{/* Command & Skills & Files Suggestions Menu */}
{showSuggestions && suggestions.length > 0 && (
    <div
        className="absolute z-[100] bg-[#16161a] border border-zinc-800 rounded-xl shadow-[0_20px_50px_rgba(0,0,0,0.6)] overflow-hidden transition-all duration-200"
        style={{
            bottom: 'calc(100% + 12px)',
            left: cursorOffset ? `${Math.min(Math.max(cursorOffset.left + 52, 16), 400)}px` : '50%',
            transform: cursorOffset ? 'none' : 'translateX(-50%)',
            width: 'min(380px, calc(100vw - 32px))',
            opacity: 1,
            visibility: 'visible',
        }}
    >
        <div className="max-h-64 overflow-y-auto custom-scrollbar p-1.5">
            <div className="px-2 py-1 text-[10px] font-bold text-zinc-500 uppercase tracking-wider flex items-center justify-between">
                <span>
                    {activeTrigger === '#' && '⚡ Skills Disponibles'}
                    {activeTrigger === '@' && '📁 Archivos del Workspace'}
                    {(activeTrigger === '/' || activeTrigger === '%') && '💻 Comandos del Sistema'}
                </span>
                <span className="text-[9px] text-zinc-600 font-mono">↑↓ para navegar</span>
            </div>
            {suggestions.map((item, index) => (
                <button
                    key={item.id}
                    type="button"
                    onClick={() => handleSelectSuggestion(item)}
                    className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs transition-colors ${index === selectedIndex
                        ? 'bg-indigo-500/15 text-indigo-300 border border-indigo-500/30'
                        : 'text-zinc-300 hover:bg-zinc-900 border border-transparent'
                        }`}
                >
                    <div className="flex items-center gap-2.5 min-w-0 pr-2">
                        {item.type === 'skill' && <Zap size={13} className="text-yellow-400 shrink-0" />}
                        {item.type === 'file' && <FileText size={13} className="text-blue-400 shrink-0" />}
                        {item.type === 'command' && <Terminal size={13} className="text-emerald-400 shrink-0" />}
                        <span className="font-mono font-medium truncate">{item.label}</span>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                        {item.scope && (
                            <span className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-zinc-800 text-zinc-400 border border-zinc-700">
                                {item.scope}
                            </span>
                        )}
                        <span className="text-zinc-500 text-[10px] truncate max-w-[120px]">{item.desc}</span>
                    </div>
                </button>
            ))}
        </div>
    </div>
)}
```

- [ ] **Step 2: Update keyboard event handlers for Enter / Tab selection**

In `handleKeyDown`:
```typescript
if (showSuggestions && suggestions.length > 0) {
    if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex(prev => (prev > 0 ? prev - 1 : suggestions.length - 1));
        return;
    }
    if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex(prev => (prev < suggestions.length - 1 ? prev + 1 : 0));
        return;
    }
    if (e.key === 'Tab' || e.key === 'Enter') {
        e.preventDefault();
        handleSelectSuggestion(suggestions[selectedIndex]);
        return;
    }
    if (e.key === 'Escape') {
        setShowSuggestions(false);
        setActiveTrigger(null);
        return;
    }
}
```

- [ ] **Step 3: Commit UI changes**

```bash
git add kogniterm-desktop/apps/desktop/src/components/chat/ChatInput.tsx
git commit -m "feat(desktop): render styled autocomplete popup with icons and keyboard navigation"
```

---

### Task 4: End-to-End Verification & Desktop Build Test

**Files:**
- Build verification in `kogniterm-desktop/apps/desktop`

- [ ] **Step 1: Run pytest suite to ensure backend tests pass**

Run: `pytest tests/test_server_api.py -v`
Expected: PASS

- [ ] **Step 2: Run TypeScript build in desktop app to ensure no type errors**

Run: `cd kogniterm-desktop/apps/desktop && npm run build`
Expected: Successfully compiled without TypeScript errors.

- [ ] **Step 3: Commit final build confirmation**

```bash
git add .
git commit -m "chore: verify build and end-to-end desktop file & skill autocompletion"
```
