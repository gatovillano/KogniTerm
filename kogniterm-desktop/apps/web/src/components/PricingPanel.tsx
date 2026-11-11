import { Show, createSignal, onMount, For } from "solid-js";
import { api, type Plan, type Subscription } from "../lib/api";
import { IconCheck, IconCreditCard, IconRefresh } from "./Icons";

export function PricingPanel() {
  const [plans, setPlans] = createSignal<Plan[]>([]);
  const [subscription, setSubscription] = createSignal<Subscription | null>(null);
  const [loading, setLoading] = createSignal(false);
  const [error, setError] = createSignal<string | null>(null);
  const [checkoutSession, setCheckoutSession] = createSignal<{
    checkout_url: string;
    session_id: string;
    provider: string;
  } | null>(null);
  const [message, setMessage] = createSignal<string | null>(null);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const [p, sub] = await Promise.all([api.listPlans(), api.getSubscription()]);
      setPlans(p);
      setSubscription(sub);
    } catch (e: any) {
      setError(e?.message || "No se pudo cargar la información de planes");
    } finally {
      setLoading(false);
    }
  }

  onMount(() => {
    void loadData();
  });

  async function selectPlan(plan: Plan) {
    setLoading(true);
    setError(null);
    try {
      const result = await api.createCheckout({
        plan_id: plan.id,
        success_url: `${window.location.origin}/pago/exito`,
        cancel_url: `${window.location.origin}/pago/cancelar`,
        customer_email: "",
        provider: "mock",
      });
      setCheckoutSession(result);
      setMessage(`Sesión de checkout creada para ${plan.name}. Redirigiendo al pago…`);
      window.open(result.checkout_url, "_blank");
    } catch (e: any) {
      setError(e?.message || "Error al crear sesión de pago");
    } finally {
      setLoading(false);
    }
  }

  async function completeCheckout() {
    if (!checkoutSession()) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.completeCheckout({
        session_id: checkoutSession()!.session_id,
      });
      setSubscription(result.subscription);
      setCheckoutSession(null);
      setMessage(result.message);
      setTimeout(() => setMessage(null), 5000);
    } catch (e: any) {
      setError(e?.message || "Error al completar el pago");
    } finally {
      setLoading(false);
    }
  }

  async function switchTo(planId: string) {
    setLoading(true);
    setError(null);
    try {
      const result = await api.switchPlan({ plan_id: planId, provider: "mock" });
      setSubscription(result);
      setMessage(`Plan cambiado a ${result.plan_id}`);
      setTimeout(() => setMessage(null), 5000);
    } catch (e: any) {
      setError(e?.message || "Error al cambiar de plan");
    } finally {
      setLoading(false);
    }
  }

  async function cancel() {
    if (!window.confirm("¿Estás seguro de que deseas cancelar tu suscripción actual?")) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.cancelSubscription(true);
      setSubscription(result);
      setMessage("Suscripción cancelada (al final del periodo)");
      setTimeout(() => setMessage(null), 5000);
    } catch (e: any) {
      setError(e?.message || "Error al cancelar suscripción");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div class="space-y-5">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2 text-[12px] text-[var(--kt-text-muted)]">
          <IconCreditCard size={14} />
          <span>Suscripción y cuotas de KogniTerm</span>
        </div>
        <button
          onClick={loadData}
          class="inline-flex items-center gap-1.5 text-[11.5px] px-3 py-1.5 rounded-xl bg-[var(--kt-bg-hover)] hover:bg-[var(--kt-bg-active)] border border-[var(--kt-border-subtle)] text-[var(--kt-text-secondary)] hover:text-[var(--kt-text-primary)] transition-all"
        >
          <IconRefresh size={12} />
          <span>Actualizar</span>
        </button>
      </div>

      <Show when={message()}>
        <div
          class="rounded-xl bg-amber-500/10 border border-amber-500/25 p-3 text-amber-300 text-[12.5px] animate-fade-in"
          role="status"
        >
          {message()}
        </div>
      </Show>

      <Show when={checkoutSession()}>
        <div class="rounded-xl bg-emerald-500/10 border border-emerald-500/25 p-3 flex items-center justify-between gap-3 text-[12.5px]">
          <span class="text-emerald-300">Checkout pendiente de confirmación.</span>
          <button
            onClick={completeCheckout}
            class="px-3 py-1 rounded-full bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-200 font-medium text-[12px]"
          >
            Confirmar pago
          </button>
        </div>
      </Show>

      <Show when={error()}>
        <div class="rounded-xl bg-red-500/10 border border-red-500/25 p-3 text-red-300 text-[12.5px] animate-fade-in">
          {error()}
        </div>
      </Show>

      <Show when={!loading()}>
        <Show when={plans().length > 0}>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <For each={plans()}>
              {(plan) => (
                <PlanCard
                  plan={plan}
                  isCurrent={subscription()?.plan_id === plan.id && subscription()?.status === "active"}
                  onSelect={() => selectPlan(plan)}
                  onSwitch={() => switchTo(plan.id)}
                  disabled={subscription()?.plan_id === plan.id && subscription()?.status === "active"}
                />
              )}
            </For>
          </div>
        </Show>

        <div class="rounded-2xl border border-[var(--kt-border-subtle)] bg-[var(--kt-bg-hover)] p-4">
          <h3 class="text-[13.5px] font-semibold text-[var(--kt-text-primary)] mb-3">Tu Suscripción Actual</h3>
          <Show
            when={subscription()}
            fallback={<p class="text-[12.5px] text-[var(--kt-text-muted)]">No hay suscripción activa.</p>}
          >
            <div class="grid grid-cols-3 gap-4 text-[13px]">
              <div>
                <p class="text-[var(--kt-text-faint)] text-[10.5px] uppercase tracking-wider">Plan</p>
                <p class="text-[var(--kt-text-primary)] font-medium mt-0.5">{subscription()!.plan_id}</p>
              </div>
              <div>
                <p class="text-[var(--kt-text-faint)] text-[10.5px] uppercase tracking-wider">Estado</p>
                <p class={clsx("text-[12.5px] font-medium mt-0.5", statusColor(subscription()!.status))}>
                  {subscription()!.status}
                </p>
              </div>
              <div>
                <p class="text-[var(--kt-text-faint)] text-[10.5px] uppercase tracking-wider">Hasta</p>
                <p class="text-[var(--kt-text-primary)] text-[12px] mt-0.5">
                  {formatDate(subscription()!.current_period_end)}
                </p>
              </div>
              <div class="col-span-3 flex flex-wrap gap-2 pt-2">
                <button
                  disabled={subscription()!.plan_id === "plan_free"}
                  onClick={() => switchTo("plan_pro_monthly")}
                  class="flex-1 px-4 py-2 rounded-xl bg-[var(--kt-bg-active)] hover:bg-[var(--kt-btn-primary-bg)] hover:text-[var(--kt-btn-primary-text)] border border-[var(--kt-border-default)] text-[var(--kt-text-primary)] text-[12px] font-medium disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                >
                  Cambiar a Pro Mensual
                </button>
                <button
                  onClick={cancel}
                  class="flex-1 px-4 py-2 rounded-xl bg-red-500/15 border border-red-500/30 text-red-300 hover:bg-red-500/25 text-[12px] font-medium transition-all"
                >
                  Cancelar Suscripción
                </button>
              </div>
            </div>
          </Show>
        </div>
      </Show>

      <Show when={loading()}>
        <div class="flex items-center justify-center py-10">
          <div class="flex flex-col items-center gap-3">
            <div class="w-7 h-7 border-2 border-[var(--kt-border-default)] border-t-[var(--kt-text-primary)] rounded-full animate-spin" />
            <p class="text-[var(--kt-text-muted)] text-[12px]">Cargando planes y suscripción…</p>
          </div>
        </div>
      </Show>
    </div>
  );
}

