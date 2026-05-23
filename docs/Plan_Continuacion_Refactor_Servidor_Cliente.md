# Plan de Continuación de Refactorización: Arquitectura Cliente-Servidor (TUI Desacoplada)

> **Autor**: Antigravity  
> **Fecha**: 2026-05-18  
> **Estado**: Propuesta de Implementación Estructurada  
> **Área**: KogniTerm Client-Server Refactoring  

---

## 1. Contexto y Diagnóstico Actual

Actualmente, la interfaz **TUI (Textual)** de KogniTerm ([`kogniterm/terminal/tui/tui_app.py`](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/terminal/tui/tui_app.py)) sigue operando bajo un modelo **monolítico híbrido**. Aunque el servidor backend en FastAPI ya existe y está activo, la TUI continúa consumiendo una lógica local de procesamiento:

### Hallazgos Críticos del Diagnóstico
1. **Acoplamiento Físico Directo**:
   - En el punto de entrada de la terminal ([`kogniterm/terminal/terminal.py`](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/terminal/terminal.py)), se instancian localmente `LLMService()`, `CommandExecutor()` y `AgentState()`, inyectándose directamente al constructor de la clase `KogniTermTUI`.
   - La TUI importa e instancia componentes como `AgentInteractionManager` y `CommandApprovalHandler` para procesar peticiones localmente.
2. **Hilos Síncronos Locales**:
   - El método `process_agent_request` en `tui_app.py` utiliza `@work(thread=True)` para arrancar un hilo de fondo local en la máquina de la TUI, llamando a `self.agent_interaction_manager.invoke_agent(user_input)` síncronamente.
   - Las aprobaciones de comandos se bloquean a nivel de hilo TUI local mediante `ask_for_approval_sync`.
3. **Inversión de Dependencias (Circular Imports / Spaghetti Code)**:
   - El servidor backend (`kogniterm/server/session_pool.py`) e incluso los agentes de LangGraph en el core (`kogniterm/core/agents/*.py`) importan módulos visuales desde el directorio de la terminal (`kogniterm/terminal/terminal_ui`, `kogniterm/terminal/visual_components`, etc.), impidiendo empaquetar el servidor por separado de la TUI.
4. **Ausencia de Canal WebSocket en la TUI**:
   - No existe un cliente WebSocket implementado en `tui_app.py` o `api_client_tui.py`. El cliente de la TUI solo cuenta con métodos HTTP REST síncronos en `api_client_tui.py`.

---

## 2. Estado Objetivo (Target Architecture)

El objetivo de esta fase de refactorización es lograr que **KogniTermTUI sea un cliente visual 100% ligero y reactivo**, libre de dependencias de ejecución de IA locales, interactuando con el servidor centralizado de la siguiente manera:

```
┌────────────────────────────────────────────────────────┐
│                   CLIENTE TUI (Textual)                │
│                                                        │
│   ┌────────────────────────────────────────────────┐   │
│   │               KogniTermTUI App                 │   │
│   │                                                │   │
│   │  - UI Renderers (ChatLog, ToolOutput, etc)    │   │
│   │  - WS Client Thread (Persistente, Async)       │◄──┼──┐
│   └────────────────────────────────────────────────┘   │  │
└──────────────────────────┬─────────────────────────────┘  │
                           │                                │
                           │ WS Bidireccional               │
                           │ JSON Events                    │
                           ▼                                │
┌────────────────────────────────────────────────────────┐  │
│                   SERVIDOR BACKEND (FastAPI)           │  │ Confirmaciones
│                                                        │  │ de Aprobación
│   ┌────────────────────────────────────────────────┐   │  │ (Remote Handshake)
│   │               FastAPI (ws://)                  │   │  │
│   │                                                │   │  │
│   │   SessionPool                                  │   │  │
│   │   └── AgentSession                             │   │  │
│   │       ├── AgentInteractionManager (Core Run)   │───┼──┘
│   │       ├── ServerUI (Event Queue & Push)        │   │
│   │       └── ThreadPoolExecutor (Agent Workers)   │   │
│   └────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────┘
```

### Reglas Clave del Estado Objetivo:
* **TUI de Pantalla Pura**: La TUI solo captura eventos de teclado/ratón, dibuja widgets elegantes e interactúa con un socket de red.
* **Backend de Procesamiento Centralizado**: Toda la inicialización del modelo (Gemini, OpenAI, etc.), base de datos ChromaDB, indexación, LangGraph y ejecución de comandos bash se desplaza al backend FastAPI.
* **Handshake de Confirmaciones**: La aprobación de comandos Bash y edición de archivos se solicita de forma asíncrona mediante un evento `approval_required` enviado por el servidor hacia el cliente WebSocket, deteniendo el hilo de ejecución en el servidor mediante eventos de exclusión mutua (`threading.Event`) hasta que la TUI responda con un evento `approval_response`.

