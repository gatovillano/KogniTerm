import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { CheckCircle2, Circle, Loader2, ListTodo } from 'lucide-react';
export const TaskTracker = ({ taskPlans }) => {
    const hasTasks = Object.values(taskPlans).some((plan) => plan.length > 0);
    if (!hasTasks) {
        return null;
    }
    const getStatusIcon = (status) => {
        switch (status) {
            case 'done':
                return _jsx(CheckCircle2, { size: 16, className: "text-emerald-500" });
            case 'in-progress':
                return _jsx(Loader2, { size: 16, className: "text-indigo-400 animate-spin" });
            case 'pending':
            default:
                return _jsx(Circle, { size: 16, className: "text-zinc-500" });
        }
    };
    return (_jsxs("div", { className: "flex flex-col w-full bg-zinc-900 border-l border-zinc-800 overflow-y-auto", children: [_jsxs("div", { className: "p-4 border-b border-zinc-800 sticky top-0 bg-zinc-900/90 backdrop-blur-md z-10 flex items-center gap-2", children: [_jsx(ListTodo, { size: 18, className: "text-indigo-400" }), _jsx("h3", { className: "font-medium text-sm text-zinc-200", children: "Plan de Tareas" })] }), _jsx("div", { className: "p-4 space-y-6", children: Object.entries(taskPlans).map(([agentName, tasks]) => {
                    if (tasks.length === 0)
                        return null;
                    const completed = tasks.filter((t) => t.status === 'done').length;
                    const total = tasks.length;
                    const progress = Math.round((completed / total) * 100);
                    return (_jsxs("div", { className: "space-y-3", children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsx("h4", { className: "text-xs font-semibold text-zinc-400 uppercase tracking-wider", children: agentName.replace(/_/g, ' ') }), _jsxs("span", { className: "text-[10px] text-zinc-500 font-medium", children: [progress, "%"] })] }), _jsx("div", { className: "h-1 w-full bg-zinc-800 rounded-full overflow-hidden", children: _jsx("div", { className: "h-full bg-indigo-500 transition-all duration-500 ease-out", style: { width: `${progress}%` } }) }), _jsx("div", { className: "space-y-2 mt-2", children: tasks.map((task, idx) => (_jsxs("div", { className: `flex items-start gap-3 p-2 rounded-lg text-sm transition-colors ${task.status === 'in-progress'
                                        ? 'bg-indigo-950/40 border border-indigo-500/30'
                                        : 'hover:bg-zinc-800/40 border border-transparent'}`, children: [_jsx("div", { className: "mt-0.5 shrink-0", children: getStatusIcon(task.status) }), _jsx("span", { className: `leading-snug text-xs ${task.status === 'done'
                                                ? 'text-zinc-500 line-through'
                                                : task.status === 'in-progress'
                                                    ? 'text-indigo-200 font-medium'
                                                    : 'text-zinc-300'}`, children: task.task })] }, idx))) })] }, agentName));
                }) })] }));
};
