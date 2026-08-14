import React, { useState } from 'react';
import { Project } from '../../types/project';
import { 
  Sparkles, PanelLeft, Plus, Folder, ChevronDown, ChevronRight, 
  Trash2, Zap, HeartPulse, History, Files, Settings, FolderPlus,
  Filter, Sun, Moon, Monitor
} from 'lucide-react';
import { useTheme } from '../../hooks/useTheme';

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
  const { theme, setTheme } = useTheme();
  const [filterText, setFilterText] = useState('');
  const [isFilterOpen, setIsFilterOpen] = useState(false);

  const toggleThemeQuick = () => {
    if (theme === 'light') setTheme('dark');
    else if (theme === 'dark') setTheme('system');
    else setTheme('light');
  };

  // Helper to normalize path comparison
  const normalizePath = (p?: string) => p ? p.replace(/\\/g, '/').replace(/\/$/, '') : '';

  // Group threads by project path with accurate path matching
  const threadsByProject = React.useMemo(() => {
    const map: Record<string, any[]> = {};
    projects.forEach(p => { 
      map[normalizePath(p.path)] = []; 
    });
    const unmapped: any[] = [];

    threads.forEach(t => {
      const threadWorkspace = normalizePath(t.workspaceDir || t.workspace_dir);
      
      let matchedKey: string | undefined = undefined;
      
      if (threadWorkspace) {
        const normTW = threadWorkspace.toLowerCase();
        matchedKey = Object.keys(map).find(pPath => {
          if (!pPath) return false;
          const normPP = pPath.toLowerCase();
          // 1. Coincidencia exacta de ruta
          if (normPP === normTW) return true;
          // 2. Coincidencia de subdirectorio (el hilo está dentro del proyecto)
          if (normTW.startsWith(normPP + '/')) return true;
          // 3. Coincidencia de nombre de carpeta de último nivel
          const pName = pPath.split('/').filter(Boolean).pop();
          const tName = threadWorkspace.split('/').filter(Boolean).pop();
          return Boolean(pName && tName && pName.toLowerCase() === tName.toLowerCase());
        });
      }

      // Si coincide, añadir a la carpeta del proyecto.
      if (matchedKey && map[matchedKey]) {
        map[matchedKey].push(t);
      } else if (!threadWorkspace && projects.length > 0) {
        // Fallback para hilos sin workspace_dir explícito: asociar al primer proyecto
        const firstKey = normalizePath(projects[0].path);
        if (map[firstKey]) {
          map[firstKey].push(t);
        } else {
          unmapped.push(t);
        }
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
          className="p-1 hover:bg-slate-200/50 rounded-md text-slate-400 hover:text-slate-700 transition-colors ml-auto cursor-pointer"
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
                className="p-1 hover:bg-slate-200/50 rounded text-slate-400 hover:text-slate-600 transition-colors cursor-pointer"
                title="Filtrar proyectos"
              >
                <Filter size={13} />
              </button>
              <button
                onClick={onOpenAddProjectModal}
                className="p-1 hover:bg-slate-200/50 rounded text-slate-400 hover:text-slate-600 transition-colors cursor-pointer"
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
                className="w-full px-2 py-1 text-xs rounded border border-slate-200 focus:outline-none focus:border-indigo-500 bg-white text-slate-800"
              />
            </div>
          )}

          {/* Project List */}
          <div className="flex-1 overflow-y-auto goose-scrollbar px-2 py-1 space-y-1">
            {projects
              .filter(p => p.name.toLowerCase().includes(filterText.toLowerCase()))
              .map(project => {
                const normPath = normalizePath(project.path);
                const projectThreads = threadsByProject.map[normPath] || [];
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
                          className="p-0.5 hover:bg-slate-200/60 rounded text-slate-400 hover:text-slate-700 cursor-pointer"
                          title="Nuevo chat en este proyecto"
                        >
                          <Plus size={12} />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onDeleteProject(project.id);
                          }}
                          className="p-0.5 hover:bg-slate-200/60 rounded text-slate-400 hover:text-rose-600 cursor-pointer"
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
                                className="opacity-0 group-hover:opacity-100 p-0.5 text-slate-400 hover:text-rose-600 transition-all rounded hover:bg-slate-200/60 cursor-pointer"
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
                        className="opacity-0 group-hover:opacity-100 p-0.5 text-slate-400 hover:text-rose-600 transition-all rounded hover:bg-slate-200/60 cursor-pointer"
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

      {/* Footer Settings & Theme */}
      <div className="px-2.5 py-2 border-t border-slate-200/40 dark:border-zinc-800 mt-auto flex flex-col gap-1">
        <div
          onClick={toggleThemeQuick}
          title={`Cambiar tema. Actual: ${theme === 'light' ? 'Claro' : theme === 'dark' ? 'Oscuro' : 'Sistema'}`}
          className={`flex items-center gap-2.5 px-2 py-1.5 text-slate-600 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-zinc-100 hover:bg-slate-200/40 dark:hover:bg-zinc-800/40 rounded-md text-[13px] cursor-pointer transition-colors ${
            isSidebarCollapsed ? 'justify-center px-0' : ''
          }`}
        >
          {theme === 'light' && <Sun size={15} className="text-amber-500 shrink-0" />}
          {theme === 'dark' && <Moon size={15} className="text-indigo-400 shrink-0" />}
          {theme === 'system' && <Monitor size={15} className="text-slate-400 dark:text-zinc-400 shrink-0" />}
          {!isSidebarCollapsed && (
            <span className="flex-1 flex items-center justify-between">
              <span>Tema</span>
              <span className="text-[11px] font-mono capitalize text-slate-400 dark:text-zinc-500">
                {theme === 'light' ? 'Claro' : theme === 'dark' ? 'Oscuro' : 'Sistema'}
              </span>
            </span>
          )}
        </div>

        <div
          onClick={onOpenSettings}
          className={`flex items-center gap-2.5 px-2 py-1.5 text-slate-600 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-zinc-100 hover:bg-slate-200/40 dark:hover:bg-zinc-800/40 rounded-md text-[13px] cursor-pointer transition-colors ${
            isSidebarCollapsed ? 'justify-center px-0' : ''
          }`}
        >
          <Settings size={15} className="text-slate-400 dark:text-zinc-400 shrink-0" />
          {!isSidebarCollapsed && <span>Ajustes</span>}
        </div>
      </div>
    </aside>
  );
};