---

## 3. Plan de Acción Detallado (Paso a Paso)

El proceso de refactorización se dividirá en 5 fases secuenciales que aseguran cambios estables, seguros y con facilidad de pruebas previas.

### 📋 Fase 1: Desacoplamiento de Módulos Visuales Compartidos (Inversión de Dependencias)
**Objetivo**: Mover los componentes reutilizables a un namespace independiente para que el servidor y core no importen desde el directorio `terminal/`.

1. **Crear Módulo Compartido de UI (`kogniterm/ui/`)**:
   - Crear el directorio `kogniterm/ui/` con un archivo `__init__.py`.
   - Mover los componentes agnósticos de Textual a esta nueva ubicación:
     - `kogniterm/terminal/terminal_ui.py` ➔ `kogniterm/ui/terminal_ui.py` (Clase base de eventos e interfaz abstracta).
     - `kogniterm/terminal/visual_components.py` ➔ `kogniterm/ui/visual_components.py` (Paneles, tablas y layouts de texto Rich).
     - `kogniterm/terminal/themes.py` ➔ `kogniterm/ui/themes.py` (Sistema global de paletas y temas).
     - `kogniterm/terminal/security.py` ➔ `kogniterm/ui/security.py` (Scrubbing y remoción de secretos).
2. **Actualizar Referencias en el Servidor y Core**:
   - Modificar las cabeceras de importación en `kogniterm/server/session_pool.py`.
   - Modificar las cabeceras en `kogniterm/core/agents/*.py` y en las herramientas (`kogniterm/core/skills/`).
   - *Resultado esperado*: `kogniterm/terminal/` es un consumidor puro. El backend puede correr de forma aislada sin dependencias de este directorio.

---

### 📡 Fase 2: Implementación de la Conexión WebSocket en la TUI
**Objetivo**: Dotar a la TUI de un cliente WebSocket asíncrono robusto e integrado con el ciclo de eventos de Textual.

1. **Integración en `tui_app.py`**:
   - Incorporar la librería `websockets` o `httpx` (con soporte para WS async) como dependencia de red del cliente.
   - En el evento `on_mount` de `KogniTermTUI`, arrancar un Textual Worker asíncrono y exclusivo:
     ```python
     @work(exclusive=True)
     async def _maintain_websocket_connection(self):
         # Loop infinito de reconexión con backoff exponencial
     ```
2. **Visualización de Estado en la Interfaz (UI State Indicators)**:
   - Añadir un banner de conexión transparente o un indicador luminoso (por ejemplo, `● Conectado` / `○ Desconectado`) en la esquina del `StatusFooter` de la TUI.
   - Mostrar un Splash Screen bloqueante si el servidor no está en línea, permitiendo reintentar la conexión periódicamente cada 3 segundos.

---

### 🔄 Fase 3: Ruteo de Eventos en Tiempo Real (JSON ➔ Widgets)
**Objetivo**: Enrutar los eventos serializados que emite el backend y mapearlos a la actualización en tiempo real de los widgets existentes.

1. **Reemplazo de `process_agent_request`**:
   - En lugar de arrancar el agente local en un hilo, la TUI enviará el prompt del usuario en formato JSON al socket:
     ```json
     {
       "type": "message",
       "text": "mensaje de usuario"
     }
     ```
2. **Dispatcher de Eventos Recibidos**:
   - Diseñar la función `_route_websocket_event(self, event: dict)` encargada de procesar las señales:
     * **`stream` / `chunk`**: Llamar a `self._safe_call(self.chat_log.write_stream, data["content"])`.
     * **`tool_start` / `tool_call`**: Lanzar la notificación interactiva de la herramienta a través de `self.chat_log.write_tool_notification(...)`.
     * **`tool_output` / `tool_result`**: Canalizar la salida a `self.update_terminal_output(...)` (PTY widget) o `ToolOutputWidget`.
     * **`task_tracker`**: Actualizar el panel lateral de progreso en `TaskTrackerPanelWidget`.
     * **`done` / `error`**: Detener la animación del spinner principal y volver a habilitar la caja de texto.

---

