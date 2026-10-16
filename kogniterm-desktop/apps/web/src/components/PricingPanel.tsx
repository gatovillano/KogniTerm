import { Show, createSignal, createMemo, onCleanup, For } from "solid-js";
import { api, type Plan, type Subscription } from "../lib/api";

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
      setMessage(
        `Sesión de checkout creada para ${plan.name}. Redirigiendo al pago...`,
      );
      // En modo mock, abrir la URL de checkout en una nueva pestaña
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
      setMessage(`✅ ${result.message}`);
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
      setMessage(`✅ Plan cambiado a ${result.plan_id}`);
      setTimeout(() => setMessage(null), 5000);
    } catch (e: any) {
      setError(e?.message || "Error al cambiar de plan");
    } finally {
      setLoading(false);
    }
  }

  async function cancel() {
    if (
      !window.confirm(
        "¿Estás seguro de que deseas cancelar tu suscripción actual?",
      )
    )
      return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.cancelSubscription(true);
      setSubscription(result);
      setMessage("✅ Suscripción cancelada (al final del periodo)");
      setTimeout(() => setMessage(null), 5000);
    } catch (e: any) {
      setError(e?.message || "Error al cancelar suscripción");
    } finally {
      setLoading(false);
    }
  }

  onCleanup(() => {});

  return (
    <div class="p-6 max-w-5xl mx-auto space-y-6">
      <div class="flex items-center justify-between">
        <h2 class="text-2xl font-bold text-white">💳 Planes y Suscripciones</h2>
        <button
          onClick={loadData}
          class="text-xs px-3 py-1.5 rounded bg-white/10 text-zinc-300 hover:bg-white/20 transition"
        >
          ↻ Actualizar
        </button>
      </div>

      {message() && (
        <div
          class="rounded-lg bg-amber-500/10 border border-amber-500/20 p-3 text-amber-200 text-sm animate-fade-in"
          role="status"
        >
          {message()}
        </div>
      )}

      {error() && (
        <div
          class="rounded-lg bg-red-500/10 border border-red-500/20 p-3 text-red-200 text-sm animate-fade-in"
        >
          {error()}
        </div>
      )}

      <Show when={!loading()}>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <For each={plans()}>
            {(plan) => (
              <PlanCard
                plan={plan}
                isCurrent={
                  subscription()?.plan_id === plan.id &&
                  subscription()?.status === "active"
                }
                onSelect={() => selectPlan(plan)}
                onSwitch={() => switchTo(plan.id)}
                disabled={
                  subscription()?.plan_id === plan.id &&
                  subscription()?.status === "active"
                }
              />
            )}
          </For>
        </div>

        <div class="mt-8 rounded-xl border border-white/10 bg-black/40 p-6">
          <h3 class="text-lg font-semibold mb-4">Tu Suscripción Actual</h3>
          <Show when={subscription()}>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
              <div>
                <p class="text-zinc-400 text-xs uppercase tracking-wider">Plan</p>
                <p class="text-white font-medium">{subscription()!.plan_id}</p>
              </div>
              <div>
                <p class="text-zinc-400 text-xs uppercase tracking-wider">Estado</p>
                <p class={clsx("text-xs font-medium", statusColor(subscription()!.status))}>
                  {subscription()!.status}
                </p>
              </div>
              <div>
                <p class="text-zinc-400 text-xs uppercase tracking-wider">Hasta</p>
                <p class="text-white text-xs">{formatDate(subscription()!.current_period_end)}</p>
              </div>
              <div class="md:col-span-3 flex gap-3">
                <button
                  disabled={subscription()!.plan_id === "plan_free"}
                  onClick={() => switchTo("plan_pro_monthly")}
                  class="flex-1 px-4 py-2 rounded bg-blue-600/20 border border-blue-500/40 text-blue-300 hover:bg-blue-600/40 disabled:opacity-50 disabled:cursor-not-allowed transition"
                >
                  Cambiar a Pro Mensual
                </button>
                <button
                  onClick={cancel}
                  class="flex-1 px-4 py-2 rounded bg-red-600/20 border border-red-500/40 text-red-300 hover:bg-red-600/40 transition"
                >
                  Cancelar Suscripción
                </button>
              </div>
            </div>
          </Show>
          <Show when={!subscription()}>
            <p class="text-zinc-400">No hay suscripción activa.</p>
          </Show>
        </div>

        <div class="mt-8 rounded-xl border border-white/10 bg-black/40 p-6">
          <h3 class="text-lg font-semibold mb-4">Métodos de Pago e Historial</h3>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <p class="text-zinc-400 text-xs uppercase tracking-wider mb-2">Métodos de Pago</p>
              <p class="text-zinc-400 text-sm">Cargando métodos...</p>
            </div>
            <div>
              <p class="text-zinc-400 text-xs uppercase tracking-wider mb-2">Historial</p>
              <p class="text-zinc-400 text-sm">Cargando historial...</p>
            </div>
          </div>
        </div>

        <div class="mt-8 rounded-xl border border-white/10 bg-black/40 p-6">
          <h3 class="text-lg font-semibold mb-4">Cuota de Uso</h3>
          <p class="text-zinc-400 text-sm">Consulta tu uso de tokens y sesiones en tiempo real.</p>
        </div>
      </Show>

      {loading() && (
        <div class="flex items-center justify-center py-10">
          <div class="flex flex-col items-center gap-3">
            <div class="w-8 h-8 border-4 border-blue-500/30 border-t-blue-500 rounded-full animate-spin"></div>
            <p class="text-zinc-400 text-xs">Cargando planes y suscripción...</p>
          </div>
        </div>
      )}
    </div>
  );
}

