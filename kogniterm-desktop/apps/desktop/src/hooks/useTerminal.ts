import { useState, useCallback } from 'react';

export interface CommandResult {
    output: string;
    error?: string;
    exitCode?: number;
}

export function useTerminal() {
    const [isExecuting, setIsExecuting] = useState(false);

    const executeCommand = useCallback(async (command: string): Promise<CommandResult> => {
        setIsExecuting(true);

        try {
            const response = await fetch('http://localhost:8001/api/execute', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ command }),
            });

            const result = await response.json();
            setIsExecuting(false);

            return result;
        } catch (error) {
            setIsExecuting(false);
            return {
                output: '',
                error: error instanceof Error ? error.message : 'Error desconocido',
                exitCode: 1,
            };
        }
    }, []);

    return { executeCommand, isExecuting };
}
