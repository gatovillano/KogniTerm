import { createStore } from "solid-js/store";
import { api } from "./api";

export type TaskStatus = "pending" | "in_progress" | "done" | "failed";

export interface TaskItem {
  id: string;
  agent?: string;
  text: string;
  status: TaskStatus;
}

export interface TabTasksState {
  tasks: TaskItem[];
  isOpen: boolean;
  updatedAt: number;
}

export function normalizeStatus(raw: any): TaskStatus {
  const s = String(raw ?? "").toLowerCase().trim();
  if (s === "done" || s === "completed" || s === "success") return "done";
  if (s === "in_progress" || s === "in-progress" || s === "running") return "in_progress";
  if (s === "failed" || s === "error" || s === "cancelled") return "failed";
  return "pending";
}

const [state, setState] = createStore<{ byTab: Record<string, TabTasksState> }>({
  byTab: {},
});

export const tasksStore = {
  get state() {
    return state;
  },

  get(tabId: string): TabTasksState {
    return state.byTab[tabId] ?? { tasks: [], isOpen: false, updatedAt: 0 };
  },

  setAgentPlans(tabId: string, agentPlans: Record<string, any[]>) {
    const items: TaskItem[] = [];
    let idx = 0;
    for (const [agentName, list] of Object.entries(agentPlans || {})) {
      if (Array.isArray(list)) {
        list.forEach((t, i) => {
          if (t && typeof t === "object") {
            items.push({
              id: `${agentName}-${i}-${idx++}`,
              agent: agentName,
              text: String(t.task ?? t.content ?? t.description ?? `Tarea ${i + 1}`),
              status: normalizeStatus(t.status),
            });
          }
        });
      }
    }

    const current = state.byTab[tabId];
    // Si entran nuevas tareas y no se había configurado isOpen, abrir automáticamente
    const shouldOpen = current ? current.isOpen : items.length > 0;

    setState("byTab", tabId, {
      tasks: items,
      isOpen: shouldOpen,
      updatedAt: Date.now(),
    });
  },

  setTodos(tabId: string, todos: any[]) {
    const items: TaskItem[] = (todos || []).map((t, i) => ({
      id: String(t.id ?? `todo-${i}`),
      agent: t.agent ? String(t.agent) : undefined,
      text: String(t.content ?? t.task ?? `Tarea ${i + 1}`),
      status: normalizeStatus(t.status),
    }));

    const current = state.byTab[tabId];
    const shouldOpen = current ? current.isOpen : items.length > 0;

    setState("byTab", tabId, {
      tasks: items,
      isOpen: shouldOpen,
      updatedAt: Date.now(),
    });
  },

  toggleOpen(tabId: string) {
    const current = state.byTab[tabId];
    if (!current) return;
    setState("byTab", tabId, "isOpen", !current.isOpen);
  },

  setOpen(tabId: string, open: boolean) {
    if (state.byTab[tabId]) {
      setState("byTab", tabId, "isOpen", open);
    }
  },

  clear(tabId: string) {
    setState("byTab", tabId, {
      tasks: [],
      isOpen: false,
      updatedAt: Date.now(),
    });
  },

  async fetchSessionTodos(tabId: string) {
    const todos = await api.sessionTodos(tabId);
    if (todos && todos.length > 0) {
      this.setTodos(tabId, todos);
    }
  },
};
