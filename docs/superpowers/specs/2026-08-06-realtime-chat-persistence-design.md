# Design Spec: Persistencia en Tiempo Real Mensaje a Mensaje y Streaming Continuo

## Contexto y Objetivo
En el cliente desktop (`kogniterm-desktop`), al salir y volver a entrar a una conversación (o al reiniciar la aplicación), se perdían los mensajes recientes si el agente estaba respondiendo o si la respuesta no había concluido el ciclo completo.
El objetivo es garantizar:
1. **Persistencia mensaje a mensaje a disco**: Que cada `HumanMessage`, `AIMessage` y `ToolMessage` sea guardado inmediatamente a disco (`messages.json` y `metadata.json`) en el `ThreadManager`.
2. **Re-acoplamiento de streaming en vivo**: Que al volver a un chat donde el agente está ejecutando/generando en segundo plano, la interfaz reanude el indicador de generación, razonamiento en vivo, streaming de respuesta y salidas de terminal sin parpadeos ni pérdida de estado.

## Cambios Propuestos

### 1. Backend (`kogniterm/server/session_pool.py`)
- **Guardado Inmediato**:
  - En `AgentSession.send(...)`: Invocar `self.thread_manager.save_thread_messages(self.session_id, self.agent_state.messages)` inmediatamente tras añadir el `HumanMessage`.
  - En `_run_agent_loop` y hooks de la sesión: Invocar `save_thread_messages` tras añadir o actualizar mensajes en el estado.
- **Búfer de Estado de Streaming**:
  - Mantener en `AgentSession` las variables de estado en vivo `current_thinking`, `current_response` y `active_terminal_entries`.
  - Actualizar estas variables en tiempo real dentro de `ServerUI` al emitir eventos `live_update`, `chunk` y `terminal_output`.
  - Resetear estas variables al emitir el evento `done` o `error`.

### 2. Protocolo WebSocket (`kogniterm/server/app.py`)
- En el handler `@application.websocket("/ws/{session_id}")`:
  - Enviar en la carga útil de `connected` el campo `is_running: session.is_running` y los datos del `live_state` activo (`thinking`, `response`, `terminal_entries`).

### 3. Cliente Desktop (`kogniterm-desktop/apps/desktop/src/hooks/useChat.ts`)
- En `useChat(threadId)`:
  - Al procesar el evento `connected` de WebSocket, verificar `data.is_running`. Si es `true`, activar `isGenerating = true` y restaurar los datos parciales de `live_state`.
  - Sincronizar el caché en memoria `threadsCacheRef` con cada actualización de mensajes.

## Plan de Verificación
- **Prueba 1**: Enviar un mensaje, cambiar inmediatamente a otra conversación y volver al chat original mientras el agente genera respuesta. Verificar que la respuesta se sigue transmitiendo en vivo.
- **Prueba 2**: Cerrar la app/re-cargar el cliente durante la respuesta del agente. Verificar que todos los mensajes completados y el mensaje del usuario persisten en disco al volver a cargar.
