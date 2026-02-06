import { useState, useEffect } from 'react';
import { Folder, File, ChevronRight, Home } from 'lucide-react';

interface FileItem {
    name: string;
    path: string;
    isDirectory: boolean;
    size?: number;
}

interface FileExplorerProps {
    workspacePath: string;
}

export const FileExplorer = ({ workspacePath }: FileExplorerProps) => {
    const [files, setFiles] = useState<FileItem[]>([]);
    const [currentPath, setCurrentPath] = useState(workspacePath);
    const [loading, setLoading] = useState(false);

    const loadDirectory = async (path: string) => {
        setLoading(true);
        try {
            const response = await fetch('http://127.0.0.1:8001/api/files/list', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ path }),
            });

            const data = await response.json();
            setFiles(data.items);
            setCurrentPath(data.currentPath);
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
        }
    };

    const formatSize = (bytes?: number) => {
        if (!bytes) return '';
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    };

    return (
        <div className="h-full flex flex-col bg-slate-950">
            {/* Header */}
            <div className="h-12 bg-slate-900/50 border-b border-slate-800 flex items-center px-4 gap-2">
                <button
                    onClick={() => loadDirectory(workspacePath)}
                    className="p-1.5 rounded hover:bg-slate-800 transition-colors"
                    title="Ir al directorio raíz"
                >
                    <Home size={16} className="text-slate-400" />
                </button>
                <span className="text-sm text-slate-400 truncate flex-1">{currentPath}</span>
            </div>

            {/* File List */}
            <div className="flex-1 overflow-y-auto custom-scrollbar">
                {loading ? (
                    <div className="flex items-center justify-center h-32">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                    </div>
                ) : (
                    <div className="p-2">
                        {files.map((item) => (
                            <button
                                key={item.path}
                                onClick={() => handleItemClick(item)}
                                className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-slate-800/50 transition-colors text-left group"
                            >
                                {item.isDirectory ? (
                                    <Folder size={16} className="text-blue-400 flex-shrink-0" />
                                ) : (
                                    <File size={16} className="text-slate-500 flex-shrink-0" />
                                )}
                                <span className="flex-1 text-sm text-slate-300 truncate group-hover:text-slate-100">
                                    {item.name}
                                </span>
                                {!item.isDirectory && item.size !== undefined && (
                                    <span className="text-xs text-slate-500">{formatSize(item.size)}</span>
                                )}
                                {item.isDirectory && (
                                    <ChevronRight size={14} className="text-slate-600 flex-shrink-0" />
                                )}
                            </button>
                        ))}
                        {files.length === 0 && (
                            <div className="text-center py-8 text-slate-500">
                                Directorio vacío
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};
