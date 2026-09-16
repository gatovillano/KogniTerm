import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
export const ThinkingSpinner = ({ text = 'Thinking', compact = false, }) => {
    const displayText = text.includes('pensando') ? 'Thinking' : text;
    if (compact) {
        return (_jsxs("span", { className: "inline-flex items-center text-xs font-normal text-zinc-500 dark:text-zinc-400 select-none animate-fade-in", children: [_jsx("span", { children: displayText }), _jsxs("span", { className: "inline-flex ml-0.5 text-zinc-400", children: [_jsx("span", { className: "animate-[waveDots_1.4s_infinite_0s]", children: "." }), _jsx("span", { className: "animate-[waveDots_1.4s_infinite_0.2s]", children: "." }), _jsx("span", { className: "animate-[waveDots_1.4s_infinite_0.4s]", children: "." })] })] }));
    }
    return (_jsx("div", { className: "flex w-full my-2 justify-start animate-fade-in", children: _jsxs("div", { className: "flex items-center text-sm font-normal text-zinc-500 dark:text-zinc-400 select-none", children: [_jsx("span", { children: displayText }), _jsxs("span", { className: "inline-flex ml-0.5 text-zinc-400", children: [_jsx("span", { className: "animate-[waveDots_1.4s_infinite_0s]", children: "." }), _jsx("span", { className: "animate-[waveDots_1.4s_infinite_0.2s]", children: "." }), _jsx("span", { className: "animate-[waveDots_1.4s_infinite_0.4s]", children: "." })] })] }) }));
};
