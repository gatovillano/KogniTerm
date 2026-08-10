# Multimodal Image Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable users to attach or paste images in KogniTerm Desktop and send them to multimodal LLM models for visual understanding and analysis.

**Architecture:** Images are captured in React (`ChatInput.tsx`) via clipboard paste, drag-and-drop, or file selector, converted to base64 Data URLs, and sent alongside user text over WebSocket. The Python server (`app.py`, `session_pool.py`, `llm_service.py`) formats these as OpenAI-compliant multimodal message content arrays (`[{"type": "text", "text": "..."}, {"type": "image_url", "image_url": {"url": "data:..."}}]`) for LiteLLM.

**Tech Stack:** React, TypeScript, Tailwind CSS, Python (FastAPI, LangChain, LiteLLM).

## Global Constraints
- Base64 Data URL format for images (`data:image/<type>;base64,<data>`).
- Backward compatibility: Text-only messages must continue working identically.
- Message history persistence: Image attachments must persist when saving and loading thread history.

---

### Task 1: Update Frontend Data Types & WebSocket Messaging (`kogniterm-desktop/apps/desktop`)

**Files:**
- Modify: `kogniterm-desktop/apps/desktop/src/types/chat.ts`
- Modify: `kogniterm-desktop/apps/desktop/src/hooks/useChat.ts`

**Interfaces:**
- Consumes: WebSocket connection to `ws://127.0.0.1:8765/ws/{threadId}`
- Produces: `Message.images?: string[]`, updated `sendMessage(content: string, images?: string[])` signature

- [ ] **Step 1: Add `images` property to `Message` interface**

Update `kogniterm-desktop/apps/desktop/src/types/chat.ts`:
```typescript
export interface Message {
    id: string;
    role: 'user' | 'assistant' | 'system' | 'tool';
    content: string;
    images?: string[];
    reasoning?: string;
    tool_calls?: ToolCall[];
    tool_call_id?: string;
    timestamp: number;
}
```

- [ ] **Step 2: Update `useChat.ts` to support image payload in `sendMessage`**

Update `sendMessage` in `kogniterm-desktop/apps/desktop/src/hooks/useChat.ts`:
```typescript
const sendMessage = useCallback((content: string, images: string[] = []) => {
    const trimmed = content.trim();

    if (trimmed === '/clear' || trimmed === '%clear') {
        setMessages([]);
        setAppliedDiffs([]);
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
        images: images.length > 0 ? images : undefined,
        timestamp: Date.now(),
    };

    setMessages((prev) => [...prev, newMessage]);
    setIsGenerating(true);
    setError(null);

    socketRef.current.send(JSON.stringify({
        type: 'message',
        text: content,
        images: images.length > 0 ? images : undefined
    }));
}, []);
```

- [ ] **Step 3: Commit frontend message updates**

```bash
git add kogniterm-desktop/apps/desktop/src/types/chat.ts kogniterm-desktop/apps/desktop/src/hooks/useChat.ts
git commit -m "feat(desktop): add image payload support to Message interface and useChat hook"
```

---

### Task 2: Implement Image Paste, Drag-and-Drop & Preview UI in `ChatInput.tsx`

**Files:**
- Modify: `kogniterm-desktop/apps/desktop/src/components/chat/ChatInput.tsx`

**Interfaces:**
- Consumes: `onSendMessage: (message: string, images?: string[]) => void`
- Produces: Base64 image attachment thumbnails with removal actions, clipboard paste, file drag & drop, file picker trigger.

- [ ] **Step 1: Add `attachedImages` state and helper functions to `ChatInput.tsx`**

In `ChatInput.tsx`:
```typescript
interface ChatInputProps {
    onSendMessage: (message: string, images?: string[]) => void;
    // ...
}
```
Add file reader helper and state:
```typescript
const [attachedImages, setAttachedImages] = useState<string[]>([]);
const fileInputRef = useRef<HTMLInputElement>(null);

const handleFiles = (files: FileList | File[]) => {
    Array.from(files).forEach((file) => {
        if (!file.type.startsWith('image/')) return;
        const reader = new FileReader();
        reader.onload = (e) => {
            const result = e.target?.result as string;
            if (result) {
                setAttachedImages((prev) => [...prev, result]);
            }
        };
        reader.readAsDataURL(file);
    });
};

const handlePaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const items = e.clipboardData.items;
    const imageFiles: File[] = [];
    for (let i = 0; i < items.length; i++) {
        if (items[i].type.startsWith('image/')) {
            const file = items[i].getAsFile();
            if (file) imageFiles.push(file);
        }
    }
    if (imageFiles.length > 0) {
        handleFiles(imageFiles);
    }
};

const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        handleFiles(e.dataTransfer.files);
    }
};
```

- [ ] **Step 2: Add image thumbnail previews above `textarea` and update `handleSubmit`**

In `handleSubmit`:
```typescript
const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (input.trim() || attachedImages.length > 0) {
        onSendMessage(input.trim(), attachedImages);
        setInput('');
        setAttachedImages([]);
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
        }
        setShowSuggestions(false);
        setActiveTrigger(null);
    }
};
```
Render image thumbnail pills inside the input form:
```tsx
{attachedImages.length > 0 && (
    <div className="flex items-center gap-2 px-3 pt-2 pb-1 overflow-x-auto custom-scrollbar">
        {attachedImages.map((imgUrl, idx) => (
            <div key={idx} className="relative group shrink-0 rounded-lg overflow-hidden border border-zinc-700 bg-zinc-900 w-14 h-14">
                <img src={imgUrl} alt={`Adjunto ${idx + 1}`} className="w-full h-full object-cover" />
                <button
                    type="button"
                    onClick={() => setAttachedImages((prev) => prev.filter((_, i) => i !== idx))}
                    className="absolute top-1 right-1 bg-black/70 hover:bg-red-600 text-white rounded-full p-0.5 transition-colors"
                >
                    <X size={10} />
                </button>
            </div>
        ))}
    </div>
)}
```

