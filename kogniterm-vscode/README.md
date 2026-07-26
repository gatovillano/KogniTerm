# KogniTerm - VS Code Extension

Extensión de VS Code para [KogniTerm](https://github.com/kogniterm), el Entorno de Desarrollo Agéntico (ADE) de terminal. Trabaja directamente con tu código usando agentes de IA especializados, sin salir de tu IDE favorito.

## ✨ Características

- **Chat en tiempo real** con agentes de IA especializados en desarrollo de software
- **Contexto automático** del archivo activo y selección del editor
- **Streaming de respuestas** para una experiencia de usuario fluida
- **Aprobación de herramientas** - Revisa y aprueba/rechaza acciones del agente
- **Integración profunda** con el editor de VS Code
- **Sesiones persistentes** que se sincronizan con el backend de KogniTerm
- **Reconexión automática** en caso de desconexión
- **Soporte multi-idioma** (español/inglés)

## 📋 Requisitos

- VS Code >= 1.80.0
- Node.js >= 16.x
- KogniTerm backend corriendo (por defecto en `ws://127.0.0.1:8765`)

## 🚀 Instalación

### Desde VSIX (recomendado)

1. Compila la extensión:
   ```bash
   cd kogniterm-vscode
   npm install
   npm run compile
   npm install -g @vscode/vsce
   vsce package
   ```

2. Instala el archivo generado:
   ```bash
   code --install-extension kogniterm-vscode-0.1.0.vsix
   ```

### Desarrollo

1. Clona el repositorio:
   ```bash
   git clone https://github.com/kogniterm/kogniterm-vscode.git
   cd kogniterm-vscode
   ```

2. Instala dependencias:
   ```bash
   npm install
   ```

3. Compila y ejecuta en modo debug:
   ```bash
   npm run watch
   ```

4. Presiona `F5` en VS Code para abrir una nueva ventana con la extensión cargada.

## ⚙️ Configuración

La extensión se configura a través de `settings.json` de VS Code:

```json
{
  "kogniterm.serverUrl": "ws://127.0.0.1:8765",
  "kogniterm.autoConnect": true,
  "kogniterm.autoSendContext": true,
  "kogniterm.showNotifications": true
}
```

### Opciones disponibles

| Configuración | Tipo | Default | Descripción |
|--------------|------|---------|-------------|
| `kogniterm.serverUrl` | string | `ws://127.0.0.1:8765` | URL del servidor KogniTerm (WebSocket) |
| `kogniterm.autoConnect` | boolean | `true` | Conectar automáticamente al iniciar VS Code |
| `kogniterm.autoSendContext` | boolean | `true` | Enviar automáticamente el archivo activo como contexto |
| `kogniterm.showNotifications` | boolean | `true` | Mostrar notificaciones nativas |

## 🎮 Uso

### Comandos disponibles

| Comando | Descripción |
|---------|-------------|
| `KogniTerm: Conectar al Servidor` | Establece conexión WebSocket con KogniTerm |
| `KogniTerm: Desconectar del Servidor` | Cierra la conexión actual |
| `KogniTerm: Enviar Selección al Agente` | Envía el texto seleccionado al agente |
| `KogniTerm: Enviar Archivo Actual al Agente` | Envía el archivo activo completo como contexto |
| `KogniTerm: Limpiar Chat` | Borra el historial del chat |
| `KogniTerm: Mostrar Estado de Conexión` | Muestra el estado actual de la conexión |

### Context Menu

- Click derecho sobre una selección → **KogniTerm: Enviar Selección al Agente**
- Click derecho en el editor → **KogniTerm: Enviar Archivo Actual al Agente**

### Atajos de teclado

Puedes asignar atajos personalizados en `keybindings.json`:

```json
{
  "key": "ctrl+shift+k",
  "command": "kogniterm.sendSelection",
  "when": "editorHasSelection"
},
{
  "key": "ctrl+shift+enter",
  "command": "kogniterm.sendFile"
}
```

## 🏗️ Arquitectura

```
kogniterm-vscode/
├── src/
│   ├── extension.ts              # Punto de entrada de la extensión
│   ├── client/
│   │   └── KogniTermClient.ts    # Cliente WebSocket para comunicación con backend
│   ├── ui/
│   │   ├── ChatPanel.ts          # Lógica del panel de chat
│   │   └── chatPanel.js          # Script del WebView
│   ├── integration/
│   │   └── EditorContext.ts      # Integración con el editor de VS Code
│   └── utils/
│       └── messageFormatter.ts   # Utilidades de formateo
├── media/
│   └── style.css                 # Estilos del panel de chat
├── package.json
├── tsconfig.json
└── README.md
```

### Flujo de comunicación

```
[VS Code Editor] ←→ [Extension (TypeScript)] ←→ [WebSocket] ←→ [KogniTerm Backend (FastAPI)]
```

1. El usuario escribe un mensaje en el panel de chat
2. La extensión envía el mensaje por WebSocket al backend
3. El backend procesa la solicitud con el agente correspondiente
4. Las respuestas se transmiten en tiempo real (streaming) de vuelta a la extensión
5. La extensión muestra las respuestas en el panel de chat

## 🔧 Desarrollo

### Estructura del proyecto

- **extension.ts**: Registra comandos, proveedores de vistas y listeners
- **KogniTermClient**: Maneja la conexión WebSocket y el protocolo de mensajes
- **ChatPanel**: Gestiona la UI del chat y el estado de los mensajes
- **EditorContext**: Extrae contexto del editor activo (archivos, selecciones)
- **messageFormatter**: Utilidades para formatear mensajes y contenido

### Protocolo de mensajes

La extensión y el backend se comunican usando mensajes JSON:

#### Enviados por la extensión:
```json
{
  "type": "chat",
  "data": {
    "text": "¿Cómo implemento este patrón?",
    "context": { "file": "...", "selection": "..." }
  }
}
```

```json
{
  "type": "context",
  "data": {
    "type": "file",
    "data": { "uri": "...", "content": "...", "language": "python" }
  }
}
```

#### Recibidos del backend:
```json
{
  "type": "stream",
  "data": { "text": "Paso 1: ", "thinking": "Analizando el código..." }
}
```

```json
{
  "type": "tool_call",
  "data": {
    "name": "file_editor",
    "description": "Editar archivo main.py",
    "skill": "advanced-file-editor"
  }
}
```

## 🧪 Pruebas

```bash
# Compilar
npm run compile

# Ejecutar tests
npm test

# Lint
npm run lint
```

## 📦 Empaquetado

```bash
# Instalar vsce
npm install -g @vscode/vsce

# Crear paquete VSIX
vsce package

# Publicar (requiere token de VS Code Marketplace)
vsce publish
```

## 🤝 Contribuir

1. Fork el repositorio
2. Crea una rama: `git checkout -b feature/nueva-funcionalidad`
3. Commit: `git commit -m 'feat: agregar nueva funcionalidad'`
4. Push: `git push origin feature/nueva-funcionalidad`
5. Abre un Pull Request

## 📄 Licencia

MIT - Ver [LICENSE](LICENSE) para más detalles.

## 🔗 Enlaces

- [KogniTerm Backend](https://github.com/kogniterm/kogniterm)
- [VS Code Extension API](https://code.visualstudio.com/api)
- [WebSocket Protocol](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)
