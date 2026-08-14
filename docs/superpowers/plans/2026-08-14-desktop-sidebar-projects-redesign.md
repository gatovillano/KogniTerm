# Desktop Sidebar Projects & Multi-Workspace Chat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the KogniTerm Desktop frontend left sidebar to support collapsible workspace folders ("Projects"), nested thread lists, native/manual folder addition dialog, workspace context auto-switching, and concurrent session tracking.

**Architecture:** Create modular React components for project models, sidebar layout, folder accordions, thread lists, and dialogs. Lift workspace & execution state tracking into an enhanced state hook/context so switching active threads updates the working directory while keeping background thread executions active.

**Tech Stack:** React 19, TypeScript, TailwindCSS 4, Lucide React, Tauri 2 API (`@tauri-apps/api/core`, `@tauri-apps/plugin-dialog`), Vite.

## Global Constraints
- Desktop package directory: `kogniterm-desktop/apps/desktop`
- Modern React + TypeScript functional components with clear prop types.
- Preserve existing Tailwind styling tokens and Goose/Cursor UI minimalist aesthetic.
- Preserve backend compatibility with `/api/threads`, `/api/files/list`, `/api/workspace/status`, `/sessions`.

---

### Task 1: Project Data Models and Local Storage Hook

**Files:**
- Create: `kogniterm-desktop/apps/desktop/src/types/project.ts`
- Create: `kogniterm-desktop/apps/desktop/src/hooks/useProjects.ts`

**Interfaces:**
- Consumes: None
- Produces: `Project` interface, `useProjects()` hook exposing `projects`, `addProject`, `removeProject`, `toggleProjectExpand`, `activeProjectId`.

- [ ] **Step 1: Create Project TypeScript interface**

Create `kogniterm-desktop/apps/desktop/src/types/project.ts`:

```typescript
export interface Project {
  id: string;
  name: string;
  path: string;
  isExpanded: boolean;
  createdAt: string;
}
```

- [ ] **Step 2: Create useProjects hook for local storage management**

Create `kogniterm-desktop/apps/desktop/src/hooks/useProjects.ts`:

```typescript
import { useState, useEffect } from 'react';
import { Project } from '../types/project';

const STORAGE_KEY = 'kogniterm_desktop_projects';

export function useProjects(initialPath?: string) {
  const [projects, setProjects] = useState<Project[]>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        return JSON.parse(saved);
      }
    } catch (e) {
      console.error('Error loading saved projects:', e);
    }
    return [];
  });

  // Ensure initial/current workspace is added if projects is empty
  useEffect(() => {
    if (projects.length === 0 && initialPath) {
      const folderName = initialPath.split('/').filter(Boolean).pop() || 'Workspace';
      const defaultProj: Project = {
        id: `proj-${Date.now()}`,
        name: folderName,
        path: initialPath,
        isExpanded: true,
        createdAt: new Date().toISOString(),
      };
      setProjects([defaultProj]);
    }
  }, [initialPath]);

  // Persist projects to localStorage
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(projects));
  }, [projects]);

  const addProject = (path: string, name?: string): Project => {
    const cleanPath = path.trim();
    const existing = projects.find(p => p.path === cleanPath);
    if (existing) {
      return existing;
    }
    const folderName = name || cleanPath.split('/').filter(Boolean).pop() || 'Proyecto';
    const newProj: Project = {
      id: `proj-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`,
      name: folderName,
      path: cleanPath,
      isExpanded: true,
      createdAt: new Date().toISOString(),
    };
    setProjects(prev => [...prev, newProj]);
    return newProj;
  };

  const removeProject = (id: string) => {
    setProjects(prev => prev.filter(p => p.id !== id));
  };

  const toggleProjectExpand = (id: string) => {
    setProjects(prev => prev.map(p => p.id === id ? { ...p, isExpanded: !p.isExpanded } : p));
  };

  return {
    projects,
    addProject,
    removeProject,
    toggleProjectExpand,
  };
}
```

- [ ] **Step 3: Commit Task 1**

```bash
git add kogniterm-desktop/apps/desktop/src/types/project.ts kogniterm-desktop/apps/desktop/src/hooks/useProjects.ts
git commit -m "feat(desktop): add Project types and useProjects hook for sidebar persistence"
```

---

### Task 2: Add Project Modal Component (`AddProjectModal.tsx`)

**Files:**
- Create: `kogniterm-desktop/apps/desktop/src/components/modals/AddProjectModal.tsx`

