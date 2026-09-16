# Abay Repository — Payment Integration (Production)

## Gateways
- **Telebirr** SuperApp / Fabric (`payments/services/telebirr_service.py`)
- **Chapa** official SDK (`payments/services/chapa_service.py`)
- **PayPal** Orders v2 (`payments/services/paypal_service.py`)

Simulation is **disabled**. There is no test/simulate complete path.

## Checkout flow
1. Frontend: `POST /payments/create/order/` with `{ book_id, payment_method, phone_number? }`
2. Backend creates `Purchase` (pending) and calls the gateway
3. Response: `{ success, checkOutUrl, merch_order_id }`
4. Frontend opens `checkOutUrl`
5. Gateway notifies `/payments/telebirr/notify/` or `/payments/chapa/callback/`
6. User returns to `/payments/return/?ref=...` → redirected to **online reader** `/books/<id>/read/`

## Free books
Completed immediately; response includes `read_url`. No download.

## After purchase
Downloads are **not allowed**. Customers read via the in-app reader (with offline cache support).

## Required environment variables
```
USE_SIMULATED_PAYMENT=False
TELEBIRR_ENABLED=True
TELEBIRR_BASE_URL=...
TELEBIRR_FABRIC_APP_ID=...
TELEBIRR_APP_SECRET=...
TELEBIRR_MERCHANT_APP_ID=...
TELEBIRR_MERCHANT_CODE=...
TELEBIRR_PRIVATE_KEY=...
TELEBIRR_PUBLIC_KEY=...

CHAPA_SECRET_KEY=...
CHAPA_PUBLIC_KEY=...
CHAPA_WEBHOOK_SECRET=...

PAYPAL_CLIENT_ID=...
PAYPAL_CLIENT_SECRET=...
PAYPAL_MODE=live

BASE_URL=https://your-domain.com
```

## Key endpoints
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/payments/create/order/` | Create order, return checkOutUrl |
| POST | `/payments/telebirr/notify/` | Telebirr async notify |
| GET/POST | `/payments/chapa/callback/` | Chapa webhook + verify |
| GET | `/payments/paypal/return/` | Capture PayPal order |
| GET | `/payments/return/` | User return + status poll |
