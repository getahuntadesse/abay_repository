# Production payments — Telebirr, Chapa, PayPal

## Endpoints

| Gateway | Create checkout | Webhook / return |
|---------|-----------------|------------------|
| **Telebirr** | `POST /payments/purchase/<book_id>/` `payment_method=telebirr` | `POST /payments/webhook/telebirr/` |
| **Chapa** | `payment_method=chapa` (+ email) | `POST /payments/webhook/chapa/` |
| **PayPal** | `payment_method=paypal` | Capture: `POST /payments/paypal/capture/` · Return: `GET /payments/paypal/return/` |

All create responses (success):

```json
{
  "success": true,
  "gateway": "telebirr|chapa|paypal",
  "redirect_url": "https://...",
  "payment_url": "https://...",
  "transaction_id": "PUR-...",
  "reference": "..."
}
```

Frontend: open `redirect_url` (or `payment_url`).

## Environment

See `.env.example` for full keys. Required:

- **Telebirr:** `TELEBIRR_FABRIC_APP_ID`, `TELEBIRR_APP_SECRET`, `TELEBIRR_MERCHANT_APP_ID`, `TELEBIRR_MERCHANT_CODE`, `TELEBIRR_PRIVATE_KEY` (PEM or base64), public HTTPS `TELEBIRR_NOTIFY_URL`
- **Chapa:** `CHAPA_SECRET_KEY`, HTTPS `CHAPA_CALLBACK_URL`
- **PayPal:** `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_MODE=live`, `PAYPAL_RETURN_URL`

Set `BASE_URL=https://your-domain.com`.

## Code modules

- `payments/telebirr.py` — Fabric token + preorder + RSA-SHA256 + checkout URL
- `payments/chapa.py` — initialize + verify + webhook HMAC helper
- `payments/paypal_service.py` — Orders v2 create + capture
- `payments/views.py` — `purchase_book`, webhooks, `paypal_return`

## Portal setup

1. Telebirr SuperApp: register notify URL, upload/get RSA keys, enable H5 Checkout  
2. Chapa dashboard: webhook URL, live secret key  
3. PayPal developer: live app credentials, return URL  

## Security notes

- Webhooks are CSRF-exempt and must stay publicly reachable over HTTPS  
- Chapa status is re-verified via API on webhook  
- Purchase completion is idempotent (`_complete_purchase`)  
- Never commit real secrets; use environment variables only  
