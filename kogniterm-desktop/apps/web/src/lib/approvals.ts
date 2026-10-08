import { createStore } from "solid-js/store";

export interface ApprovalReq {
  id: string;
  tabId: string;
  title: string;
  message: string;
  diff: string;
  file_path: string;
}

export interface QuestionReq {
  id: string;
  tabId: string;
  title: string;
  question: string;
  options: string[];
  allow_freeform: boolean;
}

const [state, setState] = createStore<{
  approvals: ApprovalReq[];
  questions: QuestionReq[];
  /** auto-aprobación en memoria por pestaña (equivale a "accept_all" de la TUI) */
  autoApprove: Record<string, boolean>;
}>({ approvals: [], questions: [], autoApprove: {} });

const STORAGE_KEY = "kogniterm_auto_approve";

function getSavedAuto(): boolean | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw !== null ? JSON.parse(raw) === true : null;
  } catch {
    return null;
  }
}

function saveAuto(v: boolean): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(v));
  } catch {
    /* ignore */
  }
}

export const approvals = {
  get state() {
    return state;
  },
  forTab(tabId: string): ApprovalReq[] {
    return state.approvals.filter((a) => a.tabId === tabId);
  },
  questionsFor(tabId: string): QuestionReq[] {
    return state.questions.filter((q) => q.tabId === tabId);
  },
  pushApproval(a: ApprovalReq) {
    if (!state.approvals.some((x) => x.id === a.id)) {
      setState("approvals", (list) => [...list, a]);
    }
  },
  resolveApproval(id: string) {
    setState("approvals", (list) => list.filter((x) => x.id !== id));
  },
  pushQuestion(q: QuestionReq) {
    if (!state.questions.some((x) => x.id === q.id)) {
      setState("questions", (list) => [...list, q]);
    }
  },
  resolveQuestion(id: string) {
    setState("questions", (list) => list.filter((x) => x.id !== id));
  },
  isAuto(tabId: string): boolean {
    if (typeof state.autoApprove[tabId] === "boolean") {
      return state.autoApprove[tabId];
    }
    const saved = getSavedAuto();
    if (saved !== null) {
      return saved;
    }
    return false;
  },
  setAuto(tabId: string, v: boolean) {
    setState("autoApprove", tabId, v);
    saveAuto(v);
  },
  /**
   * Aplica el valor real que envía el backend en `connected` (config global/proyecto).
   * Si el usuario ya tiene una preferencia persistida en localStorage, se respeta la del usuario.
   */
  seedAuto(tabId: string, v: boolean) {
    const saved = getSavedAuto();
    if (saved !== null) {
      setState("autoApprove", tabId, saved);
    } else if (state.autoApprove[tabId] === undefined) {
      setState("autoApprove", tabId, v);
    }
  },
};
