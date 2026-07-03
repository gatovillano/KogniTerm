import React, { useState, useEffect } from 'react';
import { 
  Search, Zap, Shield, ShieldAlert, ShieldCheck, 
  Copy, Code, Terminal, User, FileCode, Check, RefreshCw 
} from 'lucide-react';

interface ToolInfo {
  name: string;
  description: string;
}

interface SkillInfo {
  name: string;
  version: string;
  author: string;
  description: string;
  category: string;
  scope: 'default' | 'agent' | 'global' | 'workspace' | 'external';
  path: string;
  security_level: 'low' | 'standard' | 'medium' | 'high' | 'elevated';
  tags: string[];
  dependencies: string[];
  tools: ToolInfo[];
  loaded: boolean;
}

export const SkillsPanel: React.FC = () => {
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [selectedSkill, setSelectedSkill] = useState<SkillInfo | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [copiedPath, setCopiedPath] = useState(false);

  useEffect(() => {
    fetchSkills();
  }, []);

  const fetchSkills = async () => {
    setIsLoading(true);
    try {
      const res = await fetch('http://localhost:8765/api/skills');
      if (res.ok) {
        const data = await res.json();
        const skillList = data.skills || [];
        setSkills(skillList);
        if (skillList.length > 0) {
          setSelectedSkill(skillList[0]);
        }
      }
    } catch (error) {
      console.error('Error fetching skills:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopyPath = (path: string) => {
    navigator.clipboard.writeText(path);
    setCopiedPath(true);
    setTimeout(() => setCopiedPath(false), 2000);
  };

  const getScopeBadge = (scope: SkillInfo['scope']) => {
    switch (scope) {
      case 'default':
        return <span className="px-2 py-0.5 rounded bg-blue-500/10 border border-blue-500/25 text-[10px] font-bold text-blue-400 uppercase tracking-wide">Por Defecto</span>;
      case 'workspace':
        return <span className="px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/25 text-[10px] font-bold text-emerald-400 uppercase tracking-wide">Workspace</span>;
      case 'global':
        return <span className="px-2 py-0.5 rounded bg-purple-500/10 border border-purple-500/25 text-[10px] font-bold text-purple-400 uppercase tracking-wide">Global</span>;
      case 'agent':
        return <span className="px-2 py-0.5 rounded bg-indigo-500/10 border border-indigo-500/25 text-[10px] font-bold text-indigo-400 uppercase tracking-wide">Agente</span>;
      default:
        return <span className="px-2 py-0.5 rounded bg-zinc-500/10 border border-zinc-500/25 text-[10px] font-bold text-zinc-400 uppercase tracking-wide">Externo</span>;
    }
  };

  const getSecurityBadge = (level: SkillInfo['security_level']) => {
    switch (level) {
      case 'low':
      case 'standard':
        return (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-[10px] font-semibold text-emerald-400">
            <ShieldCheck size={11} /> Nivel {level.toUpperCase()}
          </span>
        );
      case 'medium':
        return (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/20 text-[10px] font-semibold text-amber-400">
            <Shield size={11} /> Nivel {level.toUpperCase()}
          </span>
        );
      default:
        return (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-rose-500/10 border border-rose-500/20 text-[10px] font-semibold text-rose-400">
            <ShieldAlert size={11} /> Nivel {level.toUpperCase()}
          </span>
        );
    }
  };

  const filteredSkills = skills.filter(s => 
    s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    s.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
    s.tags.some(t => t.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const scopeGroups: Record<SkillInfo['scope'], SkillInfo[]> = {
    workspace: filteredSkills.filter(s => s.scope === 'workspace'),
    global: filteredSkills.filter(s => s.scope === 'global'),
    agent: filteredSkills.filter(s => s.scope === 'agent'),
    default: filteredSkills.filter(s => s.scope === 'default'),
    external: filteredSkills.filter(s => s.scope === 'external'),
  };

  return (
    <div className="flex h-full bg-[#0e0e11] overflow-hidden select-none animate-in fade-in duration-300">
      
      {/* Left List Pane */}
      <aside className="w-1/3 min-w-[280px] max-w-sm border-r border-[#27272a]/20 bg-[#151518]/20 flex flex-col min-h-0">
        
        {/* Search & Refresh Header */}
        <div className="p-4 border-b border-[#27272a]/20 space-y-3">
          <div className="flex justify-between items-center">
            <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-400">Habilidades (Skills)</h2>
            <button 
              onClick={fetchSkills}
              className="p-1.5 rounded hover:bg-zinc-800 text-zinc-500 hover:text-zinc-300 transition-colors"
              title="Recargar habilidades"
            >
              <RefreshCw size={13} />
            </button>
          </div>
          <div className="relative">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-[#18181b]/60 border border-zinc-850 rounded-lg pl-9 pr-3 py-2 text-xs text-zinc-200 placeholder-zinc-650 focus:outline-none focus:border-indigo-500 transition-colors"
              placeholder="Buscar habilidades o herramientas..."
            />
            <Search className="absolute left-3 top-2.5 text-zinc-650" size={13} />
          </div>
        </div>

        {/* Scrollable list grouped by scope */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-3 space-y-4">
          {isLoading ? (
            <div className="h-full flex items-center justify-center">
              <div className="w-5 h-5 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
            </div>
          ) : filteredSkills.length === 0 ? (
            <div className="text-center py-12 text-zinc-600 text-xs italic">
              No se encontraron habilidades.
            </div>
          ) : (
            Object.entries(scopeGroups).map(([scope, groupSkills]) => {
              if (groupSkills.length === 0) return null;

              const scopeNames: Record<string, string> = {
                workspace: '📁 Workspace / Proyecto',
                global: '⚙️ Global (Usuario)',
                agent: '🤖 Creadas por Agente',
                default: '⚡ Por Defecto (Bundled)',
                external: '🔌 Externas / Legacy',
              };

              return (
                <div key={scope} className="space-y-1">
                  <h3 className="text-[10px] font-bold text-zinc-600 uppercase tracking-wide px-2 py-1">
                    {scopeNames[scope]}
                  </h3>
                  <div className="space-y-0.5">
                    {groupSkills.map(skill => {
                      const isSelected = selectedSkill?.name === skill.name;
                      return (
                        <button
                          key={skill.name}
                          onClick={() => setSelectedSkill(skill)}
                          className={`w-full text-left px-3 py-2 rounded-lg text-xs transition-all flex items-start justify-between gap-2 border ${
                            isSelected
                              ? 'bg-zinc-800/80 border-[#27272a] text-white font-medium shadow-sm'
                              : 'border-transparent text-zinc-500 hover:text-zinc-300 hover:bg-[#151518]/40'
                          }`}
                        >
                          <div className="min-w-0 flex-1 space-y-1">
                            <p className="font-semibold truncate">{skill.name}</p>
                            <p className="text-[10px] text-zinc-600 truncate">{skill.description}</p>
                          </div>
                          {skill.tools && skill.tools.length > 0 && (
                            <span className="text-[9px] font-mono text-zinc-650 bg-zinc-950 px-1.5 py-0.5 rounded border border-zinc-850 self-center">
                              {skill.tools.length}
                            </span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </aside>

      {/* Right Details Pane */}
      <main className="flex-1 overflow-y-auto custom-scrollbar p-6 bg-[#0c0c0e]">
        {selectedSkill ? (
          <div className="space-y-6 max-w-3xl animate-in fade-in duration-200">
            
            {/* Header section */}
            <div className="space-y-3 pb-5 border-b border-[#27272a]/20">
              <div className="flex items-center gap-2.5">
                <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-indigo-500/10 to-indigo-600/15 border border-indigo-500/20 flex items-center justify-center shadow-lg text-indigo-400">
                  <Zap size={18} />
                </div>
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <h1 className="text-base font-bold text-white leading-none">{selectedSkill.name}</h1>
                    <span className="px-1.5 py-0.5 rounded bg-zinc-900 border border-zinc-850 text-[9px] font-mono text-zinc-500">v{selectedSkill.version}</span>
                  </div>
                  {selectedSkill.author && (
                    <p className="text-[10px] text-zinc-500 mt-1 flex items-center gap-1">
                      <User size={10} /> Autor: {selectedSkill.author}
                    </p>
                  )}
                </div>
              </div>

              {/* Badges row */}
              <div className="flex gap-2">
                {getScopeBadge(selectedSkill.scope)}
                {getSecurityBadge(selectedSkill.security_level)}
              </div>
            </div>

            {/* Description Card */}
            <div className="space-y-2">
              <h4 className="text-[10px] font-bold text-zinc-500 uppercase tracking-wide">Descripción</h4>
              <div className="p-4 rounded-xl bg-[#151518]/40 border border-zinc-850 text-xs text-zinc-300 leading-relaxed">
                {selectedSkill.description}
              </div>
            </div>

            {/* Path and Tags info */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <h4 className="text-[10px] font-bold text-zinc-500 uppercase tracking-wide">Directorio local</h4>
                <div className="flex items-center gap-2 p-2 bg-[#18181b]/30 border border-zinc-850 rounded-lg">
                  <p className="text-[9px] font-mono text-zinc-500 truncate flex-1">{selectedSkill.path}</p>
                  <button
                    onClick={() => handleCopyPath(selectedSkill.path)}
                    className="p-1.5 text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 rounded transition-all shrink-0"
                    title="Copiar ruta"
                  >
                    {copiedPath ? <Check size={11} className="text-emerald-400" /> : <Copy size={11} />}
                  </button>
                </div>
              </div>
              <div className="space-y-2">
                <h4 className="text-[10px] font-bold text-zinc-500 uppercase tracking-wide">Etiquetas</h4>
                <div className="flex flex-wrap gap-1.5">
                  {selectedSkill.tags && selectedSkill.tags.length > 0 ? (
                    selectedSkill.tags.map(tag => (
                      <span key={tag} className="px-2 py-0.5 rounded bg-zinc-900 border border-zinc-850 text-[10px] font-medium text-zinc-400">
                        {tag}
                      </span>
                    ))
                  ) : (
                    <span className="text-[10px] text-zinc-650 italic">Ninguna etiqueta</span>
                  )}
                </div>
              </div>
            </div>

            {/* Dependencies */}
            {selectedSkill.dependencies && selectedSkill.dependencies.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-[10px] font-bold text-zinc-500 uppercase tracking-wide">Dependencias requeridas</h4>
                <div className="flex flex-wrap gap-1">
                  {selectedSkill.dependencies.map(dep => (
                    <span key={dep} className="flex items-center gap-1 px-2 py-0.5 rounded bg-zinc-900 border border-zinc-850 text-[10px] text-zinc-400 font-mono">
                      <FileCode size={11} /> {dep}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Tools list */}
            <div className="space-y-3">
              <h4 className="text-[10px] font-bold text-zinc-500 uppercase tracking-wide flex items-center gap-1.5">
                <Code size={12} className="text-indigo-400" />
                Herramientas expuestas por la habilidad ({selectedSkill.tools?.length || 0})
              </h4>

              <div className="grid grid-cols-1 gap-2">
                {selectedSkill.tools && selectedSkill.tools.length > 0 ? (
                  selectedSkill.tools.map((tool, idx) => (
                    <div 
                      key={idx} 
                      className="p-3 bg-[#151518]/30 border border-zinc-850 rounded-xl hover:border-zinc-800/80 transition-colors space-y-1.5"
                    >
                      <div className="flex items-center gap-1.5">
                        <Terminal size={11} className="text-zinc-500" />
                        <span className="text-xs font-bold text-zinc-200 font-mono">{tool.name}</span>
                      </div>
                      <p className="text-[10px] text-zinc-500 leading-normal pl-4">{tool.description}</p>
                    </div>
                  ))
                ) : (
                  <div className="p-4 text-center text-zinc-650 text-[10px] bg-zinc-950/40 border border-zinc-850/60 rounded-xl italic">
                    Esta habilidad no expone ninguna herramienta programática directa (sólo instrucciones de agente).
                  </div>
                )}
              </div>
            </div>

          </div>
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-zinc-600 text-center">
            <Zap size={32} className="text-zinc-700 mb-3" />
            <p className="text-xs italic">Selecciona una habilidad de la lista lateral para inspeccionar sus características.</p>
          </div>
        )}
      </main>

    </div>
  );
};
