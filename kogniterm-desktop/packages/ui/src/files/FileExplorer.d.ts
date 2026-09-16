import React from 'react';
import { FileItem } from '@kogniterm/types';
export interface FileExplorerProps {
    workspacePath: string;
    serverUrl?: string;
    onFileSelect?: (file: FileItem) => void;
}
export declare const FileExplorer: React.FC<FileExplorerProps>;
//# sourceMappingURL=FileExplorer.d.ts.map