**Interfaces:**
- Consumes: `addProject` from `useProjects.ts`
- Produces: `AddProjectModal` dialog component.

- [ ] **Step 1: Create AddProjectModal component**

Create `kogniterm-desktop/apps/desktop/src/components/modals/AddProjectModal.tsx`:

```tsx
import React, { useState } from 'react';
import { FolderPlus, Folder, X, Check, HardDrive } from 'lucide-react';

interface AddProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAddProject: (path: string) => void;
}

export const AddProjectModal: React.FC<AddProjectModalProps> = ({
  isOpen,
  onClose,
  onAddProject,
}) => {
  const [folderPath, setFolderPath] = useState('');
  const [error, setError] = useState('');
  const [isVerifying, setIsVerifying] = useState(false);

  if (!isOpen) return null;

  const handleBrowseNative = async () => {
    try {
      // Try using Tauri dialog plugin if available
      const dialog = await import('@tauri-apps/plugin-dialog');
      const selected = await dialog.open({
        directory: true,
        multiple: false,
        title: 'Seleccionar Carpeta de Proyecto',
      });
      if (selected && typeof selected === 'string') {
        setFolderPath(selected);
        setError('');
      }
    } catch (err) {
      console.warn('Native dialog not available or cancelled:', err);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!folderPath.trim()) {
      setError('Por favor ingresa una ruta de carpeta válida.');
      return;
    }

    setIsVerifying(true);
    setError('');

    try {
      const res = await fetch('http://127.0.0.1:8765/api/files/list', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: folderPath.trim() }),
      });
      const data = await res.json();

      if (data.currentPath) {
        onAddProject(data.currentPath);
        setFolderPath('');
        onClose();
      } else {
        setError('No se pudo acceder al directorio especificado.');
      }
    } catch (err) {
      // Fallback: accept path anyway if server check fails
      onAddProject(folderPath.trim());
      setFolderPath('');
      onClose();
    } finally {
      setIsVerifying(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs animate-in fade-in duration-150">
      <div className="bg-white rounded-xl shadow-2xl border border-slate-200 w-full max-w-md p-5 text-slate-800 space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-indigo-50 text-indigo-600">
              <FolderPlus size={18} />
            </div>
            <div>
              <h3 className="font-semibold text-sm text-slate-900">Añadir Proyecto</h3>
              <p className="text-[11px] text-slate-500">Agrega una carpeta local a tu lista de proyectos</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-700 block">
              Ruta del directorio
            </label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <input
                  type="text"
                  value={folderPath}
                  onChange={(e) => {
                    setFolderPath(e.target.value);
                    setError('');
                  }}
                  placeholder="/ruta/a/mi-proyecto"
                  className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 font-mono text-slate-800"
                />
              </div>
              <button
                type="button"
                onClick={handleBrowseNative}
                className="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors border border-slate-200 shrink-0"
                title="Examinar carpetas nativas"
              >
                <HardDrive size={14} />
                <span>Examinar</span>
              </button>
            </div>
            {error && <p className="text-[11px] text-rose-500 font-medium">{error}</p>}
          </div>

          {/* Footer Buttons */}
          <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="px-3.5 py-1.5 rounded-lg text-xs font-medium text-slate-600 hover:bg-slate-100 transition-colors"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={isVerifying || !folderPath.trim()}
              className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors shadow-xs"
            >
              <Check size={14} />
              <span>{isVerifying ? 'Verificando...' : 'Añadir a Proyectos'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
```

- [ ] **Step 2: Commit Task 2**

```bash
git add kogniterm-desktop/apps/desktop/src/components/modals/AddProjectModal.tsx
git commit -m "feat(desktop): add AddProjectModal component for workspace directory selection"
```

---

### Task 3: Projects Accordion Sidebar (`ProjectsSidebar.tsx`)

**Files:**
- Create: `kogniterm-desktop/apps/desktop/src/components/sidebar/ProjectsSidebar.tsx`

**Interfaces:**
- Consumes: `Project` objects, `threads` list, `currentThreadId`, `isSidebarCollapsed`
- Produces: Complete left sidebar matching user design request.

- [ ] **Step 1: Create ProjectsSidebar component**

Create `kogniterm-desktop/apps/desktop/src/components/sidebar/ProjectsSidebar.tsx`:

