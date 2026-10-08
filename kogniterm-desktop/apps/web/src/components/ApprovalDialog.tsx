import { For, Show, createSignal } from "solid-js";
import { approvals, type ApprovalReq, type QuestionReq } from "../lib/approvals";
import { replyApproval, replyQuestion, setAutoApprove } from "../lib/session";

/** Diálogo de aprobación de herramienta — diseño modal moderno con cristal y botones curvos. */
export function ApprovalDialog(props: { tabId: string }) {
  const pending = () => approvals.forTab(props.tabId);
  const current = () => pending()[0];
  const [busy, setBusy] = createSignal<string | null>(null);

  async function decide(req: ApprovalReq, approved: boolean, always: boolean) {
    // "Aceptar siempre" debe propagarse al backend: si no, el siguiente comando
    // llega ya auto-aprobado por la config global y el usuario nunca ve el diálogo.
    if (always && approved) setAutoApprove(props.tabId, true);
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
        <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xl animate-fade-in p-4">
          <div class="w-[520px] max-w-[92vw] max-h-[85vh] overflow-y-auto rounded-3xl glass-modal p-6 animate-scale-in select-none">
            {/* Cabecera */}
            <div class="flex items-center gap-3 mb-4">
              <span class="w-8 h-8 rounded-full bg-amber-500/20 text-amber-300 flex items-center justify-center font-bold text-[15px] shadow-[0_0_12px_rgba(245,158,11,0.3)]">
                ⚠
              </span>
              <span class="text-white text-[16px] font-semibold tracking-tight">{req().title}</span>
              <div class="flex-1" />
              <Show when={pending().length > 1}>
                <span class="text-[11px] font-mono px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300">
                  +{pending().length - 1} pendientes
                </span>
              </Show>
            </div>

            {/* Contenido */}
            <div class="space-y-3 mb-6 select-text">
              <p class="text-[13px] text-slate-200 whitespace-pre-wrap font-mono bg-black/40 rounded-2xl p-3.5 leading-relaxed">
                {req().message}
              </p>
              <Show when={req().file_path}>
                <p class="text-[12px] text-slate-400 px-1">
                  Archivo: <span class="font-mono text-slate-200">{req().file_path}</span>
                </p>
              </Show>
              <Show when={req().diff}>
                <details class="text-[12px]">
                  <summary class="cursor-pointer text-slate-400 hover:text-white px-1 font-medium transition-colors">
                    Ver diff del cambio
                  </summary>
                  <pre class="mt-2 max-h-[220px] overflow-auto whitespace-pre-wrap font-mono bg-black/50 rounded-2xl p-3.5 text-slate-200 text-[11.5px] leading-relaxed">
                    {req().diff}
                  </pre>
                </details>
              </Show>
              <p class="text-[11.5px] text-slate-400 px-1">
                La ejecución está en pausa esperando tu confirmación.
              </p>
            </div>

            {/* Botones curvos de acción */}
            <div class="flex flex-wrap gap-2 justify-end">
              <button
                disabled={busy() !== null}
                onClick={() => decide(req(), false, false)}
                class="px-5 py-2 rounded-full bg-white/[0.08] hover:bg-white/[0.14] text-zinc-200 hover:text-white text-[13px] font-medium transition-all active:scale-95 disabled:opacity-50"
              >
                {busy() === "no" ? "Rechazando…" : "Rechazar"}
              </button>
              <button
                disabled={busy() !== null}
                onClick={() => decide(req(), true, true)}
                title="Aceptar esta y auto-aprobar el resto en esta pestaña (como accept_all de la TUI)"
                class="px-5 py-2 rounded-full bg-white/[0.12] hover:bg-white/[0.18] text-zinc-100 hover:text-white text-[13px] font-medium transition-all active:scale-95 disabled:opacity-50 border border-white/[0.08]"
              >
                Aceptar siempre
              </button>
              <button
                disabled={busy() !== null}
                onClick={() => decide(req(), true, false)}
                class="px-6 py-2 rounded-full bg-zinc-800 hover:bg-zinc-700 text-white text-[13px] font-semibold shadow-sm border border-white/[0.08] transition-all active:scale-95 disabled:opacity-50"
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

/** Diálogo de pregunta del agente — modal estilizado con selección de opciones. */
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
        <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xl animate-fade-in p-4">
          <div class="w-[500px] max-w-[92vw] max-h-[85vh] overflow-y-auto rounded-3xl glass-modal p-6 animate-scale-in select-none">
            {/* Cabecera */}
            <div class="flex items-center gap-3 mb-4">
              <span class="w-8 h-8 rounded-full bg-white/[0.1] text-zinc-200 flex items-center justify-center font-bold text-[15px] shadow-sm">
                ?
              </span>
              <span class="text-white text-[16px] font-semibold tracking-tight">{q().title}</span>
              <div class="flex-1" />
              <Show when={pending().length > 1}>
                <span class="text-[11px] font-mono px-2.5 py-0.5 rounded-full bg-white/[0.08] text-zinc-300">
                  +{pending().length - 1} pendientes
                </span>
              </Show>
            </div>

            {/* Contenido */}
            <div class="space-y-4 mb-4 select-text">
              <p class="text-[13.5px] text-zinc-200 leading-relaxed">{q().question}</p>
              
              <div class="flex flex-col gap-2">
                <For each={q().options}>
                  {(opt) => (
                    <button
                      disabled={busy()}
                      onClick={() => answer(opt)}
                      class="text-left px-4 py-2.5 rounded-2xl bg-white/[0.04] hover:bg-white/[0.1] hover:text-white text-[13px] text-zinc-200 transition-all duration-150 active:scale-[0.98] disabled:opacity-50 border border-transparent hover:border-white/[0.08]"
                    >
                      {opt}
                    </button>
                  )}
                </For>
              </div>

              <Show when={q().allow_freeform}>
                <form
                  class="flex gap-2 mt-3"
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (free().trim()) void answer(free().trim());
                  }}
                >
                  <input
                    value={free()}
                    onInput={(e) => setFree(e.currentTarget.value)}
                    placeholder="O escribe tu respuesta personalizada…"
                    class="flex-1 bg-white/[0.05] focus:bg-white/[0.08] focus:ring-2 focus:ring-white/20 border border-white/[0.08] rounded-full px-4 py-2 text-[13px] text-white placeholder-zinc-500 outline-none transition-all"
                  />
                  <button
                    type="submit"
                    disabled={!free().trim() || busy()}
                    class="px-5 py-2 rounded-full bg-zinc-800 hover:bg-zinc-700 text-zinc-100 text-[13px] font-medium shadow-sm border border-white/[0.08] transition-all active:scale-95 disabled:opacity-40"
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
      <span
        class="text-[11px] px-2.5 py-0.5 rounded-full bg-gradient-to-r from-amber-500 to-orange-500 text-black font-bold animate-pulse shadow-[0_0_10px_rgba(245,158,11,0.5)]"
        title="Aprobaciones/preguntas pendientes"
      >
        {n()} ⏳
      </span>
    </Show>
  );
}
