import React, { useState, useEffect } from 'react';
import { Settings, Cpu, Globe, Folder, Key, Check, AlertCircle, RefreshCw, X, Server } from 'lucide-react';

interface ProviderModel {
  id: string;
  name: string;
  models: string[];
}

interface ConfigScopeData {
  global: Record<string, any>;
  project: Record<string, any>;
  merged: Record<string, any>;
}

interface LLMSettingsProps {
  isOpen: boolean;
  onClose: () => void;
}

export const LLMSettingsModal: React.FC<LLMSettingsProps> = ({ isOpen, onClose }) => {
  const [activeScope, setActiveScope] = useState<'global' | 'project'>('project');
  const [originalConfig, setOriginalConfig] = useState<ConfigScopeData | null>(null);
  const [editableGlobal, setEditableGlobal] = useState<Record<string, any>>({});
  const [editableProject, setEditableProject] = useState<Record<string, any>>({});
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({
    google: '',
    openai: '',
    anthropic: '',
    openrouter: '',
    kilocode: '',
    ollama_cloud: ''
  });

  const [providers, setProviders] = useState<ProviderModel[]>([
    { id: 'google', name: 'Google AI', models: ['gemini/gemini-2.5-pro', 'gemini/gemini-2.5-flash', 'gemini/gemini-1.5-pro'] },
    { id: 'openai', name: 'OpenAI', models: ['openai/gpt-4o', 'openai/gpt-4o-mini', 'openai/o1-mini', 'openai/o3-mini'] },
    { id: 'anthropic', name: 'Anthropic', models: ['anthropic/claude-3-5-sonnet', 'anthropic/claude-3-5-haiku'] },
    { id: 'openrouter', name: 'OpenRouter', models: ['openrouter/auto'] },
    { id: 'ollama', name: 'Ollama (Local)', models: ['ollama/llama3.1', 'ollama/codellama', 'ollama/qwen2.5-coder'] },
    { id: 'ollama_cloud', name: 'Ollama Cloud', models: ['ollama_cloud/qwen2.5-coder-72b'] },
    { id: 'antigravity', name: 'Antigravity', models: ['antigravity/gemini-2.5-pro', 'antigravity/claude-3-5-sonnet'] },
    { id: 'kilocode', name: 'KiloCode', models: ['kilocode/kilo-auto'] }
  ]);

  const [selectedProvider, setSelectedProvider] = useState<string>('google');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [status, setStatus] = useState<{ type: 'success' | 'error', message: string } | null>(null);

  useEffect(() => {
    if (isOpen) {
      fetchConfig();
      fetchAvailableModels();
    }
  }, [isOpen]);

  const fetchConfig = async () => {
    try {
      const res = await fetch('/api/config/all');
      if (res.ok) {
        const data: ConfigScopeData = await res.json();
        setOriginalConfig(data);
        setEditableGlobal({ ...data.global });
        setEditableProject({ ...data.project });

        const activeModel = data.merged?.default_model || 'gemini/gemini-2.5-flash';
        let inferredProvider = 'google';
        const modelLower = activeModel.toLowerCase();
        if (modelLower.includes('openrouter')) inferredProvider = 'openrouter';
        else if (modelLower.includes('gpt') || modelLower.includes('openai') || modelLower.startsWith('o1') || modelLower.startsWith('o3')) inferredProvider = 'openai';
        else if (modelLower.includes('claude') || modelLower.includes('anthropic')) inferredProvider = 'anthropic';
        else if (modelLower.includes('ollama_cloud')) inferredProvider = 'ollama_cloud';
        else if (modelLower.includes('ollama')) inferredProvider = 'ollama';
        else if (modelLower.includes('antigravity')) inferredProvider = 'antigravity';
        else if (modelLower.includes('kilocode')) inferredProvider = 'kilocode';
        setSelectedProvider(inferredProvider);
      }
    } catch (error) {
      console.warn('Backend REST endpoint /api/config/all no responde. Usando simulación local.');
    }
  };

  const fetchAvailableModels = async () => {
    try {
      const res = await fetch('/api/models/available');
      if (res.ok) {
        const data = await res.json();
        if (data.providers) {
          setProviders(data.providers);
        }
      }
    } catch (error) {
      console.warn('Backend REST endpoint /api/models/available no responde.');
    }
  };

  const getScopeValue = (key: string, scope: 'global' | 'project') => {
    const target = scope === 'global' ? editableGlobal : editableProject;
    return target[key];
  };

  const setScopeValue = (key: string, value: any, scope: 'global' | 'project') => {
    if (scope === 'global') {
      setEditableGlobal(prev => ({ ...prev, [key]: value }));
    } else {
      setEditableProject(prev => ({ ...prev, [key]: value }));
    }
  };

  const handleSaveAll = async () => {
    setIsLoading(true);
    setStatus(null);
    try {
      const savePromises: Promise<any>[] = [];

      // 1. Guardar cambios Globales
      if (originalConfig) {
        for (const key in editableGlobal) {
          if (JSON.stringify(editableGlobal[key]) !== JSON.stringify(originalConfig.global[key])) {
            savePromises.push(
              fetch('/api/config/set', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ key, value: editableGlobal[key], scope: 'global' })
              })
            );
          }
        }

        // 2. Guardar cambios Proyecto
        for (const key in editableProject) {
          if (JSON.stringify(editableProject[key]) !== JSON.stringify(originalConfig.project[key])) {
            savePromises.push(
              fetch('/api/config/set', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ key, value: editableProject[key], scope: 'project' })
              })
            );
          }
        }
      }

      // 3. Guardar API Keys
      const providersKeys = ['google', 'openai', 'anthropic', 'openrouter', 'kilocode', 'ollama_cloud'];
      for (const provider of providersKeys) {
        const inputKey = apiKeys[provider];
        if (inputKey && inputKey.trim() !== '') {
          savePromises.push(
            fetch('/api/config/set_key', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ 
                provider, 
                key_value: inputKey.trim(),
                scope: activeScope
              })
            })
          );
        }
      }

      if (savePromises.length > 0) {
        const results = await Promise.all(savePromises);
        const allOk = results.every(res => res.ok);
        if (allOk) {
          setStatus({ type: 'success', message: 'Configuración guardada exitosamente en kogniterm-server.' });
          setTimeout(() => onClose(), 1200);
        } else {
          setStatus({ type: 'error', message: 'Algunos cambios no pudieron guardarse.' });
        }
      } else {
        setStatus({ type: 'success', message: 'Configuración actualizada.' });
        setTimeout(() => onClose(), 1000);
      }

    } catch (error) {
      console.error(error);
      setStatus({ type: 'error', message: 'Error al conectar con kogniterm-server.' });
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  const currentModels = providers.find(p => p.id === selectedProvider)?.models || [];
  const selectedModelValue = getScopeValue('default_model', activeScope) || currentModels[0] || '';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-md p-4">
      <div className="w-full max-w-2xl bg-[#18181b] border border-white/10 rounded-2xl shadow-2xl flex flex-col overflow-hidden text-zinc-100 font-sans text-xs">
        
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-black/30">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
              <Cpu className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white">Configuración LLM & Modelos</h2>
              <p className="text-[11px] text-zinc-400">Réplica exacta del mecanismo backend de Kogniterm Desktop</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-white/10 text-zinc-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Scope Bar */}
        <div className="px-6 py-2.5 bg-black/20 border-b border-white/5 flex items-center justify-between text-xs">
          <span className="font-semibold text-zinc-500 text-[10px] uppercase tracking-wider">Ámbito de Configuración:</span>
          <div className="flex bg-zinc-900 p-1 rounded-xl gap-1 border border-white/5">
            <button
              onClick={() => setActiveScope('global')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs transition-all ${
                activeScope === 'global' ? 'bg-indigo-600 text-white font-medium' : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              <Globe className="w-3.5 h-3.5" /> Global (Usuario)
            </button>
            <button
              onClick={() => setActiveScope('project')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs transition-all ${
                activeScope === 'project' ? 'bg-indigo-600 text-white font-medium' : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              <Folder className="w-3.5 h-3.5" /> Proyecto (Local)
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-6 overflow-y-auto max-h-[460px] custom-scrollbar">
          
          {/* Provider Selector */}
          <div>
            <label className="text-xs font-semibold text-zinc-300 block mb-2">Proveedor de Lenguaje</label>
            <div className="grid grid-cols-4 gap-2">
              {providers.map(prov => (
                <button
                  key={prov.id}
                  type="button"
                  onClick={() => {
                    setSelectedProvider(prov.id);
                    const defaultM = prov.models[0] || '';
                    if (defaultM) setScopeValue('default_model', defaultM, activeScope);
                  }}
                  className={`px-3 py-2.5 rounded-xl border text-xs font-medium transition-all text-left flex items-center justify-between ${
                    selectedProvider === prov.id
                      ? 'bg-indigo-600/20 border-indigo-500/50 text-indigo-300 font-semibold'
                      : 'bg-zinc-900/60 border-white/5 text-zinc-400 hover:bg-zinc-800'
                  }`}
                >
                  <span className="truncate">{prov.name}</span>
                  {selectedProvider === prov.id && <div className="w-1.5 h-1.5 rounded-full bg-indigo-400" />}
                </button>
              ))}
            </div>
          </div>

          {/* Model Selector */}
          <div>
            <label className="text-xs font-semibold text-zinc-300 block mb-1.5">Modelo Predeterminado</label>
            <select
              value={selectedModelValue}
              onChange={(e) => setScopeValue('default_model', e.target.value, activeScope)}
              className="w-full bg-zinc-900 border border-white/10 rounded-xl px-4 py-2.5 text-xs text-zinc-200 outline-none focus:border-indigo-500"
            >
              {currentModels.map(m => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>

          {/* API Key Input */}
          <div>
            <label className="text-xs font-semibold text-zinc-300 block mb-1.5 flex items-center gap-1.5">
              <Key className="w-3.5 h-3.5 text-indigo-400" /> API Key ({selectedProvider.toUpperCase()})
            </label>
            <input
              type="password"
              placeholder={`Ingresa tu API Key para ${selectedProvider}...`}
              value={apiKeys[selectedProvider] || ''}
              onChange={(e) => setApiKeys({ ...apiKeys, [selectedProvider]: e.target.value })}
              className="w-full bg-zinc-900 border border-white/10 rounded-xl px-4 py-2.5 text-xs text-zinc-200 font-mono focus:border-indigo-500 outline-none"
            />
            <p className="text-[10px] text-zinc-500 mt-1">Se guardará de forma segura en las variables de entorno o archivo de configuración de Kogniterm.</p>
          </div>

          {status && (
            <div className={`p-3 rounded-xl flex items-center gap-2 text-xs ${status.type === 'success' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'}`}>
              {status.type === 'success' ? <Check className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
              <span>{status.message}</span>
            </div>
          )}

        </div>

        {/* Modal Footer */}
        <div className="p-4 bg-black/40 border-t border-white/5 flex items-center justify-end space-x-2">
          <button onClick={onClose} className="px-4 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors">
            Cancelar
          </button>
          <button
            onClick={handleSaveAll}
            disabled={isLoading}
            className="px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium transition-colors shadow-lg glow-indigo disabled:opacity-50 flex items-center gap-2"
          >
            {isLoading && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
            Guardar Configuración
          </button>
        </div>

      </div>
    </div>
  );
};