function PlanCard({
  plan,
  isCurrent,
  onSelect,
  onSwitch,
  disabled,
}: {
  plan: Plan;
  isCurrent: boolean;
  onSelect: () => void;
  onSwitch: () => void;
  disabled: boolean;
}) {
  const isPopular = plan.tier === "pro";
  const priceDisplay = plan.price === 0 ? "Gratis" : `$${plan.price.toFixed(2)}/${plan.billing_cycle}`;

  return (
    <div
      class={clsx(
        "rounded-xl border p-6 relative flex flex-col min-h-[500px] transition hover:border-white/20",
        isCurrent
          ? "border-blue-500 bg-blue-500/10 shadow-[0_0_20px_rgba(59,130,246,0.15)]"
          : "border-white/10 bg-white/[0.03]",
        isPopular ? "ring-1 ring-blue-500/30" : "",
      )}
    >
      {isPopular && (
        <div class="absolute -top-3 left-1/2 -translate-x-1/2">
          <span class="px-3 py-1 rounded-full bg-blue-600 text-blue-100 text-xs font-bold uppercase tracking-wider">
            Popular
          </span>
        </div>
      )}
      {isCurrent && (
        <div class="absolute top-4 right-4">
          <span class="px-2 py-1 rounded bg-green-600/20 text-green-300 text-xs border border-green-600/40">
            Activo
          </span>
        </div>
      )}
      <h3 class="text-lg font-bold text-white mb-1">{plan.name}</h3>
      <p class="text-zinc-400 text-sm mb-4 line-clamp-2">{plan.description}</p>

      <div class="mb-6">
        <span class="text-3xl font-bold text-white">{plan.price === 0 ? "Gratis" : `$${plan.price.toFixed(2)}`}</span>
        <span class="text-zinc-400 text-sm ml-1">/{plan.billing_cycle === "monthly" ? "mes" : "año"}</span>
      </div>

      <ul class="flex-1 space-y-3 mb-6">
        <For each={plan.features}>
          {(feature) => (
            <li class="flex items-start gap-2 text-sm text-zinc-300">
              <span class="text-green-400">✓</span>
              <span>{feature}</span>
            </li>
          )}
        </For>
      </ul>

      <button
        onClick={disabled ? () => {} : plan.price === 0 ? onSwitch : onSelect}
        disabled={disabled}
        class={clsx(
          "w-full px-4 py-3 rounded-lg font-semibold transition flex items-center justify-center gap-2",
          disabled
            ? "bg-white/[0.05] text-zinc-500 border border-white/10 cursor-not-allowed"
            : plan.price === 0
              ? "bg-green-600/20 border border-green-500/40 text-green-300 hover:bg-green-600/40"
              : "bg-blue-600/20 border border-blue-500/40 text-blue-300 hover:bg-blue-600/40",
        )}
      >
        {disabled ? "Plan actual" : plan.price === 0 ? "Seleccionar Gratis" : `Contratar - $${plan.price.toFixed(2)}`}
      </button>
    </div>
  );
}

function statusColor(status: string): string {
  switch (status) {
    case "active":
      return "text-green-400";
    case "canceled":
      return "text-red-400";
    case "past_due":
      return "text-amber-400";
    case "trialing":
      return "text-blue-400";
    default:
      return "text-zinc-400";
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

// clsx helper inline
function clsx(...classes: (string | boolean | undefined | null)[]): string {
  return classes.filter(Boolean).join(" ");
}