### 🛡️ Fase 4: Confirmaciones Remotas de Seguridad
**Objetivo**: Permitir que el backend solicite la aprobación del usuario antes de ejecutar comandos bash o mutar el código del host, pausando el agente síncronamente en el servidor hasta recibir respuesta.

1. **Event Dispatcher de Aprobación**:
   - Al recibir el evento:
     ```json
     {
       "type": "approval_required",
       "data": {
         "id": "uuid-evento-servidor",
         "message": "¿Deseas ejecutar el comando...",
         "diff_content": "diff o texto",
         "file_path": "ruta_archivo"
       }
     }
     ```
     La TUI abrirá de forma no bloqueante el widget `InlineApprovalWidget` o el modal `CommandApprovalModal` en la capa visual correspondiente.
2. **Retorno de Respuesta (Approval Callback)**:
   - Al dar click en **Aceptar** o **Rechazar** en la interfaz Textual, la TUI enviará el callback al WebSocket de inmediato:
     ```json
     {
       "type": "approval_response",
       "id": "uuid-evento-servidor",
       "approved": true
     }
     ```
   - En el Servidor, `ServerUI.handle_approval_response(request_id, approved)` recibirá la señal y despertará al hilo de LangGraph bloqueado utilizando un `threading.Event` interno por sesión.

---

### 📁 Fase 5: Inicialización Contextual del Workspace y CLI
**Objetivo**: Pasar el entorno local de ejecución del usuario al servidor y refactorizar el punto de entrada CLI.

1. ** Handshake Contextual de CWD**:
   - El servidor requiere saber en qué directorio físico del Host está posicionado el usuario para poder realizar búsquedas e indexaciones con ChromaDB.
   - Al conectar la TUI por primera vez, el cliente debe enviar un evento de inicialización o realizar un `POST /sessions` inyectando el `workspace_directory = os.getcwd()` actual.
   - El backend creará la sesión y configurará el entorno shell (`CommandExecutor`) y el índice semántico apuntando a dicha ubicación.
2. **Actualización de `terminal.py` (Punto de Entrada Ligero)**:
   - Eliminar las instanciaciones locales e inyecciones de `LLMService()`, `CommandExecutor()` y `AgentState()` en el constructor de `KogniTermTUI` en `terminal.py`.
   - Modificar la invocación de `KogniTermTUI` para recibir simplemente la URL del servidor (`http://127.0.0.1:8765`) y el `session_id`.

---

## 4. Matriz de Riesgos y Mitigaciones

| Riesgo / Desafío | Impacto | Estrategia de Mitigación |
| :--- | :---: | :--- |
| **Desconexión abrupta de la TUI a mitad de un proceso** | **Alto** | El agente se ejecuta en un pool de hilos independiente en el Servidor (`AgentSession`). Si el socket muere, el agente continúa ejecutándose. Al reconectarse, la TUI puede consultar los últimos mensajes persistidos vía REST para recuperar el hilo visual. |
| **Problemas de sincronización en aprobaciones remotas (Timeout)** | **Medio** | Si la aprobación queda huérfana en el servidor por desconexión, añadir un timeout de 10 minutos. Transcurrido ese tiempo, el agente asume rechazo automático y libera el worker thread de forma segura. |
| **Diferencias de latencia en streaming visual** | **Bajo** | El protocolo WebSocket local tiene latencia menor a 5ms. El ruteo de eventos directos garantiza que no exista delay perceptible en comparación a la ejecución local. |

---

## 5. Criterios de Aceptación (Definition of Done)

Para considerar la refactorización completada exitosamente, se deben verificar los siguientes puntos:

1. **Cero Motores Locales**: `KogniTermTUI` arranca de forma instantánea sin requerir cargar localmente SDKs de IA, ChromaDB, bases de datos vectoriales ni instanciar `LLMService`.
2. **Desacoplamiento Absoluto**: El directorio `kogniterm/server` y `kogniterm/core` no realizan ninguna importación que comience con `kogniterm.terminal`. Todas las dependencias compartidas se importan de `kogniterm.ui`.
3. **Flujo de Eventos Operacional**: Escribir en la caja de chat de la TUI transmite el mensaje, inicia el spinner de forma asíncrona, recibe fragmentos de streaming de respuesta y ejecuta comandos pidiendo confirmación de forma exitosa mediante red.
4. **Resistencia de Sesión**: Cerrar la TUI y volverla a abrir reconecta automáticamente al mismo `session_id` (`tui-default`) y recupera el historial de chat del backend sin perder el estado del agente persistente.
