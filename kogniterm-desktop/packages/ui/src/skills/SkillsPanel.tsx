import { useState, useEffect } from 'react';
import {
  Search,
  Zap,
  Copy,
  Terminal,
  Check,
  RefreshCw,
  Loader2,
} from 'lucide-react';
import { SkillInfo } from '@kogniterm/types';

export interface SkillsPanelProps {
  serverUrl?: string;
}

export const SkillsPanel: React.FC<SkillsPanelProps> = ({
  serverUrl = 'http://127.0.0.1:8765',
}) => {
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
      const res = await fetch(`${serverUrl}/api/skills`);
      if (res.ok) {
        const data = await res.json();
        const skillList = data.skills || [];
        setSkills(skillList);
        if (skillList.length > 0 && !selectedSkill) {
          setSelectedSkill(skillList[0]);
        }
      }
    } catch (err) {
      console.error('Error fetching skills:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const filteredSkills = skills.filter(
    (skill) =>
      skill.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      skill.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      skill.category.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleCopyPath = (path: string) => {
    navigator.clipboard.writeText(path);
    setCopiedPath(true);
    setTimeout(() => setCopiedPath(false), 2000);
  };

  return (
    <div className="flex h-full w-full bg-zinc-950 text-zinc-100 overflow-hidden">
      {/* Sidebar / List */}
      <div className="w-80 border-r border-zinc-800 flex flex-col h-full bg-zinc-900/60">
        <div className="p-3 border-b border-zinc-800 space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-sm flex items-center gap-1.5 text-zinc-200">
              <Zap size={16} className="text-amber-400" />
              Skills del Agente
            </h3>
            <button
              onClick={fetchSkills}
              disabled={isLoading}
              className="p-1 rounded hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 disabled:opacity-50"
            >
              {isLoading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            </button>
          </div>

          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-2.5 text-zinc-500" />
            <input
              type="text"
              placeholder="Buscar skills..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-indigo-500"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {filteredSkills.map((skill) => (
            <button
              key={skill.name}
              onClick={() => setSelectedSkill(skill)}
              className={`w-full text-left p-2.5 rounded-lg text-xs transition-colors flex flex-col gap-1 border ${
                selectedSkill?.name === skill.name
                  ? 'bg-indigo-600/15 border-indigo-500/40 text-indigo-200'
                  : 'bg-zinc-900/40 border-transparent hover:bg-zinc-800/60 text-zinc-300'
              }`}
            >
              <div className="flex items-center justify-between w-full">
                <span className="font-semibold">{skill.name}</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 font-mono">
                  v{skill.version || '1.0'}
                </span>
              </div>
              <p className="text-[11px] text-zinc-400 line-clamp-2">{skill.description}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Main Details */}
      <div className="flex-1 overflow-y-auto p-6 bg-zinc-950">
        {selectedSkill ? (
          <div className="max-w-2xl space-y-6">
            <div className="flex items-start justify-between border-b border-zinc-800 pb-4">
              <div>
                <h2 className="text-xl font-bold text-zinc-100 flex items-center gap-2">
                  {selectedSkill.name}
                  <span className="text-xs font-mono font-normal px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                    {selectedSkill.category}
                  </span>
                </h2>
                <p className="text-sm text-zinc-400 mt-1">{selectedSkill.description}</p>
              </div>

              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => handleCopyPath(selectedSkill.path)}
                  className="flex items-center gap-1 text-xs text-zinc-400 hover:text-zinc-200 bg-zinc-900 border border-zinc-800 px-2.5 py-1.5 rounded-lg transition-colors"
                >
                  {copiedPath ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
                  <span>{copiedPath ? 'Copiado' : 'Ruta'}</span>
                </button>
              </div>
            </div>

            {/* Tools provided by the skill */}
            {selectedSkill.tools && selectedSkill.tools.length > 0 && (
              <div className="space-y-3">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-zinc-400 flex items-center gap-1.5">
                  <Terminal size={14} /> Herramientas expuestas ({selectedSkill.tools.length})
                </h4>
                <div className="space-y-2">
                  {selectedSkill.tools.map((tool) => (
                    <div
                      key={tool.name}
                      className="p-3 rounded-lg bg-zinc-900/60 border border-zinc-800/80 text-xs"
                    >
                      <span className="font-mono font-bold text-indigo-300">{tool.name}</span>
                      <p className="text-zinc-400 mt-1">{tool.description}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-zinc-600 text-sm">
            Selecciona una skill para ver sus detalles
          </div>
        )}
      </div>
    </div>
  );
};
