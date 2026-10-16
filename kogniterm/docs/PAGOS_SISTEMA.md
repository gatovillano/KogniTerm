# 💳 Sistema de Pagos y Suscripciones - KogniTerm

## Resumen

KogniTerm incluye un sistema completo de pagos y suscripciones integrado en el backend FastAPI (`kogniterm/server/payments/`) con soporte para:

- **Catálogo de planes**: Free, Pro Monthly, Pro Yearly, Enterprise
- **Checkout**: Stripe (producción), MercadoPago (Latam), Mock (desarrollo)
- **Gestión de suscripciones**: activar, cambiar, cancelar
- **Webhooks**: eventos de Stripe y MercadoPago
- **Historial de pagos y métodos de pago**
- **Cuota de uso**: tokens y sesiones por plan
- **Cliente de escritorio**: panel de precios en KogniTerm Desktop

## Arquitectura Backend

```
kogniterm/server/payments/
├── __init__.py      # Exporta router y servicio
├── models.py        # Modelos Pydantic (planes, suscripciones, pagos)
├── router.py        # Endpoints REST (montados en /api/payments)
└── service.py       # Lógica de negocio e integración con pasarelas
```

### Endpoints REST (prefijo `/api/payments`)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/plans` | Lista todos los planes disponibles |
| GET | `/plans/{plan_id}` | Detalle de un plan específico |
| GET | `/subscription` | Suscripción activa del usuario |
| POST | `/checkout` | Crea sesión de checkout (Stripe/MercadoPago/Mock) |
| POST | `/checkout/complete` | Completa checkout (mock/simulación) |
| POST | `/subscription/switch` | Cambia de plan |
| POST | `/subscription/cancel` | Cancela la suscripción |
| GET | `/payment-methods` | Lista métodos de pago del usuario |
| GET | `/history` | Historial de facturación |
| GET | `/quota` | Cuota de uso (tokens/sesiones) |
| POST | `/webhook` | Webhook de eventos de pasarela de pago |

### Planes Predefinidos

| Plan | Precio | Tokens/mes | Sesiones | Modelos Personalizados |
|------|--------|------------|----------|------------------------|
| Free | $0 | 100,000 | 2 | No |
| Pro Monthly | $19.99 | 5,000,000 | 10 | Sí |
| Pro Yearly | $199.99 | 5,000,000 | 10 | Sí |
| Enterprise | $99.99 | 100,000,000 | 100 | Sí |

## Integración con KogniTerm Desktop

El panel de pagos está disponible en el cliente de escritorio:

1. Abre **Ajustes** (`Ctrl+,` o menú ☰ → Ajustes)
2. Selecciona la pestaña **"Pagos"** (icono 💳)
3. Verás los planes disponibles y tu suscripción actual
4. Puedes contratar un plan, cambiar de plan o cancelar

### Archivos modificados/creados en el frontend

- `kogniterm-desktop/apps/web/src/lib/api.ts` — Métodos API para pagos (`listPlans`, `getSubscription`, `createCheckout`, `completeCheckout`, `switchPlan`, `cancelSubscription`, etc.)
- `kogniterm-desktop/apps/web/src/components/PricingPanel.tsx` — Componente UI del panel de precios
- `kogniterm-desktop/apps/web/src/components/SettingsModals.tsx` — Pestaña "Pagos" en UnifiedSettingsModal
- `kogniterm-desktop/apps/web/src/App.tsx` — Botón "Pagos y Suscripciones" en el menú

## Pruebas

Archivo: `tests/test_payments.py`

Casos de prueba cubiertos:
- `test_list_plans` — Catálogo de planes
- `test_get_plan_by_id` — Detalle de plan + 404 inexistente
- `test_get_default_subscription` — Plan Free por defecto
- `test_create_checkout_session` — Checkout y activación de plan
- `test_cancel_subscription` — Cancelación de suscripción
- `test_get_payment_methods` — Métodos de pago (mock)
- `test_get_payment_history` — Historial de facturación
- `test_get_quota_usage` — Métricas de cuota de uso

## Configuración de Pasarelas de Pago

### Stripe (Producción)

Configura las siguientes variables de entorno:

```bash
export STRIPE_SECRET_KEY=sk_test_...
export STRIPE_WEBHOOK_SECRET=whsec_...
```

Instala el SDK:
```bash
pip install stripe
```

### MercadoPago (Latam)

```bash
export MERCADOPAGO_ACCESS_TOKEN=APP_USR-...
```

Instala el SDK:
```bash
pip install mercadopago
```

### Modo Mock (Desarrollo)

Si no se configura ninguna pasarela, el sistema funciona en modo simulación con almacenamiento en memoria. Ideal para desarrollo y pruebas.

## Webhooks

### Stripe

Configura el webhook en tu dashboard de Stripe apuntando a:
```
https://tu-dominio.com/api/payments/webhook
```

Eventos manejados:
- `checkout.session.completed` → Activa la suscripción
- `customer.subscription.deleted` → Cancela la suscripción

### MercadoPago

Usa el endpoint `handle_mercadopago_webhook` para procesar notificaciones de pago.

## Uso desde la API

### Obtener planes disponibles

```bash
curl -H "X-User-ID: user_123" http://localhost:8755/api/payments/plans
```

### Crear sesión de checkout

```bash
curl -X POST http://localhost:8755/api/payments/checkout \
  -H "Content-Type: application/json" \
  -H "X-User-ID: user_123" \
  -d '{
    "plan_id": "plan_pro_monthly",
    "success_url": "https://tu-app.com/success",
    "cancel_url": "https://tu-app.com/cancel",
    "customer_email": "usuario@ejemplo.com",
    "provider": "mock"
  }'
```

### Consultar suscripción

```bash
curl -H "X-User-ID: user_123" http://localhost:8755/api/payments/subscription
```

### Cambiar de plan

```bash
curl -X POST http://localhost:8755/api/payments/subscription/switch \
  -H "Content-Type: application/json" \
  -H "X-User-ID: user_123" \
  -d '{"plan_id": "plan_pro_yearly", "provider": "mock"}'
```

### Cancelar suscripción

```bash
curl -X POST "http://localhost:8755/api/payments/subscription/cancel?at_period_end=true" \
  -H "X-User-ID: user_123"
```

## Notas de Seguridad

- Los endpoints de pagos requieren autenticación por token (mismo token que el resto de la API KogniTerm)
- Las sesiones de checkout generan IDs aleatorios seguros
- El almacenamiento en memoria es temporal; para producción usa una base de datos persistente
- Los webhooks de Stripe verifican la firma (`Stripe-Signature` header)

## Roadmap

- [ ] Persistencia en base de datos (PostgreSQL/SQLite) en lugar de memoria
- [ ] Facturación automática recurrente con Stripe
- [ ] Facturas descargables en PDF
- [ ] Cupones y códigos de descuento
- [ ] Soporte para más pasarelas (PayPal, etc.)
- [ ] Analytics de ingresos y churn