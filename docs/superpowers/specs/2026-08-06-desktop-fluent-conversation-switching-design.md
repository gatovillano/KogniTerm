# Design Doc: Fluent Conversation Switching & State Preservation in KogniTerm Desktop

## Executive Summary
This design doc specifies the architecture and implementation for smooth, fluid switching between conversations (threads) in the KogniTerm desktop application (`kogniterm-desktop`). It addresses state wiping on thread change, lost scroll positions, and lost Task Tracker / Terminal states.

## Problem Statement
Currently, switching between threads in the desktop client causes:
1. **Flicker & UI reset**: `useChat` resets all state (`messages`, `taskPlans`, `terminalEntries`, `pendingApproval`) on thread ID change, causing a blank state while waiting for network fetches.
2. **Scroll loss**: `scrollToBottom()` forces auto-scroll on every message update regardless of where the user is reading or which thread was loaded.
3. **Loss of Task Tracker and Terminal history**: Context for background/completed tasks and terminal outputs is discarded on thread switch.

## Proposed Architecture

### 1. Per-Thread Memory Cache (`threadsStateMap`)
Inside `useChat` or a dedicated state manager hook:
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

- Every thread retains its data in a map keyed by `threadId`.
- Switching `threadId` instantly displays cached state (0ms latency).
- Active WebSocket connections switch gracefully without destroying thread memory.

### 2. Intelligent Scroll Position Management
- **Scroll Position Tracking**: On scroll events, the scroll position (`scrollTop`) and proximity to bottom (`isUserNearBottom`) are updated in the active thread's state.
- **Switching Threads**: When returning to a thread, `scrollTop` is restored to `threadState.scrollPosition`. If it's a newly loaded thread, it scrolls to bottom.
- **Streaming Updates**: New streaming chunks or messages trigger `scrollToBottom` ONLY if `isUserNearBottom` is `true`.

### 3. Task Tracker & Terminal Panel Synchronization
- `taskPlans`, `terminalEntries`, and `pendingApproval` are scoped per `threadId`.
- Right sidebar displays the exact task plan breakdown and terminal execution logs for the currently selected thread.

## Verification Plan
1. **Thread Switch Testing**: Create multiple threads, generate responses/tasks in Thread A, switch to Thread B, create tasks in Thread B, switch back to Thread A. Verify state (messages, tasks, terminal) remains instant and intact.
2. **Scroll Testing**: Scroll up in Thread A, switch to Thread B, switch back to Thread A. Verify scroll position remains at the exact line user was viewing.
