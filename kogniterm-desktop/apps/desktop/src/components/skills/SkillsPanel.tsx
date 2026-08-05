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
        return <span className="px-2 py-0.5 rounded bg-blue-50 border border-blue-200/80 text-[10px] font-bold text-blue-700 uppercase tracking-wide">Por Defecto</span>;
      case 'workspace':
        return <span className="px-2 py-0.5 rounded bg-emerald-50 border border-emerald-200/80 text-[10px] font-bold text-emerald-700 uppercase tracking-wide">Workspace</span>;
      case 'global':
        return <span className="px-2 py-0.5 rounded bg-purple-50 border border-purple-200/80 text-[10px] font-bold text-purple-700 uppercase tracking-wide">Global</span>;
      case 'agent':
        return <span className="px-2 py-0.5 rounded bg-indigo-50 border border-indigo-200/80 text-[10px] font-bold text-indigo-700 uppercase tracking-wide">Agente</span>;
      default:
        return <span className="px-2 py-0.5 rounded bg-slate-100 border border-slate-200 text-[10px] font-bold text-slate-600 uppercase tracking-wide">Externo</span>;
    }
  };

  const getSecurityBadge = (level: SkillInfo['security_level']) => {
    switch (level) {
      case 'low':
      case 'standard':
        return (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-emerald-50 border border-emerald-200/80 text-[10px] font-semibold text-emerald-700">
            <ShieldCheck size={11} /> Nivel {level.toUpperCase()}
          </span>
        );
      case 'medium':
        return (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-amber-50 border border-amber-200/80 text-[10px] font-semibold text-amber-700">
            <Shield size={11} /> Nivel {level.toUpperCase()}
          </span>
        );
      default:
        return (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-rose-50 border border-rose-200/80 text-[10px] font-semibold text-rose-700">
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
    <div className="flex h-full bg-[#fafafa] overflow-hidden select-none animate-fade-in">
      
      {/* Left List Pane */}
      <aside className="w-1/3 min-w-[280px] max-w-sm border-r border-slate-200/60 bg-[#f8f9fa] flex flex-col min-h-0">
        
        {/* Search & Refresh Header */}
        <div className="p-4 border-b border-slate-200/60 space-y-3">
          <div className="flex justify-between items-center">
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">Habilidades (Skills)</h2>
            <button 
              onClick={fetchSkills}
              className="p-1.5 rounded-lg hover:bg-slate-200/60 text-slate-400 hover:text-slate-700 transition-colors"
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
              className="w-full bg-white border border-slate-200/80 rounded-xl pl-9 pr-3 py-2 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:border-indigo-500 transition-all shadow-2xs"
              placeholder="Buscar habilidades o herramientas..."
            />
            <Search className="absolute left-3 top-2.5 text-slate-400" size={13} />
          </div>
        </div>

        {/* Scrollable list grouped by scope */}
        <div className="flex-1 overflow-y-auto goose-scrollbar p-3 space-y-4">
          {isLoading ? (
            <div className="h-full flex items-center justify-center">
              <div className="w-5 h-5 border-2 border-indigo-600/30 border-t-indigo-600 rounded-full animate-spin" />
            </div>
          ) : filteredSkills.length === 0 ? (
            <div className="text-center py-12 text-slate-400 text-xs italic">
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
                  <h3 className="text-[10px] font-bold text-slate-400 uppercase tracking-wide px-2 py-1">
                    {scopeNames[scope]}
                  </h3>
                  <div className="space-y-0.5">
                    {groupSkills.map(skill => {
                      const isSelected = selectedSkill?.name === skill.name;
                      return (
                        <button
                          key={skill.name}
                          onClick={() => setSelectedSkill(skill)}
                          className={`w-full text-left px-3 py-2 rounded-xl text-xs transition-all flex items-start justify-between gap-2 border ${
                            isSelected
                              ? 'bg-white border-slate-200/90 text-slate-900 font-medium shadow-2xs'
                              : 'border-transparent text-slate-600 hover:text-slate-900 hover:bg-slate-200/40'
                          }`}
                        >
                          <div className="min-w-0 flex-1 space-y-0.5">
                            <p className="font-semibold truncate text-slate-800">{skill.name}</p>
                            <p className="text-[10px] text-slate-400 truncate">{skill.description}</p>
                          </div>
                          {skill.tools && skill.tools.length > 0 && (
                            <span className="text-[9px] font-mono text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200/80 self-center">
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
      <main className="flex-1 overflow-y-auto goose-scrollbar p-6 bg-[#fafafa]">
        {selectedSkill ? (
          <div className="space-y-6 max-w-3xl animate-fade-in">
            
            {/* Header section */}
            <div className="space-y-3 pb-5 border-b border-slate-200/60">
              <div className="flex items-center gap-2.5">
                <div className="h-9 w-9 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 shadow-2xs">
                  <Zap size={18} />
                </div>
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <h1 className="text-base font-bold text-slate-900 leading-none">{selectedSkill.name}</h1>
                    <span className="px-1.5 py-0.5 rounded bg-slate-100 border border-slate-200 text-[9px] font-mono text-slate-500">v{selectedSkill.version}</span>
                  </div>
                  {selectedSkill.author && (
                    <p className="text-[10px] text-slate-400 mt-1 flex items-center gap-1">
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
              <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-wide">Descripción</h4>
              <div className="p-4 rounded-2xl bg-white border border-slate-200/80 text-xs text-slate-700 leading-relaxed shadow-card-light">
                {selectedSkill.description}
              </div>
            </div>

            {/* Path and Tags info */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-wide">Directorio local</h4>
                <div className="flex items-center gap-2 p-2.5 bg-white border border-slate-200/80 rounded-xl">
                  <p className="text-[9px] font-mono text-slate-500 truncate flex-1">{selectedSkill.path}</p>
                  <button
                    onClick={() => handleCopyPath(selectedSkill.path)}
                    className="p-1 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded transition-all shrink-0"
                    title="Copiar ruta"
                  >
                    {copiedPath ? <Check size={11} className="text-emerald-600" /> : <Copy size={11} />}
                  </button>
                </div>
              </div>
              <div className="space-y-2">
                <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-wide">Etiquetas</h4>
                <div className="flex flex-wrap gap-1.5">
                  {selectedSkill.tags && selectedSkill.tags.length > 0 ? (
                    selectedSkill.tags.map(tag => (
                      <span key={tag} className="px-2 py-0.5 rounded-lg bg-slate-100 border border-slate-200/80 text-[10px] font-medium text-slate-600">
                        {tag}
                      </span>
                    ))
                  ) : (
                    <span className="text-[10px] text-slate-400 italic">Ninguna etiqueta</span>
                  )}
                </div>
              </div>
            </div>

            {/* Dependencies */}
            {selectedSkill.dependencies && selectedSkill.dependencies.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-wide">Dependencias requeridas</h4>
                <div className="flex flex-wrap gap-1">
                  {selectedSkill.dependencies.map(dep => (
                    <span key={dep} className="flex items-center gap-1 px-2 py-0.5 rounded-lg bg-slate-100 border border-slate-200/80 text-[10px] text-slate-600 font-mono">
                      <FileCode size={11} /> {dep}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Tools list */}
            <div className="space-y-3">
              <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-wide flex items-center gap-1.5">
                <Code size={12} className="text-indigo-600" />
                Herramientas expuestas por la habilidad ({selectedSkill.tools?.length || 0})
              </h4>

              <div className="grid grid-cols-1 gap-2">
                {selectedSkill.tools && selectedSkill.tools.length > 0 ? (
                  selectedSkill.tools.map((tool, idx) => (
                    <div 
                      key={idx} 
                      className="p-3.5 bg-white border border-slate-200/80 rounded-2xl space-y-1.5 shadow-card-light hover:border-slate-300 transition-colors"
                    >
                      <div className="flex items-center gap-1.5">
                        <Terminal size={12} className="text-slate-400" />
                        <span className="text-xs font-semibold text-slate-800 font-mono">{tool.name}</span>
                      </div>
                      <p className="text-[11px] text-slate-500 leading-normal pl-4">{tool.description}</p>
                    </div>
                  ))
                ) : (
                  <div className="p-4 text-center text-slate-400 text-[10px] bg-slate-100/50 border border-slate-200/60 rounded-2xl italic">
                    Esta habilidad no expone ninguna herramienta programática directa (sólo instrucciones de agente).
                  </div>
                )}
              </div>
            </div>

          </div>
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-slate-400 text-center">
            <Zap size={32} className="text-slate-300 mb-3" />
            <p className="text-xs italic">Selecciona una habilidad de la lista lateral para inspeccionar sus características.</p>
          </div>
        )}
      </main>

    </div>
  );
};
