import { useState, useCallback, useEffect, useRef } from 'react';
import { Message } from '../types/chat';
import { ApprovalRequest } from '../components/chat/CommandApproval';
import { TerminalEntry } from '../components/chat/TerminalPanel';

export function useChat(threadId: string | null) {
    const [messages, setMessages] = useState<Message[]>([]);
    const [isGenerating, setIsGenerating] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [isConnected, setIsConnected] = useState(false);
    const [taskPlans, setTaskPlans] = useState<Record<string, {task: string, status: string}[]>>({});
    const [pendingApproval, setPendingApproval] = useState<ApprovalRequest | null>(null);
    const [terminalEntries, setTerminalEntries] = useState<TerminalEntry[]>([]);
    const [isTerminalVisible, setIsTerminalVisible] = useState(false);
    const socketRef = useRef<WebSocket | null>(null);

    useEffect(() => {
        let active = true;
        
        setMessages([]); // Clear on switch
        setTaskPlans({}); // Clear task plans on switch
        setTerminalEntries([]); // Clear terminal on switch
        setPendingApproval(null); // Clear pending approvals

        // Fetch thread messages from API
        fetch(`http://127.0.0.1:8765/api/threads/${threadId}/messages`)
            .then(res => {
                if (res.ok) return res.json();
                return { messages: [] };
            })
            .then(data => {
                if (active && data.messages && data.messages.length > 0) {
                    setMessages(data.messages);
                }
            })
            .catch(err => console.error("Error loading messages:", err));

        let ws: WebSocket | null = null;

        const initWs = async () => {
            let workspaceDir: string | undefined = undefined;
            try {
                const { invoke } = await import('@tauri-apps/api/core');
                workspaceDir = await invoke<string>('get_cwd');
                console.log("CWD de Tauri para WebSocket:", workspaceDir);
            } catch (err) {
                console.warn("No se pudo obtener el CWD de Tauri para WebSocket:", err);
            }

            if (!active) return;

            const queryParams = workspaceDir ? `?workspace_dir=${encodeURIComponent(workspaceDir)}` : '';
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

                if (data.type === 'chunk') {
                    const payload = data.data || data;
                    setMessages((prev) => {
                        const lastMessage = prev[prev.length - 1];
                        if (lastMessage && lastMessage.role === 'assistant') {
                            const newMessages = [...prev];
                            newMessages[newMessages.length - 1] = {
                                ...lastMessage,
                                content: lastMessage.content + (payload.content || ''),
                            };
                            return newMessages;
                        } else {
                            return [
                                ...prev,
                                {
                                    id: Date.now().toString(),
                                    role: 'assistant',
                                    content: payload.content || '',
                                    timestamp: Date.now(),
                                },
                            ];
                        }
                    });
                } else if (data.type === 'reasoning') {
                    const payload = data.data || data;
                    setMessages((prev) => {
                        const lastMessage = prev[prev.length - 1];
                        if (lastMessage && lastMessage.role === 'assistant') {
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
                    setMessages((prev) => {
                        const lastMessage = prev[prev.length - 1];
                        const thinking = payload.thinking || '';
                        const response = payload.response || '';
                        
                        if (!thinking && !response) return prev;

                        if (lastMessage && lastMessage.role === 'assistant') {
                            const newMessages = [...prev];
                            newMessages[newMessages.length - 1] = {
                                ...lastMessage,
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
                    setTerminalEntries((prev) => [
                        ...prev,
                        {
                            id: Date.now().toString(),
                            tool: payload.tool || '',
                            command: payload.tool || '',
                            output: payload.content || '',
                            timestamp: Date.now(),
                        },
                    ]);
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
                    setMessages((prev) => [
                        ...prev,
                        {
                            id: Date.now().toString(),
                            role: 'tool',
                            content: typeof payload.content === 'string' ? payload.content : JSON.stringify(payload.content || ''),
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
                    setMessages((prev) => [
                        ...prev,
                        {
                            id: Date.now().toString(),
                            role: 'system',
                            content: payload.content || payload.text || '',
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
    }, [threadId]);

    const sendMessage = useCallback((content: string) => {
        const trimmed = content.trim();

        // 1. Manejo de Meta-comandos locales
        if (trimmed === '/clear' || trimmed === '%clear') {
            setMessages([]);
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
            timestamp: Date.now(),
        };

        setMessages((prev) => [...prev, newMessage]);
        setIsGenerating(true);
        setError(null);

        // Enviar mensaje exclusivamente por WebSocket
        socketRef.current.send(JSON.stringify({ type: 'message', text: content }));
    }, []);

    const respondApproval = useCallback((requestId: string, approved: boolean) => {
        if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
            socketRef.current.send(JSON.stringify({
                type: 'approval_response',
                id: requestId,
                approved,
            }));
        }
        setPendingApproval(null);
    }, []);

    const sendTerminalInput = useCallback((text: string) => {
        if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
            socketRef.current.send(JSON.stringify({
                type: 'terminal_input',
                text,
            }));
        }
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
        isConnected,
        taskPlans,
        pendingApproval,
        respondApproval,
        terminalEntries,
        isTerminalVisible,
        sendTerminalInput,
        closeTerminal,
        clearTerminal,
    };
}
