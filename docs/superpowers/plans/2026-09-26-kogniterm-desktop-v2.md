# KogniTerm Desktop v2 & Web Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-architect `kogniterm-desktop` using OpenCode's Electron + SolidJS codebase (`packages/desktop`, `packages/app`, `packages/ui`) connected to `kogniterm server`, while migrating the current React desktop UI to `kogniterm-web`.

**Architecture:** Monorepo using npm/pnpm/bun workspaces and Turbo for `kogniterm-desktop`. Sidecar launcher in Electron main process probes/spawns `python -m kogniterm.server`. `kogniterm-web` is upgraded with the current React UI components and decoupled from desktop.

**Tech Stack:** Electron, SolidJS, electron-vite, electron-builder, TypeScript, TailwindCSS, Python (KogniTerm Server FastAPI/WebSocket), Vite, React.

## Global Constraints

- **AGENTS.md Compliance**: All terminal/stream output handlers in TypeScript MUST strictly parse non-echo output and detect `##KOGNITERM_DONE_MARKER##` without freezing.
- **Independence**: `kogniterm-web` MUST NOT depend on any file within `kogniterm-desktop`.
- **Package Scope**: All OpenCode `@opencode-ai/*` imports must be rebranded to `@kogniterm/*`.

---

### Task 1: Migrate React UI to `kogniterm-web` and Update `start-web.sh`

**Files:**
- Modify: `start-web.sh:45-53`
- Create/Overwrite: `kogniterm-web/package.json`
- Create/Overwrite: `kogniterm-web/vite.config.ts`
- Copy: `kogniterm-desktop/apps/desktop/src/*` -> `kogniterm-web/src/`
- Copy: `kogniterm-desktop/packages/ui/src/*` -> `kogniterm-web/src/ui/`

**Interfaces:**
- Consumes: Current React UI components (`ChatMessage`, `TerminalPanel`, `ChatInput`, etc.).
- Produces: Standalone web bundle in `kogniterm-web/dist`.

- [ ] **Step 1: Copy React UI files into `kogniterm-web`**

```bash
mkdir -p /home/gato/Proyectos/Gemini-Interpreter/kogniterm-web/src
cp -r /home/gato/Proyectos/Gemini-Interpreter/kogniterm-desktop/apps/desktop/src/* /home/gato/Proyectos/Gemini-Interpreter/kogniterm-web/src/
mkdir -p /home/gato/Proyectos/Gemini-Interpreter/kogniterm-web/src/ui
cp -r /home/gato/Proyectos/Gemini-Interpreter/kogniterm-desktop/packages/ui/src/* /home/gato/Proyectos/Gemini-Interpreter/kogniterm-web/src/ui/
```

- [ ] **Step 2: Update `kogniterm-web/package.json`**

Write `kogniterm-web/package.json` with React, Vite, Tailwind, Lucide, and Xterm dependencies.

- [ ] **Step 3: Update `start-web.sh` to target `kogniterm-web` directly**

Modify `start-web.sh` to remove the conditional `if [ -d "${SCRIPT_DIR}/kogniterm-desktop/apps/desktop" ]` block and always set `FRONTEND_SRC_DIR="${SCRIPT_DIR}/kogniterm-web"`.

- [ ] **Step 4: Test build `kogniterm-web`**

Run: `cd /home/gato/Proyectos/Gemini-Interpreter/kogniterm-web && npm install && npm run build`
Expected: `dist/` directory generated cleanly.

- [ ] **Step 5: Commit**

```bash
git add kogniterm-web/ start-web.sh
git commit -m "feat(web): migrate desktop React UI to kogniterm-web and decouple start-web.sh"
```

---

### Task 2: Scaffold `kogniterm-desktop` OpenCode Monorepo

**Files:**
- Overwrite: `kogniterm-desktop/package.json`
- Overwrite: `kogniterm-desktop/turbo.json`
- Create: `kogniterm-desktop/packages/desktop/`
- Create: `kogniterm-desktop/packages/app/`
- Create: `kogniterm-desktop/packages/ui/`

**Interfaces:**
- Consumes: Source packages from `/tmp/opencode_src/packages/{desktop,app,ui}`.
- Produces: `@kogniterm/desktop`, `@kogniterm/app`, `@kogniterm/ui` monorepo layout.

