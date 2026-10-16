# 💳 Sistema de Pagos y Suscripciones - KogniTerm

Este documento describe el sistema completo de pagos, suscripciones y facturación implementado en el servidor backend de KogniTerm.

## Arquitectura

El sistema de pagos está organizado en el paquete `kogniterm/server/payments/` con los siguientes módulos:

| Módulo | Descripción |
|--------|-------------|
| `models.py` | Modelos base de Pydantic (planes, suscripciones, checkout, historial) |
| `models_extended.py` | Modelos extendidos (reembolsos, cupones, facturas, impuestos, registros) |
| `service.py` | Servicio base con integración Stripe / MercadoPago / Mock |
| `service_extended.py` | Servicio extendido con lógica de negocio completa |
| `router.py` | Router REST base (planes, suscripción, checkout, webhooks) |
| `router_extended.py` | Router extendido (precios, cupones, facturas, reembolsos, cuotas) |

## Endpoints REST

### Base (en `/api/payments`)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/plans` | Catálogo de planes disponibles |
| `GET` | `/plans/{plan_id}` | Detalle de un plan específico |
| `GET` | `/subscription` | Suscripción activa del usuario |
| `POST` | `/checkout` | Crear sesión de checkout (Stripe/MP/Mock) |
| `POST` | `/checkout/complete` | Completar checkout (mock/simulación) |
| `POST` | `/subscription/switch` | Cambiar de plan |
| `POST` | `/subscription/cancel` | Cancelar suscripción |
| `GET` | `/payment-methods` | Métodos de pago del usuario |
| `GET` | `/history` | Historial de facturación |
| `GET` | `/quota` | Cuota de uso y límites |
| `POST` | `/webhook` | Webhook de pasarela de pago |

### Extendido (en `/api/payments`)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `POST` | `/pricing/calculate` | Calcular precio con descuentos e impuestos |
| `GET` | `/coupons` | Listar cupones disponibles |
| `POST` | `/coupons/apply` | Aplicar cupón a un plan |
| `POST` | `/invoices` | Crear factura |
| `GET` | `/invoices/{invoice_id}` | Obtener factura por ID |
| `GET` | `/invoices` | Listar facturas del usuario |
| `POST` | `/invoices/{invoice_id}/pay` | Marcar factura como pagada |
| `POST` | `/refunds` | Solicitar reembolso |
| `GET` | `/refunds/{refund_id}` | Obtener reembolso por ID |
| `GET` | `/refunds` | Listar reembolsos del usuario |
| `GET` | `/records` | Listar registros de pago |
| `GET` | `/records/{payment_id}` | Obtener registro de pago |
| `GET` | `/providers/health` | Estado de proveedores de pago |
| `GET` | `/quota/enforce` | Verificar límites de cuota |

## Planes de Suscripción

| Plan | Precio | Ciclo | Tokens/mes | Sesiones | Modelos avanzados |
|------|--------|-------|------------|----------|-------------------|
| Free | $0 | Mensual | 100,000 | 2 | No |
| Pro Monthly | $19.99 | Mensual | 5,000,000 | 10 | Sí |
| Pro Yearly | $199.99 | Anual | 5,000,000 | 10 | Sí |
| Enterprise | $99.99 | Mensual | 100,000,000 | 100 | Sí |

## Características Implementadas

### 1. Integración con Pasarelas de Pago
- **Stripe**: Checkout sessions, suscripciones recurrentes, webhooks
- **MercadoPago**: Preferencias de pago, webhooks
- **Mock/Simulación**: Modo de desarrollo sin pasarela real

### 2. Cálculo de Precios Dinámico
- Aplicación de cupones (porcentaje o monto fijo)
- Impuestos por país (IVA, GST, Sales Tax)
- Validación de cupón (expiración, usos máximos, planes aplicables)

### 3. Gestión de Cupones
- Cupones predefinidos (WELCOME20, SAVE10, FIXED5)
- Creación de cupones personalizados
- Control de usos por usuario y totales
- Fechas de validez

