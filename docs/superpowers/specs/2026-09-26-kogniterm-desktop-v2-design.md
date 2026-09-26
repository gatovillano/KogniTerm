# Specification: KogniTerm Desktop v2 (OpenCode Fork) & Web UI Migration

- **Date**: 2026-09-26
- **Status**: Approved
- **Scope**: Re-architect `kogniterm-desktop` based on OpenCode (`@opencode-ai/desktop`, `@opencode-ai/app`, `@opencode-ai/ui`) using Electron + SolidJS, while migrating current React desktop UI to `kogniterm-web`.

---

## 1. Overview & Strategy

KogniTerm requires a dedicated, state-of-the-art desktop application (`kogniterm-desktop`) leveraging OpenCode's Electron + SolidJS architecture, while modernizing `kogniterm-web` by transferring the current React UI components into it.

### Objectives:
1. **`kogniterm-web` Modernization**: Move the existing React UI components from `kogniterm-desktop/apps/desktop` and `kogniterm-desktop/packages/ui` into `kogniterm-web/`, replacing the legacy web interface so `kogniterm-web` retains the current desktop aesthetics.
2. **`kogniterm-desktop` v2 Creation**: Scaffold a new monorepo inside `kogniterm-desktop/` based on OpenCode's dev branch (`packages/desktop`, `packages/app`, `packages/ui`) using Electron, SolidJS, and `electron-vite`.
3. **`kogniterm server` Integration**: Connect the desktop application to `kogniterm server` (`python -m kogniterm.server`) via a hybrid sidecar launcher in Electron.

---

## 2. System Architecture

```
                               ┌─────────────────────────────────────────┐
                               │       KogniTerm Desktop (Electron)      │
                               │  ┌───────────────────────────────────┐  │
                               │  │ SolidJS Frontend (@kogniterm/app) │  │
                               │  └─────────────────┬─────────────────┘  │
                               │                    │ IPC / HTTP / WS    │
                               │  ┌─────────────────▼─────────────────┐  │
                               │  │ Sidecar Launcher (sidecar.ts)     │  │
                               │  └─────────────────┬─────────────────┘  │
                               └────────────────────┼────────────────────┘
                                                    │
                                                    │ Spawns or connects to
                                                    ▼
┌──────────────────┐               ┌─────────────────────────────────────┐
│  KogniTerm Web   │ HTTP / WS     │          KogniTerm Server           │
│  (React / Vite)  ├──────────────►│    python -m kogniterm.server       │
└──────────────────┘               └─────────────────────────────────────┘
```

---

## 3. Detailed Component Specification

### Phase 1: `kogniterm-web` Migration
- **Source**: `kogniterm-desktop/apps/desktop` (React + Tailwind + Lucide icons + Xterm) and `kogniterm-desktop/packages/ui`.
- **Target**: `kogniterm-web/`
- **Actions**:
  - Copy React UI components, styles, hooks, and types into `kogniterm-web/`.
  - Configure `kogniterm-web/package.json` and `vite.config.ts` so `kogniterm-web` builds independently to `kogniterm-web/dist`.
  - Update `start-web.sh` to explicitly serve `kogniterm-web/dist` on port 3000 without depending on `kogniterm-desktop`.

### Phase 2: `kogniterm-desktop` OpenCode Architecture
- **Structure**: Monorepo with workspaces managed by `turbo` and `bun`/`npm`/`pnpm`:
  - **`packages/desktop`** (`@kogniterm/desktop`):
    - `src/main`: Electron main process (`index.ts`, `windows.ts`, `sidecar.ts`, `ipc.ts`, `menu.ts`).
    - `src/preload`: IPC bridge exposed via `contextBridge`.
    - `src/renderer`: Entry point for SolidJS renderer app.
    - Build toolchain: `electron.vite.config.ts`, `electron-builder.config.ts`.
  - **`packages/app`** (`@kogniterm/app`):
    - SolidJS desktop UI adapted from OpenCode `packages/app`.
    - `src/api/client.ts`: `KogniTermClient` communicating with `kogniterm server` REST & WebSocket APIs.
    - Components for sessions, agent selector, command palette (`Cmd+K`), code diff viewer, and terminal panels.
  - **`packages/ui`** (`@kogniterm/ui`):
    - KogniTerm SolidJS design system (buttons, modals, theme providers, dark/light modes, KogniTerm SVGs/logos).

---

## 4. Sidecar & Backend Protocol

### 4.1 `sidecar.ts` Lifecycle Manager
1. **Probe Phase**: Checks if `http://127.0.0.1:8765/health` is active.
2. **Launch Phase**: If offline, spawns `python -m kogniterm.server --host 127.0.0.1 --port 8765` as an Electron sub-process.
3. **Shutdown Phase**: Sends `SIGTERM`/`SIGINT` to the spawned Python process upon Electron window close.

### 4.2 Terminal & Stream Parsing Rules
- In accordance with `AGENTS.md` rules for pseudo-terminals and non-echo environments:
  - All terminal output parsers in `packages/app` MUST strictly filter command echoes and verify completion using the clean marker `##KOGNITERM_DONE_MARKER##` to prevent terminal deadlocks.

---

## 5. Verification & Acceptance Criteria

1. **`kogniterm-web`**:
   - `npm run build` inside `kogniterm-web` succeeds.
   - Running `./start-web.sh` serves the updated web UI correctly.
2. **`kogniterm-desktop`**:
   - `npm run typecheck` passes across `desktop`, `app`, and `ui` packages.
   - `npm run dev` / `npm run build` launches Electron with OpenCode's visual styling and successfully connects to `kogniterm server`.
