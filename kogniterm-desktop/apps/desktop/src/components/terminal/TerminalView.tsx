import React, { useRef, useCallback } from 'react';
import { Terminal } from './Terminal';
import { useTerminal } from '../../hooks/useTerminal';

export const TerminalView: React.FC = () => {
    const { executeCommand, isExecuting } = useTerminal();
    const terminalRef = useRef<any>(null);

    const handleCommand = useCallback(async (command: string) => {
        // Mostrar que el comando se está ejecutando
        if ((window as any).writeToTerminal) {
            (window as any).writeToTerminal(`\x1b[90mEjecutando: ${command}\x1b[0m`);
        }

        const result = await executeCommand(command);

        // Mostrar resultado
        if ((window as any).writeToTerminal) {
            if (result.output) {
                (window as any).writeToTerminal(result.output);
            }
            if (result.error) {
                (window as any).writeToTerminal(`\x1b[31m${result.error}\x1b[0m`);
            }
        }
    }, [executeCommand]);

    return (
        <div className="h-full w-full flex flex-col">
            <div className="h-12 bg-slate-900/50 border-b border-slate-800 flex items-center px-4">
                <div className="flex items-center gap-2">
                    <div className="h-3 w-3 rounded-full bg-red-500"></div>
                    <div className="h-3 w-3 rounded-full bg-yellow-500"></div>
                    <div className="h-3 w-3 rounded-full bg-green-500"></div>
                </div>
                <span className="ml-4 text-sm text-slate-400">Terminal</span>
                {isExecuting && (
                    <span className="ml-auto text-xs text-blue-400 animate-pulse">Ejecutando...</span>
                )}
            </div>
            <div className="flex-1 overflow-hidden">
                <Terminal ref={terminalRef} onCommand={handleCommand} />
            </div>
        </div>
    );
};
