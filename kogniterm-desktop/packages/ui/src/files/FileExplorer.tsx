import React, { useState, useEffect } from 'react';
import { Folder, File, ChevronRight, Home, RefreshCw, Loader2 } from 'lucide-react';
import { FileItem } from '@kogniterm/types';

export interface FileExplorerProps {
  workspacePath: string;
  serverUrl?: string;
  onFileSelect?: (file: FileItem) => void;
}

export const FileExplorer: React.FC<FileExplorerProps> = ({
  workspacePath,
  serverUrl = 'http://127.0.0.1:8765',
  onFileSelect,
}) => {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [currentPath, setCurrentPath] = useState(workspacePath);
  const [loading, setLoading] = useState(false);

  const loadDirectory = async (path: string) => {
    setLoading(true);
    try {
      const response = await fetch(`${serverUrl}/api/files/list`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ path }),
      });

      const data = await response.json();
      setFiles(data.items || []);
      setCurrentPath(data.currentPath || path);
    } catch (error) {
      console.error('Error loading directory:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDirectory(workspacePath);
  }, [workspacePath]);

  const handleItemClick = (item: FileItem) => {
    if (item.isDirectory) {
      loadDirectory(item.path);
    } else if (onFileSelect) {
      onFileSelect(item);
    }
  };

  const handleNavigateUp = () => {
    const parentPath = currentPath.split('/').slice(0, -1).join('/') || '/';
    loadDirectory(parentPath);
  };

  return (
    <div className="flex flex-col h-full bg-zinc-900 border-r border-zinc-800 text-zinc-300">
      {/* Navigation header */}
      <div className="p-3 border-b border-zinc-800 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <button
            onClick={() => loadDirectory(workspacePath)}
            className="p-1 rounded hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200"
            title="Ir a la raíz"
          >
            <Home size={16} />
          </button>
          <span className="text-xs font-mono truncate text-zinc-400" title={currentPath}>
            {currentPath}
          </span>
        </div>

        <button
          onClick={() => loadDirectory(currentPath)}
          disabled={loading}
          className="p-1 rounded hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 disabled:opacity-50"
          title="Refrescar"
        >
          {loading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
        </button>
      </div>

      {/* Breadcrumb / up folder */}
      {currentPath !== workspacePath && (
        <button
          onClick={handleNavigateUp}
          className="flex items-center gap-2 px-3 py-2 text-xs text-zinc-400 hover:bg-zinc-800/60 border-b border-zinc-800/40 text-left"
        >
          <ChevronRight size={14} className="rotate-180" />
          <span>.. (subir un nivel)</span>
        </button>
      )}

      {/* File list */}
      <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
        {files.length === 0 && !loading && (
          <div className="p-4 text-center text-xs text-zinc-500">Carpeta vacía</div>
        )}

        {files.map((item) => (
          <div
            key={item.path}
            onClick={() => handleItemClick(item)}
            className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs hover:bg-zinc-800/70 cursor-pointer select-none transition-colors group"
          >
            {item.isDirectory ? (
              <Folder size={15} className="text-amber-400 shrink-0" />
            ) : (
              <File size={15} className="text-zinc-400 shrink-0" />
            )}
            <span className="truncate flex-1 font-mono text-zinc-300 group-hover:text-zinc-100">
              {item.name}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};
