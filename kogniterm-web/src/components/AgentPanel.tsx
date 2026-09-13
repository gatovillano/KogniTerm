import React, { useState } from 'react';
import { Bot, Cpu, Terminal, Code, Shield, Plus, Edit2 } from 'lucide-react';
import { useAgents } from '../hooks/useAgents';

interface AgentPanelProps {
  selectedAgent: string;
  setSelectedAgent: (id: string) => void;
}

const iconMap: Record<string, any> = {
  cpu: Cpu,
  terminal: Terminal,
  code: Code,
  shield: Shield,
  bot: Bot
};

export function AgentPanel({ selectedAgent, setSelectedAgent }: AgentPanelProps) {
  const { agents, loading, createCustomAgent } = useAgents();
  const [isCreating, setIsCreating] = useState(false);
  
  // Formulario de creación
  const [newAgent, setNewAgent] = useState({
    name: '',
    role: '',
    description: '',
    model: 'gemini-2.5-pro',
    config: {}
  });

  const handleCreate = async () => {
    if (!newAgent.name.trim() || !newAgent.role.trim()) return;
    const success = await createCustomAgent(newAgent);
    if (success) {
      setIsCreating(false);
      setNewAgent({ name: '', role: '', description: '', model: 'gemini-2.5-pro', config: {} });
    }
  };

  if (loading) {
    return <div className="p-8 text-center opacity-70">Cargando agentes...</div>;
  }

  return (
    <div className="flex-1 p-8 overflow-y-auto custom-scrollbar">
      <div className="max-w-4xl mx-auto space-y-6">
        
        {/* Header con botón de creación */}
        <div className="flex justify-between items-center">
          <h2 className="text-lg font-semibold">Panel de Agentes Autónomos</h2>
          <button 
            onClick={() => setIsCreating(true)}
            className="px-4 py-2 chat-card rounded-lg flex items-center space-x-2 hover:opacity-90 transition-all"
          >
            <Plus className="w-4 h-4" />
            <span>Crear Agente</span>
          </button>
        </div>

        {/* Formulario de creación (si está activo) */}
        {isCreating && (
          <div className="chat-card p-6 rounded-2xl space-y-4">
            <h3 className="font-semibold">Crear Agente Personalizado</h3>
            <div className="grid grid-cols-2 gap-4">
              <input 
                type="text" 
                placeholder="Nombre"
                value={newAgent.name}
                onChange={(e) => setNewAgent({...newAgent, name: e.target.value})}
                className="chat-input-box rounded-lg p-2"
              />
              <input 
                type="text" 
                placeholder="Rol"
                value={newAgent.role}
                onChange={(e) => setNewAgent({...newAgent, role: e.target.value})}
                className="chat-input-box rounded-lg p-2"
              />
              <input 
                type="text" 
                placeholder="Modelo LLM"
                value={newAgent.model}
                onChange={(e) => setNewAgent({...newAgent, model: e.target.value})}
                className="chat-input-box rounded-lg p-2 col-span-2"
              />
              <textarea 
                placeholder="Descripción"
                value={newAgent.description}
                onChange={(e) => setNewAgent({...newAgent, description: e.target.value})}
                className="chat-input-box rounded-lg p-2 col-span-2"
                rows={3}
              />
            </div>
            <div className="flex space-x-2 pt-2">
              <button 
                onClick={handleCreate}
                className="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-500 transition-colors"
              >
                Crear
              </button>
              <button 
                onClick={() => setIsCreating(false)}
                className="px-4 py-2 chat-card rounded-lg hover:opacity-100"
              >
                Cancelar
              </button>
            </div>
          </div>
        )}

        {/* Grid de Agentes */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {agents.map(agent => {
            const Icon = iconMap[agent.icon] || Bot;
            return (
              <div 
                key={agent.id} 
                className={`chat-card p-5 rounded-2xl flex flex-col space-y-4 cursor-pointer transition-all border-2 ${
                  selectedAgent === agent.id ? 'border-indigo-500 bg-indigo-500/5' : 'border-transparent hover:border-indigo-500/30'
                }`}
                onClick={() => setSelectedAgent(agent.id)}
              >
                <div className="flex items-center space-x-3">
                  <div className="p-2.5 rounded-xl chat-card text-emerald-500">
                    <Icon className="w-5 h-5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center space-x-2">
                      <h3 className="font-semibold text-sm truncate">{agent.name}</h3>
                      {agent.is_custom && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-400 whitespace-nowrap">
                          Personalizado
                        </span>
                      )}
                    </div>
                    <p className="text-xs opacity-70">{agent.role}</p>
                    {agent.description && (
                      <p className="text-xs opacity-50 mt-1 line-clamp-2">{agent.description}</p>
                    )}
                  </div>
                </div>
                <div className="flex items-center justify-between pt-3 border-t border-inherit text-xs">
                  <span className="font-mono opacity-60">{agent.model}</span>
                  {selectedAgent !== agent.id && (
                    <button className="px-3 py-1 rounded chat-card hover:opacity-100 transition-opacity">
                      Seleccionar
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}