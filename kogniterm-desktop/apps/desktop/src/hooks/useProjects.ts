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
  }, [initialPath, projects.length]);

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
