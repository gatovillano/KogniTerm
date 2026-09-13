import { useState, useCallback, useRef, useEffect } from 'react';

interface StreamingConfig {
  sessionId: string;
  message: string;
  agent: string;
  model: string;
}

interface UseChatStreamReturn {
  streamMessage: (config: StreamingConfig) => Promise<string>;
  isStreaming: boolean;
  streamedText: string;
  cancelStreaming: () => void;
}

export function useChatStream(): UseChatStreamReturn {
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamedText, setStreamedText] = useState('');
  const wsRef = useRef<WebSocket | null>(null);
  const cancelRef = useRef<(() => void) | null>(null);
  const fullTextRef = useRef('');

  // Auto-save streamed text to localStorage
  useEffect(() => {
    if (streamedText) {
      localStorage.setItem('kogniterm_stream_buffer', streamedText);
    }
  }, [streamedText]);

  // Restore previous stream on mount
  useEffect(() => {
    const saved = localStorage.getItem('kogniterm_stream_buffer');
    if (saved) {
      setStreamedText(saved);
    }
  }, []);

  const cancelStreaming = useCallback(() => {
    if (cancelRef.current) {
      cancelRef.current();
      cancelRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsStreaming(false);
  }, []);

  const streamMessage = useCallback(async (config: StreamingConfig): Promise<string> => {
    // Clean up previous stream
    if (cancelRef.current) {
      cancelRef.current();
    }

    setIsStreaming(true);
    setStreamedText('');
    fullTextRef.current = '';

    return new Promise((resolve, reject) => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/ws/${config.sessionId}`;
      
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      // Cleanup function
      const cancel = () => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.close();
        }
        setIsStreaming(false);
        reject(new Error('Stream cancelled'));
      };

      cancelRef.current = cancel;

      ws.onopen = () => {
        ws.send(JSON.stringify({
          type: 'message',
          text: config.message,
          agent: config.agent,
          model: config.model
        }));
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('WebSocket event received:', data.type, data);
          
          if (data.type === 'stream' || data.type === 'chunk') {
            // El texto está en data.data.content o data.content
            const chunk = data.data?.content || data.data || data.content || '';
            console.log('Accumulating chunk:', chunk.substring(0, 50));
            fullTextRef.current += chunk;
            setStreamedText(prev => prev + chunk);
          } else if (data.type === 'done') {
            console.log('Stream completed. Full text:', fullTextRef.current);
            setIsStreaming(false);
            localStorage.removeItem('kogniterm_stream_buffer');
            ws.close();
            resolve(fullTextRef.current);
          } else if (data.type === 'error') {
            setIsStreaming(false);
            setStreamedText('');
            localStorage.removeItem('kogniterm_stream_buffer');
            reject(new Error(data.data || 'Unknown error'));
          } else {
            // Filtrar eventos del backend como terminal_output o live_update que NO deben ir al stream de texto
            const isControlEvent = ['connected', 'user_message', 'thread_title_updated', 'tool_call', 
                                    'task_tracker', 'set_terminal_cursor', 'live_update', 'terminal_output', 
                                    'live_stop', 'applied_diff', 'tool_result', 'tool_execution'].includes(data.type);

            if (!isControlEvent && data.type) {
              console.log('Skipping non-stream control event:', data.type);
            }

            // Emitir CustomEvent para componentes suscritos (TaskTracker, ToolIndicators, etc.)
            window.dispatchEvent(new CustomEvent('kogniterm_event', { 
              detail: data 
            }));
          }
        } catch (e) {
          console.warn('Error parsing WebSocket message:', e);
        }
      };

      ws.onerror = () => {
        setIsStreaming(false);
        setStreamedText('');
        localStorage.removeItem('kogniterm_stream_buffer');
        reject(new Error('WebSocket connection error'));
      };

      ws.onclose = () => {
        if (isStreaming && fullTextRef.current === '') {
          setIsStreaming(false);
          reject(new Error('Connection closed unexpectedly'));
        }
      };
    });
  }, []);

  return {
    streamMessage,
    isStreaming,
    streamedText,
    cancelStreaming
  };
}