import * as vscode from 'vscode';

export class ChatPanel {
  private messages: any[] = [];

  private webview?: vscode.Webview;

  constructor(private extensionUri: vscode.Uri) {}

  public setWebview(webview: vscode.Webview): void {
    this.webview = webview;
    // Re-enviar historial existente al webview recién creado
    for (const message of this.messages) {
      this.webview.postMessage({ command: 'addMessage', message });
    }
  }

  public addUserMessage(text: string): void {
    this.addMessage({
      role: 'user',
      content: text,
      timestamp: new Date().toISOString()
    });
  }

  public addAssistantMessage(text: string): void {
    this.addMessage({
      role: 'assistant',
      content: text,
      timestamp: new Date().toISOString()
    });
  }

  public addSystemMessage(text: string, type: 'info' | 'warning' | 'error' = 'info'): void {
    this.addMessage({
      role: 'system',
      content: text,
      type,
      timestamp: new Date().toISOString()
    });
  }

  public appendStream(data: { text?: string; thinking?: string }): void {
    // Actualizar el último mensaje del asistente o crear uno nuevo
    const lastMessage = this.messages[this.messages.length - 1];
    
    if (lastMessage?.role === 'assistant') {
      if (data.thinking) {
        lastMessage.thinking = (lastMessage.thinking || '') + data.thinking;
      }
      if (data.text) {
        lastMessage.content = (lastMessage.content || '') + data.text;
      }
    } else {
      this.addMessage({
        role: 'assistant',
        content: data.text || '',
        thinking: data.thinking,
        timestamp: new Date().toISOString()
      });
    }

    this.postMessage({ command: 'updateLastMessage', message: lastMessage || this.messages[this.messages.length - 1] });
  }

  public showToolCall(data: { name: string; description?: string; skill?: string }): void {
    this.addMessage({
      role: 'tool',
      content: data.description || data.name,
      toolName: data.name,
      skill: data.skill,
      timestamp: new Date().toISOString()
    });
  }

  public showLiveUpdate(data: { thinking?: string; response?: string }): void {
    if (data.thinking) {
      const lastMessage = this.messages[this.messages.length - 1];
      if (lastMessage?.role === 'thinking') {
        lastMessage.content = data.thinking;
        this.postMessage({ command: 'updateLastThinkingMessage', message: lastMessage });
      } else {
        const thinkingMsg = {
          role: 'thinking',
          content: data.thinking,
          timestamp: new Date().toISOString()
        };
        this.messages.push(thinkingMsg);
        this.postMessage({ command: 'addMessage', message: thinkingMsg });
      }
    }
    if (data.response) {
      // Si llega texto de respuesta final, cerramos la etapa de pensamiento
      this.addAssistantMessage(data.response);
    }
  }

  public updateTaskTracker(tasksData: any): void {
    this.postMessage({ command: 'updateTaskTracker', tasks: tasksData });
  }

  public updateSessionId(sessionId: string): void {
    this.postMessage({ command: 'updateSession', sessionId });
  }

  public clear(): void {
    this.messages = [];
    this.postMessage({ command: 'clear' });
  }

  private addMessage(message: any): void {
    this.messages.push(message);
    this.postMessage({ command: 'addMessage', message });
  }

  private postMessage(message: any): void {
    if (this.webview) {
      this.webview.postMessage(message);
    } else {
      console.log('[KogniTerm Chat - Pending webview]', message);
    }
  }
}
