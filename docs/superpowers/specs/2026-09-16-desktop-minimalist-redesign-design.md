# Desktop Minimalist Redesign (Linear / Cursor Aesthetic)

**Date**: 2026-09-16  
**Status**: Approved  
**Target Application**: KogniTerm Desktop (`kogniterm-desktop/apps/desktop`)

---

## 1. Overview & Objectives

Transform the KogniTerm Desktop UI from its current colorful, pill-heavy layout into a sleek, monochromatic, technical minimalist interface inspired by **Linear**, **Raycast**, and **Cursor**.

### Key Principles:
- **Zero-Chrome Header**: Remove the heavy top `<header>` bar entirely to give 100% vertical space and visual focus to the workspace and conversation.
- **Distraction-Free Empty State**: Eliminate the oversized 7xl digital clock, greeting banners, and suggestion cards. The centered prompt input becomes the pure focal point.
- **Subtle Floating HUD (Top-Right)**: Float essential quick-actions (Auto-approval toggle, current directory switcher, and right panel toggle) in the top-right corner with low resting opacity (`opacity-30`) that softly intensifies on hover (`opacity-100`).
- **Crisp Monochromatic Surfaces**: Replace heavy rounded pills and colorful badges with flat surfaces, ultra-fine 1px borders (`border-zinc-200/60` / `border-zinc-800/60`), and subtle typography.

---

## 2. UI Component Changes

### 2.1 Complete Removal of `<header>` in `App.tsx`
- Remove the fixed `h-14` header bar with its colorful pills ("Ubicación actual", "Claro/Oscuro", "Auto-aprobación ON/OFF", and green glowing "kogniterm" badge).
- Window drag / top region remains clean and unobstructed.

### 2.2 Top-Right Floating Controls (Micro-HUD)
- Absolute positioned container at `top-3 right-4 z-30 flex items-center gap-1.5`.
- Actions:
  - **Auto-Approve Toggle**: Discrete ghost button with a small icon (Zap/Shield). When active, a subtle 1.5px amber/emerald indicator dot or accent glyph shows without a heavy colored badge.
  - **Workspace Directory Picker**: Minimalist mono breadcrumb button showing the current folder name (e.g., `~/Gemini-Interpreter`), opening the change-directory dialog.
  - **Right Panel Toggle**: Ghost icon button (`PanelRightOpen` / `PanelRightClose`) to smoothly collapse/expand the Tasks & Terminal sidebar.
- Resting state: `text-zinc-400 dark:text-zinc-500 opacity-40 hover:opacity-100 transition-all duration-150`.

### 2.3 Empty State Refactoring
- When `messages.length === 0`:
  - Centered layout without the 7xl clock widget and greeting banner.
  - Floating centered `ChatInput` with sleek border and minimal keyboard shortcut guide below: `↵ to send · ⇧↵ for newline`.
  - Remove the 2 bulky suggestion action cards ("Analizar código", "Guía de despliegue").

### 2.4 Chat Input & Message Area Polishing
- In `ChatInput.tsx`:
  - Flatten input container: replace bulky shadows with clean `border border-zinc-200/80 dark:border-zinc-800 bg-white/80 dark:bg-zinc-900/80 backdrop-blur-md`.
  - Subtle send button styling matching Cursor/Linear.
- In `App.tsx` active chat mode:
  - Ensure the bottom pinned chat input matches the same minimalist aesthetic with seamless transition when messages are present.
  - Simplify bottom status bar to subtle 11px monospace metrics.

---

## 3. Data Flow & State Management

All state interactions remain intact:
- `autoApprove`: Toggled via the floating HUD button and persisted via `/api/config/set`.
- `isRightSidebarOpen`: Controlled via the floating panel button.
- `currentDir`: Changed via the directory button in the floating HUD.
- `theme`: Managed in the left sidebar footer as already implemented.

---

## 4. Verification Plan

### Automated Checks
- Run TypeScript type checks and build: `npm run build` in `kogniterm-desktop/apps/desktop`.

### Manual / Visual Verification
1. Verify the top header is completely removed and the conversation area starts cleanly at the top.
2. Verify empty state displays only the centered minimalist prompt bar with no giant clock or cards.
3. Verify top-right floating HUD buttons are discrete, appear on hover, and properly toggle auto-approval and right panel.
4. Verify sending a message transitions smoothly to the active chat view with bottom input.
5. Verify both dark mode and light mode render crisp borders and monochromatic tones.
