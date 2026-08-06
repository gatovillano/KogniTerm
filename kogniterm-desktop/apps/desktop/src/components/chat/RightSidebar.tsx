import React, { useEffect, useState, useCallback } from 'react';
import { ListTodo, Terminal, ShieldCheck, PanelRightClose, PanelRightOpen } from 'lucide-react';
import { TaskTracker } from './TaskTracker';
import { CommandApproval, ApprovalRequest } from './CommandApproval';
import { TerminalSidebar } from './TerminalSidebar';
import { TerminalEntry } from './TerminalPanel';

type TabId = 'tasks' | 'terminal' | 'approval';

export const RightSidebar: React.FC<{
    taskPlans: Record<string, any[]>;
    hasActiveTasks: boolean;
    pendingApproval: ApprovalRequest | null;
    onApprove: (id: string) => void;
    onReject: (id: string) => void;
    terminalEntries: TerminalEntry[];
    onTerminalInput: (text: string) => void;
    onClearTerminal: () => void;
    isOpen: boolean;
    onToggle: () => void;
}> = ({
    taskPlans,
    hasActiveTasks,
    pendingApproval,
    onApprove,
    onReject,
    terminalEntries,
    onTerminalInput,
    onClearTerminal,
    isOpen,
    onToggle,
}) => {
    const [activeTab, setActiveTab] = useState<TabId>('tasks');
    const [width, setWidth] = useState<number>(() => {
        const saved = localStorage.getItem('kogniterm_right_sidebar_width');
        if (saved) {
            const parsed = parseInt(saved, 10);
            if (!isNaN(parsed) && parsed >= 240 && parsed <= 800) {
                return parsed;
            }
        }
        return 320;
    });
    const [isResizing, setIsResizing] = useState(false);

    useEffect(() => {
        if (pendingApproval) {
            setActiveTab('approval');
        }
    }, [pendingApproval?.id]);

    const startResizing = useCallback((e: React.MouseEvent) => {
        e.preventDefault();
        setIsResizing(true);
    }, []);

    const handleDoubleClick = useCallback(() => {
        setWidth(320);
        localStorage.setItem('kogniterm_right_sidebar_width', '320');
    }, []);

    useEffect(() => {
        const handleMouseMove = (e: MouseEvent) => {
            if (!isResizing) return;
            const newWidth = window.innerWidth - e.clientX;
            const minWidth = 240;
            const maxWidth = Math.min(800, window.innerWidth * 0.6);
            const clampedWidth = Math.max(minWidth, Math.min(maxWidth, newWidth));
            setWidth(clampedWidth);
            localStorage.setItem('kogniterm_right_sidebar_width', clampedWidth.toString());
        };

        const handleMouseUp = () => {
            setIsResizing(false);
        };

        if (isResizing) {
            window.addEventListener('mousemove', handleMouseMove);
            window.addEventListener('mouseup', handleMouseUp);
            document.body.style.userSelect = 'none';
            document.body.style.cursor = 'col-resize';
        }

        return () => {
            window.removeEventListener('mousemove', handleMouseMove);
            window.removeEventListener('mouseup', handleMouseUp);
            document.body.style.userSelect = '';
            document.body.style.cursor = '';
        };
    }, [isResizing]);

    const totalActiveTasks = Object.values(taskPlans).reduce(
        (acc, plan) => acc + (plan?.filter((t: any) => t.status !== 'done').length || 0),
        0
    );

    const tabs: { id: TabId; label: string; icon: React.ElementType; badge?: number }[] = [
        {
            id: 'tasks',
            label: 'Tareas',
            icon: ListTodo,
            badge: totalActiveTasks > 0 ? totalActiveTasks : undefined,
        },
        {
            id: 'terminal',
            label: 'Terminal',
            icon: Terminal,
            badge: terminalEntries.length > 0 ? terminalEntries.length : undefined,
        },
        {
            id: 'approval',
            label: 'Aprobación',
            icon: ShieldCheck,
            badge: pendingApproval ? 1 : undefined,
        },
    ];

    return (
        <aside
            style={{ width: `${width}px` }}
            className={`relative flex h-full shrink-0 flex-col border-l border-zinc-800 bg-zinc-950 animate-slide-in-right ${
                isResizing ? 'select-none transition-none' : ''
            }`}
        >
            {/* Handle de redimensionamiento */}
            <div
                onMouseDown={startResizing}
                onDoubleClick={handleDoubleClick}
                className="group absolute -left-1 top-0 bottom-0 z-20 w-2 cursor-col-resize hover:bg-indigo-500/20 active:bg-indigo-500/30 transition-colors flex items-center justify-center"
                title="Arrastrar para redimensionar (doble clic para restablecer a 320px)"
            >
                <div className={`h-full w-0.5 transition-colors ${isResizing ? 'bg-indigo-500' : 'bg-transparent group-hover:bg-indigo-500/60'}`} />
            </div>

            <div className="flex items-center justify-between border-b border-zinc-800/80 bg-zinc-950/80 px-2 pt-2 backdrop-blur-sm">
                <div className="flex items-center justify-center gap-1">
                    {tabs.map((tab) => {
                        const isActive = activeTab === tab.id;
                        const Icon = tab.icon;
                        return (
                            <button
                                key={tab.id}
                                onClick={() => setActiveTab(tab.id)}
                                className={`relative flex h-9 w-9 shrink-0 appearance-none items-center justify-center rounded-lg border-0 bg-transparent transition-colors ${
                                    isActive
                                        ? 'text-zinc-100'
                                        : 'text-zinc-500 hover:text-zinc-300'
                                }`}
                                title={tab.label}
                            >
                                <Icon size={15} />
                                {tab.badge !== undefined && tab.badge > 0 && (
                                    <span className="absolute -right-1 -top-1 rounded-full bg-indigo-500 px-1 font-mono text-[10px] font-semibold leading-none text-white">
                                        {tab.badge}
                                    </span>
                                )}
                                {isActive && (
                                    <div className="absolute bottom-0 left-1/2 h-[2px] w-4 -translate-x-1/2 rounded-full bg-indigo-500" />
                                )}
                            </button>
                        );
                    })}
                </div>
                <button
                    onClick={onToggle}
                    title={isOpen ? 'Ocultar panel' : 'Mostrar panel'}
                    className="flex h-8 w-8 appearance-none items-center justify-center rounded-lg border-0 bg-transparent text-zinc-500 transition-colors hover:text-zinc-200"
                >
                    {isOpen ? <PanelRightClose size={15} /> : <PanelRightOpen size={15} />}
                </button>
            </div>

            {isOpen && (
                <div className="flex-1 overflow-hidden">
                    <div className="flex h-full flex-col">
                        {activeTab === 'tasks' && (
                            <div className="h-full overflow-y-auto">
                                {hasActiveTasks ? (
                                    <TaskTracker taskPlans={taskPlans} />
                                ) : (
                                    <div className="flex h-full flex-col items-center justify-center gap-2 text-zinc-600">
                                        <ListTodo size={24} className="text-zinc-600" />
                                        <p className="text-[12px]">Sin tareas activas</p>
                                    </div>
                                )}
                            </div>
                        )}

                        {activeTab === 'terminal' && (
                            <div className="flex h-full flex-col">
                                <TerminalSidebar
                                    entries={terminalEntries}
                                    onTerminalInput={onTerminalInput}
                                    onClear={onClearTerminal}
                                    isActive={activeTab === 'terminal'}
                                />
                            </div>
                        )}

                        {activeTab === 'approval' && pendingApproval && (
                            <div className="h-full overflow-y-auto">
                                <CommandApproval
                                    request={pendingApproval}
                                    onApprove={(id) => {
                                        onApprove(id);
                                        setActiveTab('terminal');
                                    }}
                                    onReject={onReject}
                                />
                            </div>
                        )}
                        {activeTab === 'approval' && !pendingApproval && (
                            <div className="flex h-full flex-col items-center justify-center gap-2 text-zinc-600">
                                <ShieldCheck size={24} className="text-zinc-600" />
                                <p className="text-[12px]">Sin aprobaciones pendientes</p>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </aside>
    );
};
