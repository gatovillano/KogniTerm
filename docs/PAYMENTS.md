# Sistema de Pagos y Suscripciones · KogniTerm

Documentación operativa del dominio implementado en `kogniterm/server/payments/`.

---

## 1. Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│  Clientes                                                 │
│  kogniterm-web · Desktop (Electron) · VS Code · CLI         │
└──────────────┬───────────────────────────┬──────────────────┘
               │ REST                     │ Webhook
               ▼                           ▼
┌──────────────────────────────┐  ┌─────────────────────────┐
│  api.py  (router FastAPI)    │  │  api.py /webhook/{prov} │
│  /api/payments/*             │  └────────────┬────────────┘
└──────────────┬───────────────┘               │
               ▼                               ▼
┌─────────────────────────────────────────────────────────────┐
│  service.py · PaymentService                               │
│  · catálogo        · ciclo de vida de suscripciones       │
│  · créditos        · idempotencia      · reembolsos        │
└───┬───────────────┬──────────────────┬─────────────────────┘
    ▼               ▼                  ▼
┌─────────┐  ┌──────────────┐   ┌──────────────────────────┐
│providers│  │ entitlements │   │ store.py                 │
│ ·mock   │  │  tier→límites│   │ · escritura atómica      │
│ ·stripe │  └──────────────┘   │ · lock fcntl             │
│ ·mercado│                     │ · migración v1→v2        │
└───┬─────┘                     │ · bitácora encadenada     │
    │                           └────────────┬─────────────┘
    ▼                                        ▼
┌─────────────┐              ┌──────────────────────────────┐
│credentials  │              │ ~/.kogniterm/payments_data.json│
│ .py (0600)  │              └──────────────────────────────┘
└─────────────┘
```

| Módulo | Responsabilidad |
|---|---|
| `models.py` | Modelos Pydantic del dominio (planes, transacciones, suscripciones, libro, auditoría) |
| `errors.py` | Jerarquía de errores; cada excepción define su `http_status` y `code` |
| `catalog.py` | Catálogo por defecto + límites por tier (`TIER_LIMITS`) |
| `store.py` | Persistencia atómica, lock, migración de esquema, bitácora encadenada |
| `credentials.py` | Secretos en archivo separado 0600; precedencia env > archivo |
| `providers.py` | Estrategia: `MockProvider`, `StripeProvider`, `MercadoPagoProvider` |
| `entitlements.py` | Traduce plan contratado → capacidades; `require_tier`, `require_credits` |
| `service.py` | Orquestador: checkout, eventos, créditos, reembolsos, reconciliación |
| `api.py` | Router REST montado en `app.py` con prefijo `/api/payments` |

---

## 2. Puesta en marcha

```bash
# 1. Instalar dependencias opcionales (para producción)
pip install stripe                 # proveedor Stripe
# MercadoPago usa la API REST directamente: no requiere SDK

# 2. Configurar credenciales
kogniterm pay config --provider stripe \
    --secret-key sk_live_... \
    --webhook-secret whsec_...

# 3. Definir el proveedor activo
export KOGNITERM_PAYMENT_PROVIDER=stripe
export KOGNITERM_PUBLIC_BASE_URL=https://tu-dominio.com

# 4. Registrar el webhook en el panel del proveedor
#    Stripe:  POST https://tu-dominio.com/api/payments/webhook/stripe
#    MP:      POST https://tu-dominio.com/api/payments/webhook/mercadopago
```

### Desarrollo local sin credenciales

```bash
export KOGNITERM_MOCK_WEBHOOK_SECRET=un-secreto-cualquiera
export KOGNITERM_PAYMENT_PROVIDER=mock
kogniterm pay status
```

El proveedor `mock` **sí verifica firma** (HMAC + ventana de tolerancia), de modo
que el flujo de desarrollo ejercita exactamente el mismo camino de verificación
que producción.

---

## 3. Variables de entorno

| Variable | Por defecto | Descripción |
|---|---|---|
| `KOGNITERM_PAYMENT_PROVIDER` | `mock` | Proveedor activo: `mock`, `stripe`, `mercadopago` |
| `KOGNITERM_PAYMENTS_FILE` | `~/.kogniterm/payments_data.json` | Almacén de datos |
| `KOGNITERM_PAYMENTS_CREDENTIALS_FILE` | `~/.kogniterm/payments_credentials.json` | Secretos (0600) |
| `KOGNITERM_PUBLIC_BASE_URL` | `http://localhost:5173` | Base de redirecciones de checkout |
| `KOGNITERM_FREE_CREDITS` | `100` | Créditos del plan gratuito |
| `KOGNITERM_WEBHOOK_TOLERANCE` | `300` | Ventana anti-replay (segundos) |
| `KOGNITERM_MOCK_WEBHOOK_SECRET` | aleatorio | Secreto de firma del mock |
| `STRIPE_SECRET_KEY` | — | Sobrescribe el archivo de credenciales |
| `STRIPE_WEBHOOK_SECRET` | — | **Obligatorio** para procesar webhooks |
| `MERCADOPAGO_ACCESS_TOKEN` | — | Sobrescribe el archivo de credenciales |
| `MERCADOPAGO_WEBHOOK_SECRET` | — | **Obligatorio** para procesar webhooks |

---

## 4. API REST

### Catálogo
| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/payments/plans` | Planes y packs, con precios y features |
| `GET` | `/api/payments/providers` | Estado de proveedores (nunca incluye secretos) |

### Suscripción
| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/payments/subscription/{user_id}` | Suscripción + créditos + límites + historial |
| `GET` | `/api/payments/entitlements/{user_id}` | Solo límites efectivos (ligero) |
| `GET` | `/api/payments/transactions/{user_id}` | Transacciones del usuario |
| `GET` | `/api/payments/credits/{user_id}/ledger` | Libro de movimientos de créditos |

### Compra
| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/payments/checkout` | Crea la sesión de cobro → devuelve `checkout_url` |
| `GET` | `/api/payments/transactions/{tx_id}/status` | Estado de una transacción |
| `POST` | `/api/payments/mock-checkout/complete` | Solo mock: aprueba una transacción |

### Créditos y reembolsos
| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/payments/refund` | Reembolso total o parcial |
| `POST` | `/api/payments/credits/grant` | Otorga créditos (soporte/promociones) |
| `POST` | `/api/payments/credits/consume` | Descuenta créditos |

### Admin
| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/payments/webhook/{provider}` | Recepción de eventos |
| `POST` | `/api/payments/credentials` | Guarda credenciales |
| `POST` | `/api/payments/reconcile` | Degrada suscripciones vencidas |
| `GET` | `/api/payments/audit/verify` | Verifica la cadena de auditoría |

### Ejemplos

```bash
curl -X POST localhost:8765/api/payments/checkout \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"alice","plan_id":"pro_monthly"}'
# → {"status":"pending","transaction_id":"tx_...","checkout_url":"https://..."}
```

```bash
curl localhost:8765/api/payments/subscription/alice
# → {"subscription":{...},"entitlements":{...},"transactions":[...],"credit_ledger":[...]}
```

---

## 5. CLI

```bash
kogniterm pay plans                    # catálogo
kogniterm pay status                  # proveedores + salud del almacén
kogniterm pay config --provider stripe --secret-key sk_... --webhook-secret whsec_...
kogniterm pay sub alice               # suscripción, créditos y límites
kogniterm pay grant alice 5000        # cortesía / soporte
kogniterm pay consume alice 250       # consumo
kogniterm pay refund tx_abc123         # reembolso total
kogniterm pay refund tx_abc123 1000    # reembolso parcial (centavos)
kogniterm pay history alice           # transacciones
kogniterm pay ledger alice            # movimientos de créditos
kogniterm pay reconcile               # expiraciones
kogniterm pay audit                   # verifica bitácora
```

---

## 6. Integración con el resto del sistema

```python
from kogniterm.server.payments import get_payment_service, require_tier
from kogniterm.server.payments.models import SubscriptionTier

service = get_payment_service()

# Antes de una operación de alto consumo:
sub = service.get_subscription(user_id)
require_tier(sub, SubscriptionTier.PRO, "agentes en paralelo")

# Al consumir:
service.consume_credits(user_id, 250, reason="agent_call", model="claude-opus")
```

El servidor ejecuta un **barrido cada 15 minutos** (`lifespan` en `app.py`) que
degrada a Free las suscripciones vencidas. Es idempotente y barato, así que
puede invocarse también desde `/api/payments/reconcile`.

---

## 7. Planes incluidos

| Plan | Precio | Intervalo | Créditos | Agentes/sesión | Subagentes |
|---|---|---|---|---|---|
| Free | gratis | mes | 100 | 2 | 1 |
| Pro Mensual | $19.99 | mes | 5.000 | 8 | 3 |
| Pro Anual | $199.00 | año | 5.000/mes | 8 | 3 |
| Enterprise | $799.00 | año | 20.000 | 32 | 8 |

Paquetes sueltos: 5.000 por $9.90 y 27.500 por $39.90.

Personalización: edita `settings.plans` en `payments_data.json` o sobrescribe
el catálogo en `catalog.py`. Un plan puede endurecer los límites del tier
(via `limits`) pero nunca relajarlos por debajo.

---

## 8. Garantías de seguridad

Estas son las propiedades que el sistema garantiza y que hay tests que las verifican:

| Garantía | Cómo se cumple | Test |
|---|---|---|
| **Ningún webhook se procesa sin firma válida** | `verify_webhook` es obligatorio; sin secreto configurado el sistema **rechaza**, nunca degrada a parsear sin verificar | `test_webhook_sin_firma_se_rechaza`, `test_stripe_sin_webhook_secret_no_procesa` |
| **Anti-replay** | Ventana de tolerancia sobre el timestamp (300 s) | `test_webhook_con_timestamp_viejo_se_rechaza` |
| **Idempotencia** | Clave `provider:sha256(payload)` sobre eventos ya procesados | `test_replay_no_duplica_creditos` |
| **Anti-abuso** | Máximo de checkouts por usuario y hora | `test_rate_limit_de_checkouts` |
| **Atomicidad** | Escritura a temporal + `os.replace`; rollback en memoria si el cuerpo lanza | `test_rollback_en_memoria_si_falla` |
| **Integridad de auditoría** | Bitácora encadenada por hash SHA-256 | `test_bitacora_detecta_manipulacion` |
| **Secretos fuera del almacén** | Archivo separado 0600; el JSON de datos nunca contiene claves | `test_credenciales_no_en_el_almacen` |
| **Permisos del almacén** | `0600` en el fichero de datos | `test_almacen_tiene_permisos_0600` |
| **Datos no perdidos** | Un JSON corrupto se aísla y se reinicia limpio | `test_json_corrupto_se_aisla_y_reinicia` |
| **Degradación por expiración** | Reconciliación automática e idempotente | `test_reconciliacion_es_idempotente` |

### Migración desde el esquema v1

Al arrancar con un `payments_data.json` del módulo anterior, los datos se
migran al esquema v2 **y se reescribe el archivo en disco**. Esto importa por un
motivo de seguridad: el v1 guardaba las claves de Stripe y MercadoPago dentro de
`settings`. La migración las descarta deliberadamente (deben rotarse) y la
reescritura las elimina físicamente del disco.

---

## 9. Tests

```bash
pytest tests/test_payments.py tests/server/test_payments.py -v
```

**99 tests**: 70 en `tests/test_payments.py` (dominio, seguridad, API) y 29 en
`tests/server/test_payments.py` (ciclo de vida vía HTTP).

Los tests aíslan el almacén con `tmp_path` y `KOGNITERM_PAYMENTS_FILE`, por lo
que **nunca escriben sobre el archivo real del usuario**.

---

## 10. Añadir un proveedor

1. Crear la clase en `providers.py` heredando de `PaymentProvider`.
2. Implementar `create_checkout`, `verify_webhook`, `parse_event` (y opcionalmente `refund`).
3. Registrar el valor en el enum `PaymentProviderType` (models.py).
4. Añadir el mapeo de variables de entorno en `credentials.ENV_KEYS`.

El servicio no requiere cambios: solo conoce el contrato.

---

## 11. Notas de operación

- **Moneda**: los importes se guardan en centavos de la unidad mínima del plan
  (`price_cents`). Stripe espera centavos; MercadoPago, unidades decimales
  (la conversión ocurre dentro del proveedor).
- **Reembolsos parciales**: los créditos se revocan en proporción al dinero
  devuelto, redondeando hacia abajo. Si un usuario ya consumió los créditos, se
  revoca lo que quede (`min(saldo, calculado)`) y nunca queda negativo.
- **Un plan por pago único** (`one_time`/`lifetime`) no establish
  `expires_at`, por lo que sobrevive a la reconciliación.
- **Downgrade por reembolso**: si `auto_downgrade` está activo (por defecto) y
  el reembolso es total, el usuario vuelve al plan gratuito.
