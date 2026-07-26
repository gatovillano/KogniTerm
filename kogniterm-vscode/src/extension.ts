import * as vscode from 'vscode';
import { KogniTermClient } from './client/KogniTermClient';
import { ChatPanel } from './ui/ChatPanel';
import { EditorContext } from './integration/EditorContext';

let client: KogniTermClient | undefined;
let chatPanel: ChatPanel | undefined;
let editorContext: EditorContext | undefined;

export function activate(context: vscode.ExtensionContext) {
  console.log('KogniTerm extension is now active!');

  // Inicializar componentes
  chatPanel = new ChatPanel(context.extensionUri);
  editorContext = new EditorContext();

  // Crear cliente WebSocket
  const config = vscode.workspace.getConfiguration('kogniterm');
  const serverUrl = config.get<string>('serverUrl', 'ws://127.0.0.1:8765/ws/chat');
  
  client = new KogniTermClient(serverUrl, chatPanel, editorContext);

  // Registrar comandos
  const commands = [
    vscode.commands.registerCommand('kogniterm.connect', () => client?.connect()),
    vscode.commands.registerCommand('kogniterm.disconnect', () => client?.disconnect()),
    vscode.commands.registerCommand('kogniterm.sendSelection', () => {
      const selection = editorContext?.getSelection();
      if (selection) {
        client?.sendContext({
          type: 'selection',
          data: selection
        });
      }
    }),
    vscode.commands.registerCommand('kogniterm.sendFile', () => {
      const file = editorContext?.getActiveFile();
      if (file) {
        client?.sendContext({
          type: 'file',
          data: file
        });
      }
    }),
    vscode.commands.registerCommand('kogniterm.clearChat', () => {
      chatPanel?.clear();
    }),
    vscode.commands.registerCommand('kogniterm.showStatus', () => {
      const status = client?.getStatus();
      const connectedText = status ? (status.connected ? 'Conectado' : 'Desconectado') : 'Desconectado';
      const sessionText = status?.sessionId ? status.sessionId : 'Sin sesión';
      vscode.window.showInformationMessage(
        `KogniTerm: ${connectedText} - ${sessionText}`
      );
    })  ];

  // Registrar proveedores de vistas
  const chatViewProvider = new ChatPanelProvider(context.extensionUri);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider('kogniterm.chat', chatViewProvider)
  );

  // Registrar listener para cambios en archivos activos
  const activeEditorListener = vscode.window.onDidChangeActiveTextEditor(() => {
    if (config.get<boolean>('autoSendContext', true)) {
      const file = editorContext?.getActiveFile();
      if (file && client?.isConnected()) {
        client?.sendContext({
          type: 'file_context',
          data: file
        });
      }
    }
  });

  // Auto-conectar si está habilitado
  if (config.get<boolean>('autoConnect', true)) {
    setTimeout(() => client?.connect(), 1000);
  }

  // Suscripciones que se limpiarán al desactivar
  // Suscripciones que se limpiarán al desactivar
  context.subscriptions.push(
    client,
    editorContext,
    ...commands,
    activeEditorListener
  );}

export function deactivate() {
  console.log('KogniTerm extension is deactivating...');
  client?.disconnect();
}

// Proveedor del panel de chat WebView
class ChatPanelProvider implements vscode.WebviewViewProvider {
  private _view?: vscode.WebviewView;

  constructor(private readonly _extensionUri: vscode.Uri) {}

  public resolveWebviewView(
    webviewView: vscode.WebviewView,
    context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken
  ) {
    this._view = webviewView;

    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this._extensionUri]
    };

    // Conectar el Webview con el ChatPanel global
    if (chatPanel) {
      chatPanel.setWebview(webviewView.webview);
    }

    webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

    // Manejar mensajes desde el WebView
    webviewView.webview.onDidReceiveMessage(
      data => {
        switch (data.command) {
          case 'sendMessage':
            client?.sendMessage(data.text);
            break;
          case 'approveTool':
            client?.approveTool(data.toolId);
            break;
          case 'rejectTool':
            client?.rejectTool(data.toolId);
            break;
        }
      }
    );
  }

  public sendMessage(message: string) {
    if (this._view) {
      this._view.webview.postMessage({ command: 'addMessage', message });
    }
  }

  public clear() {
    if (this._view) {
      this._view.webview.postMessage({ command: 'clear' });
    }
  }

  private _getHtmlForWebview(webview: vscode.Webview): string {
    const styleUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'media', 'style.css'));
    const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'out', 'ui', 'chatPanel.js'));
    const markedUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'node_modules', 'marked', 'marked.min.js'));

    return `<!DOCTYPE html>
      <html lang="es">
      <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>KogniTerm Chat</title>
        <link rel="stylesheet" href="${styleUri}">
        <script src="${markedUri}"></script>
      </head>
      <body>
        <div id="app">
          <div id="task-tracker-container" style="display: none;">
            <div id="task-tracker-header">
              <span>📋 Tareas del Agente</span>
              <span id="task-progress-badge">0/0</span>
            </div>
            <div id="task-list"></div>
          </div>
          <div id="chat-container">
            <div id="messages"></div>
            <div id="input-area">
              <textarea id="message-input" placeholder="Escribe un mensaje..." rows="3"></textarea>
              <button id="send-button">Enviar</button>
            </div>
          </div>
        </div>
        <script src="${scriptUri}"></script>
      </body>
      </html>`;
  }
}
