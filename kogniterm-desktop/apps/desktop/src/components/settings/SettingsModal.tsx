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
    ollama_cloud: '',
    custom_openai: ''
  });
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});

  // Telegram Config
  const [telegramEnabled, setTelegramEnabled] = useState(false);
  const [telegramName, setTelegramName] = useState('telegram_bot_default');
  const [telegramToken, setTelegramToken] = useState('');
  const [telegramChatId, setTelegramChatId] = useState('');
  const [isTelegramModified, setIsTelegramModified] = useState(false);
  const [originalTelegram, setOriginalTelegram] = useState<any>(null);

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
        else if (modelLower.includes('custom_openai') || modelLower.includes('custom-openai')) inferredProvider = 'custom_openai';
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
          setOriginalTelegram(tgChannel);
          setTelegramEnabled(tgChannel.enabled);
          setTelegramName(tgChannel.name);
          setTelegramToken(tgChannel.params?.token || '');
          setTelegramChatId(tgChannel.params?.chat_id?.toString() || '');
        } else {
          setOriginalTelegram(null);
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
      const activeKeysScope = activeScope; // Guardar las llaves en el scope activo
      const providersKeys = ['google', 'openai', 'anthropic', 'openrouter', 'kilocode', 'ollama_cloud', 'custom_openai'];
      for (const provider of providersKeys) {
        const inputKey = apiKeys[provider];
        if (inputKey && inputKey.trim() !== '') {
          savePromises.push(
            fetch('http://localhost:8765/api/config/set', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ 
                key: `api_key_${provider}`, 
                value: inputKey.trim(), 
                scope: activeKeysScope 
              })
            })
          );
        }
      }

      // 4. Save Telegram channel configuration if modified
      const currentTgState = {
        enabled: telegramEnabled,
        name: telegramName,
        token: telegramToken,
        chat_id: telegramChatId
      };
      
      const originalTgState = originalTelegram ? {
        enabled: originalTelegram.enabled,
        name: originalTelegram.name,
        token: originalTelegram.params?.token || '',
        chat_id: originalTelegram.params?.chat_id?.toString() || ''
      } : {
        enabled: false,
        name: 'telegram_bot_default',
        token: '',
        chat_id: ''
      };

      const tgModified = JSON.stringify(currentTgState) !== JSON.stringify(originalTgState) || isTelegramModified;

      if (tgModified) {
        const tgPayload = {
          name: telegramName || "telegram_bot_default",
          type: "telegram_bot",
          enabled: telegramEnabled,
          params: {
            token: telegramToken,
            chat_id: telegramChatId ? parseInt(telegramChatId, 10) || telegramChatId : null
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
            window.location.reload(); // Recargar para aplicar los cambios del socket y backend
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="w-full max-w-3xl h-[600px] bg-[#111113] border border-zinc-800 rounded-2xl shadow-2xl flex flex-col overflow-hidden glass-panel select-none">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800/80 bg-zinc-900/40 shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-1.5 rounded-lg bg-indigo-600/10 text-indigo-400">
              <Settings size={18} />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white leading-none">Panel de Configuración</h2>
              <p className="text-[10px] text-zinc-500 mt-1">Configura el comportamiento, modelos y bot de KogniTerm</p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-1.5 rounded-full hover:bg-zinc-800/80 text-zinc-500 hover:text-white transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Scope selector bar */}
        <div className="px-6 py-2.5 bg-zinc-900/20 border-b border-zinc-800/60 flex items-center justify-between shrink-0 text-xs text-zinc-400">
          <span className="font-semibold text-zinc-500">ÁMBITO A EDITAR:</span>
          <div className="flex bg-zinc-900 border border-zinc-800 p-0.5 rounded-lg">
            <button
              onClick={() => setActiveScope('global')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-medium transition-all ${
                activeScope === 'global'
                  ? 'bg-indigo-600/10 border border-indigo-500/20 text-indigo-400 font-semibold'
                  : 'border border-transparent hover:text-zinc-200'
              }`}
            >
              <Globe size={13} />
              Global (Usuario)
            </button>
            <button
              onClick={() => setActiveScope('project')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-medium transition-all ${
                activeScope === 'project'
                  ? 'bg-indigo-600/10 border border-indigo-500/20 text-indigo-400 font-semibold'
                  : 'border border-transparent hover:text-zinc-200'
              }`}
            >
              <Folder size={13} />
              Proyecto (Local)
            </button>
          </div>
        </div>

        {/* Content Area */}
        <div className="flex flex-1 min-h-0">
          
          {/* Sidebar Tabs */}
          <aside className="w-[200px] border-r border-zinc-800/60 bg-zinc-900/10 flex flex-col p-3 gap-1 shrink-0">
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
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-semibold transition-all text-left ${
                    activeTab === tab.id
                      ? 'bg-indigo-600/15 text-indigo-400 border border-indigo-500/20 shadow-md shadow-indigo-500/5'
                      : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/40 border border-transparent'
                  }`}
                >
                  <Icon size={15} />
                  <span>{tab.name}</span>
                </button>
              );
            })}
          </aside>

          {/* Main Panel Pane */}
          <main className="flex-1 overflow-y-auto custom-scrollbar p-6">
            
            {/* LLM Models and Keys Tab */}
            {activeTab === 'llm' && (
              <div className="space-y-5 animate-in fade-in duration-150">
                <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400 mb-2">Configuración LLM</h3>
                      {/* Providers list selection */}
                <div className="space-y-2">
                  <label className="text-[10px] font-bold text-zinc-500 uppercase tracking-wide">Proveedor de Inteligencia Artificial</label>
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
                      { id: 'custom_openai', name: 'Custom OpenAI' },
                    ].map(prov => (
                      <button
                        key={prov.id}
                        type="button"
                        onClick={() => {
                          setSelectedProvider(prov.id);
                          // Default model assignment if empty
                          const p = providers.find(pr => pr.id === prov.id);
                          const defaultM = p?.models[0] || (prov.id === 'google' ? 'gemini/gemini-1.5-flash' : prov.id === 'custom_openai' ? 'custom_openai/local-model' : '');
                          if (defaultM) {
                            setScopeValue('default_model', defaultM, activeScope);
                          }
                        }}
                        className={`px-2.5 py-2.5 rounded-lg border text-[11px] font-medium transition-all text-left flex items-center justify-between ${
                          selectedProvider === prov.id
                            ? 'bg-indigo-600/10 border-indigo-500/30 text-indigo-300 shadow-[0_0_10px_rgba(99,102,241,0.15)] font-semibold'
                            : 'bg-zinc-900/50 border-zinc-800 text-zinc-400 hover:bg-zinc-800 hover:border-zinc-700'
                        }`}
                      >
                        {prov.name}
                        {selectedProvider === prov.id && <div className="w-1.5 h-1.5 rounded-full bg-indigo-400" />}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Model dropdown selection */}
                <div className="space-y-1.5">
                  <div className="flex justify-between items-center">
                    <label className="text-[10px] font-bold text-zinc-500 uppercase tracking-wide">Modelo Predeterminado</label>
                    {activeScope === 'project' && getInheritedValue('default_model') && (
                      <span className="text-[9px] text-zinc-600 font-mono">Heredado global: {getInheritedValue('default_model')}</span>
                    )}
                  </div>
                  <div className="relative">
                    {currentModels.length > 0 ? (
                      <select
                        value={getScopeValue('default_model', activeScope) || ''}
                        onChange={(e) => setScopeValue('default_model', e.target.value, activeScope)}
                        className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2.5 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500 transition-colors"
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
                        className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2.5 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500 transition-colors"
                        placeholder="Ej: gemini/gemini-1.5-flash o gpt-4o"
                      />
                    )}
                  </div>
                </div>

                {/* API Key inputs */}
                {selectedProvider !== 'ollama' && selectedProvider !== 'antigravity' && (
                  <div className="space-y-1.5">
                    <div className="flex justify-between items-center">
                      <label className="text-[10px] font-bold text-zinc-500 uppercase tracking-wide">
                        API Key para {selectedProvider.toUpperCase()}
                      </label>
                      {originalConfig?.has_keys[`api_key_${selectedProvider}`] && (
                        <span className="text-[9px] text-emerald-500/80 font-bold flex items-center gap-1">
                          <CheckCircle size={10} /> Registrada en Backend
                        </span>
                      )}
                    </div>
                    <div className="relative flex items-center">
                      <input
                        type={showKeys[selectedProvider] ? 'text' : 'password'}
                        value={apiKeys[selectedProvider] || ''}
                        onChange={(e) => setApiKeys({ ...apiKeys, [selectedProvider]: e.target.value })}
                        className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2.5 pr-10 text-xs text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-indigo-500 transition-colors font-mono"
                        placeholder={
                          originalConfig?.has_keys[`api_key_${selectedProvider}`] 
                            ? "••••••••••••••••••••••••••••••••" 
                            : "Escribe o pega la clave de API aquí..."
                        }
                      />
                      <button
                        type="button"
                        onClick={() => toggleShowKey(selectedProvider)}
                        className="absolute right-3 text-zinc-500 hover:text-zinc-300"
                      >
                        {showKeys[selectedProvider] ? <EyeOff size={14} /> : <Eye size={14} />}
                      </button>
                    </div>
                    <p className="text-[9px] text-zinc-650 italic">
                      Las llaves de API se enmascaran en tránsito y se almacenan de forma segura de acuerdo a la configuración local o de usuario.
                    </p>
                  </div>
                )}

                {selectedProvider === 'antigravity' && (
                  <div className="p-3.5 bg-indigo-950/20 border border-indigo-900/35 rounded-xl text-xs text-indigo-300 leading-relaxed flex flex-col gap-2">
                    <span className="font-bold flex items-center gap-1.5 text-indigo-400">
                      <Sparkles size={13} className="animate-pulse" /> Autenticación por Sesión de Antigravity
                    </span>
                    <span>
                      Google Antigravity no requiere una clave de API estática. En su lugar, utiliza las credenciales de tu sesión OAuth2 de Google Cloud SDK local. Asegúrate de haber iniciado sesión ejecutando <code>agy login</code> o <code>gcloud auth application-default login</code> en tu terminal de trabajo.
                    </span>
                  </div>
                )}

                {/* Local Ollama API URL (if selectedProvider === 'ollama') */}
                {selectedProvider === 'ollama' && (
                  <div className="space-y-1.5">
                    <div className="flex justify-between items-center">
                      <label className="text-[10px] font-bold text-zinc-500 uppercase tracking-wide">Servidor de Ollama (Base URL)</label>
                      {activeScope === 'project' && getInheritedValue('ollama_api_base') && (
                        <span className="text-[9px] text-zinc-600 font-mono">Heredado: {getInheritedValue('ollama_api_base')}</span>
                      )}
                    </div>
                    <input
                      type="text"
                      value={getScopeValue('ollama_api_base', activeScope) || ''}
                      onChange={(e) => setScopeValue('ollama_api_base', e.target.value, activeScope)}
                      className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2.5 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500 transition-colors"
                      placeholder="http://127.0.0.1:11434"
                    />
                  </div>
                )}

                {/* Custom OpenAI Base URL (if selectedProvider === 'custom_openai') */}
                {selectedProvider === 'custom_openai' && (
                  <div className="space-y-1.5">
                    <div className="flex justify-between items-center">
                      <label className="text-[10px] font-bold text-zinc-500 uppercase tracking-wide">URL Base de API Compatible con OpenAI</label>
                      {activeScope === 'project' && getInheritedValue('custom_openai_api_base') && (
                        <span className="text-[9px] text-zinc-650 font-mono">Heredado: {getInheritedValue('custom_openai_api_base')}</span>
                      )}
                    </div>
                    <input
                      type="text"
                      value={getScopeValue('custom_openai_api_base', activeScope) || ''}
                      onChange={(e) => setScopeValue('custom_openai_api_base', e.target.value, activeScope)}
                      className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2.5 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500 transition-colors"
                      placeholder="http://localhost:8387/v1"
                    />
                  </div>
                )}
              </div>
            )}

            {/* Advanced Settings Tab */}
            {activeTab === 'advanced' && (
              <div className="space-y-5 animate-in fade-in duration-150">
                <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400 mb-2">Ajustes Avanzados</h3>

                {/* Reasoning Effort setting */}
                <div className="space-y-1.5">
                  <div className="flex justify-between items-center">
                    <label className="text-[10px] font-bold text-zinc-500 uppercase tracking-wide">Esfuerzo de Razonamiento (Reasoning Effort)</label>
                    {activeScope === 'project' && getInheritedValue('reasoning_effort') && (
                      <span className="text-[9px] text-zinc-600 uppercase font-bold">Heredado: {getInheritedValue('reasoning_effort')}</span>
                    )}
                  </div>
                  <select
                    value={getScopeValue('reasoning_effort', activeScope) || 'medium'}
                    onChange={(e) => setScopeValue('reasoning_effort', e.target.value, activeScope)}
                    className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2.5 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500 transition-colors"
                  >
                    <option value="low">Bajo (Low)</option>
                    <option value="medium">Medio (Medium)</option>
                    <option value="high">Alto (High)</option>
                  </select>
                  <p className="text-[9px] text-zinc-500">Afecta el nivel de procesamiento y el tiempo de respuesta en modelos con razonamiento nativo.</p>
                </div>

                {/* Summary Model setting */}
                <div className="space-y-1.5">
                  <div className="flex justify-between items-center">
                    <label className="text-[10px] font-bold text-zinc-500 uppercase tracking-wide">Modelo de Resumen (Summary Model)</label>
                    {activeScope === 'project' && getInheritedValue('summary_model') && (
                      <span className="text-[9px] text-zinc-600 font-mono">Heredado: {getInheritedValue('summary_model')}</span>
                    )}
                  </div>
                  <input
                    type="text"
                    value={getScopeValue('summary_model', activeScope) || ''}
                    onChange={(e) => setScopeValue('summary_model', e.target.value, activeScope)}
                    className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2.5 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500 transition-colors"
                    placeholder="Ej: gemini/gemini-1.5-flash"
                  />
                  <p className="text-[9px] text-zinc-500">Modelo utilizado para generar resúmenes cortos al consolidar hilos de conversación.</p>
                </div>

                {/* TUI Theme setting */}
                <div className="space-y-1.5">
                  <div className="flex justify-between items-center">
                    <label className="text-[10px] font-bold text-zinc-500 uppercase tracking-wide">Tema de la TUI</label>
                    {activeScope === 'project' && getInheritedValue('theme') && (
                      <span className="text-[9px] text-zinc-600 font-semibold">Heredado: {getInheritedValue('theme')}</span>
                    )}
                  </div>
                  <select
                    value={getScopeValue('theme', activeScope) || 'default'}
                    onChange={(e) => setScopeValue('theme', e.target.value, activeScope)}
                    className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2.5 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500 transition-colors"
                  >
                    <option value="default">Por Defecto</option>
                    <option value="dracula">Dracula</option>
                    <option value="nord">Nord</option>
                    <option value="monokai">Monokai</option>
                    <option value="solarized-dark">Solarized Dark</option>
                    <option value="solarized-light">Solarized Light</option>
                    <option value="github-dark">GitHub Dark</option>
                    <option value="github-light">GitHub Light</option>
                    <option value="gruvbox">Gruvbox</option>
                    <option value="one-dark">One Dark</option>
                  </select>
                  <p className="text-[9px] text-zinc-500">Cambia la paleta de colores empleada al interactuar con el asistente en la terminal (TUI).</p>
                </div>
              </div>
            )}

            {/* Agent System Instructions Tab */}
            {activeTab === 'instructions' && (
              <div className="space-y-5 animate-in fade-in duration-150">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400">Instrucciones del Agente</h3>
                  <span className="text-[9px] text-zinc-500 bg-zinc-900 border border-zinc-800 px-2 py-0.5 rounded-full font-bold uppercase">
                    Ámbito: {activeScope}
                  </span>
                </div>

                <p className="text-[10px] text-zinc-500 leading-normal mb-3">
                  Añade pautas de comportamiento fijas para el asistente (ej. *"Responde siempre en español"*, *"Evita modificar código sin antes justificarlo"*).
                </p>

                {/* Instructions List */}
                <div className="space-y-1.5 max-h-[220px] overflow-y-auto custom-scrollbar border border-zinc-800/80 bg-zinc-950/40 p-2.5 rounded-xl">
                  {activeInstructions.length > 0 ? (
                    activeInstructions.map((instr: string, index: number) => (
                      <div 
                        key={index}
                        className="flex items-start justify-between gap-3 p-2 bg-[#17171a] border border-zinc-800/50 rounded-lg text-xs hover:border-zinc-800 transition-colors animate-in slide-in-from-bottom-2 duration-100"
                      >
                        <span className="text-zinc-300 break-words flex-1 pr-2">{instr}</span>
                        <button
                          type="button"
                          onClick={() => handleRemoveInstruction(index)}
                          className="p-1 text-zinc-500 hover:text-red-400 hover:bg-red-400/10 rounded transition-all shrink-0 mt-0.5"
                          title="Eliminar instrucción"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    ))
                  ) : (
                    <div className="py-8 text-center text-[10px] text-zinc-500 italic">
                      No hay instrucciones personalizadas configuradas en este ámbito.
                    </div>
                  )}
                </div>

                {/* Add new Instruction input */}
                <div className="flex items-center gap-2 mt-2">
                  <input
                    type="text"
                    value={newInstruction}
                    onChange={(e) => setNewInstruction(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') handleAddInstruction(); }}
                    className="flex-1 bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2.5 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500 placeholder-zinc-650 transition-colors"
                    placeholder="Añadir una nueva pauta o instrucción de sistema..."
                  />
                  <button
                    type="button"
                    onClick={handleAddInstruction}
                    className="p-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition-colors flex items-center justify-center shrink-0 shadow-lg shadow-indigo-600/10"
                  >
                    <Plus size={16} />
                  </button>
                </div>
              </div>
            )}

            {/* Telegram Bot Integration Tab */}
            {activeTab === 'telegram' && (
              <div className="space-y-4 animate-in fade-in duration-150">
                <div className="flex items-center justify-between border-b border-zinc-800/60 pb-3">
                  <div>
                    <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400 leading-none">Integración Telegram Bot</h3>
                    <p className="text-[9px] text-zinc-500 mt-1.5">Permite controlar tu asistente de forma remota a través de Telegram</p>
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
                    <div className="w-9 h-5 bg-zinc-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-zinc-450 after:border-zinc-350 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-indigo-600 peer-checked:after:bg-white peer-checked:after:border-white"></div>
                  </label>
                </div>

                {telegramEnabled && (
                  <div className="space-y-4 pt-1 animate-in slide-in-from-top-3 duration-200">
                    {/* Name input */}
                    <div className="grid grid-cols-3 items-center gap-4">
                      <label className="text-[10px] font-bold text-zinc-500 uppercase tracking-wide">Nombre del Bot</label>
                      <div className="col-span-2">
                        <input
                          type="text"
                          value={telegramName}
                          onChange={(e) => {
                            setTelegramName(e.target.value);
                            setIsTelegramModified(true);
                          }}
                          className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500 transition-colors"
                          placeholder="MiAsistenteBot"
                        />
                      </div>
                    </div>

                    {/* Token input */}
                    <div className="grid grid-cols-3 items-center gap-4">
                      <label className="text-[10px] font-bold text-zinc-500 uppercase tracking-wide">Bot Token (BotFather)</label>
                      <div className="col-span-2">
                        <input
                          type="password"
                          value={telegramToken}
                          onChange={(e) => {
                            setTelegramToken(e.target.value);
                            setIsTelegramModified(true);
                          }}
                          className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500 transition-colors font-mono"
                          placeholder="123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ..."
                        />
                      </div>
                    </div>

                    {/* Chat ID input & Detection Button */}
                    <div className="grid grid-cols-3 items-start gap-4">
                      <div className="space-y-0.5">
                        <label className="text-[10px] font-bold text-zinc-500 uppercase tracking-wide">Chat ID Permitido</label>
                        <p className="text-[9px] text-zinc-600">Solo este chat controlará el bot</p>
                      </div>
                      <div className="col-span-2 flex gap-2">
                        <input
                          type="text"
                          value={telegramChatId}
                          onChange={(e) => {
                            setTelegramChatId(e.target.value);
                            setIsTelegramModified(true);
                          }}
                          className="flex-1 bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500 transition-colors font-mono"
                          placeholder="Ej: 987654321"
                        />
                        <button
                          type="button"
                          onClick={detectTelegramChatId}
                          disabled={isDetectingChatId || !telegramToken}
                          className="px-3 py-2 bg-zinc-900 hover:bg-zinc-800 disabled:opacity-50 text-indigo-400 hover:text-indigo-300 font-semibold border border-zinc-850 rounded-lg text-xs transition-colors shrink-0 flex items-center gap-1.5"
                        >
                          {isDetectingChatId ? (
                            <Loader2 size={13} className="animate-spin" />
                          ) : (
                            <Send size={12} />
                          )}
                          Detectar ID
                        </button>
                      </div>
                    </div>

                    {/* Detection Status alert box */}
                    {detectionStatus && (
                      <div className="p-3 bg-zinc-950 border border-zinc-800 rounded-xl text-[10px] text-zinc-400 leading-normal animate-in fade-in duration-200">
                        {detectionStatus.includes('éxito') ? (
                          <span className="text-emerald-400 font-bold block mb-1">✓ Éxito</span>
                        ) : detectionStatus.includes('Error') ? (
                          <span className="text-rose-400 font-bold block mb-1">✗ Error</span>
                        ) : (
                          <span className="text-indigo-400 font-bold block mb-1">ℹ Instrucciones</span>
                        )}
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
        <div className="px-6 py-4 bg-zinc-900/40 border-t border-zinc-850 flex items-center justify-between shrink-0">
          
          {/* Status Message */}
          <div className="flex-1 pr-4">
            {status && (
              <div className={`p-2.5 rounded-lg text-[10px] font-medium flex items-center gap-2 animate-in fade-in duration-300 max-w-sm ${
                status.type === 'success' 
                  ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400' 
                  : 'bg-rose-500/10 border border-rose-500/20 text-rose-400'
              }`}>
                {status.type === 'success' ? <CheckCircle size={13} /> : <AlertCircle size={13} />}
                {status.message}
              </div>
            )}
          </div>

          <div className="flex justify-end gap-2.5">
            <button
              onClick={onClose}
              disabled={isLoading}
              className="px-4 py-2 rounded-lg text-xs font-semibold text-zinc-500 hover:text-white hover:bg-zinc-900 transition-colors"
            >
              Cancelar
            </button>
            <button
              onClick={handleSaveAll}
              disabled={isLoading}
              className="px-4 py-2 rounded-lg text-xs font-bold bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-500/25 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 transition-all"
            >
              {isLoading ? (
                <Loader2 size={13} className="animate-spin" />
              ) : (
                <Save size={13} />
              )}
              Guardar Cambios
            </button>
          </div>
        </div>

      </div>
    </div>
  );
};
