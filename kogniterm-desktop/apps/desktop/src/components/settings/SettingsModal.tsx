import React, { useState, useEffect } from 'react';
import { 
  X, Save, Cpu, CheckCircle, AlertCircle, 
  Trash2, Plus, Globe, Folder, Settings, MessageSquare, 
  Send, Eye, EyeOff, Loader2, Sparkles 
} from 'lucide-react';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface ConfigScopeData {
  global: Record<string, any>;
  project: Record<string, any>;
  merged: Record<string, any>;
  has_keys: Record<string, boolean>;
}

interface ProviderModel {
  id: string;
  name: string;
  models: string[];
}

export const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState<'llm' | 'advanced' | 'instructions' | 'telegram'>('llm');
  const [activeScope, setActiveScope] = useState<'global' | 'project'>('project');
  
  // Config loaded from backend
  const [originalConfig, setOriginalConfig] = useState<ConfigScopeData | null>(null);
  
  // Edited values
  const [editableGlobal, setEditableGlobal] = useState<Record<string, any>>({});
  const [editableProject, setEditableProject] = useState<Record<string, any>>({});
  
  // API Keys inputs (separate from main config object to manage text changes cleanly)
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({
    google: '',
    openai: '',
    anthropic: '',
    openrouter: '',
    kilocode: '',
    ollama_cloud: ''
  });
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});

  // Telegram Config
  const [telegramEnabled, setTelegramEnabled] = useState(false);
  const [telegramName, setTelegramName] = useState('telegram_bot_default');
  const [telegramToken, setTelegramToken] = useState('');
  const [telegramChatId, setTelegramChatId] = useState('');
  const [isTelegramModified, setIsTelegramModified] = useState(false);

  // Telegram chat_id detection
  const [isDetectingChatId, setIsDetectingChatId] = useState(false);
  const [detectionStatus, setDetectionStatus] = useState<string | null>(null);

  // Available models from backend
  const [providers, setProviders] = useState<ProviderModel[]>([]);
  const [selectedProvider, setSelectedProvider] = useState('google');

  // Input for adding new instruction
  const [newInstruction, setNewInstruction] = useState('');

  // UI state
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState<{ type: 'success' | 'error', message: string } | null>(null);

  useEffect(() => {
    if (isOpen) {
      fetchConfig();
      fetchAvailableModels();
      fetchTelegramConfig();
    }
  }, [isOpen]);

  const fetchConfig = async () => {
    try {
      const res = await fetch('http://localhost:8765/api/config/all');
      if (res.ok) {
        const data: ConfigScopeData = await res.json();
        setOriginalConfig(data);
        setEditableGlobal({ ...data.global });
        setEditableProject({ ...data.project });

        // Infer active provider based on current default_model
        const activeModel = data.merged.default_model || 'gemini/gemini-1.5-flash';
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
      console.error('Error fetching configuration:', error);
    }
  };

  const fetchAvailableModels = async () => {
    try {
      const res = await fetch('http://localhost:8765/api/models/available');
      if (res.ok) {
        const data = await res.json();
        if (data.providers) {
          setProviders(data.providers);
        }
      }
    } catch (error) {
      console.error('Error fetching available models:', error);
    }
  };

  const fetchTelegramConfig = async () => {
    try {
      const res = await fetch('http://localhost:8765/config/channels');
      if (res.ok) {
        const data = await res.json();
        const channels = data.channels || [];
        const tgChannel = channels.find((c: any) => c.type === 'telegram_bot');
        if (tgChannel) {
          setTelegramEnabled(tgChannel.enabled);
          setTelegramName(tgChannel.name);
          setTelegramToken(tgChannel.params?.token || '');
          setTelegramChatId(tgChannel.params?.chat_id?.toString() || '');
        } else {
          setTelegramEnabled(false);
          setTelegramName('telegram_bot_default');
          setTelegramToken('');
          setTelegramChatId('');
        }
        setIsTelegramModified(false);
      }
    } catch (error) {
      console.error('Error fetching telegram channels:', error);
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

  const toggleShowKey = (provider: string) => {
    setShowKeys(prev => ({ ...prev, [provider]: !prev[provider] }));
  };

  const handleAddInstruction = () => {
    if (!newInstruction.trim()) return;
    const currentList = getScopeValue('agent_instructions', activeScope) || [];
    const updatedList = [...currentList, newInstruction.trim()];
    setScopeValue('agent_instructions', updatedList, activeScope);
    setNewInstruction('');
  };

  const handleRemoveInstruction = (index: number) => {
    const currentList = getScopeValue('agent_instructions', activeScope) || [];
    const updatedList = currentList.filter((_: any, i: number) => i !== index);
    setScopeValue('agent_instructions', updatedList, activeScope);
  };

  const detectTelegramChatId = async () => {
    if (!telegramToken.trim()) {
      setDetectionStatus('Por favor, ingresa el token del bot primero.');
      return;
    }
    setIsDetectingChatId(true);
    setDetectionStatus('Buscando mensajes privados... Envía cualquier mensaje a tu bot en Telegram.');

    try {
      const res = await fetch('http://localhost:8765/api/config/telegram/detect-chat-id', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: telegramToken })
      });

      if (res.ok) {
        const data = await res.json();
        if (data.chat_id) {
          setTelegramChatId(data.chat_id.toString());
          setIsTelegramModified(true);
          setDetectionStatus(`¡Chat ID detectado con éxito: ${data.chat_id}!`);
        } else {
          setDetectionStatus('No se detectó ningún mensaje privado. Asegúrate de haberle hablado al bot e intenta nuevamente.');
        }
      } else {
        setDetectionStatus('Error al conectar con la API de Telegram. Verifica el token.');
      }
    } catch (error) {
      setDetectionStatus('Error de conexión.');
    } finally {
      setIsDetectingChatId(false);
    }
  };

  const handleSaveAll = async () => {
    setIsLoading(true);
    setStatus(null);
    try {
      const savePromises: Promise<any>[] = [];

      // 1. Detect configuration differences for Global scope
      if (originalConfig) {
        for (const key in editableGlobal) {
          if (JSON.stringify(editableGlobal[key]) !== JSON.stringify(originalConfig.global[key])) {
            savePromises.push(
              fetch('http://localhost:8765/api/config/set', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ key, value: editableGlobal[key], scope: 'global' })
              })
            );
          }
        }

        // 2. Detect configuration differences for Project scope
        for (const key in editableProject) {
          if (JSON.stringify(editableProject[key]) !== JSON.stringify(originalConfig.project[key])) {
            savePromises.push(
              fetch('http://localhost:8765/api/config/set', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ key, value: editableProject[key], scope: 'project' })
              })
            );
          }
        }
      }

      // 3. Save modified API Keys
      const activeKeysScope = activeScope; 
      const providersKeys = ['google', 'openai', 'anthropic', 'openrouter', 'kilocode', 'ollama_cloud'];
      for (const provider of providersKeys) {
        const inputKey = apiKeys[provider];
        if (inputKey && inputKey.trim() !== '') {
          savePromises.push(
            fetch('http://localhost:8765/api/config/set_key', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ 
                provider, 
                key_value: inputKey.trim(),
                scope: activeKeysScope
              })
            })
          );
        }
      }

      // 4. Save Telegram Bot Configuration
      if (isTelegramModified) {
        const tgPayload = {
          name: telegramName,
          type: 'telegram_bot',
          enabled: telegramEnabled,
          params: {
            token: telegramToken,
            chat_id: telegramChatId ? parseInt(telegramChatId, 10) : undefined
          }
        };

        savePromises.push(
          fetch('http://localhost:8765/config/channels', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(tgPayload)
          })
        );
      }

      // Wait for all saves to finish
      if (savePromises.length > 0) {
        const results = await Promise.all(savePromises);
        const allOk = results.every(res => res.ok);
        if (allOk) {
          setStatus({ type: 'success', message: 'Configuraciones guardadas con éxito.' });
          setTimeout(() => {
            onClose();
            window.location.reload();
          }, 1500);
        } else {
          setStatus({ type: 'error', message: 'Algunos cambios no pudieron guardarse.' });
        }
      } else {
        setStatus({ type: 'success', message: 'No hay cambios nuevos que guardar.' });
        setTimeout(() => onClose(), 1000);
      }

    } catch (error) {
      console.error(error);
      setStatus({ type: 'error', message: 'Error de conexión con el backend.' });
    } finally {
      setIsLoading(false);
    }
  };

  const getInheritedValue = (key: string) => {
    if (!originalConfig) return null;
    return originalConfig.global[key];
  };

  if (!isOpen) return null;

  const currentModels = providers.find(p => p.id === selectedProvider)?.models || [];
  const activeInstructions = getScopeValue('agent_instructions', activeScope) || [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/30 backdrop-blur-md animate-fade-in">
      <div className="w-full max-w-3xl h-[620px] bg-white border border-slate-200/90 rounded-3xl shadow-[0_20px_60px_rgba(0,0,0,0.12)] flex flex-col overflow-hidden select-none">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50/50 shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-indigo-50 border border-indigo-100 text-indigo-600">
              <Settings size={18} />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-slate-900 leading-none">Ajustes del Sistema</h2>
              <p className="text-xs text-slate-500 mt-1">Personaliza modelos, preferencias globales y canales de KogniTerm</p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-1.5 rounded-full hover:bg-slate-200/60 text-slate-400 hover:text-slate-700 transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Scope Selector Bar */}
        <div className="px-6 py-3 bg-slate-50/30 border-b border-slate-100 flex items-center justify-between shrink-0 text-xs">
          <span className="font-semibold text-slate-400 tracking-wide text-[11px]">ÁMBITO DE APLICACIÓN:</span>
          <div className="flex bg-slate-200/60 p-1 rounded-xl gap-1">
            <button
              onClick={() => setActiveScope('global')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs transition-all ${
                activeScope === 'global'
                  ? 'bg-white text-slate-900 font-semibold shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <Globe size={13} className="text-slate-400" />
              Global (Usuario)
            </button>
            <button
              onClick={() => setActiveScope('project')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs transition-all ${
                activeScope === 'project'
                  ? 'bg-white text-slate-900 font-semibold shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <Folder size={13} className="text-slate-400" />
              Proyecto (Local)
            </button>
          </div>
        </div>

        {/* Content Area */}
        <div className="flex flex-1 min-h-0">
          
          {/* Sidebar Tabs */}
          <aside className="w-[210px] border-r border-slate-100 bg-slate-50/60 flex flex-col p-3 gap-1.5 shrink-0">
            {[
              { id: 'llm', name: 'Modelos y Llaves', icon: Cpu },
              { id: 'advanced', name: 'Ajustes Avanzados', icon: Settings },
              { id: 'instructions', name: 'Instrucciones', icon: MessageSquare },
              { id: 'telegram', name: 'Bot de Telegram', icon: Send },
            ].map(tab => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs transition-all text-left ${
                    activeTab === tab.id
                      ? 'bg-white text-indigo-600 font-semibold border border-slate-200/80 shadow-card-light'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/50'
                  }`}
                >
                  <Icon size={15} />
                  <span>{tab.name}</span>
                </button>
              );
            })}
          </aside>

          {/* Main Panel Pane */}
          <main className="flex-1 overflow-y-auto goose-scrollbar p-6">
            
            {/* LLM Models and Keys Tab */}
            {activeTab === 'llm' && (
              <div className="space-y-6 animate-fade-in">
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">Modelos de Lenguaje</h3>
                  
                  {/* Providers Grid */}
                  <div className="space-y-2">
                    <label className="text-[11px] font-medium text-slate-500">Proveedor</label>
                    <div className="grid grid-cols-4 gap-2">
                      {[
                        { id: 'google', name: 'Google AI' },
                        { id: 'openai', name: 'OpenAI' },
                        { id: 'anthropic', name: 'Anthropic' },
                        { id: 'openrouter', name: 'OpenRouter' },
                        { id: 'ollama', name: 'Ollama (Local)' },
                        { id: 'ollama_cloud', name: 'Ollama Cloud' },
                        { id: 'antigravity', name: 'Antigravity' },
                        { id: 'kilocode', name: 'KiloCode' },
                      ].map(prov => (
                        <button
                          key={prov.id}
                          type="button"
                          onClick={() => {
                            setSelectedProvider(prov.id);
                            const p = providers.find(pr => pr.id === prov.id);
                            const defaultM = p?.models[0] || (prov.id === 'google' ? 'gemini/gemini-1.5-flash' : '');
                            if (defaultM) {
                              setScopeValue('default_model', defaultM, activeScope);
                            }
                          }}
                          className={`px-3 py-2.5 rounded-xl border text-xs font-medium transition-all text-left flex items-center justify-between ${
                            selectedProvider === prov.id
                              ? 'bg-indigo-50/80 border-indigo-200 text-indigo-700 font-semibold shadow-xs'
                              : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50 hover:border-slate-300'
                          }`}
                        >
                          {prov.name}
                          {selectedProvider === prov.id && <div className="w-1.5 h-1.5 rounded-full bg-indigo-600" />}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Model Dropdown */}
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <label className="text-[11px] font-medium text-slate-500">Modelo Predeterminado</label>
                    {activeScope === 'project' && getInheritedValue('default_model') && (
                      <span className="text-[10px] text-slate-400 font-mono">Heredado global: {getInheritedValue('default_model')}</span>
                    )}
                  </div>
                  {currentModels.length > 0 ? (
                    <select
                      value={getScopeValue('default_model', activeScope) || ''}
                      onChange={(e) => setScopeValue('default_model', e.target.value, activeScope)}
                      className="w-full bg-slate-50 border border-slate-200/90 rounded-xl px-3.5 py-2.5 text-xs text-slate-800 focus:bg-white focus:border-indigo-500 transition-all focus:outline-none"
                    >
                      <option value="">Selecciona un modelo...</option>
                      {currentModels.map(m => (
                        <option key={m} value={m}>{m}</option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type="text"
                      value={getScopeValue('default_model', activeScope) || ''}
                      onChange={(e) => setScopeValue('default_model', e.target.value, activeScope)}
                      className="w-full bg-slate-50 border border-slate-200/90 rounded-xl px-3.5 py-2.5 text-xs text-slate-800 focus:bg-white focus:border-indigo-500 transition-all focus:outline-none"
                      placeholder="Ej: gemini/gemini-1.5-flash o gpt-4o"
                    />
                  )}
                </div>

                {/* API Keys */}
                {selectedProvider !== 'ollama' && selectedProvider !== 'antigravity' && (
                  <div className="space-y-2">
                    <div className="flex justify-between items-center">
                      <label className="text-[11px] font-medium text-slate-500">
                        API Key para {selectedProvider.toUpperCase()}
                      </label>
                      {originalConfig?.has_keys[`api_key_${selectedProvider}`] && (
                        <span className="text-[10px] text-emerald-600 font-medium flex items-center gap-1">
                          <CheckCircle size={11} /> Registrada en Backend
                        </span>
                      )}
                    </div>
                    <div className="relative flex items-center">
                      <input
                        type={showKeys[selectedProvider] ? 'text' : 'password'}
                        value={apiKeys[selectedProvider] || ''}
                        onChange={(e) => setApiKeys({ ...apiKeys, [selectedProvider]: e.target.value })}
                        className="w-full bg-slate-50 border border-slate-200/90 rounded-xl px-3.5 py-2.5 pr-10 text-xs text-slate-800 focus:bg-white focus:border-indigo-500 font-mono transition-all focus:outline-none"
                        placeholder={
                          originalConfig?.has_keys[`api_key_${selectedProvider}`] 
                            ? "••••••••••••••••••••••••••••••••" 
                            : "Escribe o pega tu API Key..."
                        }
                      />
                      <button
                        type="button"
                        onClick={() => toggleShowKey(selectedProvider)}
                        className="absolute right-3 text-slate-400 hover:text-slate-600"
                      >
                        {showKeys[selectedProvider] ? <EyeOff size={14} /> : <Eye size={14} />}
                      </button>
                    </div>
                  </div>
                )}

                {selectedProvider === 'antigravity' && (
                  <div className="p-4 bg-indigo-50/70 border border-indigo-100 rounded-2xl text-xs text-indigo-800 leading-relaxed flex flex-col gap-2">
                    <span className="font-semibold flex items-center gap-1.5 text-indigo-900">
                      <Sparkles size={14} className="text-indigo-600" /> Sesión Antigravity
                    </span>
                    <span>
                      Autenticado mediante sesión local de Google Cloud SDK. No requiere API Key estática.
                    </span>
                  </div>
                )}

                {selectedProvider === 'ollama' && (
                  <div className="space-y-2">
                    <label className="text-[11px] font-medium text-slate-500">Servidor de Ollama (Base URL)</label>
                    <input
                      type="text"
                      value={getScopeValue('ollama_api_base', activeScope) || ''}
                      onChange={(e) => setScopeValue('ollama_api_base', e.target.value, activeScope)}
                      className="w-full bg-slate-50 border border-slate-200/90 rounded-xl px-3.5 py-2.5 text-xs text-slate-800 focus:bg-white focus:border-indigo-500 transition-all focus:outline-none"
                      placeholder="http://127.0.0.1:11434"
                    />
                  </div>
                )}
              </div>
            )}

            {/* Advanced Settings Tab */}
            {activeTab === 'advanced' && (
              <div className="space-y-6 animate-fade-in">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">Parámetros del Sistema</h3>

                {/* Reasoning Effort setting */}
                <div className="space-y-2">
                  <label className="text-[11px] font-medium text-slate-500">Esfuerzo de Razonamiento</label>
                  <select
                    value={getScopeValue('reasoning_effort', activeScope) || 'medium'}
                    onChange={(e) => setScopeValue('reasoning_effort', e.target.value, activeScope)}
                    className="w-full bg-slate-50 border border-slate-200/90 rounded-xl px-3.5 py-2.5 text-xs text-slate-800 focus:bg-white focus:border-indigo-500 transition-all focus:outline-none"
                  >
                    <option value="low">Bajo (Low)</option>
                    <option value="medium">Medio (Medium)</option>
                    <option value="high">Alto (High)</option>
                  </select>
                </div>

                {/* Summary Model setting */}
                <div className="space-y-2">
                  <label className="text-[11px] font-medium text-slate-500">Modelo de Resumen (Summary Model)</label>
                  <input
                    type="text"
                    value={getScopeValue('summary_model', activeScope) || ''}
                    onChange={(e) => setScopeValue('summary_model', e.target.value, activeScope)}
                    className="w-full bg-slate-50 border border-slate-200/90 rounded-xl px-3.5 py-2.5 text-xs text-slate-800 focus:bg-white focus:border-indigo-500 transition-all focus:outline-none"
                    placeholder="Ej: gemini/gemini-1.5-flash"
                  />
                </div>

                {/* Auto Approve setting */}
                <div className="space-y-2 pt-4 border-t border-slate-100">
                  <div className="flex items-center justify-between">
                    <div>
                      <label className="text-xs font-semibold text-slate-800">Auto-aprobar Comandos y Ediciones</label>
                      <p className="text-[11px] text-slate-500 mt-0.5">
                        Ejecuta automáticamente modificaciones de archivos y comandos bash sin solicitar confirmación manual.
                      </p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer select-none">
                      <input 
                        type="checkbox" 
                        checked={Boolean(getScopeValue('auto_approve', activeScope))} 
                        onChange={(e) => setScopeValue('auto_approve', e.target.checked, activeScope)}
                        className="sr-only peer" 
                      />
                      <div className="w-10 h-5 bg-slate-200 rounded-full peer peer-checked:bg-indigo-600 peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all shadow-xs"></div>
                    </label>
                  </div>
                </div>
              </div>
            )}

            {/* System Instructions Tab */}
            {activeTab === 'instructions' && (
              <div className="space-y-5 animate-fade-in">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">Instrucciones del Agente</h3>
                  <span className="text-[10px] text-slate-500 bg-slate-100 border border-slate-200 px-2.5 py-1 rounded-full font-medium uppercase">
                    Ámbito: {activeScope}
                  </span>
                </div>

                <div className="space-y-2 max-h-[240px] overflow-y-auto goose-scrollbar border border-slate-200/80 bg-slate-50/50 p-3 rounded-2xl">
                  {activeInstructions.length > 0 ? (
                    activeInstructions.map((instr: string, index: number) => (
                      <div 
                        key={index}
                        className="flex items-center justify-between gap-3 p-3 bg-white border border-slate-200/80 rounded-xl text-xs shadow-xs"
                      >
                        <span className="text-slate-700 flex-1">{instr}</span>
                        <button
                          type="button"
                          onClick={() => handleRemoveInstruction(index)}
                          className="p-1 text-slate-400 hover:text-rose-500 hover:bg-rose-50 rounded-lg transition-colors"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    ))
                  ) : (
                    <div className="py-8 text-center text-xs text-slate-400 italic">
                      No hay instrucciones personalizadas configuradas en este ámbito.
                    </div>
                  )}
                </div>

                {/* Add instruction */}
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={newInstruction}
                    onChange={(e) => setNewInstruction(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') handleAddInstruction(); }}
                    className="flex-1 bg-slate-50 border border-slate-200/90 rounded-xl px-3.5 py-2.5 text-xs text-slate-800 focus:bg-white focus:border-indigo-500 transition-all focus:outline-none"
                    placeholder="Añadir una pauta..."
                  />
                  <button
                    type="button"
                    onClick={handleAddInstruction}
                    className="p-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl transition-all shadow-xs"
                  >
                    <Plus size={16} />
                  </button>
                </div>
              </div>
            )}

            {/* Telegram Bot Integration Tab */}
            {activeTab === 'telegram' && (
              <div className="space-y-5 animate-fade-in">
                <div className="flex items-center justify-between border-b border-slate-100 pb-4">
                  <div>
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">Telegram Bot</h3>
                    <p className="text-xs text-slate-500 mt-1">Control remoto del asistente mediante Telegram</p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer select-none">
                    <input 
                      type="checkbox" 
                      checked={telegramEnabled} 
                      onChange={(e) => {
                        setTelegramEnabled(e.target.checked);
                        setIsTelegramModified(true);
                      }}
                      className="sr-only peer" 
                    />
                    <div className="w-10 h-5 bg-slate-200 rounded-full peer peer-checked:bg-indigo-600 peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all shadow-xs"></div>
                  </label>
                </div>

                {telegramEnabled && (
                  <div className="space-y-4 pt-1">
                    <div className="space-y-1.5">
                      <label className="text-[11px] font-medium text-slate-500">Nombre del Bot</label>
                      <input
                        type="text"
                        value={telegramName}
                        onChange={(e) => {
                          setTelegramName(e.target.value);
                          setIsTelegramModified(true);
                        }}
                        className="w-full bg-slate-50 border border-slate-200/90 rounded-xl px-3.5 py-2.5 text-xs text-slate-800 focus:bg-white focus:border-indigo-500 transition-all focus:outline-none"
                        placeholder="MiAsistenteBot"
                      />
                    </div>

                    <div className="space-y-1.5">
                      <label className="text-[11px] font-medium text-slate-500">Bot Token (BotFather)</label>
                      <input
                        type="password"
                        value={telegramToken}
                        onChange={(e) => {
                          setTelegramToken(e.target.value);
                          setIsTelegramModified(true);
                        }}
                        className="w-full bg-slate-50 border border-slate-200/90 rounded-xl px-3.5 py-2.5 text-xs text-slate-800 font-mono focus:bg-white focus:border-indigo-500 transition-all focus:outline-none"
                        placeholder="123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ..."
                      />
                    </div>

                    <div className="space-y-1.5">
                      <label className="text-[11px] font-medium text-slate-500">Chat ID Permitido</label>
                      <div className="flex gap-2">
                        <input
                          type="text"
                          value={telegramChatId}
                          onChange={(e) => {
                            setTelegramChatId(e.target.value);
                            setIsTelegramModified(true);
                          }}
                          className="flex-1 bg-slate-50 border border-slate-200/90 rounded-xl px-3.5 py-2.5 text-xs text-slate-800 font-mono focus:bg-white focus:border-indigo-500 transition-all focus:outline-none"
                          placeholder="Ej: 987654321"
                        />
                        <button
                          type="button"
                          onClick={detectTelegramChatId}
                          disabled={isDetectingChatId || !telegramToken}
                          className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-indigo-600 font-semibold border border-slate-200 rounded-xl text-xs transition-colors shrink-0 flex items-center gap-1.5"
                        >
                          {isDetectingChatId ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
                          Detectar ID
                        </button>
                      </div>
                    </div>

                    {detectionStatus && (
                      <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-600">
                        {detectionStatus}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

          </main>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-slate-50/60 border-t border-slate-100 flex items-center justify-between shrink-0">
          <div className="flex-1 pr-4">
            {status && (
              <div className={`p-2 rounded-xl text-xs font-medium flex items-center gap-2 ${
                status.type === 'success' ? 'text-emerald-700 bg-emerald-50 border border-emerald-200' : 'text-rose-700 bg-rose-50 border border-rose-200'
              }`}>
                {status.type === 'success' ? <CheckCircle size={14} /> : <AlertCircle size={14} />}
                {status.message}
              </div>
            )}
          </div>

          <div className="flex justify-end gap-2.5">
            <button
              onClick={onClose}
              disabled={isLoading}
              className="px-4 py-2.5 rounded-xl text-xs font-semibold text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-all"
            >
              Cancelar
            </button>
            <button
              onClick={handleSaveAll}
              disabled={isLoading}
              className="px-5 py-2.5 rounded-xl text-xs font-semibold bg-slate-900 hover:bg-slate-800 text-white shadow-card-light hover:shadow-md transition-all flex items-center gap-2 active:scale-[0.98]"
            >
              {isLoading ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
              Guardar Cambios
            </button>
          </div>
        </div>

      </div>
    </div>
  );
};
