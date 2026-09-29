import React, { useEffect, useState } from 'react';

interface Plan {
  id: string;
  name: string;
  tier: string;
  price_cents: number;
  currency: string;
  interval: string;
  credits_included: number;
  features: string[];
}

interface UserSubscription {
  user_id: string;
  tier: string;
  plan_id: string;
  credits_remaining: number;
  active: boolean;
  expires_at?: number;
}

export const PricingModal: React.FC<{ isOpen: boolean; onClose: () => void; userId?: string }> = ({
  isOpen,
  onClose,
  userId = 'default_user'
}) => {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [subscription, setSubscription] = useState<UserSubscription | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [processingPlan, setProcessingPlan] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      fetchPlans();
      fetchSubscription();
    }
  }, [isOpen]);

  const fetchPlans = async () => {
    try {
      const res = await fetch('/api/payments/plans');
      if (res.ok) {
        const data = await res.json();
        setPlans(data);
      }
    } catch (e) {
      console.error('Error fetching plans:', e);
    }
  };

  const fetchSubscription = async () => {
    try {
      const res = await fetch(`/api/payments/subscription/${userId}`);
      if (res.ok) {
        const data = await res.json();
        setSubscription(data);
      }
    } catch (e) {
      console.error('Error fetching subscription:', e);
    }
  };

  const handleSelectPlan = async (planId: string) => {
    setProcessingPlan(planId);
    try {
      const res = await fetch('/api/payments/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, plan_id: planId, provider: 'mock' })
      });
      const data = await res.json();
      if (res.ok && data.transaction_id) {
        // En modo MOCK, auto-completar el pago de prueba
        const completeRes = await fetch('/api/payments/mock-checkout/complete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ transaction_id: data.transaction_id })
        });
        const completeData = await completeRes.json();
        if (completeRes.ok && completeData.subscription) {
          setSubscription(completeData.subscription);
          alert(`🎉 ¡Suscripción actualizada exitosamente al plan ${planId}!`);
        }
      } else {
        alert(data.detail || 'Error al iniciar checkout.');
      }
    } catch (e) {
      console.error('Error processing checkout:', e);
      alert('Error de conexión al procesar el pago.');
    } finally {
      setProcessingPlan(null);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-slate-900 border border-slate-700 text-slate-100 rounded-xl shadow-2xl max-w-4xl w-full p-6 relative overflow-hidden">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-slate-200 text-xl font-bold"
        >
          ✕
        </button>

        <div className="text-center mb-6">
          <h2 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-500">
            Planes y Créditos KogniTerm
          </h2>
          <p className="text-slate-400 text-sm mt-1">
            Elige el plan ideal para potenciar tus agentes y automatizaciones CLI & Web.
          </p>
          {subscription && (
            <div className="inline-block mt-3 px-4 py-1.5 bg-slate-800 border border-cyan-500/30 rounded-full text-xs text-cyan-300">
              Suscripción Actual: <span className="font-semibold uppercase">{subscription.tier}</span> | 
              Créditos Disponibles: <span className="font-semibold text-white">{subscription.credits_remaining}</span>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {plans.map((plan) => {
            const isCurrent = subscription?.plan_id === plan.id;
            return (
              <div
                key={plan.id}
                className={`flex flex-col justify-between p-5 rounded-lg border bg-slate-800/60 transition-all ${
                  isCurrent ? 'border-cyan-500 ring-2 ring-cyan-500/20' : 'border-slate-700 hover:border-slate-500'
                }`}
              >
                <div>
                  <h3 className="text-lg font-bold text-white">{plan.name}</h3>
                  <div className="my-3">
                    <span className="text-3xl font-extrabold text-white">
                      ${(plan.price_cents / 100).toFixed(2)}
                    </span>
                    <span className="text-slate-400 text-xs"> /{plan.interval}</span>
                  </div>
                  <p className="text-xs text-cyan-400 font-medium mb-4">
                    ⚡ {plan.credits_included.toLocaleString()} Créditos de IA incluidos
                  </p>
                  <ul className="space-y-2 text-xs text-slate-300">
                    {plan.features.map((feat, idx) => (
                      <li key={idx} className="flex items-center gap-2">
                        <span className="text-emerald-400">✓</span> {feat}
                      </li>
                    ))}
                  </ul>
                </div>

                <button
                  disabled={isCurrent || processingPlan === plan.id}
                  onClick={() => handleSelectPlan(plan.id)}
                  className={`mt-6 w-full py-2 px-4 rounded-md text-xs font-semibold transition-all ${
                    isCurrent
                      ? 'bg-slate-700 text-slate-400 cursor-not-allowed'
                      : 'bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white shadow-lg'
                  }`}
                >
                  {isCurrent
                    ? 'Plan Actual'
                    : processingPlan === plan.id
                    ? 'Procesando...'
                    : `Seleccionar ${plan.name}`}
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
