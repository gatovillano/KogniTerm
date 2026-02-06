import React, { useEffect, useRef } from 'react';
import { Terminal as XTerm } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import '@xterm/xterm/css/xterm.css';

interface TerminalProps {
    onCommand?: (command: string) => void;
}

export const Terminal: React.FC<TerminalProps> = ({ onCommand }) => {
    const terminalRef = useRef<HTMLDivElement>(null);
    const xtermRef = useRef<XTerm | null>(null);
    const fitAddonRef = useRef<FitAddon | null>(null);
    const currentLineRef = useRef<string>('');

    useEffect(() => {
        if (!terminalRef.current) return;

        // Crear la instancia de XTerm
        const xterm = new XTerm({
            cursorBlink: true,
            fontSize: 14,
            fontFamily: 'Menlo, Monaco, "Courier New", monospace',
            theme: {
                background: '#0f172a',
                foreground: '#e2e8f0',
                cursor: '#60a5fa',
                black: '#1e293b',
                red: '#ef4444',
                green: '#10b981',
                yellow: '#f59e0b',
                blue: '#3b82f6',
                magenta: '#a855f7',
                cyan: '#06b6d4',
                white: '#f1f5f9',
                brightBlack: '#475569',
                brightRed: '#f87171',
                brightGreen: '#34d399',
                brightYellow: '#fbbf24',
                brightBlue: '#60a5fa',
                brightMagenta: '#c084fc',
                brightCyan: '#22d3ee',
                brightWhite: '#f8fafc',
            },
            allowProposedApi: true,
        });

        // Addons
        const fitAddon = new FitAddon();
        const webLinksAddon = new WebLinksAddon();

        xterm.loadAddon(fitAddon);
        xterm.loadAddon(webLinksAddon);

        xterm.open(terminalRef.current);
        fitAddon.fit();

        xtermRef.current = xterm;
        fitAddonRef.current = fitAddon;

        // Mensaje de bienvenida
        xterm.writeln('\x1b[1;36m╔═══════════════════════════════════════════════════════╗\x1b[0m');
        xterm.writeln('\x1b[1;36m║\x1b[0m     \x1b[1;34mKogniTerm Desktop Terminal\x1b[0m                    \x1b[1;36m║\x1b[0m');
        xterm.writeln('\x1b[1;36m║\x1b[0m     Ejecuta comandos del sistema                    \x1b[1;36m║\x1b[0m');
        xterm.writeln('\x1b[1;36m╚═══════════════════════════════════════════════════════╝\x1b[0m');
        xterm.writeln('');
        xterm.write('\x1b[1;32m$\x1b[0m ');

        // Manejar entrada del usuario
        xterm.onData((data) => {
            const code = data.charCodeAt(0);

            // Enter
            if (code === 13) {
                xterm.writeln('');
                const command = currentLineRef.current.trim();
                if (command && onCommand) {
                    onCommand(command);
                }
                currentLineRef.current = '';
                xterm.write('\x1b[1;32m$\x1b[0m ');
            }
            // Backspace
            else if (code === 127) {
                if (currentLineRef.current.length > 0) {
                    currentLineRef.current = currentLineRef.current.slice(0, -1);
                    xterm.write('\b \b');
                }
            }
            // Caracteres normales
            else if (code >= 32) {
                currentLineRef.current += data;
                xterm.write(data);
            }
        });

        // Ajustar al redimensionar
        const handleResize = () => {
            fitAddon.fit();
        };

        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            xterm.dispose();
        };
    }, [onCommand]);

    // Método público para escribir en la terminal
    useEffect(() => {
        if (xtermRef.current) {
            (window as any).writeToTerminal = (text: string) => {
                xtermRef.current?.writeln(text);
            };
        }
    }, []);

    return (
        <div className="h-full w-full bg-slate-950 rounded-lg overflow-hidden border border-slate-800">
            <div ref={terminalRef} className="h-full w-full p-2" />
        </div>
    );
};
