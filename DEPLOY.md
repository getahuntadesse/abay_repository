# Abay Repository – Production Deployment Guide

## What was added / hardened

### Payments
- **Telebirr** – full SuperApp flow (Fabric token → createOrder → `checkOutUrl`, queryOrder, notify signature verify, refund). Matches Ethio telecom docs.
- **Chapa** – initialize → `checkout_url`, verify webhook.
- **PayPal** – Orders v2 create → approve URL, capture on return.
- Unified endpoint: `POST /payments/create/order/`  
  Body: `{ "book_id": 123, "payment_method": "telebirr|chapa|paypal", "phone_number": "..." }`  
  Response: `{ "success": true, "checkOutUrl": "https://...", "merch_order_id": "..." }`  
  Frontend opens `checkOutUrl` (same pattern as your sample `startPay`).

### Security & sessions
- Existing `SecurityHeadersMiddleware` (CSP, HSTS, Permissions-Policy, COOP/COEP, no-store on auth pages).
- CSP updated for Telebirr / Chapa / PayPal domains.
- Session: 8h lifetime, HttpOnly, Secure (prod), SameSite=Lax, DB backend.
- CSRF: HttpOnly + Secure in production, use sessions.
- Production auto-enables: SSL redirect, HSTS 1y, secure cookies when `DEBUG=False`.

## Quick deploy (Ubuntu + MySQL + Nginx + Gunicorn)

```bash
# 1. Unpack
unzip abay_repository_production.zip
cd abay_repository_production

# 2. Python env
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# optional: pip install argon2-cffi mysqlclient

# 3. Config
cp .env.example .env
# edit .env – set SECRET_KEY, DB_*, DEBUG=False, ALLOWED_HOSTS, all payment keys

# 4. Database
mysql -u root -p -e "CREATE DATABASE abay_repository CHARACTER SET utf8mb4;"
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput

# 5. Gunicorn
gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3 --timeout 120

# 6. Nginx reverse proxy (HTTPS with certbot)
# proxy_pass http://127.0.0.1:8000;
# location /static/ and /media/ as usual
```

Whitelist the notify/callback URLs on Telebirr Fabric portal and Chapa dashboard:
- `https://yourdomain.com/payments/telebirr/notify/`
- `https://yourdomain.com/payments/chapa/callback/`

## Frontend usage (exact pattern you requested)

```javascript
function createOrder(bookId, paymentMethod, phone) {
  fetch("/payments/create/order/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    },
    credentials: "same-origin",
    body: JSON.stringify({
      book_id: bookId,
      payment_method: paymentMethod, // "telebirr" | "chapa" | "paypal"
      phone_number: phone || "",
    }),
  })
    .then((r) => r.json())
    .then((data) => {
      if (data.success && data.checkOutUrl) {
        startPay(data.checkOutUrl);
      } else if (data.free) {
        window.location = data.download_url;
      } else {
        alert(data.error || "Payment failed");
      }
    });
}

function startPay(checkOutUrl) {
  const a = document.createElement("a");
  a.href = checkOutUrl;
  a.target = "_blank";
  a.rel = "noopener noreferrer";
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();
  a.remove();
}
```

## Notes
- Keep private keys only in `.env` (or secrets manager). Never commit them.
- Telebirr RSA private key can be multi-line PEM or single-line base64 content; the service normalizes both.
- After payment success the notify/return handlers mark the `Purchase` completed and create the author royalty `Payment`.
- Run `python manage.py check --deploy` before going live.
