import React from 'react';
import { Bot, Sparkles } from 'lucide-react';

interface ThinkingSpinnerProps {
    text?: string;
    compact?: boolean;
}

export const ThinkingSpinner: React.FC<ThinkingSpinnerProps> = ({ 
    text = "KogniTerm está pensando...",
    compact = false
}) => {
    if (compact) {
        return (
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50/90 border border-indigo-100/90 shadow-2xs backdrop-blur-xs animate-fade-in">
                <div className="relative w-3.5 h-3.5 flex items-center justify-center shrink-0">
                    {/* Outer gradient rotating ring */}
                    <div className="absolute inset-0 rounded-full border-[1.5px] border-indigo-300 border-t-indigo-600 animate-spin" />
                    <Bot size={9} className="text-indigo-600 animate-pulse shrink-0" />
                </div>
                <span className="text-[11px] font-medium text-indigo-950/80 tracking-wide flex items-center">
                    {text.replace(/\.\.\.$/, '')}
                    <span className="inline-flex ml-0.5 font-bold text-indigo-600">
                        <span className="animate-[waveDots_1.4s_infinite_0s]">.</span>
                        <span className="animate-[waveDots_1.4s_infinite_0.2s]">.</span>
                        <span className="animate-[waveDots_1.4s_infinite_0.4s]">.</span>
                    </span>
                </span>
            </div>
        );
    }

    return (
        <div className="flex w-full mb-6 justify-start animate-fade-in">
            <div className="flex max-w-[85%] items-start w-full gap-3">
                {/* Avatar Icon with Glowing Orbital Ring */}
                <div className="relative flex-shrink-0 h-8 w-8 flex items-center justify-center mt-0.5">
                    {/* Outer glowing background pulse */}
                    <div className="absolute -inset-1 rounded-full bg-gradient-to-r from-indigo-500 via-purple-500 to-cyan-500 opacity-35 blur-[3px] animate-pulse" />
                    
                    {/* Rotating Gradient Spinner Ring */}
                    <div className="absolute inset-0 rounded-full border-[2px] border-indigo-200/60 border-t-indigo-600 border-r-purple-500 animate-spin" />
                    
                    {/* Center Icon Badge */}
                    <div className="relative h-6 w-6 rounded-full bg-white flex items-center justify-center shadow-xs">
                        <Bot size={13} className="text-indigo-600 animate-pulse" />
                    </div>
                </div>

                <div className="flex flex-col gap-1.5 items-start">
                    {/* Name Header */}
                    <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider px-1">
                        KogniTerm
                    </span>

                    {/* Elegant Thinking Capsule */}
                    <div className="flex items-center gap-3 px-4 py-3 rounded-2xl bg-gradient-to-r from-indigo-50/90 via-purple-50/40 to-white border border-indigo-100/90 shadow-card-light backdrop-blur-sm">
                        <div className="relative flex items-center justify-center w-5 h-5 shrink-0">
                            {/* Inner spinning sparkle icon */}
                            <Sparkles size={14} className="text-indigo-600 animate-[spin_4s_linear_infinite]" />
                        </div>

                        <div className="flex items-center gap-1">
                            <span className="text-xs font-semibold text-indigo-950 tracking-tight">
                                KogniTerm está pensando
                            </span>
                            <div className="flex items-center text-indigo-600 font-bold text-xs ml-0.5">
                                <span className="animate-[waveDots_1.4s_infinite_0s]">.</span>
                                <span className="animate-[waveDots_1.4s_infinite_0.2s]">.</span>
                                <span className="animate-[waveDots_1.4s_infinite_0.4s]">.</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};
