import React, { useState } from 'react';
import { FileDiff, Search, Filter } from 'lucide-react';
import { AppliedDiff } from '../../types/chat';
import { AppliedDiffCard } from './AppliedDiffCard';

interface DiffSidebarProps {
    diffs: AppliedDiff[];
}

export const DiffSidebar: React.FC<DiffSidebarProps> = ({ diffs }) => {
    const [searchQuery, setSearchQuery] = useState('');

    const filteredDiffs = diffs.filter((d) => {
        const query = searchQuery.toLowerCase().trim();
        if (!query) return true;
        return (
            d.filePath.toLowerCase().includes(query) ||
            (d.toolName && d.toolName.toLowerCase().includes(query))
        );
    });

    const totalAdditions = diffs.reduce((acc, d) => acc + d.additions, 0);
    const totalDeletions = diffs.reduce((acc, d) => acc + d.deletions, 0);

    return (
        <div className="flex h-full flex-col">
            {/* Search & Summary Header */}
            <div className="border-b border-zinc-800/80 p-3 space-y-2.5 bg-zinc-950/60">
                <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-1.5 text-xs font-semibold text-zinc-300">
                        <FileDiff size={15} className="text-indigo-400" />
                        <span>Diffs Aplicados ({diffs.length})</span>
                    </div>

                    {diffs.length > 0 && (
                        <div className="flex items-center gap-1.5 font-mono text-[10px] font-bold">
                            <span className="rounded bg-emerald-500/10 border border-emerald-500/20 px-1.5 py-0.5 text-emerald-400">
                                +{totalAdditions}
                            </span>
                            <span className="rounded bg-rose-500/10 border border-rose-500/20 px-1.5 py-0.5 text-rose-400">
                                -{totalDeletions}
                            </span>
                        </div>
                    )}
                </div>

                {diffs.length > 0 && (
                    <div className="relative">
                        <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-500" />
                        <input
                            type="text"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            placeholder="Buscar por archivo..."
                            className="w-full rounded-lg border border-zinc-800 bg-zinc-900/80 py-1.5 pl-8 pr-3 font-mono text-xs text-zinc-200 placeholder-zinc-500 outline-none transition-colors focus:border-indigo-500/50"
                        />
                    </div>
                )}
            </div>

            {/* Diffs List */}
            <div className="goose-scrollbar flex-1 overflow-y-auto p-3 space-y-2.5">
                {diffs.length === 0 ? (
                    <div className="flex h-full flex-col items-center justify-center gap-2 text-center p-6 text-zinc-600">
                        <FileDiff size={28} className="text-zinc-600 opacity-60" />
                        <p className="text-[13px] font-medium text-zinc-400">Sin diffs aplicados</p>
                        <p className="text-[11px] text-zinc-600 max-w-[200px]">
                            Los cambios y ediciones aplicados durante esta sesión aparecerán aquí.
                        </p>
                    </div>
                ) : filteredDiffs.length === 0 ? (
                    <div className="flex flex-col items-center justify-center p-6 text-center text-zinc-500">
                        <Filter size={20} className="mb-1 text-zinc-600" />
                        <p className="text-xs">No hay resultados para "{searchQuery}"</p>
                    </div>
                ) : (
                    filteredDiffs.map((diff) => (
                        <AppliedDiffCard
                            key={diff.id}
                            diff={diff}
                            defaultExpanded={filteredDiffs.length === 1}
                        />
                    ))
                )}
            </div>
        </div>
    );
};
