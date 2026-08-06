# Desktop Fluent Conversation Switching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make switching between conversations in `kogniterm-desktop` instant, fluid, and stateful, preserving messages, Task Tracker (`taskPlans`), Terminal logs (`terminalEntries`), pending approvals (`pendingApproval`), message queues, and exact scroll positions per thread.

**Architecture:** Refactor `useChat` in `kogniterm-desktop/apps/desktop/src/hooks/useChat.ts` to use a per-thread cache store for `SingleThreadState`. Update `App.tsx` to handle scroll position restoration per thread and intelligent auto-scroll during live message streaming.

**Tech Stack:** React 18, TypeScript, Tailwind CSS, Tauri / Desktop Client.

## Global Constraints
- React 18 functional components and hooks.
- No breaking changes to existing WebSocket server protocol.
- Preserved existing layout and styling (Goose UI).

---

### Task 1: Refactor `useChat` Hook for Per-Thread Caching

**Files:**
- Modify: `kogniterm-desktop/apps/desktop/src/hooks/useChat.ts`

**Interfaces:**
- Produces: `SingleThreadState` interface, `setThreadScrollPosition(threadId: string, scrollTop: number, isNearBottom: boolean)` exposed helper.

- [ ] **Step 1: Define `SingleThreadState` and thread state cache ref**

Update `useChat.ts` to include:
```ts
export interface SingleThreadState {
    messages: Message[];
    taskPlans: Record<string, { task: string; status: string }[]>;
    terminalEntries: TerminalEntry[];
    pendingApproval: ApprovalRequest | null;
    messageQueue: string[];
    isGenerating: boolean;
    scrollPosition: number;
    isUserNearBottom: boolean;
}
```

- [ ] **Step 2: Implement state caching per thread ID**

Maintain a `threadsCacheRef` (`useRef<Record<string, SingleThreadState>>({})`) to cache thread states when switching away from or updating a thread.

- [ ] **Step 3: Update `useEffect([threadId])` to restore cached state on thread switch**

When switching `threadId`:
- Save current active thread state into `threadsCacheRef.current[prevThreadId]`.
- Load cached state for `newThreadId` immediately (or default empty if first time).
- Connect WebSocket without zeroing out existing cached data.

- [ ] **Step 4: Expose `setThreadScrollPosition`**

Add callback to allow `App.tsx` to update `scrollPosition` and `isUserNearBottom` in `threadsCacheRef` for the active thread.

- [ ] **Step 5: Verify typescript compilation**

Run: `cd kogniterm-desktop && npm run build --workspace=apps/desktop` (or test build script).

---

### Task 2: Implement Intelligent Scroll Restoration and Auto-Scroll in `App.tsx`

**Files:**
- Modify: `kogniterm-desktop/apps/desktop/src/App.tsx:430-510`

**Interfaces:**
- Consumes: `setThreadScrollPosition`, `messages`, `currentThreadId` from `useChat`.

- [ ] **Step 1: Add `chatContainerRef` to the chat scroll section**

Attach `ref={chatContainerRef}` to the `<section className="flex-1 overflow-y-auto goose-scrollbar ...">` element in `App.tsx`.

- [ ] **Step 2: Add `handleScroll` event listener**

Capture `scrollTop`, `scrollHeight`, and `clientHeight` on scroll events:
- Compute `isNearBottom = scrollHeight - scrollTop - clientHeight < 100`.
- Call `setThreadScrollPosition(currentThreadId, scrollTop, isNearBottom)`.

- [ ] **Step 3: Restore scroll position on `currentThreadId` change**

When `currentThreadId` changes:
- Restore `chatContainerRef.current.scrollTop` from the cached `scrollPosition` for that thread.

- [ ] **Step 4: Update `scrollToBottom` logic**

Only call `scrollToBottom()` on message updates if `isUserNearBottom` is true or if the last message was sent by the user.

- [ ] **Step 5: Verify build and component behavior**

Run build command and test switching between threads.
