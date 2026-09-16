import { useState, useEffect, useCallback } from 'react';
import { Project } from '../types/project';
import { API_BASE_URL } from '../config/api';

const STORAGE_KEY = 'kogniterm_desktop_projects';

const normalizePath = (p?: string) => (p ? p.replace(/\\/g, '/').replace(/\/+$/, '') : '');

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

  // Fetch workspaces from backend and merge/sync
  const fetchWorkspaces = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/workspaces`);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.workspaces) && data.workspaces.length > 0) {
          setProjects(prev => {
            const prevExpandedMap = new Map<string, boolean>();
            prev.forEach(p => prevExpandedMap.set(normalizePath(p.path), p.isExpanded !== false));

            const synced: Project[] = data.workspaces.map((w: any) => {
              const norm = normalizePath(w.path);
              return {
                id: w.id || `proj-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
                name: w.name || norm.split('/').filter(Boolean).pop() || 'Proyecto',
                path: norm,
                isExpanded: prevExpandedMap.has(norm) ? prevExpandedMap.get(norm)! : true,
                createdAt: new Date().toISOString(),
              };
            });
            localStorage.setItem(STORAGE_KEY, JSON.stringify(synced));
            return synced;
          });
          return;
        }
      }
    } catch (err) {
      console.warn('Backend /api/workspaces no disponible, usando caché local:', err);
    }

    // Fallback: If no projects in backend or offline, initialize with initialPath
    if (initialPath) {
      setProjects(prev => {
        if (prev.length === 0) {
          const normInit = normalizePath(initialPath);
          const folderName = normInit.split('/').filter(Boolean).pop() || 'Workspace';
          const defaultProj: Project = {
            id: `proj-${Date.now()}`,
            name: folderName,
            path: normInit,
            isExpanded: true,
            createdAt: new Date().toISOString(),
          };
          localStorage.setItem(STORAGE_KEY, JSON.stringify([defaultProj]));
          return [defaultProj];
        }
        return prev;
      });
    }
  }, [initialPath]);

  useEffect(() => {
    fetchWorkspaces();
  }, [fetchWorkspaces]);

  const addProject = async (path: string, name?: string): Promise<Project> => {
    const cleanPath = normalizePath(path.trim());
    const existing = projects.find(p => normalizePath(p.path) === cleanPath);
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

    setProjects(prev => {
      const updated = [...prev, newProj];
      localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      return updated;
    });

    try {
      await fetch(`${API_BASE_URL}/api/workspaces`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: cleanPath, name: folderName }),
      });
    } catch (err) {
      console.error('Error registrando workspace en backend:', err);
    }

    return newProj;
  };

  const removeProject = async (id: string) => {
    const target = projects.find(p => p.id === id);
    setProjects(prev => {
      const updated = prev.filter(p => p.id !== id);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      return updated;
    });

    if (target) {
      try {
        await fetch(`${API_BASE_URL}/api/workspaces?path=${encodeURIComponent(target.path)}`, {
          method: 'DELETE',
        });
      } catch (err) {
        console.error('Error eliminando workspace del backend:', err);
      }
    }
  };

  const toggleProjectExpand = (id: string) => {
    setProjects(prev => {
      const updated = prev.map(p => (p.id === id ? { ...p, isExpanded: !p.isExpanded } : p));
      localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      return updated;
    });
  };

  return {
    projects,
    addProject,
    removeProject,
    toggleProjectExpand,
    refreshWorkspaces: fetchWorkspaces,
  };
}
