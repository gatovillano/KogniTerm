import { useState, useCallback, useRef } from 'react';

export interface TerminalEventState {
  isOpen: boolean;
  sessionLabel: string;
  toolName: string;
  command: string;
  output: string;
}

export function useTerminalSidebar() {
  const [terminalState, setTerminalState] = useState<TerminalEventState>({
    isOpen: false,
    sessionLabel: 'Terminal PTY',
    toolName: '',
    command: '',
    output: '',
  });
  const isFirstOpen = useRef(true);

  const openTerminal = useCallback((label: string, toolName: string, command?: string) => {
    setTerminalState((prev) => ({
      ...prev,
      isOpen: true,
      sessionLabel: label,
      toolName: toolName,
      command: command || '',
      output: '',
    }));
    isFirstOpen.current = false;
  }, []);

  const appendOutput = useCallback((text: string) => {
    setTerminalState((prev) => ({
      ...prev,
      output: prev.output + text,
    }));
  }, []);

  const closeTerminal = useCallback(() => {
    setTerminalState((prev) => ({ ...prev, isOpen: false }));
  }, []);

  const isTerminalOpen = terminalState.isOpen;

  return {
    isTerminalOpen,
    terminalState,
    openTerminal,
    appendOutput,
    closeTerminal,
  };
}