function PlanCard(props: {
  plan: Plan;
  isCurrent: boolean;
  onSelect: () => void;
  onSwitch: () => void;
  disabled: boolean;
}) {
  const isPopular = () => props.plan.tier === "pro";

  return (
    <div
      class={clsx(
        "rounded-2xl border p-5 relative flex flex-col transition-all",
        props.isCurrent
          ? "border-emerald-500/45 bg-emerald-500/[0.06]"
          : isPopular()
            ? "border-[var(--kt-border-strong)] bg-[var(--kt-bg-hover)]"
            : "border-[var(--kt-border-subtle)] bg-[var(--kt-bg-hover)]",
      )}
    >
      <Show when={isPopular()}>
        <span class="self-start mb-2 px-2.5 py-0.5 rounded-full bg-[var(--kt-btn-primary-bg)] text-[var(--kt-btn-primary-text)] text-[10px] font-bold uppercase tracking-wider">
          Recomendado
        </span>
      </Show>
      <Show when={props.isCurrent}>
        <span class="absolute top-4 right-4 px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 text-[10.5px] font-medium border border-emerald-500/30">
          Activo
        </span>
      </Show>

      <h3 class="text-[15px] font-bold text-[var(--kt-text-primary)] mb-1">{props.plan.name}</h3>
      <p class="text-[var(--kt-text-muted)] text-[12px] mb-4 line-clamp-2">{props.plan.description}</p>

      <div class="mb-4">
        <span class="text-2xl font-bold text-[var(--kt-text-primary)] tabular-nums">
          {props.plan.price === 0 ? "Gratis" : `$${props.plan.price.toFixed(2)}`}
        </span>
        <span class="text-[var(--kt-text-muted)] text-[12px] ml-1">
          /{props.plan.billing_cycle === "monthly" ? "mes" : "año"}
        </span>
      </div>

      <ul class="flex-1 space-y-2 mb-5">
        <For each={props.plan.features}>
          {(feature) => (
            <li class="flex items-start gap-2 text-[12.5px] text-[var(--kt-text-secondary)]">
              <IconCheck size={13} class="text-emerald-400 shrink-0 mt-0.5" />
              <span>{feature}</span>
            </li>
          )}
        </For>
      </ul>

      <button
        onClick={props.disabled ? () => {} : props.plan.price === 0 ? props.onSwitch : props.onSelect}
        disabled={props.disabled}
        class={clsx(
          "w-full px-4 py-2.5 rounded-xl font-semibold text-[12.5px] transition-all flex items-center justify-center gap-2",
          props.disabled
            ? "bg-[var(--kt-bg-hover)] text-[var(--kt-text-faint)] border border-[var(--kt-border-subtle)] cursor-not-allowed"
            : "bg-[var(--kt-btn-primary-bg)] hover:bg-[var(--kt-btn-primary-hover)] text-[var(--kt-btn-primary-text)] shadow-sm active:scale-[0.98]",
        )}
      >
        {props.disabled
          ? "Plan actual"
          : props.plan.price === 0
            ? "Seleccionar Gratis"
            : `Contratar - $${props.plan.price.toFixed(2)}`}
      </button>
    </div>
  );
}

function statusColor(status: string): string {
  switch (status) {
    case "active":
      return "text-emerald-400";
    case "canceled":
      return "text-red-400";
    case "past_due":
      return "text-amber-400";
    case "trialing":
      return "text-sky-400";
    default:
      return "text-[var(--kt-text-muted)]";
  }
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("es-ES", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

function clsx(...classes: (string | boolean | undefined | null)[]): string {
  return classes.filter(Boolean).join(" ");
}
