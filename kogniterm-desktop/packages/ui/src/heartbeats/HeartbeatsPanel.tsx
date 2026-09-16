import { useState, useEffect } from 'react';
import {
  Activity,
  Plus,
  Play,
  Trash2,
  Edit2,
  Clock,
  RefreshCw,
  Loader2,
  X,
  Save,
} from 'lucide-react';
import { Heartbeat } from '@kogniterm/types';

export interface HeartbeatsPanelProps {
  serverUrl?: string;
}

export const HeartbeatsPanel: React.FC<HeartbeatsPanelProps> = ({
  serverUrl = 'http://127.0.0.1:8765',
}) => {
  const [jobs, setJobs] = useState<Heartbeat[]>([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingJob, setEditingJob] = useState<Heartbeat | null>(null);

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
    } catch (err) {
      console.error('Error fetching heartbeats:', err);
    } finally {
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

  const handleOpenEdit = (job: Heartbeat) => {
    setEditingJob(job);
    setFormName(job.name);
    setFormPrompt(job.prompt);
    setFormInterval(job.interval_seconds);
    setFormEnabled(job.enabled);
    setIsModalOpen(true);
  };

  const handleSave = async (e: React.FormEvent) => {
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
    } catch (err) {
      console.error('Error saving heartbeat:', err);
    }
  };

  const handleDelete = async (jobId: string) => {
    try {
      await fetch(`${serverUrl}/api/heartbeats/${jobId}`, { method: 'DELETE' });
      fetchJobs();
    } catch (err) {
      console.error('Error deleting heartbeat:', err);
    }
  };

  const handleTriggerNow = async (jobId: string) => {
    try {
      await fetch(`${serverUrl}/api/heartbeats/${jobId}/trigger`, { method: 'POST' });
      fetchJobs();
    } catch (err) {
      console.error('Error triggering heartbeat:', err);
    }
  };

  return (
    <div className="flex flex-col h-full w-full bg-zinc-950 text-zinc-100 p-6 max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2 text-zinc-100">
            <Activity size={22} className="text-emerald-400" />
            Routines & Heartbeats (Automatizaciones)
          </h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Tareas periódicas y monitoreo autónomo ejecutado por el agente
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={fetchJobs}
            disabled={loading}
            className="p-2 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-zinc-200"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
          </button>
          <button
            onClick={handleOpenCreate}
            className="flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3.5 py-2 text-xs font-medium text-white hover:bg-emerald-500 shadow-sm transition-colors"
          >
            <Plus size={15} />
            Nueva Rutina
          </button>
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto space-y-3">
        {jobs.length === 0 && !loading ? (
          <div className="p-12 text-center text-xs text-zinc-500 border border-dashed border-zinc-800 rounded-2xl">
            No hay rutinas o heartbeats programados
          </div>
        ) : (
          jobs.map((job) => (
            <div
              key={job.id}
              className="flex items-center justify-between p-4 rounded-xl border border-zinc-800 bg-zinc-900/60 hover:bg-zinc-900 transition-colors"
            >
              <div className="space-y-1 min-w-0 flex-1 pr-4">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-sm text-zinc-100">{job.name}</span>
                  <span
                    className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                      job.enabled
                        ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                        : 'bg-zinc-800 text-zinc-500'
                    }`}
                  >
                    {job.enabled ? 'Activo' : 'Pausado'}
                  </span>
                </div>
                <p className="text-xs text-zinc-400 font-mono line-clamp-1">{job.prompt}</p>
                <div className="flex items-center gap-4 text-[11px] text-zinc-500 pt-1">
                  <span className="flex items-center gap-1">
                    <Clock size={12} /> Cada {Math.round(job.interval_seconds / 60)} min ({job.interval_seconds}s)
                  </span>
                  {job.last_run && <span>Última ejecución: {new Date(job.last_run).toLocaleTimeString()}</span>}
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => handleTriggerNow(job.id)}
                  className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-zinc-800 hover:bg-indigo-600/20 hover:text-indigo-300 text-xs text-zinc-300 border border-zinc-700/60 transition-colors"
                  title="Ejecutar inmediatamente"
                >
                  <Play size={13} /> Ejecutar
                </button>
                <button
                  onClick={() => handleOpenEdit(job)}
                  className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800"
                >
                  <Edit2 size={15} />
                </button>
                <button
                  onClick={() => handleDelete(job.id)}
                  className="p-1.5 rounded-lg text-zinc-400 hover:text-rose-400 hover:bg-rose-500/10"
                >
                  <Trash2 size={15} />
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <form
            onSubmit={handleSave}
            className="w-full max-w-lg rounded-2xl border border-zinc-800 bg-zinc-900 p-6 space-y-4 shadow-2xl"
          >
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <h3 className="font-bold text-sm text-zinc-100">
                {editingJob ? 'Editar Rutina' : 'Crear Nueva Rutina'}
              </h3>
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="p-1 text-zinc-400 hover:text-zinc-200"
              >
                <X size={16} />
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-xs text-zinc-400 mb-1">Nombre</label>
                <input
                  type="text"
                  required
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="Ej: Healthcheck Docker diario"
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs text-zinc-400 mb-1">Prompt / Instrucción</label>
                <textarea
                  required
                  rows={3}
                  value={formPrompt}
                  onChange={(e) => setFormPrompt(e.target.value)}
                  placeholder="Instrucción para que el agente ejecute periódicamente..."
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-zinc-400 mb-1">Intervalo (segundos)</label>
                  <input
                    type="number"
                    min={30}
                    value={formInterval}
                    onChange={(e) => setFormInterval(Number(e.target.value))}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500"
                  />
                </div>

                <div className="flex items-center pt-5">
                  <label className="flex items-center gap-2 text-xs text-zinc-300 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={formEnabled}
                      onChange={(e) => setFormEnabled(e.target.checked)}
                      className="rounded border-zinc-700 bg-zinc-950 text-indigo-600 focus:ring-0"
                    />
                    <span>Habilitar rutina</span>
                  </label>
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-zinc-800">
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="px-4 py-2 rounded-lg text-xs text-zinc-400 hover:bg-zinc-800"
              >
                Cancelar
              </button>
              <button
                type="submit"
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-600 text-xs font-medium text-white hover:bg-emerald-500"
              >
                <Save size={14} /> Guardar
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};
