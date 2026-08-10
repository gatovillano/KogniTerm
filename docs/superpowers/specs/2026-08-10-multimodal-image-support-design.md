# Especificación de Diseño: Soporte de Imágenes Multimodales en KogniTerm Desktop

**Fecha**: 2026-08-10  
**Estado**: Propuesto  
**Autor**: KogniTerm Team  

## Resumen
Permitir a los usuarios adjuntar o pegar imágenes (vía portapapeles, arrastrar y soltar, o selector de archivos) en KogniTerm Desktop. Si el modelo configurado (Gemini 1.5/2.0, GPT-4o, Claude 3.5 Sonnet, Ollama LLaVA, etc.) es multimodal, el agente procesará y analizará las imágenes adjuntas junto con la consulta de texto.

---

## 1. Arquitectura y Flujo de Datos

```mermaid
sequenceDiagram
    autonumber
    actor Usuario
    participant Frontend as Desktop (React/Vite)
    participant WS as Server WebSocket (FastAPI)
    participant Session as AgentSession / LangGraph
    participant LLM as LLMService / LiteLLM
    participant API as Proveedor LLM (Gemini/OpenAI/Claude)

    Usuario->>Frontend: Pega imagen (Ctrl+V) / Arrastra / Selecciona clip
    Frontend->>Frontend: Convierte imagen a Data URL Base64 (data:image/...;base64,...)
    Usuario->>Frontend: Escribe texto y presiona Enviar
    Frontend->>WS: Envia JSON {"type":"message", "text":"...", "images":["data:image/..."]}
    WS->>Session: Llama a session.send(text, images=images)
    Session->>Session: Crea HumanMessage(content=[{text}, {image_url}])
    Session->>LLM: Invoca agente / LiteLLM con HumanMessage multimodal
    LLM->>API: Solicitud API con bloque multimodal de texto e imagen
    API-->>LLM: Respuesta streaming / estructurada
    LLM-->>Session: Eventos chunk / tool_call / done
    Session-->>WS: Retransmite eventos al cliente
    WS-->>Frontend: Renderiza respuesta en chat
```

---

## 2. Cambios Frontend (`kogniterm-desktop/apps/desktop`)

### 2.1. Tipos de Chat (`src/types/chat.ts`)
* Actualizar la interfaz `Message`:
  ```typescript
  export interface Message {
      id: string;
      role: 'user' | 'assistant' | 'system' | 'tool';
      content: string;
      images?: string[]; // Array de Data URLs Base64 (data:image/...;base64,...)
      reasoning?: string;
      tool_calls?: ToolCall[];
      tool_call_id?: string;
      timestamp: number;
  }
  ```

### 2.2. Entrada de Chat (`src/components/chat/ChatInput.tsx`)
* **Estado local**: `attachedImages: string[]` (lista de Data URLs Base64).
* **Captura de imágenes**:
  1. **Portapapeles**: Evento `onPaste` en el `<textarea>`. Si `clipboardData.items` contiene elementos `image/*`, se convierten mediante `FileReader.readAsDataURL()`.
  2. **Arrastrar y Soltar**: Eventos `onDragOver` y `onDrop` en el contenedor del input.
  3. **Selector de archivos**: Botón `<Paperclip>` que dispara un `<input type="file" accept="image/*" multiple />` oculto.
* **Previsualización UI**:
  * Barra de miniaturas horizontales encima del área de texto cuando `attachedImages.length > 0`.
  * Cada miniatura incluye un botón `X` de eliminación individual.
* **Envío**:
  * Pasa `attachedImages` a `onSendMessage(input.trim(), attachedImages)` y limpia el estado.

### 2.3. Hook de WebSocket (`src/hooks/useChat.ts`)
* Actualizar `sendMessage`:
  ```typescript
  const sendMessage = useCallback((content: string, images: string[] = []) => {
      // ...
      const newMessage: Message = {
          id: Date.now().toString(),
          role: 'user',
          content,
          images: images.length > 0 ? images : undefined,
          timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, newMessage]);
      setIsGenerating(true);
      
      socketRef.current.send(JSON.stringify({
          type: 'message',
          text: content,
          images: images.length > 0 ? images : undefined
      }));
  }, []);
  ```

### 2.4. Renderizado de Mensajes (`src/components/chat/ChatMessage.tsx`)
* Si `message.images` existe y tiene elementos:
  * Mostrar las imágenes en una cuadrícula/galería flexible encima o debajo del contenido del texto.
  * Soportar clic para agrandar o visualizar en lightbox de modal sencillo.

---

## 3. Cambios Backend (`kogniterm`)

### 3.1. Servidor WebSocket (`kogniterm/server/app.py`)
* En el manejador del WebSocket `/ws/{session_id}`:
  * Al recibir `msg_type == "message"`:
    ```python
    images = data.get("images", [])
    asyncio.create_task(session.send(text, pool._executor, images=images))
    ```

### 3.2. Gestión de Sesión (`kogniterm/server/session_pool.py`)
* Actualizar la firma de `AgentSession.send`:
  ```python
  async def send(self, message: str, executor, images: Optional[List[str]] = None) -> None:
  ```
* Construcción del `HumanMessage`:
  ```python
  if images:
      content_blocks = [{"type": "text", "text": message}]
      for img in images:
          content_blocks.append({
              "type": "image_url",
              "image_url": {"url": img}
          })
      human_msg = HumanMessage(content=content_blocks)
  else:
      human_msg = HumanMessage(content=message)

  self.agent_state.add_message(human_msg)
  ```

### 3.3. Conversor de Mensajes LiteLLM (`kogniterm/core/llm_service.py`)
* En `_to_litellm_message(self, message: BaseMessage, ...)`:
  * Si `isinstance(message, HumanMessage)` y `isinstance(message.content, list)`:
    * Preservar el contenido estructurado como lista directamente:
      ```python
      if isinstance(message, HumanMessage):
          content = message.content
          if isinstance(content, list):
              return {"role": "user", "content": content}
          elif not isinstance(content, str):
              content = json.dumps(content) if isinstance(content, (dict, list)) else str(content)
          return {"role": "user", "content": content}
      ```

### 3.4. Persistencia e Historial (`kogniterm/server/app.py`)
* En `message_to_frontend_dict(msg, index: int)`:
  * Extraer las URLs/Base64 de `image_url` si `msg.content` es una lista.
  * Devolver el campo `images` en la respuesta JSON para que las imágenes persistidas se carguen en el frontend al cambiar de hilo.

---

## 4. Plan de Verificación

1. **Prueba Manual de Frontend**:
   * Pegar una imagen desde el portapapeles con `Ctrl+V` en el área de texto.
   * Verificar que aparezca la miniatura de previsualización con su botón de eliminar.
   * Adjuntar una imagen con el botón de clip `<Paperclip>`.
2. **Prueba de Transmisión WebSocket**:
   * Enviar un mensaje con imagen adjunta.
   * Inspeccionar la consola/red del frontend para verificar la estructura del evento WebSocket enviado.
3. **Prueba de Visión Multimodal con LLM**:
   * Usar un modelo multimodal activo (ej. `antigravity/gemini-2.5-flash` o `gemini/gemini-1.5-flash`).
   * Adjuntar una imagen con un texto descriptivo o una captura de pantalla de un diagrama/código y verificar que el modelo interprete y describa el contenido de la imagen correctamente.