### 4. Facturación
- Generación de facturas con items desglosados
- Cálculo de subtotal, impuestos y total
- Estados de factura (borrador, abierta, pagada, anulada)
- Números de factura automáticos

### 5. Reembolsos
- Solicitud de reembolso parcial o total
- Motivo del reembolso (categorizado)
- Registro y tracking de reembolsos

### 6. Registro de Pagos
- Registro completo de cada transacción
- Proveedor utilizado, ID externo, montos
- Asociación con facturas y cupones

### 7. Enforzamiento de Cuotas
- Verificación de límites de tokens por mes
- Verificación de sesiones concurrentes
- Estado de suscripción (activa, cancelada, vencida)

### 8. Salud de Proveedores
- Verificación de disponibilidad de Stripe y Mock
- Detección de proveedores degradados o no disponibles

## Autenticación

Los endpoints utilizan extracción de `user_id` desde las cabeceras:
- `X-User-ID`: ID explícito de usuario
- `X-Session-ID`: ID de sesión como fallback
- IP del cliente como último recurso

El servidor principal ya maneja autenticación por token de API para endpoints sensibles.

## Variables de Entorno

| Variable | Descripción | Requerido |
|----------|-------------|-----------|
| `STRIPE_SECRET_KEY` | Clave secreta de Stripe | Opcional |
| `STRIPE_WEBHOOK_SECRET` | Secreto de webhook de Stripe | Opcional |
| `MERCADOPAGO_ACCESS_TOKEN` | Token de acceso de MercadoPago | Opcional |

Si no se configura ninguna pasarela, el sistema funciona en **modo Mock** para desarrollo y pruebas.

## Ejemplos de Uso

### Obtener planes disponibles
```bash
curl -X GET http://localhost:8765/api/payments/plans \
  -H "X-User-ID: user_123"
```

### Calcular precio con descuento e impuesto
```bash
curl -X POST "http://localhost:8765/api/payments/pricing/calculate?plan_id=plan_pro_monthly&coupon_code=WELCOME20&country_code=AR"
```

### Crear sesión de checkout
```bash
curl -X POST http://localhost:8765/api/payments/checkout \
  -H "X-User-ID: user_123" \
  -H "Content-Type: application/json" \
  -d '{
    "plan_id": "plan_pro_monthly",
    "success_url": "http://localhost:3000/success",
    "cancel_url": "http://localhost:3000/cancel",
    "customer_email": "usuario@ejemplo.com"
  }'
```

### Aplicar cupón
```bash
curl -X POST http://localhost:8765/api/payments/coupons/apply \
  -H "Content-Type: application/json" \
  -d '{
    "coupon_code": "WELCOME20",
    "plan_id": "plan_pro_monthly",
    "user_id": "user_123"
  }'
```

### Verificar cuotas antes de una acción
```bash
curl -X GET "http://localhost:8765/api/payments/quota/enforce?tokens_needed=50000&sessions_needed=1" \
  -H "X-User-ID: user_123"
```

## Pruebas

Los tests existentes están en `tests/test_payments.py` y cubren:
- Listado de planes
- Obtención de detalles de plan
- Suscripción por defecto (Free)
- Creación de sesión de checkout
- Cancelación de suscripción
- Métodos de pago
- Historial de pagos
- Cuota de uso

Para ejecutar los tests:
```bash
cd /home/gato/KogniTerm
~/.kogniterm/venv/bin/python -m pytest tests/test_payments.py -v
```

## Estructura de Datos

### PlanInfo
Define un plan de suscripción con precio, límites de tokens, sesiones y características.

### SubscriptionDetails
Estado actual de la suscripción de un usuario, incluyendo IDs de Stripe si aplica.

### InvoiceInfo
Factura completa con items, subtotal, impuestos, total y estado.

### CouponInfo
Cupón de descuento con código, tipo (porcentaje/fijo), valor, validez y límites de uso.

### RefundResponse
Solicitud de reembolso con monto, motivo, estado y fecha.

### PaymentRecord
Registro de transacción de pago con proveedor, montos y timestamps.
