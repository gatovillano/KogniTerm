# Desktop Minimalist Redesign (Linear / Cursor Aesthetic) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign KogniTerm Desktop into a clean, monochromatic, technical minimalist interface inspired by Linear, Raycast, and Cursor.

**Architecture:** Remove the heavy top `<header>` bar completely, replace the empty state widgets (7xl clock, greeting, action cards) with a centered distraction-free prompt, and add a subtle top-right floating micro-HUD for essential quick actions (Auto-approve toggle, directory picker, and right panel toggle). Refine `ChatInput` with flat surfaces and 1px crisp borders.

**Tech Stack:** React 19, TypeScript, Tailwind CSS v4, Lucide React, Tauri 2.

## Global Constraints
- Target directory: `kogniterm-desktop/apps/desktop`.
- Monochromatic neutral aesthetic: `zinc-950` / `zinc-900` / `zinc-800` in dark mode, `white` / `zinc-100` / `zinc-200` in light mode.
- 1px hairline borders (`border-zinc-200/60 dark:border-zinc-800/60`).
- No bulky pill containers, shadows, or loud badges.

---

### Task 1: Redesign Empty State, Remove Top Header, and Add Top-Right Floating HUD in `App.tsx`

**Files:**
- Modify: `kogniterm-desktop/apps/desktop/src/App.tsx`

**Interfaces:**
- Consumes: `autoApprove`, `toggleAutoApprove`, `currentDir`, `handleChangeDir`, `isRightSidebarOpen`, `setIsRightSidebarOpen` from existing state in `App.tsx`.
- Produces: Seamless canvas without fixed header bar; top-right floating HUD; centered distraction-free empty state.

- [ ] **Step 1: Replace `<header>` with top-right floating HUD**
Remove the `<header className="h-14 ...">` block and replace it with an absolute-positioned floating HUD at the top-right of the `<main>` container:
```tsx
<div className="absolute top-3 right-4 z-30 flex items-center gap-1.5 opacity-40 hover:opacity-100 transition-opacity duration-200">
  {/* Workspace Directory Trigger */}
  <button
    onClick={handleChangeDir}
    className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-mono text-zinc-500 dark:text-zinc-400 hover:text-zinc-800 dark:hover:text-zinc-200 hover:bg-zinc-200/50 dark:hover:bg-zinc-800/50 transition-colors cursor-pointer"
    title="Cambiar directorio de trabajo"
  >
    <span>{currentDir}</span>
  </button>

  {/* Auto-Approve Toggle */}
  <button
    type="button"
    onClick={toggleAutoApprove}
    title={autoApprove ? "Auto-aprobación activa (Clic para desactivar)" : "Auto-aprobación inactiva (Clic para activar)"}
    className={`flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] font-medium transition-colors cursor-pointer ${
      autoApprove 
        ? 'text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/10' 
        : 'text-zinc-400 dark:text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 hover:bg-zinc-200/50 dark:hover:bg-zinc-800/50'
    }`}
  >
    {autoApprove ? <Zap size={13} className="fill-emerald-500/20" /> : <ShieldCheck size={13} />}
    <span className="text-[11px]">{autoApprove ? "Auto" : "Manual"}</span>
  </button>

  {/* Right Sidebar Toggle */}
  <button
    type="button"
    onClick={() => setIsRightSidebarOpen(prev => !prev)}
    title={isRightSidebarOpen ? "Ocultar panel lateral" : "Mostrar panel lateral"}
    className="p-1 rounded-md text-zinc-400 dark:text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 hover:bg-zinc-200/50 dark:hover:bg-zinc-800/50 transition-colors cursor-pointer"
  >
    <PanelRightOpen size={14} />
  </button>
</div>
```

- [ ] **Step 2: Streamline Empty State**
In `activeView === 'chat'`, when `messages.length === 0`:
Remove the 7xl digital clock, greeting headline, and suggestion action cards.
Replace with a clean, centered prompt container:
```tsx
<div className="h-[75vh] flex flex-col items-center justify-center text-center px-4 animate-fade-in">
  <div className="w-full max-w-2xl flex flex-col items-center">
    <ChatInput 
      onSendMessage={handleSendMessage} 
      isGenerating={isGenerating} 
      onStopGeneration={stopGeneration}
      currentDir={currentDir}
      onChangeDir={handleChangeDir}
      messageQueue={messageQueue}
      onRemoveFromQueue={handleRemoveFromQueue}
      onProcessNext={handleProcessNextQueueItem}
      isFloating={true}
    />
    <div className="mt-3 flex items-center gap-3 text-[11px] text-zinc-400 dark:text-zinc-600 font-mono select-none">
      <span>↵ enviar</span>
      <span>·</span>
      <span>⇧↵ nueva línea</span>
    </div>
  </div>
</div>
```

- [ ] **Step 3: Verify build for Task 1**
Run: `npm --prefix kogniterm-desktop/apps/desktop run build`

---

### Task 2: Polish `ChatInput.tsx` with Linear/Cursor Minimalist Surfaces

**Files:**
- Modify: `kogniterm-desktop/apps/desktop/src/components/chat/ChatInput.tsx`

**Interfaces:**
- Consumes: Standard `ChatInputProps`.
- Produces: Crisp, flat input form container without heavy 3D drop-shadows or bulbous capsules.

- [ ] **Step 1: Refine `ChatInput.tsx` container styles**
Update the form container classes in `ChatInput.tsx`:
- Replace heavy shadows and bulbous rounded-2xl with clean `rounded-xl border border-zinc-200/80 dark:border-zinc-800 bg-white/70 dark:bg-zinc-900/70 backdrop-blur-md transition-all`.
- When focused: `focus-within:border-zinc-400 dark:focus-within:border-zinc-600 shadow-xs`.
- Clean minimal submit button: sleek circular/rounded icon button with clean contrast.

- [ ] **Step 2: Verify build for Task 2**
Run: `npm --prefix kogniterm-desktop/apps/desktop run build`

---

### Task 3: Refine Footer Status Bar & Background Patterns

**Files:**
- Modify: `kogniterm-desktop/apps/desktop/src/App.tsx`
- Modify: `kogniterm-desktop/apps/desktop/src/index.css`

**Interfaces:**
- Produces: Unified minimalist status bar and subtle background.

- [ ] **Step 1: Simplify status bar**
In `App.tsx`, polish the bottom status bar:
- Border: `border-t border-zinc-200/40 dark:border-zinc-800/40`.
- Background: `bg-transparent`.
- Typography: subtle muted `text-[11px] text-zinc-400 dark:text-zinc-600 font-mono`.

- [ ] **Step 2: Verify background styling in `index.css`**
Ensure background pattern or base surface has clean neutral `#ffffff` in light mode and `#09090b` in dark mode.

---

### Task 4: Full End-to-End Build and Verification

- [ ] **Step 1: Run TypeScript and Vite build**
Run: `npm --prefix kogniterm-desktop/apps/desktop run build`
Expected: Output with 0 errors.

- [ ] **Step 2: Review git diff for clean, concise changes**
Run: `git diff kogniterm-desktop/apps/desktop/src`
Expected: Clean removal of header, streamlined empty state, minimal floating HUD, polished input.
