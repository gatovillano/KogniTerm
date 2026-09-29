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
    return state.autoApprove[tabId] === true;
  },
  setAuto(tabId: string, v: boolean) {
    setState("autoApprove", tabId, v);
  },
};
