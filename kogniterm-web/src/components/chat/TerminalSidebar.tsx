import React, { useEffect, useRef } from 'react';
import { Terminal as XTerminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import '@xterm/xterm/css/xterm.css';
import { Terminal as TerminalIcon, X } from 'lucide-react';
import { TerminalEntry } from './TerminalPanel';

interface TerminalSidebarProps {
    entries: TerminalEntry[];
    onTerminalInput: (text: string) => void;
    onClear?: () => void;
    isActive?: boolean;
}

export const TerminalSidebar: React.FC<TerminalSidebarProps> = ({
    entries,
    onTerminalInput,
    onClear,
    isActive = true,
}) => {
    const termRef = useRef<HTMLDivElement>(null);
    const xtermRef = useRef<XTerminal | null>(null);
    const fitAddonRef = useRef<FitAddon | null>(null);

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
            fontSize: 12,
            fontFamily: "'JetBrains Mono', 'Cascadia Code', 'Fira Code', monospace",
            lineHeight: 1.35,
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

        requestAnimationFrame(() => {
            try { fitAddon.fit(); } catch { /* ignore */ }
        });

        term.onData((data: string) => {
            onTerminalInput(data);
        });

        xtermRef.current = term;
        fitAddonRef.current = fitAddon;

        return () => {
            term.dispose();
            xtermRef.current = null;
            fitAddonRef.current = null;
        };
    }, [onTerminalInput]);

    useEffect(() => {
        if (!isActive || !fitAddonRef.current) return;
        const handleResize = () => {
            requestAnimationFrame(() => {
                try { fitAddonRef.current?.fit(); } catch { /* ignore */ }
            });
        };
        handleResize();
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, [isActive]);

    useEffect(() => {
        const term = xtermRef.current;
        if (!term) return;

        if (entries.length === 0) {
            term.clear();
            return;
        }

        term.clear();
        for (const entry of entries) {
            const cmdLabel = entry.command || entry.tool;
            if (cmdLabel) {
                term.writeln(`\x1b[38;5;99m❯\x1b[0m \x1b[1m${cmdLabel}\x1b[0m`);
            }
            if (entry.output) {
                const lines = entry.output.split('\n');
                for (const line of lines) {
                    term.writeln(line);
                }
            }
        }
    }, [entries]);

    return (
        <div className="flex h-full w-full flex-col bg-[#0c0c0e]">
            <div className="flex items-center justify-between border-b border-zinc-200 bg-zinc-50 px-3 py-2">
                <div className="flex items-center gap-2">
                    <TerminalIcon size={13} className="text-emerald-600" />
                    <span className="text-[11px] font-semibold uppercase tracking-wider text-zinc-700">Terminal</span>
                    {entries.length > 0 && (
                        <span className="rounded-full bg-emerald-50 px-1.5 py-0.5 font-mono text-[10px] text-emerald-700 border border-emerald-200 font-medium">
                            {entries.length}
                        </span>
                    )}
                </div>
                {onClear && (
                    <button
                        onClick={onClear}
                        className="rounded-lg p-1 text-zinc-400 transition-colors hover:bg-zinc-200/60 hover:text-zinc-700"
                        title="Limpiar terminal"
                    >
                        <X size={13} />
                    </button>
                )}
            </div>
            <div
                ref={termRef}
                className="flex-1 w-full"
                style={{ display: isActive ? 'block' : 'none' }}
            />
        </div>
    );
};
