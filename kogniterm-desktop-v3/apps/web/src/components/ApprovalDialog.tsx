import { For, Show, createSignal } from "solid-js";
import { approvals, type ApprovalReq, type QuestionReq } from "../lib/approvals";
import { replyApproval, replyQuestion } from "../lib/session";

/** Diálogo de aprobación de herramienta — espejo del InlineApprovalWidget de la TUI.
 *  El agente queda bloqueado hasta responder (el worker espera el evento). */
export function ApprovalDialog(props: { tabId: string }) {
  const pending = () => approvals.forTab(props.tabId);
  const current = () => pending()[0];
  const [busy, setBusy] = createSignal<string | null>(null);

  async function decide(req: ApprovalReq, approved: boolean, always: boolean) {
    if (always && approved) approvals.setAuto(props.tabId, true);
    setBusy(approved ? "yes" : "no");
    try {
      await replyApproval(props.tabId, req.id, approved);
    } finally {
      setBusy(null);
    }
  }

  return (
    <Show when={current()}>
      {(req) => (
        <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div class="w-[520px] max-w-[92vw] max-h-[80vh] overflow-y-auto rounded-lg bg-[#161b22] border border-amber-500/50">
            <div class="px-4 py-3 border-b border-[#21262d] flex items-center gap-2">
              <span class="text-amber-300">⚠</span>
              <span class="text-white text-[14px] font-medium">{req().title}</span>
              <div class="flex-1" />
              <Show when={pending().length > 1}>
                <span class="text-[11px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-200">
                  +{pending().length - 1} pendientes
                </span>
              </Show>
            </div>
            <div class="px-4 py-3 space-y-2">
              <p class="text-[13px] text-[#e6edf3] whitespace-pre-wrap font-mono bg-[#0d1117] border border-[#30363d] rounded-md p-2.5">
                {req().message}
              </p>
              <Show when={req().file_path}>
                <p class="text-[12px] text-[#8b949e]">
                  Archivo: <span class="font-mono text-[#e6edf3]">{req().file_path}</span>
                </p>
              </Show>
              <Show when={req().diff}>
                <details class="text-[12px]">
                  <summary class="cursor-pointer text-[#8b949e] hover:text-white">Ver diff</summary>
                  <pre class="mt-1 max-h-[200px] overflow-auto whitespace-pre-wrap font-mono bg-[#0d1117] border border-[#30363d] rounded-md p-2.5 text-[#e6edf3]">
                    {req().diff}
                  </pre>
                </details>
              </Show>
              <p class="text-[11px] text-[#6e7681]">El agente está en pausa hasta que respondas.</p>
            </div>
            <div class="px-4 py-3 border-t border-[#21262d] flex gap-2 justify-end">
              <button
                disabled={busy() !== null}
                onClick={() => decide(req(), false, false)}
                class="px-4 py-1.5 rounded-md bg-[#21262d] hover:bg-[#30363d] text-white text-[13px] disabled:opacity-50"
              >
                {busy() === "no" ? "Rechazando…" : "Rechazar"}
              </button>
              <button
                disabled={busy() !== null}
                onClick={() => decide(req(), true, true)}
                title="Aceptar esta y auto-aprobar el resto en esta pestaña (como accept_all de la TUI)"
                class="px-4 py-1.5 rounded-md bg-[#1f6feb] hover:bg-[#388bfd] text-white text-[13px] disabled:opacity-50"
              >
                Aceptar siempre
              </button>
              <button
                disabled={busy() !== null}
                onClick={() => decide(req(), true, false)}
                class="px-4 py-1.5 rounded-md bg-[#238636] hover:bg-[#2ea043] text-white text-[13px] font-medium disabled:opacity-50"
              >
                {busy() === "yes" ? "Aceptando…" : "Aceptar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </Show>
  );
}

/** Diálogo de pregunta del agente — espejo de ask_question_sync (opciones + libre). */
export function QuestionDialog(props: { tabId: string }) {
  const pending = () => approvals.questionsFor(props.tabId);
  const current = (): QuestionReq | undefined => pending()[0];
  const [free, setFree] = createSignal("");
  const [busy, setBusy] = createSignal(false);

  async function answer(selected: string) {
    const q = current();
    if (!q || busy()) return;
    setBusy(true);
    try {
      await replyQuestion(props.tabId, q.id, selected);
      setFree("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Show when={current()}>
      {(q) => (
        <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div class="w-[480px] max-w-[92vw] max-h-[80vh] overflow-y-auto rounded-lg bg-[#161b22] border border-[#1f6feb]/50">
            <div class="px-4 py-3 border-b border-[#21262d] flex items-center gap-2">
              <span class="text-[#79c0ff]">?</span>
              <span class="text-white text-[14px] font-medium">{q().title}</span>
              <div class="flex-1" />
              <Show when={pending().length > 1}>
                <span class="text-[11px] px-1.5 py-0.5 rounded bg-[#1f6feb]/20 text-[#79c0ff]">
                  +{pending().length - 1} pendientes
                </span>
              </Show>
            </div>
            <div class="px-4 py-3 space-y-2">
              <p class="text-[13px] text-[#e6edf3] whitespace-pre-wrap">{q().question}</p>
              <div class="flex flex-col gap-1.5">
                <For each={q().options}>
                  {(opt) => (
                    <button
                      disabled={busy()}
                      onClick={() => answer(opt)}
                      class="text-left px-3 py-2 rounded-md bg-[#0d1117] border border-[#30363d] hover:border-[#1f6feb] text-[13px] text-white disabled:opacity-50"
                    >
                      {opt}
                    </button>
                  )}
                </For>
              </div>
              <Show when={q().allow_freeform}>
                <form
                  class="flex gap-2"
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (free().trim()) void answer(free().trim());
                  }}
                >
                  <input
                    value={free()}
                    onInput={(e) => setFree(e.currentTarget.value)}
                    placeholder="O escribe tu propia respuesta…"
                    class="flex-1 bg-[#0d1117] border border-[#30363d] rounded-md px-3 py-2 text-[13px] text-white placeholder-[#6e7681] outline-none focus:border-[#1f6feb]"
                  />
                  <button
                    type="submit"
                    disabled={!free().trim() || busy()}
                    class="px-4 py-2 rounded-md bg-[#238636] text-white text-[13px] disabled:opacity-50"
                  >
                    Enviar
                  </button>
                </form>
              </Show>
            </div>
          </div>
        </div>
      )}
    </Show>
  );
}

/** Insignia con conteo de pendientes (para la topbar). */
export function PendingBadge(props: { tabId: string }) {
  const n = () => approvals.forTab(props.tabId).length + approvals.questionsFor(props.tabId).length;
  return (
    <Show when={n() > 0}>
      <span class="text-[11px] px-1.5 py-0.5 rounded bg-amber-500 text-black font-semibold animate-pulse" title="Aprobaciones/preguntas pendientes">
        {n()} ⏳
      </span>
    </Show>
  );
}
