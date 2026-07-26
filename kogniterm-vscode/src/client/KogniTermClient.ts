import * as vscode from 'vscode';
import WebSocket from 'ws';
import { ChatPanel } from '../ui/ChatPanel';
import { EditorContext } from '../integration/EditorContext';

export interface ConnectionStatus {
  connected: boolean;
  sessionId?: string;
  error?: string;
}

export interface ContextData {
  type: 'file' | 'selection' | 'file_context' | 'workspace';
  data: any;
}

export class KogniTermClient {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectInterval = 3000;
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private messageQueue: string[] = [];
  private sessionId: string;

  constructor(
    private serverUrl: string,
    private chatPanel: ChatPanel,
    private editorContext: EditorContext
  ) {
    this.sessionId = `vscode-${Math.random().toString(36).substring(2, 10)}`;
  }

  public connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        resolve();
        return;
      }

      // Limpiar socket anterior si existía
      if (this.ws) {
        try {
          this.ws.removeAllListeners();
          this.ws.close();
        } catch (_) {}
        this.ws = null;
      }

      try {
        this.ws = new WebSocket(this.serverUrl);

        this.ws.onopen = () => {
          console.log('KogniTerm WebSocket connected to', this.serverUrl);
          this.reconnectAttempts = 0;
          
          // Enviar mensajes en cola
          this.flushMessageQueue();
          
          // Iniciar heartbeat
          this.startHeartbeat();
          
          resolve();
        };

        this.ws.onmessage = (event) => {
          this.handleMessage(event.data.toString());
        };

        this.ws.onerror = (error) => {
          console.error('KogniTerm WebSocket error:', error);
          this.chatPanel.addSystemMessage('Error de conexión', 'error');
        };

        this.ws.onclose = (event) => {
          console.log('KogniTerm WebSocket closed:', event.code, event.reason);
          this.cleanup();
          
          // Intentar reconexión automática si fue cierre inesperado
          if (!event.wasClean && event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.attemptReconnect();
          } else {
            this.chatPanel.addSystemMessage('Desconectado del servidor', 'warning');
          }
        };

      } catch (error) {
        vscode.window.showErrorMessage(`KogniTerm: Error al conectar - ${error}`);
        reject(error);
      }
    });
  }

  public disconnect(): void {
    if (this.ws) {
      this.ws.close(1000, 'User disconnected');
    }
    this.cleanup();
    this.chatPanel.addSystemMessage('Desconectado manualmente');
  }

  public dispose(): void {
    this.disconnect();
  }
  public sendMessage(text: string): void {
    const message = {
      type: 'message',
      text: text
    };

    console.log('[KogniTermClient] sending message:', message, 'WS State:', this.ws?.readyState);

    // Siempre mostrar el mensaje del usuario en la pantalla
    this.chatPanel.addUserMessage(text);

    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
      console.log('[KogniTermClient] WebSocket.send() executed successfully');
    } else {
      // Encolar mensaje e intentar conectar
      this.messageQueue.push(JSON.stringify(message));
      vscode.window.showWarningMessage('KogniTerm: Conectando... El mensaje se enviará automáticamente.');
      this.connect();
    }
  }

  public sendContext(context: ContextData): void {
    const message = {
      type: 'message',
      text: `[Contexto de ${context.type}]: ${JSON.stringify(context.data)}`
    };

    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  public approveTool(toolId: string): void {
    this.sendToolAction(true, toolId);
  }

  public rejectTool(toolId: string): void {
    this.sendToolAction(false, toolId);
  }

  public isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  public getStatus(): ConnectionStatus {
    return {
      connected: this.isConnected(),
      sessionId: this.getSessionId()
    };
  }

  private handleMessage(data: string): void {
    try {
      const message = JSON.parse(data);
      
      switch (message.type) {
        case 'connected':
          this.chatPanel.addSystemMessage(`Sesión inicializada: ${message.data?.session_id || 'OK'}`);
          break;
        case 'stream':
          const streamText = typeof message.data === 'string' ? message.data : (message.data?.text || '');
          this.chatPanel.appendStream({ text: streamText });
          break;
        case 'message':
          const content = typeof message.data === 'string' ? message.data : (message.data?.text || message.data?.content || JSON.stringify(message.data));
          this.chatPanel.addAssistantMessage(content);
          break;
        case 'response':
          this.chatPanel.addAssistantMessage(typeof message.data === 'string' ? message.data : JSON.stringify(message.data));
          break;
        case 'tool_start':
        case 'tool_call':
          this.chatPanel.showToolCall(typeof message.data === 'object' ? message.data : { name: message.data });
          break;
        case 'tool_output':
          this.chatPanel.addSystemMessage(`[Salida Herramienta]: ${typeof message.data === 'string' ? message.data : JSON.stringify(message.data)}`);
          break;
        case 'live_update':
          this.chatPanel.showLiveUpdate(message.data);
          break;
        case 'task_tracker':
          this.chatPanel.updateTaskTracker(message.data);
          break;
        case 'done':
          // Ciclo completado
          break;
        case 'pong':
          // Keep-alive pong
          break;
        case 'error':
          const errText = typeof message.data === 'string' ? message.data : JSON.stringify(message.data);
          this.chatPanel.addSystemMessage(errText, 'error');
          vscode.window.showErrorMessage(`KogniTerm: ${errText}`);
          break;
        case 'session':
          this.chatPanel.updateSessionId(message.session_id);
          break;
        default:
          console.log('KogniTerm message type:', message.type, message);
      }
    } catch (error) {
      console.error('KogniTerm failed to parse message:', error);
    }
  }

  private sendToolAction(approved: boolean, toolId: string): void {
    const message = {
      type: 'approval_response',
      id: toolId,
      approved: approved
    };

    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  private flushMessageQueue(): void {
    while (this.messageQueue.length > 0 && this.ws?.readyState === WebSocket.OPEN) {
      const message = this.messageQueue.shift();
      if (message) {
        this.ws.send(message);
      }
    }
  }

  private startHeartbeat(): void {
    this.heartbeatInterval = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000);
  }

  private attemptReconnect(): void {
    this.reconnectAttempts++;
    const delay = this.reconnectInterval * Math.min(this.reconnectAttempts, 5);

    setTimeout(() => {
      this.connect().catch(() => {
        // El error ya se maneja en el método connect
      });
    }, delay);
  }

  private cleanup(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
    this.ws = null;
  }

  private getSessionId(): string | undefined {
    // Extraer session_id de la URL del WebSocket si está presente
    const match = this.serverUrl.match(/\/ws\/([^\/]+)/);
    return match ? match[1] : undefined;
  }
}
