import React, { useState, useRef, useEffect } from 'react';
import { FolderPlus, X, Check, HardDrive, Folder, ChevronRight, ArrowUp } from 'lucide-react';

interface AddProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAddProject: (path: string) => void;
}

interface DirectoryItem {
  name: string;
  path: string;
  isDirectory: boolean;
}

export const AddProjectModal: React.FC<AddProjectModalProps> = ({
  isOpen,
  onClose,
  onAddProject,
}) => {
  const [folderPath, setFolderPath] = useState('');
  const [error, setError] = useState('');
  const [isVerifying, setIsVerifying] = useState(false);
  const [showBrowser, setShowBrowser] = useState(false);
  const [browserItems, setBrowserItems] = useState<DirectoryItem[]>([]);
  const [browserPath, setBrowserPath] = useState('');
  const [loadingBrowser, setLoadingBrowser] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!isOpen) {
      setFolderPath('');
      setError('');
      setShowBrowser(false);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const loadDirectory = async (path: string) => {
    setLoadingBrowser(true);
    try {
      const res = await fetch('http://127.0.0.1:8765/api/files/list', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: path || '.' }),
      });
      const data = await res.json();
      if (data.items) {
        // Filter only directories
        const dirs = data.items.filter((item: DirectoryItem) => item.isDirectory);
        setBrowserItems(dirs);
        setBrowserPath(data.currentPath);
        setFolderPath(data.currentPath);
      }
    } catch (err) {
      console.error('Error loading directory:', err);
    } finally {
      setLoadingBrowser(false);
    }
  };

  const handleBrowse = async () => {
    // 1. Try triggering native OS HTML directory picker
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }

    // 2. Toggle inline folder navigator
    setShowBrowser(prev => {
      const next = !prev;
      if (next) {
        loadDirectory(folderPath || '.');
      }
      return next;
    });
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      const firstFile = files[0] as any;
      if (firstFile.path) {
        const fullFilePath = firstFile.path;
        const relativePath = firstFile.webkitRelativePath;
        if (fullFilePath && relativePath) {
          const dirPath = fullFilePath.substring(0, fullFilePath.length - relativePath.length).replace(/[\/\\]$/, '');
          if (dirPath) {
            setFolderPath(dirPath);
            setError('');
            return;
          }
        }
        const lastSlash = Math.max(fullFilePath.lastIndexOf('/'), fullFilePath.lastIndexOf('\\'));
        if (lastSlash > 0) {
          setFolderPath(fullFilePath.substring(0, lastSlash));
          setError('');
          return;
        }
      }
    }
  };

  const handleNavigateUp = () => {
    if (!browserPath) return;
    const parts = browserPath.split('/').filter(Boolean);
    parts.pop();
    const parentPath = '/' + parts.join('/');
    loadDirectory(parentPath || '/');
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
      onAddProject(folderPath.trim());
      setFolderPath('');
      onClose();
    } finally {
      setIsVerifying(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs animate-in fade-in duration-150">
      {/* Hidden file input for native OS folder picker */}
      <input
        ref={fileInputRef}
        type="file"
        // @ts-ignore
        webkitdirectory=""
        directory=""
        style={{ display: 'none' }}
        onChange={handleFileInputChange}
      />

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
            className="p-1 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer"
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
                  className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 font-mono text-slate-800 bg-white"
                />
              </div>
              <button
                type="button"
                onClick={handleBrowse}
                className="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors border border-slate-200 shrink-0 cursor-pointer"
                title="Examinar carpetas locales"
              >
                <HardDrive size={14} />
                <span>{showBrowser ? 'Ocultar' : 'Examinar'}</span>
              </button>
            </div>
            {error && <p className="text-[11px] text-rose-500 font-medium">{error}</p>}
          </div>

          {/* Inline Folder Browser */}
          {showBrowser && (
            <div className="border border-slate-200 rounded-lg p-2 bg-slate-50 space-y-2 max-h-48 overflow-hidden flex flex-col">
              <div className="flex items-center justify-between text-[11px] text-slate-500 border-b border-slate-200/60 pb-1">
                <span className="font-mono truncate max-w-[280px]" title={browserPath}>
                  {browserPath || '/'}
                </span>
                <button
                  type="button"
                  onClick={handleNavigateUp}
                  className="p-1 hover:bg-slate-200 rounded text-slate-600 flex items-center gap-1 cursor-pointer"
                  title="Subir de nivel"
                >
                  <ArrowUp size={12} />
                  <span className="text-[10px]">Subir</span>
                </button>
              </div>

              <div className="flex-1 overflow-y-auto space-y-0.5 goose-scrollbar">
                {loadingBrowser ? (
                  <div className="p-2 text-xs text-slate-400 italic">Cargando carpetas...</div>
                ) : browserItems.length === 0 ? (
                  <div className="p-2 text-xs text-slate-400 italic">Sin subcarpetas</div>
                ) : (
                  browserItems.map((item) => (
                    <div
                      key={item.path}
                      onClick={() => loadDirectory(item.path)}
                      className="flex items-center justify-between px-2 py-1 hover:bg-slate-200/60 rounded cursor-pointer text-xs text-slate-700 transition-colors"
                    >
                      <div className="flex items-center gap-1.5 truncate">
                        <Folder size={13} className="text-slate-400 shrink-0" />
                        <span className="truncate">{item.name}</span>
                      </div>
                      <ChevronRight size={12} className="text-slate-400 shrink-0" />
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          {/* Footer Buttons */}
          <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="px-3.5 py-1.5 rounded-lg text-xs font-medium text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={isVerifying || !folderPath.trim()}
              className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors shadow-xs cursor-pointer"
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