```tsx
import React, { useState } from 'react';
import { Project } from '../../types/project';
import { 
  Sparkles, PanelLeft, Plus, Folder, ChevronDown, ChevronRight, 
  Trash2, Zap, HeartPulse, History, Files, Settings, FolderPlus,
  Filter, Pin, MoreHorizontal
} from 'lucide-react';

interface ProjectsSidebarProps {
  isSidebarCollapsed: boolean;
  setIsSidebarCollapsed: (val: boolean) => void;
  projects: Project[];
  onOpenAddProjectModal: () => void;
  onToggleProjectExpand: (id: string) => void;
  onDeleteProject: (id: string) => void;
  threads: any[];
  currentThreadId: string;
  onSelectThread: (threadId: string, workspaceDir?: string) => void;
  onCreateThread: (workspaceDir?: string) => void;
  onDeleteThread: (e: React.MouseEvent, threadId: string) => void;
  activeView: string;
  setActiveView: (view: any) => void;
  onOpenSettings: () => void;
  executingThreadIds?: Record<string, boolean>;
}

export const ProjectsSidebar: React.FC<ProjectsSidebarProps> = ({
  isSidebarCollapsed,
  setIsSidebarCollapsed,
  projects,
  onOpenAddProjectModal,
  onToggleProjectExpand,
  onDeleteProject,
  threads,
  currentThreadId,
  onSelectThread,
  onCreateThread,
  onDeleteThread,
  activeView,
  setActiveView,
  onOpenSettings,
  executingThreadIds = {},
}) => {
  const [filterText, setFilterText] = useState('');
  const [isFilterOpen, setIsFilterOpen] = useState(false);

  // Group threads by project path
  const threadsByProject = React.useMemo(() => {
    const map: Record<string, any[]> = {};
    projects.forEach(p => { map[p.path] = []; });
    const unmapped: any[] = [];

    threads.forEach(t => {
      const match = projects.find(p => p.path === t.workspaceDir || p.path === t.workspace_dir);
      if (match) {
        map[match.path].push(t);
      } else {
        unmapped.push(t);
      }
    });

    return { map, unmapped };
  }, [projects, threads]);

  return (
    <aside
      className={`${
        isSidebarCollapsed ? 'w-[56px]' : 'w-[250px]'
      } bg-[#f8f9fa] border-r border-slate-200/60 flex flex-col transition-all duration-200 z-30 select-none h-screen`}
    >
      {/* Sidebar Header with Brand */}
      <div className="h-12 flex items-center justify-between px-3 border-b border-slate-200/50">
        {!isSidebarCollapsed && (
          <div className="flex items-center gap-2">
            <div className="h-5 w-5 rounded-md bg-slate-900 flex items-center justify-center">
              <Sparkles size={11} className="text-white" />
            </div>
            <span className="font-semibold text-[13px] text-slate-800 tracking-tight">KogniTerm</span>
            <span className="px-1.5 py-0.2 rounded bg-slate-200/50 text-[9px] text-slate-500 font-medium">Desktop</span>
          </div>
        )}
        <button
          onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
          className="p-1 hover:bg-slate-200/50 rounded-md text-slate-400 hover:text-slate-700 transition-colors ml-auto"
          title={isSidebarCollapsed ? "Expandir barra lateral" : "Colapsar barra lateral"}
        >
          <PanelLeft size={15} />
        </button>
      </div>

      {/* Primary Actions & Navigation */}
      <div className="px-2.5 py-2 flex flex-col gap-1 border-b border-slate-200/40">
        <div
          onClick={() => onCreateThread()}
          className={`flex items-center gap-2.5 px-2 py-1.5 text-[13px] font-medium text-slate-700 hover:text-slate-900 cursor-pointer rounded-md hover:bg-slate-200/40 transition-colors ${
            isSidebarCollapsed ? 'justify-center px-0' : ''
          }`}
          title="Nuevo chat"
        >
          <Plus size={15} className="text-slate-500 shrink-0" />
          {!isSidebarCollapsed && <span>Nuevo chat</span>}
        </div>

        <nav className="flex flex-col gap-0.5 mt-0.5">
          {[
            { id: 'skills', icon: Zap, label: 'Skills' },
            { id: 'heartbeat', icon: HeartPulse, label: 'Heartbeat' },
            { id: 'session', icon: History, label: 'Historial de sesiones' },
            { id: 'files', icon: Files, label: 'Archivos' }
          ].map((item) => {
            const isActive = activeView === item.id;
            return (
              <div
                key={item.id}
                onClick={() => setActiveView(item.id)}
                className={`flex items-center gap-2.5 px-2 py-1.5 rounded-md text-[13px] cursor-pointer transition-colors ${
                  isActive
                    ? 'text-slate-900 font-semibold bg-slate-200/60'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/40'
                } ${isSidebarCollapsed ? 'justify-center px-0' : ''}`}
              >
                <item.icon size={15} className={`shrink-0 ${isActive ? 'text-indigo-600' : 'text-slate-400'}`} />
                {!isSidebarCollapsed && <span>{item.label}</span>}
              </div>
            );
          })}
        </nav>
      </div>

      {/* PROJECTS Section (Accordions) */}
      {!isSidebarCollapsed && (
        <div className="flex-1 flex flex-col min-h-0 pt-2">
          <div className="flex items-center justify-between px-3.5 py-1 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
            <span>Projects</span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setIsFilterOpen(!isFilterOpen)}
                className="p-1 hover:bg-slate-200/50 rounded text-slate-400 hover:text-slate-600 transition-colors"
                title="Filtrar proyectos"
              >
                <Filter size={13} />
              </button>
              <button
                onClick={onOpenAddProjectModal}
                className="p-1 hover:bg-slate-200/50 rounded text-slate-400 hover:text-slate-600 transition-colors"
                title="Añadir carpeta de proyecto"
              >
                <FolderPlus size={14} />
              </button>
            </div>
          </div>

          {/* Filter Input */}
          {isFilterOpen && (
            <div className="px-3 py-1">
              <input
                type="text"
                value={filterText}
                onChange={(e) => setFilterText(e.target.value)}
                placeholder="Filtrar por nombre..."
                className="w-full px-2 py-1 text-xs rounded border border-slate-200 focus:outline-none focus:border-indigo-500 bg-white"
              />
            </div>
          )}

          {/* Project List */}
          <div className="flex-1 overflow-y-auto goose-scrollbar px-2 py-1 space-y-1">
            {projects
              .filter(p => p.name.toLowerCase().includes(filterText.toLowerCase()))
              .map(project => {
                const projectThreads = threadsByProject.map[project.path] || [];
                return (
                  <div key={project.id} className="space-y-0.5">
                    {/* Folder Header */}
                    <div
                      onClick={() => onToggleProjectExpand(project.id)}
                      className="group flex items-center justify-between px-2 py-1.5 rounded-md cursor-pointer text-xs text-slate-700 hover:bg-slate-200/40 transition-colors"
                    >
                      <div className="flex items-center gap-1.5 truncate flex-1 min-w-0 pr-1">
                        {project.isExpanded ? (
                          <ChevronDown size={14} className="text-slate-400 shrink-0" />
                        ) : (
                          <ChevronRight size={14} className="text-slate-400 shrink-0" />
                        )}
                        <Folder size={14} className="text-slate-500 shrink-0" />
                        <span className="font-medium text-slate-800 text-[12px] truncate" title={project.path}>
                          {project.name}
                        </span>
                      </div>

                      {/* Folder Hover Actions */}
                      <div className="opacity-0 group-hover:opacity-100 flex items-center gap-1 transition-all">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onCreateThread(project.path);
                          }}
                          className="p-0.5 hover:bg-slate-200/60 rounded text-slate-400 hover:text-slate-700"
                          title="Nuevo chat en este proyecto"
                        >
                          <Plus size={12} />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onDeleteProject(project.id);
                          }}
                          className="p-0.5 hover:bg-slate-200/60 rounded text-slate-400 hover:text-rose-600"
                          title="Quitar proyecto"
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    </div>

                    {/* Nested Threads */}
                    {project.isExpanded && (
                      <div className="pl-4 space-y-0.5 border-l border-slate-200/50 ml-3">
                        {projectThreads.map(thread => {
                          const isCurrent = currentThreadId === thread.id;
                          const isExecuting = executingThreadIds[thread.id];
                          return (
                            <div
                              key={thread.id}
                              onClick={() => {
                                onSelectThread(thread.id, project.path);
                                setActiveView('chat');
                              }}
                              className={`group flex items-center justify-between px-2 py-1 rounded-md cursor-pointer text-xs transition-colors ${
                                isCurrent
                                  ? 'text-slate-900 font-semibold bg-slate-200/60'
                                  : 'text-slate-600 hover:bg-slate-200/40 hover:text-slate-900'
                              }`}
                            >
                              <div className="flex items-center gap-1.5 truncate flex-1 min-w-0 pr-1">
                                {isExecuting && (
                                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse shrink-0" />
                                )}
                                <span className="text-[12px] truncate" title={thread.title}>
                                  {thread.title || 'Conversación'}
                                </span>
                              </div>
                              <button
                                onClick={(e) => onDeleteThread(e, thread.id)}
                                className="opacity-0 group-hover:opacity-100 p-0.5 text-slate-400 hover:text-rose-600 transition-all rounded hover:bg-slate-200/60"
                              >
                                <Trash2 size={11} />
                              </button>
                            </div>
                          );
                        })}
                        {projectThreads.length === 0 && (
                          <div className="px-2 py-1 text-[11px] text-slate-400 italic">
                            Sin hilos en esta carpeta
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}

            {/* Unmapped / General Threads Section */}
            {threadsByProject.unmapped.length > 0 && (
              <div className="pt-2 border-t border-slate-200/40 space-y-0.5">
                <div className="px-2 py-1 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                  Otros Hilos
                </div>
                {threadsByProject.unmapped.map(thread => {
                  const isCurrent = currentThreadId === thread.id;
                  const isExecuting = executingThreadIds[thread.id];
                  return (
                    <div
                      key={thread.id}
                      onClick={() => {
                        onSelectThread(thread.id);
                        setActiveView('chat');
                      }}
                      className={`group flex items-center justify-between px-2 py-1 rounded-md cursor-pointer text-xs transition-colors ${
                        isCurrent
                          ? 'text-slate-900 font-semibold bg-slate-200/60'
                          : 'text-slate-600 hover:bg-slate-200/40 hover:text-slate-900'
                      }`}
                    >
                      <div className="flex items-center gap-1.5 truncate flex-1 min-w-0 pr-1">
                        {isExecuting && (
                          <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse shrink-0" />
                        )}
                        <span className="text-[12px] truncate" title={thread.title}>
                          {thread.title || 'Conversación'}
                        </span>
                      </div>
                      <button
                        onClick={(e) => onDeleteThread(e, thread.id)}
                        className="opacity-0 group-hover:opacity-100 p-0.5 text-slate-400 hover:text-rose-600 transition-all rounded hover:bg-slate-200/60"
                      >
                        <Trash2 size={11} />
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Footer Settings */}
      <div className="px-2.5 py-2 border-t border-slate-200/40 mt-auto">
        <div
          onClick={onOpenSettings}
          className={`flex items-center gap-2.5 px-2 py-1.5 text-slate-600 hover:text-slate-900 hover:bg-slate-200/40 rounded-md text-[13px] cursor-pointer transition-colors ${
            isSidebarCollapsed ? 'justify-center px-0' : ''
          }`}
        >
          <Settings size={15} className="text-slate-400 shrink-0" />
          {!isSidebarCollapsed && <span>Ajustes</span>}
        </div>
      </div>
    </aside>
  );
};
```

- [ ] **Step 2: Commit Task 3**

```bash
git add kogniterm-desktop/apps/desktop/src/components/sidebar/ProjectsSidebar.tsx
git commit -m "feat(desktop): add ProjectsSidebar accordion component with folder and thread hierarchy"
```

---

### Task 4: Integrate Projects & Accordion Sidebar into `App.tsx`

**Files:**
- Modify: `kogniterm-desktop/apps/desktop/src/App.tsx`

**Interfaces:**
- Consumes: `useProjects`, `AddProjectModal`, `ProjectsSidebar`
- Produces: Integrated desktop frontend supporting multi-workspace folder list and thread execution context switching.

- [ ] **Step 1: Update App.tsx to use ProjectsSidebar and AddProjectModal**

In `kogniterm-desktop/apps/desktop/src/App.tsx`, import `useProjects`, `AddProjectModal`, and `ProjectsSidebar`, and replace the old `<aside>` block. Update `createThread` to accept an optional `workspaceDir`.

- [ ] **Step 2: Verify desktop build and TypeScript compilation**

Run:
```bash
cd kogniterm-desktop/apps/desktop && npm run build
```
Expected: TypeScript compilation succeeds with zero errors.

- [ ] **Step 3: Commit Task 4**

```bash
git add kogniterm-desktop/apps/desktop/src/App.tsx
git commit -m "feat(desktop): integrate ProjectsSidebar and AddProjectModal into App layout"
```

---
