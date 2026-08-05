import React, { useState, useEffect } from 'react';
import {
  Activity,
  Plus,
  Play,
  Trash2,
  Edit2,
  CheckCircle,
  AlertTriangle,
  Clock,
  RefreshCw,
  Loader2,
  X,
  Save,
  MessageSquare,
  Terminal,
  ShieldAlert,
} from 'lucide-react';

export interface Heartbeat {
  id: string;
  name: string;
  prompt: string;
  interval_seconds: number;
  enabled: boolean;
  session_id?: string | null;
  last_run?: string | null;
  last_status?: string | null;
  last_error?: string | null;
}

interface HeartbeatsTabProps {
  serverUrl?: string;
}

export const HeartbeatsTab: React.FC<HeartbeatsTabProps> = ({
  serverUrl = 'http://localhost:8765',
}) => {
  const [heartbeats, setHeartbeats] = useState<Heartbeat[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [triggeringId, setTriggeringId] = useState<string | null>(null);

  // Form State (for Create & Edit)
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingHeartbeat, setEditingHeartbeat] = useState<Heartbeat | null>(null);
  
  const [formName, setFormName] = useState('');
  const [formPrompt, setFormPrompt] = useState('');
  const [formIntervalValue, setFormIntervalValue] = useState<number>(5);
  const [formIntervalUnit, setFormIntervalUnit] = useState<'seconds' | 'minutes' | 'hours'>('minutes');
  const [formEnabled, setFormEnabled] = useState(true);
  const [formSessionId, setFormSessionId] = useState('');

  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Fetch Heartbeats from Backend
  const fetchHeartbeats = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${serverUrl}/config/heartbeats`);
      if (!res.ok) {
        throw new Error(`HTTP error ${res.status}`);
      }
      const data = await res.json();
      setHeartbeats(data.heartbeats || []);
    } catch (err: any) {
      console.error('Error loading heartbeats:', err);
      setError('No se pudo conectar con el servidor KogniTerm. Verifica que esté en ejecución.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHeartbeats();
  }, [serverUrl]);

  // Open form for creating
  const handleOpenCreate = () => {
    setEditingHeartbeat(null);
    setFormName('');
    setFormPrompt('');
    setFormIntervalValue(5);
    setFormIntervalUnit('minutes');
    setFormEnabled(true);
    setFormSessionId('');
    setFormError(null);
    setIsFormOpen(true);
  };

  // Open form for editing
  const handleOpenEdit = (hb: Heartbeat) => {
    setEditingHeartbeat(hb);
    setFormName(hb.name);
    setFormPrompt(hb.prompt);
    
    // Calculate best unit
    let sec = hb.interval_seconds;
    if (sec % 3600 === 0 && sec >= 3600) {
      setFormIntervalValue(sec / 3600);
      setFormIntervalUnit('hours');
    } else if (sec % 60 === 0 && sec >= 60) {
      setFormIntervalValue(sec / 60);
      setFormIntervalUnit('minutes');
    } else {
      setFormIntervalValue(sec);
      setFormIntervalUnit('seconds');
    }

    setFormEnabled(hb.enabled);
    setFormSessionId(hb.session_id || '');
    setFormError(null);
    setIsFormOpen(true);
  };

  // Convert unit to seconds
  const calculateSeconds = (val: number, unit: 'seconds' | 'minutes' | 'hours'): number => {
    if (unit === 'hours') return val * 3600;
    if (unit === 'minutes') return val * 60;
    return val;
  };

  // Format seconds to human readable
  const formatInterval = (sec: number): string => {
    if (sec >= 3600 && sec % 3600 === 0) {
      const h = sec / 3600;
      return `Cada ${h} ${h === 1 ? 'hora' : 'horas'}`;
    }
    if (sec >= 60 && sec % 60 === 0) {
      const m = sec / 60;
      return `Cada ${m} ${m === 1 ? 'minuto' : 'minutos'}`;
    }
    return `Cada ${sec} segundos`;
  };

  // Save Heartbeat (Create / Update)
  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formName.trim()) {
      setFormError('El nombre del heartbeat es obligatorio.');
      return;
    }
    if (!formPrompt.trim()) {
      setFormError('El prompt de la instrucción es obligatorio.');
      return;
    }

    const intervalSec = calculateSeconds(formIntervalValue, formIntervalUnit);
    if (intervalSec < 5) {
      setFormError('El intervalo mínimo es de 5 segundos.');
      return;
    }

    setSaving(true);
    setFormError(null);

    const payload: Partial<Heartbeat> = {
      id: editingHeartbeat ? editingHeartbeat.id : undefined,
      name: formName.trim(),
      prompt: formPrompt.trim(),
      interval_seconds: intervalSec,
      enabled: formEnabled,
      session_id: formSessionId.trim() || null,
    };

    try {
      const url = editingHeartbeat
        ? `${serverUrl}/config/heartbeats/${editingHeartbeat.id}`
        : `${serverUrl}/config/heartbeats`;

      const res = await fetch(url, {
        method: editingHeartbeat ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        throw new Error('Error al guardar el heartbeat');
      }

      setIsFormOpen(false);
      await fetchHeartbeats();
    } catch (err: any) {
      console.error('Error saving heartbeat:', err);
      setFormError('No se pudo guardar la configuración. Intenta nuevamente.');
    } finally {
      setSaving(false);
    }
  };

  // Toggle Enabled
  const handleToggle = async (hb: Heartbeat) => {
    try {
      const newEnabled = !hb.enabled;
      setHeartbeats((prev) =>
        prev.map((h) => (h.id === hb.id ? { ...h, enabled: newEnabled } : h))
      );

      const res = await fetch(
        `${serverUrl}/config/heartbeats/${hb.id}/toggle?enabled=${newEnabled}`,
        { method: 'PATCH' }
      );
      if (!res.ok) {
        fetchHeartbeats();
      }
    } catch (err) {
      console.error('Error toggling heartbeat:', err);
      fetchHeartbeats();
    }
  };

  // Delete Heartbeat
  const handleDelete = async (id: string, name: string) => {
    if (!window.confirm(`¿Estás seguro de eliminar el heartbeat "${name}"?`)) {
      return;
    }
    try {
      setHeartbeats((prev) => prev.filter((h) => h.id !== id));
      await fetch(`${serverUrl}/config/heartbeats/${id}`, { method: 'DELETE' });
    } catch (err) {
      console.error('Error deleting heartbeat:', err);
      fetchHeartbeats();
    }
  };

  // Trigger Heartbeat Manually
  const handleTriggerNow = async (id: string) => {
    setTriggeringId(id);
    try {
      const res = await fetch(`${serverUrl}/config/heartbeats/${id}/trigger`, {
        method: 'POST',
      });
      if (!res.ok) {
        throw new Error('Error al disparar el heartbeat');
      }
      // Re-fetch to update last_run status
      await fetchHeartbeats();
    } catch (err: any) {
      console.error('Error triggering heartbeat:', err);
      alert('Error al disparar el heartbeat en el servidor.');
    } finally {
      setTriggeringId(null);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-150">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-800/80 pb-4">
        <div>
          <h2 className="text-base font-bold text-zinc-100 flex items-center gap-2">
            <Activity className="text-indigo-400" size={18} />
            Heartbeats Configurables
          </h2>
          <p className="text-xs text-zinc-400 mt-1">
            Programa instrucciones periódicas para que el servidor de KogniTerm las ejecute automáticamente.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchHeartbeats}
            disabled={loading}
            className="p-2 rounded-lg bg-zinc-800/60 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors border border-zinc-700/50"
            title="Recargar lista"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
          <button
            onClick={handleOpenCreate}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md shadow-indigo-600/20 transition-all"
          >
            <Plus size={14} />
            Nuevo Heartbeat
          </button>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="flex items-start gap-3 p-3.5 rounded-xl bg-red-950/40 border border-red-800/40 text-red-300 text-xs">
          <AlertTriangle className="shrink-0 text-red-400 mt-0.5" size={16} />
          <div className="flex-1">
            <p className="font-semibold">{error}</p>
          </div>
        </div>
      )}

      {/* Loading state */}
      {loading && heartbeats.length === 0 && (
        <div className="flex flex-col items-center justify-center py-12 text-zinc-500 gap-3">
          <Loader2 size={24} className="animate-spin text-indigo-400" />
          <span className="text-xs">Cargando heartbeats del servidor...</span>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && heartbeats.length === 0 && (
        <div className="flex flex-col items-center justify-center py-12 px-4 rounded-xl border border-dashed border-zinc-800/80 bg-zinc-900/20 text-center space-y-3">
          <div className="p-3 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            <Clock size={24} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-zinc-200">No hay heartbeats configurados</h3>
            <p className="text-xs text-zinc-500 mt-1 max-w-sm">
              Crea tu primer latido periódico para realizar verificaciones automáticas de git, monitoreo de servidor o tareas repetitivas.
            </p>
          </div>
          <button
            onClick={handleOpenCreate}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition-all mt-2"
          >
            <Plus size={14} />
            Crear Heartbeat
          </button>
        </div>
      )}

      {/* Heartbeats List */}
      {!loading && heartbeats.length > 0 && (
        <div className="grid grid-cols-1 gap-3">
          {heartbeats.map((hb) => (
            <div
              key={hb.id}
              className={`p-4 rounded-xl border transition-all ${
                hb.enabled
                  ? 'bg-zinc-900/60 border-zinc-800/80 hover:border-zinc-700/80'
                  : 'bg-zinc-950/40 border-zinc-800/40 opacity-75'
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-1.5 flex-1 min-w-0">
                  <div className="flex items-center gap-2.5 flex-wrap">
                    <h3 className="text-sm font-bold text-zinc-100 truncate">{hb.name}</h3>

                    {/* Enabled / Disabled Badge */}
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                        hb.enabled
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                          : 'bg-zinc-800/60 text-zinc-500 border-zinc-700/40'
                      }`}
                    >
                      {hb.enabled ? 'Activo' : 'Inactivo'}
                    </span>

                    {/* Interval Badge */}
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-zinc-800/70 text-zinc-300 text-[11px] font-medium border border-zinc-700/50">
                      <Clock size={11} className="text-indigo-400" />
                      {formatInterval(hb.interval_seconds)}
                    </span>

                    {/* Last Status Badge */}
                    {hb.last_status && (
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-medium border ${
                          hb.last_status === 'success'
                            ? 'bg-emerald-950/40 text-emerald-300 border-emerald-800/40'
                            : 'bg-red-950/40 text-red-300 border-red-800/40'
                        }`}
                      >
                        {hb.last_status === 'success' ? (
                          <CheckCircle size={10} className="text-emerald-400" />
                        ) : (
                          <AlertTriangle size={10} className="text-red-400" />
                        )}
                        {hb.last_status === 'success' ? 'Éxito' : 'Error'}
                      </span>
                    )}
                  </div>

                  {/* Prompt Text Preview */}
                  <div className="flex items-start gap-2 bg-zinc-950/60 p-2.5 rounded-lg border border-zinc-800/60 font-mono text-[11px] text-zinc-300">
                    <MessageSquare size={13} className="text-zinc-500 mt-0.5 shrink-0" />
                    <p className="line-clamp-2 leading-relaxed whitespace-pre-wrap">{hb.prompt}</p>
                  </div>

                  {/* Details Row */}
                  <div className="flex items-center gap-4 text-[11px] text-zinc-500 pt-1">
                    {hb.session_id && (
                      <span className="flex items-center gap-1">
                        <Terminal size={11} />
                        Sesión: <code className="text-zinc-400">{hb.session_id}</code>
                      </span>
                    )}
                    {hb.last_run && (
                      <span>
                        Última ejecución:{' '}
                        <span className="text-zinc-400">
                          {new Date(hb.last_run).toLocaleString()}
                        </span>
                      </span>
                    )}
                    {hb.last_error && (
                      <span className="text-red-400 truncate max-w-xs" title={hb.last_error}>
                        Error: {hb.last_error}
                      </span>
                    )}
                  </div>
                </div>

                {/* Quick Action Controls */}
                <div className="flex items-center gap-1.5 shrink-0">
                  {/* Toggle Switch */}
                  <button
                    onClick={() => handleToggle(hb)}
                    className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                      hb.enabled ? 'bg-indigo-600' : 'bg-zinc-700'
                    }`}
                    title={hb.enabled ? 'Desactivar heartbeat' : 'Activar heartbeat'}
                  >
                    <span
                      className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                        hb.enabled ? 'translate-x-4' : 'translate-x-0'
                      }`}
                    />
                  </button>

                  {/* Trigger Now Button */}
                  <button
                    onClick={() => handleTriggerNow(hb.id)}
                    disabled={triggeringId === hb.id}
                    className="p-1.5 rounded-lg bg-zinc-800/80 hover:bg-indigo-600/20 text-zinc-400 hover:text-indigo-300 border border-zinc-700/60 transition-all disabled:opacity-50"
                    title="Ejecutar ahora manualmente"
                  >
                    {triggeringId === hb.id ? (
                      <Loader2 size={14} className="animate-spin text-indigo-400" />
                    ) : (
                      <Play size={14} />
                    )}
                  </button>

                  {/* Edit Button */}
                  <button
                    onClick={() => handleOpenEdit(hb)}
                    className="p-1.5 rounded-lg bg-zinc-800/80 hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 border border-zinc-700/60 transition-all"
                    title="Editar heartbeat"
                  >
                    <Edit2 size={14} />
                  </button>

                  {/* Delete Button */}
                  <button
                    onClick={() => handleDelete(hb.id, hb.name)}
                    className="p-1.5 rounded-lg bg-zinc-800/80 hover:bg-red-950/50 text-zinc-400 hover:text-red-400 border border-zinc-700/60 hover:border-red-800/50 transition-all"
                    title="Eliminar heartbeat"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal / Form Overlay for Create & Edit */}
      {isFormOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="w-full max-w-lg rounded-2xl bg-zinc-900 border border-zinc-800 shadow-2xl overflow-hidden space-y-0">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-4 border-b border-zinc-800 bg-zinc-900/50">
              <h3 className="text-sm font-bold text-zinc-100 flex items-center gap-2">
                <Activity size={16} className="text-indigo-400" />
                {editingHeartbeat ? 'Editar Heartbeat' : 'Nuevo Heartbeat'}
              </h3>
              <button
                onClick={() => setIsFormOpen(false)}
                className="p-1 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
              >
                <X size={16} />
              </button>
            </div>

            {/* Modal Form Content */}
            <form onSubmit={handleSave} className="p-5 space-y-4">
              {formError && (
                <div className="p-3 rounded-lg bg-red-950/50 border border-red-800/50 text-red-300 text-xs flex items-center gap-2">
                  <ShieldAlert size={14} className="shrink-0 text-red-400" />
                  <span>{formError}</span>
                </div>
              )}

              {/* Name Input */}
              <div className="space-y-1">
                <label className="text-xs font-semibold text-zinc-300">Nombre descriptivo *</label>
                <input
                  type="text"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="ej. Git Repository Health Watcher"
                  className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-xs text-zinc-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                  required
                />
              </div>

              {/* Prompt Input */}
              <div className="space-y-1">
                <label className="text-xs font-semibold text-zinc-300">
                  Instrucción / Prompt periódico *
                </label>
                <textarea
                  value={formPrompt}
                  onChange={(e) => setFormPrompt(e.target.value)}
                  placeholder="ej. Revisa si hay archivos pendientes en git status y resume los cambios."
                  rows={3}
                  className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-xs text-zinc-100 font-mono focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 resize-none"
                  required
                />
              </div>

              {/* Interval & Unit Input */}
              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-2 space-y-1">
                  <label className="text-xs font-semibold text-zinc-300">Periodicidad / Intervalo *</label>
                  <input
                    type="number"
                    min={1}
                    value={formIntervalValue}
                    onChange={(e) => setFormIntervalValue(Math.max(1, parseInt(e.target.value) || 1))}
                    className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-xs text-zinc-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                    required
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-zinc-300">Unidad</label>
                  <select
                    value={formIntervalUnit}
                    onChange={(e) => setFormIntervalUnit(e.target.value as any)}
                    className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-xs text-zinc-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                  >
                    <option value="seconds">Segundos</option>
                    <option value="minutes">Minutos</option>
                    <option value="hours">Horas</option>
                  </select>
                </div>
              </div>

              {/* Session ID Input */}
              <div className="space-y-1">
                <label className="text-xs font-semibold text-zinc-300">ID de Sesión Objetivo (Opcional)</label>
                <input
                  type="text"
                  value={formSessionId}
                  onChange={(e) => setFormSessionId(e.target.value)}
                  placeholder="ej. mi_sesion_dedicada (Si está vacío, se crea una por defecto)"
                  className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-xs text-zinc-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                />
              </div>

              {/* Enabled Checkbox */}
              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="formEnabled"
                  checked={formEnabled}
                  onChange={(e) => setFormEnabled(e.target.checked)}
                  className="w-4 h-4 rounded bg-zinc-950 border-zinc-800 text-indigo-600 focus:ring-indigo-500"
                />
                <label htmlFor="formEnabled" className="text-xs text-zinc-300 cursor-pointer select-none">
                  Activar este heartbeat inmediatamente tras guardar
                </label>
              </div>

              {/* Modal Footer Buttons */}
              <div className="flex items-center justify-end gap-2 pt-4 border-t border-zinc-800">
                <button
                  type="button"
                  onClick={() => setIsFormOpen(false)}
                  className="px-4 py-2 rounded-lg text-xs font-semibold text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md shadow-indigo-600/20 transition-all disabled:opacity-50"
                >
                  {saving ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    <Save size={14} />
                  )}
                  Guardar Heartbeat
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
