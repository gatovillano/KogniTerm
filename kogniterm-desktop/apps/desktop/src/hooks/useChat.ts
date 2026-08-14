import { useState, useCallback, useEffect, useRef } from 'react';
import { Message, AppliedDiff } from '../types/chat';
import { ApprovalRequest } from '../components/chat/CommandApproval';
import { TerminalEntry } from '../components/chat/TerminalPanel';

export function parseAppliedDiff(
    rawContent: string,
    fallbackFilePath?: string,
    toolName?: string
): AppliedDiff | null {
    if (!rawContent || typeof rawContent !== 'string') return null;

    let diffText = rawContent;
    let filePath = fallbackFilePath || '';
    let extractedTool = toolName || '';

    // 1. JSON Payload format
    if (rawContent.trim().startsWith('{') && rawContent.trim().endsWith('}')) {
        try {
            const parsed = JSON.parse(rawContent);
            if (parsed.diff_content) diffText = parsed.diff_content;
            else if (parsed.diff) diffText = parsed.diff;
            if (parsed.file_path || parsed.filePath) filePath = parsed.file_path || parsed.filePath;
            if (parsed.tool || parsed.tool_name || parsed.operation) {
                extractedTool = parsed.tool || parsed.tool_name || parsed.operation;
            }
        } catch (e) {
            // Ignore parse errors
        }
    }

    // 2. Explicit ```diff ... ``` code block format
    const explicitDiffBlockMatch = diffText.match(/```diff\n([\s\S]*?)\n```/i);
    let isExplicitDiffBlock = false;
    if (explicitDiffBlockMatch) {
        isExplicitDiffBlock = true;
        const headerText = diffText.substring(0, diffText.indexOf('```'));
        const opMatch = headerText.match(/Operación:\s*`?([a-zA-Z0-9_\-]+)`?/i);
        if (opMatch && !extractedTool) extractedTool = opMatch[1];
        const pathMatch = headerText.match(/Cambios aplicados en\s*`?([^`\n]+)`?/i);
        if (pathMatch && !filePath) filePath = pathMatch[1];

        diffText = explicitDiffBlockMatch[1];
    } else {
        // Look for header pattern like "Operación: tool_name --- a/path"
        const opLineMatch = diffText.match(/Operación:\s*`?([a-zA-Z0-9_\-]+)`?\s*/i);
        if (opLineMatch) {
            if (!extractedTool) extractedTool = opLineMatch[1];
            diffText = diffText.replace(/Operación:\s*`?[a-zA-Z0-9_\-]+`?\s*/i, '');
        }

        const titleMatch = diffText.match(/✅\s*Diff aplicado:\s*([^\n]+)/i) || diffText.match(/✅\s*Cambios aplicados en\s*`?([^`\n]+)`?/i);
        if (titleMatch && !filePath) {
            filePath = titleMatch[1].trim();
        }
    }

    // STRICT VALIDATION: MUST have valid unified diff header markers or explicit ```diff block
    const hasHeaderLines = /--- (a\/|\/|[^\s]+)[\s\S]*?\+\+\+ (b\/|\/|[^\s]+)/.test(diffText) || /diff --git a\//.test(diffText) || /Index:\s+/.test(diffText);
    const hasHunkHeader = /^@@\s+-\d+(?:,\d+)?\s+\+\d+(?:,\d+)?\s+@@/m.test(diffText);

    // If no header lines, no hunk header (@@ -X,Y +A,B @@), and not explicit ```diff, reject as NOT a diff
    if (!hasHeaderLines && !hasHunkHeader && !isExplicitDiffBlock) {
        return null;
    }

    // Extract file path from unified diff headers if not already set
    if (!filePath) {
        const pathMatch = diffText.match(/\+\+\+\s+(?:b\/)?([^\s\n]+)/) || diffText.match(/---\s+(?:a\/)?([^\s\n]+)/);
        if (pathMatch && pathMatch[1] !== '/dev/null' && pathMatch[1] !== 'a' && pathMatch[1] !== 'b') {
            filePath = pathMatch[1];
        }
    }

    // 4. Parse diff lines & count additions/deletions accurately
    const lines = diffText.split('\n');
    let additions = 0;
    let deletions = 0;
    let inHunk = false;

    for (const line of lines) {
        const trimmed = line.trim();

        if (trimmed.startsWith('@@')) {
            inHunk = true;
            continue;
        }

        if (line.includes('--- ') || line.includes('+++ ') || line.includes('Index:') || line.includes('diff --git')) {
            inHunk = true;
            continue;
        }

        if (inHunk || isExplicitDiffBlock) {
            // Standard diff additions and deletions
            if (line.startsWith('+') && !line.startsWith('+++')) {
                additions++;
            } else if (line.startsWith('-') && !line.startsWith('---')) {
                deletions++;
            }
            // Rich Console line numbers format: e.g. "188+" or "185 185 - ..." or "195+ - ..."
            else if (/^\d+(\s+\d+)?\s*\+/.test(trimmed)) {
                additions++;
            } else if (/^\d+(\s+\d+)?\s*-/.test(trimmed)) {
                deletions++;
            }
        }
    }

    if (additions === 0 && deletions === 0) {
        return null;
    }

    // Clean up file path if it starts with extra slashes or prefixes like "a//"
    let cleanPath = filePath.replace(/^a\/+/, '').replace(/^b\/+/, '').trim();
    if (!cleanPath || cleanPath === 'archivo_modificado') {
        const fallbackMatch = diffText.match(/(?:[a-zA-Z0-9_\-\.]+\/)+[a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+/);
        if (fallbackMatch) {
            cleanPath = fallbackMatch[0];
        }
    }

    return {
        id: Date.now().toString() + '_' + Math.random().toString(36).substring(2, 7),
        filePath: cleanPath || 'archivo_modificado',
        toolName: extractedTool || toolName || 'edición',
        diffContent: diffText.trim(),
        additions,
        deletions,
        timestamp: Date.now(),
    };
}

export interface SingleThreadState {
    messages: Message[];
    taskPlans: Record<string, { task: string; status: string }[]>;
    terminalEntries: TerminalEntry[];
    pendingApproval: ApprovalRequest | null;
    appliedDiffs: AppliedDiff[];
    isGenerating: boolean;
    scrollPosition: number;
    isUserNearBottom: boolean;
}

export function useChat(threadId: string | null, targetWorkspaceDir?: string) {
    const threadsCacheRef = useRef<Record<string, SingleThreadState>>({});
    const activeThreadIdRef = useRef<string | null>(threadId);
    activeThreadIdRef.current = threadId;
    const prevThreadIdRef = useRef<string | null>(threadId);

    const [messages, setMessages] = useState<Message[]>(() => {
        if (threadId && threadsCacheRef.current[threadId]) {
            return threadsCacheRef.current[threadId].messages;
        }
        return [];
    });
    const [isGenerating, setIsGenerating] = useState<boolean>(() => {
        if (threadId && threadsCacheRef.current[threadId]) {
            return threadsCacheRef.current[threadId].isGenerating;
        }
        return false;
    });
    const [error, setError] = useState<string | null>(null);
    const [isConnected, setIsConnected] = useState(false);
    const [taskPlans, setTaskPlans] = useState<Record<string, { task: string; status: string }[]>>(() => {
        if (threadId && threadsCacheRef.current[threadId]) {
            return threadsCacheRef.current[threadId].taskPlans;
        }
        return {};
    });
    const [pendingApproval, setPendingApproval] = useState<ApprovalRequest | null>(() => {
        if (threadId && threadsCacheRef.current[threadId]) {
            return threadsCacheRef.current[threadId].pendingApproval;
        }
        return null;
    });
    const [terminalEntries, setTerminalEntries] = useState<TerminalEntry[]>(() => {
        if (threadId && threadsCacheRef.current[threadId]) {
            return threadsCacheRef.current[threadId].terminalEntries;
        }
        return [];
    });
    const [isTerminalVisible, setIsTerminalVisible] = useState(false);
    const [appliedDiffs, setAppliedDiffs] = useState<AppliedDiff[]>(() => {
        if (threadId && threadsCacheRef.current[threadId]) {
            return threadsCacheRef.current[threadId].appliedDiffs;
        }
        return [];
    });
    const [scrollPosition, setScrollPosition] = useState<number>(() => {
        if (threadId && threadsCacheRef.current[threadId]) {
            return threadsCacheRef.current[threadId].scrollPosition;
        }
        return 0;
    });
    const [isUserNearBottom, setIsUserNearBottom] = useState<boolean>(() => {
        if (threadId && threadsCacheRef.current[threadId]) {
            return threadsCacheRef.current[threadId].isUserNearBottom;
        }
        return true;
    });

    const socketRef = useRef<WebSocket | null>(null);

    // Keep cache synchronized with active states for active thread
    useEffect(() => {
        if (!threadId || prevThreadIdRef.current !== threadId) return;
        threadsCacheRef.current[threadId] = {
            messages,
            taskPlans,
            terminalEntries,
            pendingApproval,
            appliedDiffs,
            isGenerating,
            scrollPosition,
            isUserNearBottom,
        };
    }, [threadId, messages, taskPlans, terminalEntries, pendingApproval, appliedDiffs, isGenerating, scrollPosition, isUserNearBottom]);

    const setThreadScrollPosition = useCallback((scrollTop: number, isNearBottom: boolean) => {
        setScrollPosition(scrollTop);
        setIsUserNearBottom(isNearBottom);
        if (threadId) {
            if (threadsCacheRef.current[threadId]) {
                threadsCacheRef.current[threadId].scrollPosition = scrollTop;
                threadsCacheRef.current[threadId].isUserNearBottom = isNearBottom;
            }
        }
    }, [threadId]);

    const recordDiffIfAny = useCallback((content: string, filePath?: string, toolName?: string) => {
        if (!content) return;
        const parsed = parseAppliedDiff(content, filePath, toolName);
        if (parsed) {
            setAppliedDiffs((prev) => {
                if (prev.some(d => d.filePath === parsed.filePath && d.diffContent === parsed.diffContent)) {
                    return prev;
                }
                return [parsed, ...prev];
            });
        }
    }, []);

    useEffect(() => {
        let active = true;
        
        // Save previous thread state before switching to a new thread
        if (prevThreadIdRef.current && prevThreadIdRef.current !== threadId) {
            threadsCacheRef.current[prevThreadIdRef.current] = {
                messages,
                taskPlans,
                terminalEntries,
                pendingApproval,
                appliedDiffs,
                isGenerating,
                scrollPosition,
                isUserNearBottom,
            };
        }
        prevThreadIdRef.current = threadId;

        if (threadId && threadsCacheRef.current[threadId]) {
            const cached = threadsCacheRef.current[threadId];
            setMessages(cached.messages);
            setTaskPlans(cached.taskPlans);
            setTerminalEntries(cached.terminalEntries);
            setPendingApproval(cached.pendingApproval);
            setAppliedDiffs(cached.appliedDiffs);
            setIsGenerating(cached.isGenerating);
            setScrollPosition(cached.scrollPosition);
            setIsUserNearBottom(cached.isUserNearBottom);
        } else {
            setMessages([]);
            setTaskPlans({});
            setTerminalEntries([]);
            setPendingApproval(null);
            setAppliedDiffs([]);
            setIsGenerating(false);
            setScrollPosition(0);
            setIsUserNearBottom(true);
        }

        // Fetch thread messages from API
        fetch(`http://127.0.0.1:8765/api/threads/${threadId}/messages`)
            .then(res => {
                if (res.ok) return res.json();
                return { messages: [] };
            })
            .then(data => {
                if (active && data.messages) {
                    if (data.messages.length > 0) {
                        setMessages(data.messages);
                        // Extract applied diffs from initial thread messages
                        const extracted: AppliedDiff[] = [];
                        data.messages.forEach((m: Message) => {
                            if (m.content) {
                                const parsed = parseAppliedDiff(m.content);
                                if (parsed && !extracted.some(d => d.filePath === parsed.filePath && d.diffContent === parsed.diffContent)) {
                                    extracted.push(parsed);
                                }
                            }
                        });
                        if (extracted.length > 0) {
                            setAppliedDiffs((prev) => {
                                const combined = [...extracted, ...prev];
                                const seen = new Set();
                                return combined.filter(d => {
                                    const key = `${d.filePath}_${d.diffContent}`;
                                    if (seen.has(key)) return false;
                                    seen.add(key);
                                    return true;
                                });
                            });
                        }
                    } else {
                        const cached = threadId ? threadsCacheRef.current[threadId] : null;
                        if (!cached || cached.messages.length === 0) {
                            setMessages([]);
                        }
                    }
                }
            })
            .catch(err => console.error("Error loading messages:", err));

        let ws: WebSocket | null = null;

        const initWs = async () => {
            let workspaceDir: string | undefined = targetWorkspaceDir;
            let token: string | undefined = undefined;
            try {
                const { invoke } = await import('@tauri-apps/api/core');
                token = await invoke<string>('get_api_token');
                if (!workspaceDir) {
                    workspaceDir = await invoke<string>('get_cwd');
                }
                console.log("WorkspaceDir para WebSocket:", workspaceDir);
            } catch (err) {
                console.warn("No se pudo obtener CWD/token de Tauri para WebSocket:", err);
            }

            if (!active) return;

            const params = new URLSearchParams();
            if (workspaceDir) params.set('workspace_dir', workspaceDir);
            if (token) params.set('token', token);
            const queryParams = params.toString() ? `?${params.toString()}` : '';
            const wsUrl = `ws://127.0.0.1:8765/ws/${threadId}${queryParams}`;
            ws = new WebSocket(wsUrl);
            socketRef.current = ws;

            ws.onopen = () => {
                if (active) {
                    setIsConnected(true);
                    setError(null);
                }
            };

            ws.onclose = () => {
                if (active) {
                    setIsConnected(false);
                }
            };

            ws.onerror = () => {
                if (active) {
                    setError('Error de conexión con el servidor.');
                    setIsGenerating(false);
                }
            };

            ws.onmessage = (event) => {
                if (!active) return;
                const data = JSON.parse(event.data);

                if (data.type === 'connected') {
                    const payload = data.data || data;
                    if (payload.is_running) {
                        setIsGenerating(true);
                        if (payload.live_state) {
                            const { thinking, response, terminal_entries } = payload.live_state;
                            if (thinking || response) {
                                setMessages((prev) => {
                                    const lastMessage = prev[prev.length - 1];
                                    if (lastMessage && lastMessage.role === 'assistant') {
                                        return prev.map((m, idx) => idx === prev.length - 1 ? {
                                            ...m,
                                            reasoning: thinking || m.reasoning,
                                            content: response || m.content,
                                        } : m);
                                    } else {
                                        return [
                                            ...prev,
                                            {
                                                id: Date.now().toString(),
                                                role: 'assistant',
                                                content: response || '',
                                                reasoning: thinking || '',
                                                timestamp: Date.now(),
                                            },
                                        ];
                                    }
                                });
                            }
                            if (terminal_entries && Array.isArray(terminal_entries) && terminal_entries.length > 0) {
                                setTerminalEntries(terminal_entries);
                                setIsTerminalVisible(true);
                            }
                        }
                    } else {
                        setIsGenerating(false);
                    }
                } else if (data.type === 'chunk') {
                    const payload = data.data || data;
                    const chunkContent = payload.content || '';
                    if (chunkContent) recordDiffIfAny(chunkContent);

                    setMessages((prev) => {
                        const lastMessage = prev[prev.length - 1];
                        // Si el último assistant ya completó un ciclo de herramientas,
                        // este chunk pertenece a una nueva fase de respuesta.
                        const isNewPhase = lastMessage?.role === 'assistant'
                            && lastMessage.tool_calls && lastMessage.tool_calls.length > 0;
                        if (lastMessage && lastMessage.role === 'assistant' && !isNewPhase) {
                            const newMessages = [...prev];
                            newMessages[newMessages.length - 1] = {
                                ...lastMessage,
                                content: lastMessage.content + chunkContent,
                            };
                            return newMessages;
                        } else {
                            return [
                                ...prev,
                                {
                                    id: Date.now().toString(),
                                    role: 'assistant',
                                    content: chunkContent,
                                    timestamp: Date.now(),
                                },
                            ];
                        }
                    });
                } else if (data.type === 'reasoning') {
                    const payload = data.data || data;
                    setMessages((prev) => {
                        const lastMessage = prev[prev.length - 1];
                        // Si el último assistant ya ejecutó herramientas, este bloque de
                        // reasoning pertenece a una nueva fase de pensamiento.
                        const isNewPhase = lastMessage?.role === 'assistant'
                            && lastMessage.tool_calls && lastMessage.tool_calls.length > 0;
                        if (lastMessage && lastMessage.role === 'assistant' && !isNewPhase) {
                            const newMessages = [...prev];
                            newMessages[newMessages.length - 1] = {
                                ...lastMessage,
                                reasoning: (lastMessage.reasoning || '') + (payload.content || ''),
                            };
                            return newMessages;
                        } else {
                            return [
                                ...prev,
                                {
                                    id: Date.now().toString(),
                                    role: 'assistant',
                                    content: '',
                                    reasoning: payload.content || '',
                                    timestamp: Date.now(),
                                },
                            ];
                        }
                    });
                } else if (data.type === 'live_update') {
                    const payload = data.data || data;
                    
                    // Handle terminal-type live updates — show in terminal panel
                    if (payload.special_type === 'terminal') {
                        setTerminalEntries((prev) => [
                            ...prev,
                            {
                                id: Date.now().toString(),
                                tool: payload.tool || '',
                                command: payload.command || '',
                                output: payload.output || '',
                                timestamp: Date.now(),
                            },
                        ]);
                        setIsTerminalVisible(true);
                        return;
                    }
                    
                    if (payload.special_type) return;

                    const thinking = payload.thinking || '';
                    const response = payload.response || '';
                    if (response) recordDiffIfAny(response);

                    setMessages((prev) => {
                        if (!thinking && !response) return prev;

                        const lastMessage = prev[prev.length - 1];
                        // Si el último assistant ya completó un ciclo de herramientas,
                        // este live_update pertenece a una nueva fase de pensamiento/respuesta.
                        // No mutar ese mensaje: crear uno nuevo para mantener la secuencialidad.
                        const isNewPhase = lastMessage?.role === 'assistant'
                            && lastMessage.tool_calls && lastMessage.tool_calls.length > 0;
                        if (lastMessage && lastMessage.role === 'assistant' && !isNewPhase) {
                            const newMessages = [...prev];
                            newMessages[newMessages.length - 1] = {
                                ...lastMessage,
                                // live_update envía el thinking acumulado completo (snapshot),
                                // así que reemplazamos (no concatenamos) solo si viene uno nuevo.
                                reasoning: thinking || lastMessage.reasoning,
                                content: response || lastMessage.content,
                            };
                            return newMessages;
                        } else {
                            return [
                                ...prev,
                                {
                                    id: Date.now().toString(),
                                    role: 'assistant',
                                    content: response,
                                    reasoning: thinking,
                                    timestamp: Date.now(),
                                },
                            ];
                        }
                    });
                } else if (data.type === 'terminal_output') {
                    // Terminal output from command execution
                    const payload = data.data || data;
                    const entryId = payload.tool_call_id || payload.id || Date.now().toString();
                    setTerminalEntries((prev) => {
                        const existingIndex = prev.findIndex((e) => e.id === entryId);
                        const newEntry: TerminalEntry = {
                            id: entryId,
                            tool: payload.tool || '',
                            command: payload.command || payload.tool || '',
                            output: payload.content || payload.output || '',
                            timestamp: Date.now(),
                        };
                        if (existingIndex >= 0) {
                            const updated = [...prev];
                            updated[existingIndex] = newEntry;
                            return updated;
                        } else {
                            return [...prev, newEntry];
                        }
                    });
                    setIsTerminalVisible(true);
                } else if (data.type === 'tool_call') {
                    const payload = data.data || data;
                    setMessages((prev) => {
                        const lastMessage = prev[prev.length - 1];
                        const toolCall = {
                            id: payload.id || data.id || Date.now().toString(),
                            name: payload.name || 'Unknown Tool',
                            args: payload.args || payload.description || ''
                        };

                        if (lastMessage && lastMessage.role === 'assistant') {
                            const newMessages = [...prev];
                            const tool_calls = [...(lastMessage.tool_calls || []), toolCall];
                            newMessages[newMessages.length - 1] = {
                                ...lastMessage,
                                tool_calls,
                            };
                            return newMessages;
                        } else {
                            return [
                                ...prev,
                                {
                                    id: Date.now().toString(),
                                    role: 'assistant',
                                    content: '',
                                    tool_calls: [toolCall],
                                    timestamp: Date.now(),
                                },
                            ];
                        }
                    });
                } else if (data.type === 'tool_result') {
                    const payload = data.data || data;
                    const contentStr = typeof payload.content === 'string' ? payload.content : JSON.stringify(payload.content || '');
                    
                    recordDiffIfAny(contentStr, payload.file_path || payload.filePath, payload.tool || payload.tool_name);

                    setMessages((prev) => [
                        ...prev,
                        {
                            id: Date.now().toString(),
                            role: 'tool',
                            content: contentStr,
                            tool_call_id: payload.tool_call_id || data.tool_call_id,
                            timestamp: Date.now(),
                        },
                    ]);
                } else if (data.type === 'done') {
                    setIsGenerating(false);
                } else if (data.type === 'error') {
                    const payload = data.data || data;
                    setError(payload.content || payload.message || 'Unknown error');
                    setIsGenerating(false);
                } else if (data.type === 'thread_title_updated') {
                    window.dispatchEvent(new CustomEvent('thread_update'));
                } else if (data.type === 'info') {
                    const payload = data.data || data;
                    const infoText = payload.content || payload.text || '';
                    if (infoText) recordDiffIfAny(infoText);

                    setMessages((prev) => [
                        ...prev,
                        {
                            id: Date.now().toString(),
                            role: 'system',
                            content: infoText,
                            timestamp: Date.now(),
                        },
                    ]);
                } else if (data.type === 'approval_required') {
                    // Show approval dialog to the user instead of auto-approving
                    const payload = data.data || data;
                    setPendingApproval({
                        id: payload.id,
                        message: payload.message || '',
                        title: payload.title || 'Aprobación Requerida',
                        diff_content: payload.diff_content || '',
                        file_path: payload.file_path || '',
                        timestamp: Date.now(),
                    });
                } else if (data.type === 'task_tracker') {
                    const payload = data.data || data;
                    setTaskPlans(payload);
                } else if (data.type === 'set_terminal_cursor') {
                    const payload = data.data || data;
                    if (payload.active) {
                        setIsTerminalVisible(true);
                    }
                }
            };
        };

        initWs();

        return () => {
            active = false;
            if (socketRef.current) {
                socketRef.current.close();
            }
        };
    }, [threadId, targetWorkspaceDir]);

    const sendMessage = useCallback((content: string, images: string[] = []) => {
        const trimmed = content.trim();

        // 1. Manejo de Meta-comandos locales
        if (trimmed === '/clear' || trimmed === '%clear') {
            setMessages([]);
            setAppliedDiffs([]);
            return;
        }

        if (!socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) {
            setError('No hay conexión con el servidor.');
            return;
        }

        const newMessage: Message = {
            id: Date.now().toString(),
            role: 'user',
            content,
            images: images.length > 0 ? images : undefined,
            timestamp: Date.now(),
        };

        setMessages((prev) => [...prev, newMessage]);
        setIsGenerating(true);
        setError(null);

        // Enviar mensaje exclusivamente por WebSocket
        socketRef.current.send(JSON.stringify({
            type: 'message',
            text: content,
            images: images.length > 0 ? images : undefined,
        }));
    }, []);

    const respondApproval = useCallback((requestId: string, approved: boolean) => {
        if (approved && pendingApproval && pendingApproval.diff_content) {
            const parsedDiff = parseAppliedDiff(
                pendingApproval.diff_content,
                pendingApproval.file_path,
                'Aprobación'
            );
            if (parsedDiff) {
                setAppliedDiffs((prev) => [parsedDiff, ...prev]);
            }
        }
        if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
            socketRef.current.send(JSON.stringify({
                type: 'approval_response',
                id: requestId,
                approved,
            }));
        }
        setPendingApproval(null);
    }, [pendingApproval]);

    const sendTerminalInput = useCallback((text: string) => {
        if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
            socketRef.current.send(JSON.stringify({
                type: 'terminal_input',
                text,
            }));
        }
    }, []);

    const stopGeneration = useCallback(() => {
        if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
            socketRef.current.send(JSON.stringify({ type: 'interrupt' }));
        }
        setIsGenerating(false);
    }, []);

    const closeTerminal = useCallback(() => {
        setIsTerminalVisible(false);
    }, []);

    const clearTerminal = useCallback(() => {
        setTerminalEntries([]);
    }, []);

    return {
        messages,
        isGenerating,
        error,
        sendMessage,
        stopGeneration,
        isConnected,
        taskPlans,
        pendingApproval,
        respondApproval,
        terminalEntries,
        isTerminalVisible,
        sendTerminalInput,
        closeTerminal,
        clearTerminal,
        appliedDiffs,
        scrollPosition,
        isUserNearBottom,
        setThreadScrollPosition,
    };
}

