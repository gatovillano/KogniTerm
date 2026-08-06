# Design Spec: FileCompleter and Skills Autocompletion for KogniTerm Desktop

## Overview
This document outlines the architecture and implementation for adding **FileCompleter** (`@`) and **Skills Autocompletion** (`#`) to the `kogniterm-desktop` client (`ChatInput.tsx`), matching the experience provided by the KogniTerm CLI/TUI.

## Requirements & Scope
1. **Trigger Prefixes in `ChatInput.tsx`**:
   - `@`: Triggers fuzzy workspace file autocompletion (`@src/App.tsx`).
   - `#`: Triggers skills autocompletion (`#brainstorming`, `#security-auditor`).
   - `/` or `%`: Triggers magic commands autocompletion (already existing).
2. **Backend API**:
   - New endpoint `GET /api/workspace/files` in `kogniterm/server/app.py` leveraging `fuzzy_match_files` from `kogniterm.terminal.file_completer`.
   - Reusing existing `GET /api/skills` endpoint in `kogniterm/server/app.py`.
3. **UI/UX in Desktop Client**:
   - Floating dropdown in `ChatInput.tsx` styled to match the Goose-style input capsule.
   - Categorized headings, distinct icons (`Zap` for skills, `FileText`/`Folder` for files, `Terminal` for commands), scope badges (`[workspace]`, `[global]`, etc.).
   - Full keyboard navigation (`ArrowUp`, `ArrowDown`, `Enter`, `Tab`, `Escape`).

---

## 1. Backend Architecture (`kogniterm/server/app.py`)

### A. New Endpoint: `GET /api/workspace/files`
- **Query Parameters**:
  - `query` (optional string): Term to fuzzy-match against workspace relative file paths.
  - `session_id` (optional string): Session ID to identify active workspace directory.
  - `max_results` (optional int, default 20): Maximum number of results to return.
- **Implementation**:
  - Determine workspace directory from `session_id` (or `os.getcwd()`).
  - Scan workspace files using background cached list or `os.walk`, excluding patterns in `EXCLUDE_PATTERNS` (`.git`, `node_modules`, `venv`, `dist`, `__pycache__`, etc.).
  - Run `fuzzy_match_files(query, files, workspace_dir, max_results)` from `kogniterm.terminal.file_completer`.
  - Return JSON structure:
    ```json
    {
      "query": "app.tsx",
      "results": [
        { "path": "src/App.tsx", "display": "src/App.tsx", "is_dir": false, "meta": "📄 tsx" }
      ]
    }
    ```

### B. Endpoint: `GET /api/skills`
- Existing endpoint returning registered skills list with `name`, `description`, `scope`, `category`, `tools`.
- Scope classification: `workspace`, `global`, `default`, `agent`, `external`.

---

## 2. Frontend Architecture (`kogniterm-desktop`)

### A. Trigger Detection in `ChatInput.tsx`
- On `<textarea>` change and cursor movement, inspect text immediately preceding selection cursor:
  - Match `@(\S*)$`: Set `activeTrigger = '@'`, `query = match[1]`.
  - Match `#(\S*)$`: Set `activeTrigger = '#'`, `query = match[1]`.
  - Match `([%/])(\w*)$`: Set `activeTrigger = '/'`, `query = match[2]`.

### B. Data Fetching & Caching
- **Skills (`#`)**:
  - Fetch from `http://localhost:8765/api/skills` on focus or typing `#`.
  - Cache results in React state to avoid redundant network calls.
  - Filter by fuzzy substring match against `name` and `description`.
- **Files (`@`)**:
  - Debounced (150ms) fetch to `http://localhost:8765/api/workspace/files?query=${encodeURIComponent(query)}`.
  - Display returned results.

### C. Insertion Logic
- Selecting an item (`Enter`, `Tab`, or mouse click) replaces the trigger match (`@query`, `#query`, or `/query`) with:
  - Skill: `#<skill_name> `
  - File: `@<relative_path> `
  - Command: `<command> `
- Restores focus to the `<textarea>` and updates cursor selection position.

### D. Component Layout & Styling
- Floating card rendered above/aligned with input textarea:
  - Dark background (`bg-[#16161a]`), border (`border-zinc-800`), rounded corners (`rounded-xl`), high z-index.
  - Categorized items with icon, primary title, description / meta label, and scope badge.
  - Selected item highlighted with `bg-indigo-500/10 text-indigo-300`.

---

## 3. Verification & Testing
1. **Backend Tests**:
   - Add unit test for `/api/workspace/files` endpoint in `tests/test_server_api.py`.
2. **Frontend Manual Verification**:
   - Typing `@` displays workspace files with icons and path scoring.
   - Typing `#` displays available skills (`brainstorming`, etc.) with scope badges.
   - Keyboard navigation selects items cleanly with `Enter`/`Tab`.
