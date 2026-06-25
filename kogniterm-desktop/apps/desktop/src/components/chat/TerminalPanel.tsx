import React, { useEffect, useRef, useState } from 'react';
import { Terminal as XTerminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import '@xterm/xterm/css/xterm.css';
import { Terminal, X, Minimize2, Maximize2 } from 'lucide-react';

export interface TerminalEntry {
    id: string;
    tool: string;
    command?: string;
    output: string;
    timestamp: number;
}

interface TerminalPanelProps {
    entries: TerminalEntry[];
    isVisible: boolean;
    onClose: () => void;
    onTerminalInput: (text: string) => void;
}

export const TerminalPanel: React.FC<TerminalPanelProps> = ({
    entries,
    isVisible,
    onClose,
    onTerminalInput,
}) => {
    const termRef = useRef<HTMLDivElement>(null);
    const xtermRef = useRef<XTerminal | null>(null);
    const fitAddonRef = useRef<FitAddon | null>(null);
    const [isMaximized, setIsMaximized] = useState(false);
    const lastWrittenRef = useRef<number>(0);

    // Initialize xterm
    useEffect(() => {
        if (!termRef.current || xtermRef.current) return;

        const term = new XTerminal({
            theme: {
                background: '#0c0c0e',
                foreground: '#d4d4d8',
                cursor: '#6366f1',
                cursorAccent: '#0c0c0e',
                selectionBackground: 'rgba(99, 102, 241, 0.3)',
                selectionForeground: '#ffffff',
                black: '#18181b',
                red: '#ef4444',
                green: '#22c55e',
                yellow: '#eab308',
                blue: '#6366f1',
                magenta: '#a855f7',
                cyan: '#06b6d4',
                white: '#d4d4d8',
                brightBlack: '#3f3f46',
                brightRed: '#f87171',
                brightGreen: '#4ade80',
                brightYellow: '#facc15',
                brightBlue: '#818cf8',
                brightMagenta: '#c084fc',
                brightCyan: '#22d3ee',
                brightWhite: '#fafafa',
            },
            fontSize: 13,
            fontFamily: "'JetBrains Mono', 'Cascadia Code', 'Fira Code', monospace",
            lineHeight: 1.4,
            cursorBlink: true,
            cursorStyle: 'bar',
            scrollback: 5000,
            allowProposedApi: true,
            convertEol: true,
        });

        const fitAddon = new FitAddon();
        const webLinksAddon = new WebLinksAddon();

        term.loadAddon(fitAddon);
        term.loadAddon(webLinksAddon);
        term.open(termRef.current);

        // Delay fit to ensure DOM is ready
        requestAnimationFrame(() => {
            try { fitAddon.fit(); } catch { /* ignore */ }
        });

        // Send user input to the server PTY
        term.onData((data) => {
            onTerminalInput(data);
        });

        xtermRef.current = term;
        fitAddonRef.current = fitAddon;

        return () => {
            term.dispose();
            xtermRef.current = null;
            fitAddonRef.current = null;
        };
    }, [isVisible]); // eslint-disable-line react-hooks/exhaustive-deps

    // Fit on resize or maximize toggle
    useEffect(() => {
        if (!fitAddonRef.current || !isVisible) return;

        const handleResize = () => {
            requestAnimationFrame(() => {
                try { fitAddonRef.current?.fit(); } catch { /* ignore */ }
            });
        };

        handleResize();
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, [isVisible, isMaximized]);

    // Write new entries to terminal
    useEffect(() => {
        const term = xtermRef.current;
        if (!term || entries.length === 0) return;

        // Write only new entries
        const newEntries = entries.slice(lastWrittenRef.current);
        for (const entry of newEntries) {
            if (entry.command && entry.command !== entry.tool) {
                term.writeln(`\x1b[38;5;99m❯\x1b[0m \x1b[1m${entry.command}\x1b[0m`);
            }
            if (entry.output) {
                // Write output — may contain ANSI codes already
                const lines = entry.output.split('\n');
                for (const line of lines) {
                    term.writeln(line);
                }
            }
        }
        lastWrittenRef.current = entries.length;
    }, [entries]);

    // Reset written count when entries list is cleared
    useEffect(() => {
        if (entries.length === 0) {
            lastWrittenRef.current = 0;
            if (xtermRef.current) {
                xtermRef.current.clear();
            }
        }
    }, [entries.length]);

    if (!isVisible) return null;

    return (
        <div
            className={`terminal-panel-container ${isMaximized ? 'terminal-maximized' : 'terminal-docked'}`}
        >
            {/* Header Bar */}
            <div className="terminal-panel-header">
                <div className="flex items-center gap-2">
                    <Terminal size={14} className="text-emerald-400" />
                    <span className="text-xs font-semibold text-zinc-300 tracking-wide uppercase">
                        Terminal
                    </span>
                    {entries.length > 0 && (
                        <span className="px-1.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-[10px] text-emerald-400 font-mono">
                            {entries.length}
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-1">
                    <button
                        onClick={() => setIsMaximized(!isMaximized)}
                        className="p-1.5 rounded-lg text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50 transition-all"
                        title={isMaximized ? 'Restaurar' : 'Maximizar'}
                    >
                        {isMaximized ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
                    </button>
                    <button
                        onClick={onClose}
                        className="p-1.5 rounded-lg text-zinc-500 hover:text-red-400 hover:bg-red-500/10 transition-all"
                        title="Cerrar"
                    >
                        <X size={14} />
                    </button>
                </div>
            </div>

            {/* xterm container */}
            <div className="terminal-panel-body" ref={termRef} />
        </div>
    );
};
