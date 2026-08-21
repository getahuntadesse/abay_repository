# Webhook verification (production)

## Endpoints

| Gateway | URL | Verification |
|---------|-----|----------------|
| Telebirr | `POST /payments/webhook/telebirr/` | RSA-SHA256 with `TELEBIRR_PUBLIC_KEY` |
| Chapa | `POST /payments/webhook/chapa/` | HMAC header + **API** `verify(tx_ref)` |
| PayPal | `POST /payments/webhook/paypal/` | PayPal `verify-webhook-signature` + `PAYPAL_WEBHOOK_ID` |

Also: PayPal browser return `GET /payments/paypal/return/` captures the order.

## `.env`

```env
WEBHOOK_VERIFY_STRICT=True

# Telebirr platform public key (PEM or base64 DER)
TELEBIRR_PUBLIC_KEY=-----BEGIN PUBLIC KEY-----...

# Chapa (HMAC uses CHAPA_SECRET_KEY if CHAPA_WEBHOOK_SECRET empty)
CHAPA_WEBHOOK_SECRET=
CHAPA_SECRET_KEY=CHASECK_LIVE-...
CHAPA_CALLBACK_URL=https://your-domain.com/payments/webhook/chapa/

# PayPal webhook id from developer dashboard → Webhooks
PAYPAL_WEBHOOK_ID=
PAYPAL_MODE=live
```

## Portal setup

1. **Telebirr** — set notify URL to `https://your-domain.com/payments/webhook/telebirr/` and store the **platform public key** in `TELEBIRR_PUBLIC_KEY`.
2. **Chapa** — Dashboard → Webhooks → `https://your-domain.com/payments/webhook/chapa/`.
3. **PayPal** — Developer → Webhooks → add `https://your-domain.com/payments/webhook/paypal/` for events:
   - `PAYMENT.CAPTURE.COMPLETED`
   - `CHECKOUT.ORDER.APPROVED`
   Copy the **Webhook ID** into `PAYPAL_WEBHOOK_ID`.

## Behaviour

- Invalid signatures → **401** (when `WEBHOOK_VERIFY_STRICT=True`).
- Valid paid events → purchase `pending` → `completed` (idempotent).
- Chapa always re-checks status via Chapa Verify API before completing.
