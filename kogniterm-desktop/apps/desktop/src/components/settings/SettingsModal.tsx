import React, { useState, useEffect } from 'react';
import { X, Save, Key, Cpu, Server, CheckCircle, AlertCircle } from 'lucide-react';

interface SettingsModalProps {
    isOpen: boolean;
    onClose: () => void;
}

interface LLMSettings {
    provider: string;
    model: string;
    api_key: string;
    api_key_masked?: string;
}

const PROVIDERS = [
    { id: 'google', name: 'Google AI Studio', defaultModel: 'gemini-1.5-flash' },
    { id: 'openrouter', name: 'OpenRouter / SiliconFlow', defaultModel: 'deepseek/deepseek-r1:free' },
    { id: 'openai', name: 'OpenAI', defaultModel: 'gpt-4o' },
];

export const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose }) => {
    const [settings, setSettings] = useState<LLMSettings>({
        provider: 'google',
        model: 'gemini-1.5-flash',
        api_key: ''
    });
    const [isLoading, setIsLoading] = useState(false);
    const [status, setStatus] = useState<{ type: 'success' | 'error', message: string } | null>(null);

    // Cargar configuración al abrir
    useEffect(() => {
        if (isOpen) {
            fetchSettings();
        }
    }, [isOpen]);

    const fetchSettings = async () => {
        try {
            const res = await fetch('http://localhost:8765/api/config/llm');
            if (res.ok) {
                const data = await res.json();
                setSettings({
                    provider: data.provider,
                    model: data.model.replace(/^(gemini\/|openrouter\/)/, ''), // Limpiar prefijos para visualización limpia
                    api_key: '', // No mostrar la key real
                    api_key_masked: data.api_key_masked
                });
            }
        } catch (error) {
            console.error('Error fetching settings:', error);
        }
    };

    const handleSave = async () => {
        setIsLoading(true);
        setStatus(null);
        try {
            const res = await fetch('http://localhost:8765/api/config/llm', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });

            if (res.ok) {
                setStatus({ type: 'success', message: 'Configuración guardada correctamente.' });
                setTimeout(() => {
                    onClose();
                    window.location.reload(); // Recargar para aplicar cambios en socket
                }, 1500);
            } else {
                setStatus({ type: 'error', message: 'Error al guardar la configuración.' });
            }
        } catch (error) {
            setStatus({ type: 'error', message: 'Error de conexión.' });
        } finally {
            setIsLoading(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="w-full max-w-md bg-[#18181b] border border-zinc-700 rounded-2xl shadow-2xl overflow-hidden glass-panel">

                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-700/50 bg-zinc-900/50">
                    <h2 className="text-lg font-bold text-white flex items-center gap-2">
                        <Cpu className="text-indigo-400" size={20} />
                        Configuración LLM
                    </h2>
                    <button
                        onClick={onClose}
                        className="p-2 rounded-full hover:bg-zinc-700/50 text-zinc-400 hover:text-white transition-colors"
                    >
                        <X size={18} />
                    </button>
                </div>

                {/* Body */}
                <div className="p-6 space-y-6">

                    {/* Provider */}
                    <div className="space-y-2">
                        <label className="text-xs font-medium text-zinc-400 uppercase tracking-wider flex items-center gap-2">
                            <Server size={14} /> Proveedor
                        </label>
                        <div className="grid grid-cols-1 gap-2">
                            {PROVIDERS.map((p) => (
                                <button
                                    key={p.id}
                                    onClick={() => setSettings({ ...settings, provider: p.id, model: p.defaultModel })}
                                    className={`px-4 py-3 rounded-xl border text-sm font-medium transition-all text-left flex items-center justify-between ${settings.provider === p.id
                                            ? 'bg-indigo-600/10 border-indigo-500 text-indigo-300 shadow-[0_0_15px_rgba(99,102,241,0.2)]'
                                            : 'bg-zinc-800/50 border-zinc-700/50 text-zinc-400 hover:bg-zinc-800 hover:border-zinc-600'
                                        }`}
                                >
                                    {p.name}
                                    {settings.provider === p.id && <CheckCircle size={16} className="text-indigo-400" />}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Model Name */}
                    <div className="space-y-2">
                        <label className="text-xs font-medium text-zinc-400 uppercase tracking-wider flex items-center gap-2">
                            <Cpu size={14} /> Modelo
                        </label>
                        <input
                            type="text"
                            value={settings.model}
                            onChange={(e) => setSettings({ ...settings, model: e.target.value })}
                            className="w-full bg-zinc-900/50 border border-zinc-700/50 rounded-xl px-4 py-3 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/50 transition-all"
                            placeholder="Ej: gemini-1.5-flash"
                        />
                    </div>

                    {/* API Key */}
                    <div className="space-y-2">
                        <label className="text-xs font-medium text-zinc-400 uppercase tracking-wider flex items-center gap-2">
                            <Key size={14} /> API Key
                        </label>
                        <div className="relative">
                            <input
                                type="password"
                                value={settings.api_key}
                                onChange={(e) => setSettings({ ...settings, api_key: e.target.value })}
                                className="w-full bg-zinc-900/50 border border-zinc-700/50 rounded-xl px-4 py-3 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/50 transition-all font-mono"
                                placeholder={settings.api_key_masked || "Pegar nueva API Key aquí..."}
                            />
                        </div>
                        <p className="text-[10px] text-zinc-500 ml-1">
                            La clave guardada no se mostrará por seguridad.
                        </p>
                    </div>

                    {/* Status Message */}
                    {status && (
                        <div className={`p-3 rounded-lg text-xs font-medium flex items-center gap-2 animate-in fade-in duration-300 ${status.type === 'success' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'
                            }`}>
                            {status.type === 'success' ? <CheckCircle size={14} /> : <AlertCircle size={14} />}
                            {status.message}
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="px-6 py-4 bg-zinc-900/50 border-t border-zinc-700/50 flex justify-end gap-3">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 rounded-lg text-sm font-medium text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
                    >
                        Cancelar
                    </button>
                    <button
                        onClick={handleSave}
                        disabled={isLoading || !settings.api_key && !settings.api_key_masked} // Permitir guardar si solo cambia modelo
                        className="px-4 py-2 rounded-lg text-sm font-bold bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-500/20 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 transition-all"
                    >
                        {isLoading ? (
                            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        ) : (
                            <Save size={16} />
                        )}
                        Guardar Cambios
                    </button>
                </div>
            </div>
        </div>
    );
};
