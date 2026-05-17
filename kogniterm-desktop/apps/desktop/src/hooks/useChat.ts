import { useState, useCallback, useEffect, useRef } from 'react';
import { Message } from '../types/chat';

export function useChat() {
    const [messages, setMessages] = useState<Message[]>([]);
    const [isGenerating, setIsGenerating] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [isConnected, setIsConnected] = useState(false);
    const socketRef = useRef<WebSocket | null>(null);

    useEffect(() => {
        // Initializing WebSocket connection
        // Note: In production you might want to handle reconnection logic
        const ws = new WebSocket('ws://127.0.0.1:8765/ws/chat');
        socketRef.current = ws;

        ws.onopen = () => {
            setIsConnected(true);
            setError(null);
        };

        ws.onclose = () => {
            setIsConnected(false);
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);

            if (data.type === 'chunk') {
                setMessages((prev) => {
                    const lastMessage = prev[prev.length - 1];
                    if (lastMessage && lastMessage.role === 'assistant') {
                        const newMessages = [...prev];
                        newMessages[newMessages.length - 1] = {
                            ...lastMessage,
                            content: lastMessage.content + data.content,
                        };
                        return newMessages;
                    } else {
                        return [
                            ...prev,
                            {
                                id: Date.now().toString(),
                                role: 'assistant',
                                content: data.content,
                                timestamp: Date.now(),
                            },
                        ];
                    }
                });
            } else if (data.type === 'reasoning') {
                setMessages((prev) => {
                    const lastMessage = prev[prev.length - 1];
                    if (lastMessage && lastMessage.role === 'assistant') {
                        const newMessages = [...prev];
                        newMessages[newMessages.length - 1] = {
                            ...lastMessage,
                            reasoning: (lastMessage.reasoning || '') + data.content,
                        };
                        return newMessages;
                    } else {
                        return [
                            ...prev,
                            {
                                id: Date.now().toString(),
                                role: 'assistant',
                                content: '',
                                reasoning: data.content,
                                timestamp: Date.now(),
                            },
                        ];
                    }
                });
            } else if (data.type === 'tool_call') {
                setMessages((prev) => {
                    const lastMessage = prev[prev.length - 1];
                    const toolCall = {
                        id: data.id || Date.now().toString(),
                        name: data.name,
                        args: data.args
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
                setMessages((prev) => [
                    ...prev,
                    {
                        id: Date.now().toString(),
                        role: 'tool',
                        content: typeof data.content === 'string' ? data.content : JSON.stringify(data.content),
                        tool_call_id: data.tool_call_id,
                        timestamp: Date.now(),
                    },
                ]);
            } else if (data.type === 'done') {
                setIsGenerating(false);
            } else if (data.type === 'error') {
                setError(data.content);
                setIsGenerating(false);
            } else if (data.type === 'info') {
                // Mensajes informativos del sistema (ej. confirmación de reset)
                setMessages((prev) => [
                    ...prev,
                    {
                        id: Date.now().toString(),
                        role: 'system', // Necesitaremos asegurar que 'system' está en el tipo Message o usar 'assistant' con estilo especial
                        content: data.content,
                        timestamp: Date.now(),
                    },
                ]);
            }
        };

        ws.onerror = () => {
            setError('Error de conexión con el servidor.');
            setIsGenerating(false);
        };

        return () => {
            ws.close();
        };
    }, []);

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
        socketRef.current.send(JSON.stringify({ message: content }));
    }, []);

    return { messages, isGenerating, error, sendMessage, isConnected };

}
