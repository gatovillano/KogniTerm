# Desktop Frontend Projects Sidebar & Multi-Workspace Chat Design

**Date**: 2026-08-14  
**Status**: Approved by User  
**Target Application**: KogniTerm Desktop (`kogniterm-desktop/apps/desktop`)

---

## 1. Overview & Objectives

The goal is to redesign the left sidebar of the KogniTerm Desktop application to support a **Projects (Workspaces)** hierarchy. Users will be able to add local folder paths as "Projects", expand/collapse project folders, manage chats nested within each project, create new chats directly inside a specific workspace, and run concurrent agent sessions across different project directories without interrupting background execution.

Key Features:
- **Projects Accordion Sidebar**: Collapsible list of user-added workspace folders.
- **Add Folder / Project Modal**: Native Tauri OS folder selection dialog with fallback text input.
- **Nested Thread List**: Chat threads displayed under their parent workspace folder with status indicators, relative age (`3d`, `5d`), pin toggles, and context action menus (`...`).
- **Workspace Context Auto-Switching**: Selecting a chat under Project X automatically sets the backend active working directory (`currentDir`) to Project X's root directory.
- **Concurrent Multi-Thread Sessions**: Background agent executions run independently per `thread_id` / `workspace_dir` without blocking UI navigation or other active chats.

---

## 2. Data Models & Local Storage Persistence

### 2.1 Project Model (`src/types/project.ts`)

```typescript
export interface Project {
  id: string;          // Unique project identifier (slug or uuid)
  name: string;        // Display name (e.g. "Gemini-Interpreter")
  path: string;        // Absolute path (e.g. "/home/user/projects/app")
  isExpanded: boolean; // Accordion toggle state in sidebar
  createdAt: string;   // ISO timestamp
}
```

### 2.2 Extended Thread Metadata (`src/types/thread.ts`)

```typescript
export interface ThreadMetadata {
  id: string;
  title: string;
  workspaceDir: string;  // Associated project directory path
  createdAt: string;
  updatedAt: string;
  isPinned?: boolean;
  isExecuting?: boolean; // Active streaming or background execution flag
}
```

### 2.3 Storage Key
- `kogniterm_desktop_projects`: JSON array of `Project` objects persisted in `localStorage`.
- Default project initialized automatically from current workspace path on first launch.

---

## 3. UI Component Architecture

### 3.1 Component Hierarchy
```
App.tsx
├── ProjectsSidebar.tsx
│   ├── ProjectsHeader.tsx (Filter, Add Folder button)
│   ├── ProjectItem.tsx (Folder row + expand toggle + hover actions)
│   │   └── ThreadItem.tsx (Nested chat thread + status dot + context menu)
│   └── SettingsFooter.tsx
├── AddProjectModal.tsx (Dialog for adding new workspace folder)
└── MainChatArea.tsx
```

### 3.2 Component Responsibilities

1. **`ProjectsSidebar.tsx`**:
   - Replaces the flat chat list in the left sidebar.
   - Renders the list of projects from state (`projects`).
   - Renders "Add Project" button triggering `AddProjectModal`.
   - Filters threads by `workspaceDir` and renders them under their matching project header. Hilos sin carpeta explícita o huérfanos se agrupan en una sección por defecto ("General / Otros").

2. **`ProjectItem.tsx`**:
   - Renders folder icon, folder name, expand/collapse arrow.
   - Hover buttons:
     - `+`: Create new chat thread bound to this project path.
     - `⚙`: Project settings / open folder.

3. **`ThreadItem.tsx`**:
   - Renders thread title (truncated).
   - Relative timestamp badge (`3d`, `1w`).
   - Status dot: green pulsing dot when session is active/generating in background.
   - Context menu (`...`) with options to rename or delete thread.

4. **`AddProjectModal.tsx`**:
   - Modal overlay with input field and *"Examinar..."* button.
   - Uses `@tauri-apps/plugin-dialog` or Tauri `open({ directory: true })` command if available, otherwise allows typing/pasting absolute paths.
   - Validates existence of directory before adding to state.

---

## 4. Concurrent Multi-Thread Execution Flow

1. **Independent Session Execution**:
   - `useChat(currentThreadId)` maintains WebSocket and execution state for `currentThreadId`.
   - Background event listener tracks global active execution states (`isGeneratingMap[threadId] = true/false`).

2. **Workspace Context Switching**:
   - When user clicks a thread belonging to Project B:
     - `currentThreadId` is set to Thread B's ID.
     - `currentDir` is updated to Project B's path.
     - Backend API call to `/api/files/list` with path `Project B` updates file explorer and backend working environment.
     - If Thread A in Project A is currently generating, its background execution continues uninterrupted in the backend session pool.

---

## 5. Verification & Testing Plan

1. **Local Project List Persistence**:
   - Add a new folder via Add Project dialog.
   - Refresh desktop app or restart process -> verify added project remains in sidebar.
2. **Project Accordion & Thread Nesting**:
   - Expand/collapse folders.
   - Create thread under Project X -> verify thread appears nested under Project X.
3. **Workspace Switching**:
   - Click thread under Project Y -> verify header location pill updates to Project Y path.
4. **Concurrent Execution**:
   - Send a command/prompt in Thread A (Project A).
   - Immediately switch to Thread B (Project B) -> verify Thread A status indicator shows active execution dot in sidebar and completes successfully.
