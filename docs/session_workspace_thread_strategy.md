# Estrategia de separación: workspace, sesión e hilo

## Conceptos
- **Workspace**: Un proyecto o carpeta de trabajo. Identificador único (ej: ruta absoluta, hash, nombre).
- **Session**: Una instancia de conversación persistente (ej: una ventana de TUI, CLI, Desktop, o chat Telegram). Puede estar asociada a un workspace.
- **Thread**: Un hilo de conversación dentro de una sesión (ej: subhilo, chat paralelo, issue, etc).

## Reglas
- Cada request de frontend debe incluir:
  - `workspace_id` (opcional si es global)
  - `session_id` (único por ventana/cliente)
  - `thread_id` (opcional, para subhilos)
- El backend debe enrutar y mantener el historial/config por (workspace_id, session_id, thread_id).
- Los adaptadores de canal (Telegram, CLI, TUI, Desktop) deben generar y persistir estos IDs y enviarlos en cada request/evento.
- El backend debe exponer endpoints que acepten estos IDs y devuelvan el historial, config y estado correctos.

## Ejemplo de payload
```json
{
  "workspace_id": "/home/gato/Proyectos/Gemini-Interpreter",
  "session_id": "tui-1234abcd",
  "thread_id": "main"
}
```

## Implementación mínima
- Generar `session_id` único por cliente/ventana y persistirlo localmente.
- Incluir estos IDs en cada request (header, query param o body).
- Backend: modificar SessionPool y endpoints para usar estos IDs como clave.
- Historial, config y estado se almacenan por (workspace_id, session_id, thread_id).

## Beneficios
- Separación robusta multiusuario y multiplataforma.
- No se mezclan conversaciones ni configuraciones.
- Escalable a múltiples canales y proyectos.

---

**Este documento debe guiar la refactorización de todos los canales y el backend para soportar separación real de contexto.**