Add file input element and trigger:
```tsx
<input
    type="file"
    ref={fileInputRef}
    onChange={(e) => e.target.files && handleFiles(e.target.files)}
    accept="image/*"
    multiple
    className="hidden"
/>
<button
    type="button"
    onClick={() => fileInputRef.current?.click()}
    className="p-1 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-md text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 transition-all"
    title="Adjuntar imagen"
>
    <Paperclip size={13} />
</button>
```

- [ ] **Step 3: Commit `ChatInput.tsx` updates**

```bash
git add kogniterm-desktop/apps/desktop/src/components/chat/ChatInput.tsx
git commit -m "feat(desktop): add image paste, drag & drop, and preview thumbnail bar in ChatInput"
```

---

### Task 3: Render Attached Images in `ChatMessage.tsx`

**Files:**
- Modify: `kogniterm-desktop/apps/desktop/src/components/chat/ChatMessage.tsx`

**Interfaces:**
- Consumes: `message.images?: string[]`
- Produces: Image thumbnail gallery rendering inside message bubbles.

- [ ] **Step 1: Render `message.images` gallery in `ChatMessage.tsx`**

In `ChatMessage.tsx`:
```tsx
{message.images && message.images.length > 0 && (
    <div className="flex flex-wrap gap-2 my-2">
        {message.images.map((imgUrl, index) => (
            <div key={index} className="relative group max-w-xs rounded-xl overflow-hidden border border-zinc-800 bg-zinc-900 shadow-md">
                <img
                    src={imgUrl}
                    alt={`Imagen adjunta ${index + 1}`}
                    className="max-h-60 object-contain cursor-pointer hover:opacity-95 transition-opacity"
                    onClick={() => window.open(imgUrl, '_blank')}
                />
            </div>
        ))}
    </div>
)}
```

- [ ] **Step 2: Commit `ChatMessage.tsx` updates**

```bash
git add kogniterm-desktop/apps/desktop/src/components/chat/ChatMessage.tsx
git commit -m "feat(desktop): render attached image gallery in ChatMessage component"
```

---

### Task 4: Backend WebSocket & Session Multimodal Integration (`kogniterm`)

**Files:**
- Modify: `kogniterm/server/app.py`
- Modify: `kogniterm/server/session_pool.py`
- Modify: `kogniterm/core/llm_service.py`

**Interfaces:**
- Consumes: WS `{"type": "message", "text": "...", "images": ["data:image/..."]}`
- Produces: Multimodal `HumanMessage(content=[{"type": "text", ...}, {"type": "image_url", ...}])`, LiteLLM format preservation, Thread history persistence.

- [ ] **Step 1: Receive `images` in WebSocket `/ws/{session_id}` handler in `app.py`**

In `kogniterm/server/app.py` under `if msg_type == "message":`:
```python
if msg_type == "message":
    text = data.get("text", "").strip()
    images = data.get("images", [])
    if not text and not images:
        continue
    asyncio.create_task(session.send(text, pool._executor, images=images))
```

- [ ] **Step 2: Support `images` in `AgentSession.send` in `session_pool.py`**

Update signature and message creation in `kogniterm/server/session_pool.py`:
```python
async def send(self, message: str, executor, images: Optional[List[str]] = None) -> None:
    # ...
    if images:
        content_blocks = []
        if message:
            content_blocks.append({"type": "text", "text": message})
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

- [ ] **Step 3: Preserve multimodal content list in `_to_litellm_message` in `llm_service.py`**

In `kogniterm/core/llm_service.py` under `_to_litellm_message`:
```python
if isinstance(message, HumanMessage):
    content = message.content
    if isinstance(content, list):
        return {"role": "user", "content": content}
    elif not isinstance(content, str):
        content = json.dumps(content) if isinstance(content, (dict, list)) else str(content)
    return {"role": "user", "content": content}
```

- [ ] **Step 4: Update `message_to_frontend_dict` in `app.py` for thread history reload**

In `kogniterm/server/app.py` in `message_to_frontend_dict`:
```python
images = []
content = msg.content if msg.content is not None else ""
if isinstance(content, list):
    text_parts = [part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"]
    content = " ".join(text_parts)
    for part in msg.content:
        if isinstance(part, dict) and part.get("type") == "image_url":
            img_url = part.get("image_url")
            if isinstance(img_url, dict):
                url = img_url.get("url", "")
            else:
                url = str(img_url)
            if url:
                images.append(url)

return {
    "id": f"loaded-{index}",
    "role": role,
    "content": content,
    "images": images if images else undefined, # or omitted if empty
    "reasoning": reasoning,
    "tool_calls": tool_calls,
    "tool_call_id": tool_call_id,
    "timestamp": int(datetime.utcnow().timestamp() * 1000)
}
```

- [ ] **Step 5: Commit backend multimodal updates**

```bash
git add kogniterm/server/app.py kogniterm/server/session_pool.py kogniterm/core/llm_service.py
git commit -m "feat(server): support multimodal image messages in websocket, session pool and litellm converter"
```

---

## Plan Verification

Run pytest backend suite:
```bash
pytest tests/ -v
```

Build desktop app to verify typescript types and clean compilation:
```bash
cd kogniterm-desktop/apps/desktop && npm run build
```
