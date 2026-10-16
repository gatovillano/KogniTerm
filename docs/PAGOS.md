# 💳 Sistema de Pagos y Suscripciones — KogniTerm

Documentación completa del módulo de pagos integrado en el backend FastAPI de KogniTerm.

---

## 📋 Resumen

El sistema de pagos permite gestionar planes de suscripción, crear sesiones de checkout, procesar webhooks de pasarelas de pago (Stripe y MercadoPago), cancelar suscripciones, consultar métodos de pago, historial de facturación y cuotas de uso.

Está expuesto bajo el prefijo **`/api/payments`** en el servidor FastAPI.

---

## 🏗 Arquitectura

```
kogniterm/server/payments/
├── __init__.py      # Exporta router y servicio
├── models.py        # Modelos Pydantic (planes, suscripciones, checkout, etc.)
├── router.py        # Endpoints REST de FastAPI
└── service.py       # Lógica de negocio e integración con pasarelas
```

---

## 📦 Modelos de Datos

### Planes (`PlanInfo`)
| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | str | ID único del plan |
| `name` | str | Nombre legible |
| `tier` | PlanTier | free / pro / enterprise |
| `price` | float | Precio en USD |
| `currency` | str | Moneda (default: usd) |
| `billing_cycle` | BillingCycle | monthly / yearly |
| `features` | List[str] | Características del plan |
| `token_limit_per_month` | int | Límite de tokens mensual |
| `max_sessions` | int | Sesiones concurrentes máximas |
| `custom_models_allowed` | bool | Modelos personalizados permitidos |

### Suscripción (`SubscriptionDetails`)
| Campo | Tipo | Descripción |
|-------|------|-------------|
| `user_id` | str | ID del usuario |
| `plan_id` | str | ID del plan suscrito |
| `status` | SubscriptionStatus | active / canceled / past_due / incomplete / trialing |
| `current_period_start` | str | Inicio del periodo (ISO 8601) |
| `current_period_end` | str | Fin del periodo (ISO 8601) |
| `stripe_customer_id` | str | ID de cliente en Stripe |
| `stripe_subscription_id` | str | ID de suscripción en Stripe |

### Otros modelos
- `CreateCheckoutSessionRequest` / `Response`
- `CompleteCheckoutRequest` / `Response`
- `SwitchPlanRequest`
- `PaymentMethodDetails`
- `PaymentHistoryItem`
- `UsageQuotaInfo`

---

## 🔌 Endpoints REST

Todos bajo `POST /api/payments/...` o `GET /api/payments/...`

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/plans` | Lista todos los planes disponibles |
| `GET` | `/plans/{plan_id}` | Detalle de un plan específico |
| `GET` | `/subscription` | Suscripción activa del usuario |
| `POST` | `/checkout` | Crea sesión de checkout (Stripe/MercadoPago/Mock) |
| `POST` | `/checkout/complete` | Completa una sesión de checkout (mock) |
| `POST` | `/subscription/switch` | Cambia el plan del usuario |
| `POST` | `/subscription/cancel` | Cancela la suscripción |
| `GET` | `/payment-methods` | Lista métodos de pago del usuario |
| `GET` | `/history` | Historial de facturación |
| `GET` | `/quota` | Cuota de uso (tokens, sesiones) |
| `POST` | `/webhook` | Webhook de Stripe |

---

## 💳 Planes Predefinidos

| Plan | Precio | Ciclo | Tokens/mes | Sesiones | Modelos personalizados |
|------|--------|-------|------------|----------|------------------------|
| **Free** | $0.00 | monthly | 100,000 | 2 | No |
| **Pro Monthly** | $19.99 | monthly | 5,000,000 | 10 | Sí |
| **Pro Yearly** | $199.99 | yearly | 5,000,000 | 10 | Sí |
| **Enterprise** | $99.99 | monthly | 100,000,000 | 100 | Sí |

---

## 🔧 Integración con Pasarelas

### Stripe
Configurar variables de entorno:
```bash
export STRIPE_SECRET_KEY=sk_test_...
export STRIPE_WEBHOOK_SECRET=whsec_...
```

El servicio crea sesiones de checkout de Stripe y procesa webhooks:
- `checkout.session.completed` → activa la suscripción
- `customer.subscription.deleted` → cancela la suscripción

### MercadoPago
```bash
export MERCADOPAGO_ACCESS_TOKEN=TEST-...
```

### Modo Mock (desarrollo)
Si no se configura ninguna pasarela, el sistema funciona en modo simulación:
- Los pagos se procesan inmediatamente
- No se requieren credenciales reales
- Útil para desarrollo y pruebas

---

## 🧪 Ejemplo de Uso

### Obtener planes
```bash
curl http://localhost:8755/api/payments/plans
```

### Crear sesión de checkout (mock)
```bash
curl -X POST http://localhost:8755/api/payments/checkout \
  -H "Content-Type: application/json" \
  -H "X-User-ID: user_123" \
  -d '{
    "plan_id": "plan_pro_monthly",
    "success_url": "https://miapp.com/success",
    "cancel_url": "https://miapp.com/cancel",
    "customer_email": "usuario@ejemplo.com"
  }'
```

### Obtener suscripción
```bash
curl http://localhost:8755/api/payments/subscription \
  -H "X-User-ID: user_123"
```

### Cancelar suscripción
```bash
curl -X POST "http://localhost:8755/api/payments/subscription/cancel?at_period_end=true" \
  -H "X-User-ID: user_123"
```

---

## 🧪 Pruebas

Ejecutar pruebas unitarias:
```bash
cd /home/gato/KogniTerm
PYTHONPATH=. python3 -m pytest tests/server/test_payments.py -v
```

Las pruebas cubren:
- Listado y detalle de planes
- Suscripción por defecto (Free)
- Activación de planes de pago
- Creación y completado de checkout mock
- Cambio de plan (switch)
- Cancelación (inmediata y al final del periodo)
- Métodos de pago e historial (usuarios Free)
- Cuotas de uso y registro de consumo
- Webhooks de Stripe y MercadoPago

---

## 🔐 Seguridad

- Los webhooks de Stripe verifican la firma (`Stripe-Signature` header)
- El ID de usuario se extrae de la cabecera `X-User-ID` o `X-Session-ID`
- En producción, configurar `STRIPE_WEBHOOK_SECRET` para validar eventos
- No se almacenan datos de tarjetas de crédito (PCI delegado a Stripe/MercadoPago)

---

## 📊 Monitoreo de Cuotas

El endpoint `/quota` devuelve:
- Tokens usados este mes vs límite
- Porcentaje de uso
- Sesiones activas vs límite del plan

Útil para implementar límites de rate-limiting y bloqueo por exceso de uso.

---

## 🚀 Despliegue

1. Instalar dependencias: `pip install -e .`
2. Configurar variables de entorno (Stripe o MercadoPago)
3. Iniciar el servidor: `kogniterm-server`
4. Los endpoints estarán disponibles en `http://0.0.0.0:8755/api/payments`

---