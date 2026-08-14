import React, { useState } from 'react';
import { FolderPlus, X, Check, HardDrive } from 'lucide-react';

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
      const windowTauri = (window as any).__TAURI__;
      if (windowTauri?.dialog?.open) {
        const selected = await windowTauri.dialog.open({
          directory: true,
          multiple: false,
          title: 'Seleccionar Carpeta de Proyecto',
        });
        if (selected && typeof selected === 'string') {
          setFolderPath(selected);
          setError('');
        }
      } else {
        const moduleName = '@tauri-apps/plugin-dialog';
        // @ts-ignore
        const dialog = await import(/* @vite-ignore */ moduleName);
        if (dialog?.open) {
          const selected = await dialog.open({
            directory: true,
            multiple: false,
            title: 'Seleccionar Carpeta de Proyecto',
          });
          if (selected && typeof selected === 'string') {
            setFolderPath(selected);
            setError('');
          }
        }
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
                onClick={handleBrowseNative}
                className="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors border border-slate-200 shrink-0 cursor-pointer"
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