- [ ] **Step 1: Clean old `kogniterm-desktop` prototype files**

```bash
rm -rf /home/gato/Proyectos/Gemini-Interpreter/kogniterm-desktop/apps
rm -rf /home/gato/Proyectos/Gemini-Interpreter/kogniterm-desktop/packages/*
```

- [ ] **Step 2: Copy OpenCode desktop, app, and ui packages into `kogniterm-desktop/packages/`**

```bash
cp -r /tmp/opencode_src/packages/desktop /home/gato/Proyectos/Gemini-Interpreter/kogniterm-desktop/packages/
cp -r /tmp/opencode_src/packages/app /home/gato/Proyectos/Gemini-Interpreter/kogniterm-desktop/packages/
cp -r /tmp/opencode_src/packages/ui /home/gato/Proyectos/Gemini-Interpreter/kogniterm-desktop/packages/
```

- [ ] **Step 3: Rebrand `@opencode-ai/*` package references to `@kogniterm/*`**

Search and replace package scope across `kogniterm-desktop/packages/`:
- `@opencode-ai/desktop` -> `@kogniterm/desktop`
- `@opencode-ai/app` -> `@kogniterm/app`
- `@opencode-ai/ui` -> `@kogniterm/ui`

- [ ] **Step 4: Create root `package.json` and `turbo.json` for `kogniterm-desktop`**

Configure workspaces: `["packages/*"]`.

- [ ] **Step 5: Verify workspace setup**

Run: `cd /home/gato/Proyectos/Gemini-Interpreter/kogniterm-desktop && npm install`
Expected: Dependencies resolved successfully.

- [ ] **Step 6: Commit**

```bash
git add kogniterm-desktop/
git commit -m "feat(desktop): scaffold OpenCode Electron+SolidJS monorepo structure for KogniTerm Desktop"
```

---

### Task 3: Implement `KogniTermClient` API Adapter & `sidecar.ts`

**Files:**
- Create/Modify: `kogniterm-desktop/packages/desktop/src/main/sidecar.ts`
- Create/Modify: `kogniterm-desktop/packages/app/src/api/client.ts`

**Interfaces:**
- Consumes: `python -m kogniterm.server` REST & WebSocket API at `http://127.0.0.1:8765`.
- Produces: `sidecar` launcher in Electron main, and SolidJS state adapters in `@kogniterm/app`.

- [ ] **Step 1: Implement `sidecar.ts` in `packages/desktop/src/main/sidecar.ts`**

Write probe logic for `http://127.0.0.1:8765/docs` and spawn fallback: `python3 -m kogniterm.server --host 127.0.0.1 --port 8765`.

- [ ] **Step 2: Implement `KogniTermClient` in `packages/app/src/api/client.ts`**

Connect to WebSocket `/ws/session/{session_id}` and REST endpoints. Include `##KOGNITERM_DONE_MARKER##` detection and non-echo terminal stream parsing.

- [ ] **Step 3: Wire `sidecar.ts` into Electron main entrypoint (`packages/desktop/src/main/index.ts`)**

Initialize sidecar manager on app ready and cleanup on app quit.

- [ ] **Step 4: Commit**

```bash
git add kogniterm-desktop/packages/desktop kogniterm-desktop/packages/app
git commit -m "feat(desktop): implement KogniTerm Server sidecar launcher and API client adapter"
```

---

### Task 4: Build Verification & Final Integration Check

**Files:**
- All packages in `kogniterm-desktop/` and `kogniterm-web/`

- [ ] **Step 1: Run typecheck across `kogniterm-desktop`**

Run: `cd /home/gato/Proyectos/Gemini-Interpreter/kogniterm-desktop && npm run typecheck`
Expected: 0 errors.

- [ ] **Step 2: Run `electron-vite build` for `kogniterm-desktop`**

Run: `cd /home/gato/Proyectos/Gemini-Interpreter/kogniterm-desktop/packages/desktop && npm run build`
Expected: Build output generated in `dist/`.

- [ ] **Step 3: Verify `start-web.sh` execution**

Run: `./start-web.sh --help`
Expected: Options printed, frontend directory points to `kogniterm-web`.

- [ ] **Step 4: Commit**

```bash
git commit -m "chore(desktop): verify KogniTerm Desktop build and web interface decoupling"
```
