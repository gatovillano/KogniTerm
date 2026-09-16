import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState, useEffect } from 'react';
import { Activity, Plus, Play, Trash2, Edit2, Clock, RefreshCw, Loader2, X, Save, } from 'lucide-react';
export const HeartbeatsPanel = ({ serverUrl = 'http://127.0.0.1:8765', }) => {
    const [jobs, setJobs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [editingJob, setEditingJob] = useState(null);
    const [formName, setFormName] = useState('');
    const [formPrompt, setFormPrompt] = useState('');
    const [formInterval, setFormInterval] = useState(300);
    const [formEnabled, setFormEnabled] = useState(true);
    const fetchJobs = async () => {
        setLoading(true);
        try {
            const res = await fetch(`${serverUrl}/api/heartbeats`);
            if (res.ok) {
                const data = await res.json();
                setJobs(data.jobs || []);
            }
        }
        catch (err) {
            console.error('Error fetching heartbeats:', err);
        }
        finally {
            setLoading(false);
        }
    };
    useEffect(() => {
        fetchJobs();
    }, []);
    const handleOpenCreate = () => {
        setEditingJob(null);
        setFormName('');
        setFormPrompt('');
        setFormInterval(300);
        setFormEnabled(true);
        setIsModalOpen(true);
    };
    const handleOpenEdit = (job) => {
        setEditingJob(job);
        setFormName(job.name);
        setFormPrompt(job.prompt);
        setFormInterval(job.interval_seconds);
        setFormEnabled(job.enabled);
        setIsModalOpen(true);
    };
    const handleSave = async (e) => {
        e.preventDefault();
        try {
            const payload = {
                id: editingJob ? editingJob.id : `job-${Date.now()}`,
                name: formName,
                prompt: formPrompt,
                interval_seconds: Number(formInterval),
                enabled: formEnabled,
            };
            const res = await fetch(`${serverUrl}/api/heartbeats/save`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            if (res.ok) {
                setIsModalOpen(false);
                fetchJobs();
            }
        }
        catch (err) {
            console.error('Error saving heartbeat:', err);
        }
    };
    const handleDelete = async (jobId) => {
        try {
            await fetch(`${serverUrl}/api/heartbeats/${jobId}`, { method: 'DELETE' });
            fetchJobs();
        }
        catch (err) {
            console.error('Error deleting heartbeat:', err);
        }
    };
    const handleTriggerNow = async (jobId) => {
        try {
            await fetch(`${serverUrl}/api/heartbeats/${jobId}/trigger`, { method: 'POST' });
            fetchJobs();
        }
        catch (err) {
            console.error('Error triggering heartbeat:', err);
        }
    };
    return (_jsxs("div", { className: "flex flex-col h-full w-full bg-zinc-950 text-zinc-100 p-6 max-w-5xl mx-auto space-y-6", children: [_jsxs("div", { className: "flex items-center justify-between border-b border-zinc-800 pb-4", children: [_jsxs("div", { children: [_jsxs("h2", { className: "text-xl font-bold flex items-center gap-2 text-zinc-100", children: [_jsx(Activity, { size: 22, className: "text-emerald-400" }), "Routines & Heartbeats (Automatizaciones)"] }), _jsx("p", { className: "text-xs text-zinc-400 mt-0.5", children: "Tareas peri\u00F3dicas y monitoreo aut\u00F3nomo ejecutado por el agente" })] }), _jsxs("div", { className: "flex items-center gap-2", children: [_jsx("button", { onClick: fetchJobs, disabled: loading, className: "p-2 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-zinc-200", children: loading ? _jsx(Loader2, { size: 16, className: "animate-spin" }) : _jsx(RefreshCw, { size: 16 }) }), _jsxs("button", { onClick: handleOpenCreate, className: "flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3.5 py-2 text-xs font-medium text-white hover:bg-emerald-500 shadow-sm transition-colors", children: [_jsx(Plus, { size: 15 }), "Nueva Rutina"] })] })] }), _jsx("div", { className: "flex-1 overflow-y-auto space-y-3", children: jobs.length === 0 && !loading ? (_jsx("div", { className: "p-12 text-center text-xs text-zinc-500 border border-dashed border-zinc-800 rounded-2xl", children: "No hay rutinas o heartbeats programados" })) : (jobs.map((job) => (_jsxs("div", { className: "flex items-center justify-between p-4 rounded-xl border border-zinc-800 bg-zinc-900/60 hover:bg-zinc-900 transition-colors", children: [_jsxs("div", { className: "space-y-1 min-w-0 flex-1 pr-4", children: [_jsxs("div", { className: "flex items-center gap-2", children: [_jsx("span", { className: "font-semibold text-sm text-zinc-100", children: job.name }), _jsx("span", { className: `text-[10px] px-2 py-0.5 rounded-full font-medium ${job.enabled
                                                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                                                : 'bg-zinc-800 text-zinc-500'}`, children: job.enabled ? 'Activo' : 'Pausado' })] }), _jsx("p", { className: "text-xs text-zinc-400 font-mono line-clamp-1", children: job.prompt }), _jsxs("div", { className: "flex items-center gap-4 text-[11px] text-zinc-500 pt-1", children: [_jsxs("span", { className: "flex items-center gap-1", children: [_jsx(Clock, { size: 12 }), " Cada ", Math.round(job.interval_seconds / 60), " min (", job.interval_seconds, "s)"] }), job.last_run && _jsxs("span", { children: ["\u00DAltima ejecuci\u00F3n: ", new Date(job.last_run).toLocaleTimeString()] })] })] }), _jsxs("div", { className: "flex items-center gap-2 shrink-0", children: [_jsxs("button", { onClick: () => handleTriggerNow(job.id), className: "flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-zinc-800 hover:bg-indigo-600/20 hover:text-indigo-300 text-xs text-zinc-300 border border-zinc-700/60 transition-colors", title: "Ejecutar inmediatamente", children: [_jsx(Play, { size: 13 }), " Ejecutar"] }), _jsx("button", { onClick: () => handleOpenEdit(job), className: "p-1.5 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800", children: _jsx(Edit2, { size: 15 }) }), _jsx("button", { onClick: () => handleDelete(job.id), className: "p-1.5 rounded-lg text-zinc-400 hover:text-rose-400 hover:bg-rose-500/10", children: _jsx(Trash2, { size: 15 }) })] })] }, job.id)))) }), isModalOpen && (_jsx("div", { className: "fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4", children: _jsxs("form", { onSubmit: handleSave, className: "w-full max-w-lg rounded-2xl border border-zinc-800 bg-zinc-900 p-6 space-y-4 shadow-2xl", children: [_jsxs("div", { className: "flex items-center justify-between border-b border-zinc-800 pb-3", children: [_jsx("h3", { className: "font-bold text-sm text-zinc-100", children: editingJob ? 'Editar Rutina' : 'Crear Nueva Rutina' }), _jsx("button", { type: "button", onClick: () => setIsModalOpen(false), className: "p-1 text-zinc-400 hover:text-zinc-200", children: _jsx(X, { size: 16 }) })] }), _jsxs("div", { className: "space-y-3", children: [_jsxs("div", { children: [_jsx("label", { className: "block text-xs text-zinc-400 mb-1", children: "Nombre" }), _jsx("input", { type: "text", required: true, value: formName, onChange: (e) => setFormName(e.target.value), placeholder: "Ej: Healthcheck Docker diario", className: "w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500" })] }), _jsxs("div", { children: [_jsx("label", { className: "block text-xs text-zinc-400 mb-1", children: "Prompt / Instrucci\u00F3n" }), _jsx("textarea", { required: true, rows: 3, value: formPrompt, onChange: (e) => setFormPrompt(e.target.value), placeholder: "Instrucci\u00F3n para que el agente ejecute peri\u00F3dicamente...", className: "w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500" })] }), _jsxs("div", { className: "grid grid-cols-2 gap-3", children: [_jsxs("div", { children: [_jsx("label", { className: "block text-xs text-zinc-400 mb-1", children: "Intervalo (segundos)" }), _jsx("input", { type: "number", min: 30, value: formInterval, onChange: (e) => setFormInterval(Number(e.target.value)), className: "w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500" })] }), _jsx("div", { className: "flex items-center pt-5", children: _jsxs("label", { className: "flex items-center gap-2 text-xs text-zinc-300 cursor-pointer", children: [_jsx("input", { type: "checkbox", checked: formEnabled, onChange: (e) => setFormEnabled(e.target.checked), className: "rounded border-zinc-700 bg-zinc-950 text-indigo-600 focus:ring-0" }), _jsx("span", { children: "Habilitar rutina" })] }) })] })] }), _jsxs("div", { className: "flex justify-end gap-2 pt-3 border-t border-zinc-800", children: [_jsx("button", { type: "button", onClick: () => setIsModalOpen(false), className: "px-4 py-2 rounded-lg text-xs text-zinc-400 hover:bg-zinc-800", children: "Cancelar" }), _jsxs("button", { type: "submit", className: "flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-600 text-xs font-medium text-white hover:bg-emerald-500", children: [_jsx(Save, { size: 14 }), " Guardar"] })] })] }) }))] }));
};
