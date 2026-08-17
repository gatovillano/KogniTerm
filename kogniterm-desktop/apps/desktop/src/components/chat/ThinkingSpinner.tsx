import React from 'react';

interface ThinkingSpinnerProps {
    text?: string;
    compact?: boolean;
}

export const ThinkingSpinner: React.FC<ThinkingSpinnerProps> = ({ 
    text = "Thinking",
    compact = false
}) => {
    const displayText = text.includes("pensando") ? "Thinking" : text;

    if (compact) {
        return (
            <span className="inline-flex items-center text-xs font-normal text-zinc-500 dark:text-zinc-400 select-none animate-fade-in">
                <span>{displayText}</span>
                <span className="inline-flex ml-0.5 text-zinc-400">
                    <span className="animate-[waveDots_1.4s_infinite_0s]">.</span>
                    <span className="animate-[waveDots_1.4s_infinite_0.2s]">.</span>
                    <span className="animate-[waveDots_1.4s_infinite_0.4s]">.</span>
                </span>
            </span>
        );
    }

    return (
        <div className="flex w-full my-2 justify-start animate-fade-in">
            <div className="flex items-center text-sm font-normal text-zinc-500 dark:text-zinc-400 select-none">
                <span>{displayText}</span>
                <span className="inline-flex ml-0.5 text-zinc-400">
                    <span className="animate-[waveDots_1.4s_infinite_0s]">.</span>
                    <span className="animate-[waveDots_1.4s_infinite_0.2s]">.</span>
                    <span className="animate-[waveDots_1.4s_infinite_0.4s]">.</span>
                </span>
            </div>
        </div>
    );
};

