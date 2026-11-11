import { Show, createSignal } from "solid-js";
import { approvals, type PasswordReq } from "../lib/approvals";
import { replyPassword } from "../lib/session";
import { IconLock } from "./Icons";

/** Diálogo de solicitud de contraseña seguro. */
export function PasswordDialog(props: { tabId: string }) {
  const pending = () => approvals.forTabPasswords(props.tabId);
  const current = (): PasswordReq | undefined => pending()[0];
  const [value, setValue] = createSignal("");
  const [busy, setBusy] = createSignal(false);

  async function submit(pwd: string) {
    const req = current();
    if (!req || busy()) return;
    setBusy(true);
    try {
      await replyPassword(props.tabId, req.id, pwd);
      setValue("");
    } finally {
      setBusy(false);
    }
  }

  function cancel() {
    const req = current();
    if (!req || busy()) return;
    setBusy(true);
    void replyPassword(props.tabId, req.id, "");
    setValue("");
    setBusy(false);
  }

  return (
    <Show when={current()}>
      {(req) => (
        <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-xl animate-fade-in p-4">
          <div class="w-[520px] max-w-[92vw] max-h-[85vh] overflow-y-auto rounded-3xl glass-modal p-6 animate-scale-in select-none">
            <div class="flex items-center gap-3 mb-4">
              <span class="w-9 h-9 rounded-2xl bg-violet-500/15 border border-violet-500/30 text-violet-300 flex items-center justify-center shrink-0">
                <IconLock size={17} />
              </span>
              <span class="text-[var(--kt-text-primary)] text-[16px] font-semibold tracking-tight">{req().title}</span>
              <div class="flex-1" />
              <Show when={pending().length > 1}>
                <span class="text-[11px] font-mono px-2.5 py-0.5 rounded-full bg-violet-500/20 text-violet-300">
                  +{pending().length - 1} pendientes
                </span>
              </Show>
            </div>

            <div class="space-y-3 mb-6 select-text">
              <p class="text-[13px] text-[var(--kt-text-primary)] whitespace-pre-wrap font-mono bg-[var(--kt-bg-app)] border border-[var(--kt-border-subtle)] rounded-2xl p-3.5 leading-relaxed">
                {req().message}
              </p>
              <p class="text-[11.5px] text-[var(--kt-text-muted)] px-1">
                La ejecución está en pausa esperando tu contraseña. No quedará registrada en el historial.
              </p>

              <div class="mt-3">
                <input
                  type="password"
                  value={value()}
                  onInput={(e) => setValue(e.currentTarget.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && value().trim()) {
                      e.preventDefault();
                      void submit(value());
                    }
                  }}
                  placeholder={req().placeholder || "••••••••"}
                  disabled={busy()}
                  class="w-full bg-[var(--kt-bg-hover)] focus:bg-[var(--kt-bg-input)] border border-[var(--kt-border-default)] focus:border-violet-400 rounded-2xl px-4 py-3 text-[var(--kt-text-primary)] placeholder-[var(--kt-text-faint)] focus:outline-none focus:ring-2 focus:ring-violet-500/35 transition-all text-[14px] font-mono disabled:opacity-60"
                  autocomplete="off"
                  autocapitalize="none"
                  spellcheck={false}
                />
              </div>
            </div>

            <div class="flex flex-wrap gap-2 justify-end">
              <button
                disabled={busy()}
                onClick={() => cancel()}
                class="px-5 py-2 rounded-full bg-[var(--kt-bg-hover)] hover:bg-[var(--kt-bg-active)] border border-[var(--kt-border-subtle)] text-[var(--kt-text-secondary)] hover:text-[var(--kt-text-primary)] text-[13px] font-medium transition-all active:scale-95 disabled:opacity-50"
              >
                {busy() ? "Procesando…" : "Cancelar"}
              </button>
              <button
                disabled={busy() || !value().trim()}
                onClick={() => submit(value())}
                class="px-6 py-2 rounded-full bg-violet-600 hover:bg-violet-500 text-white text-[13px] font-semibold shadow-[0_0_16px_rgba(139,92,246,0.35)] border border-violet-400/40 transition-all active:scale-95 disabled:opacity-50 disabled:pointer-events-none"
              >
                {busy() ? "Enviando…" : "Desbloquear"}
              </button>
            </div>
          </div>
        </div>
      )}
    </Show>
  );
}
