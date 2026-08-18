# Run Abay Repository on localhost with HTTPS

Django's default `runserver` is **HTTP only**. For HTTPS on localhost we use
`runserver_plus` (django-extensions) with a self-signed certificate.

## Windows (quick)

```bat
copy .env.localhost .env
pip install django-extensions Werkzeug pyOpenSSL
python scripts\generate_local_cert.py
run_https.bat
```

Or step by step:

```bat
pip install -r requirements.txt
copy .env.localhost .env
python scripts\generate_local_cert.py
python manage.py runserver_plus --cert-file certs\localhost.crt --key-file certs\localhost.key 127.0.0.1:8000
```

Open: **https://127.0.0.1:8000/**

Click **Advanced → Proceed** (self-signed cert warning is normal).

## Important `.env` flags

```env
DEBUG=True
LOCAL_HTTPS=True
BASE_URL=https://127.0.0.1:8000
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_SSL_REDIRECT=False
SECURE_HSTS_SECONDS=0
ALLOWED_HOSTS=localhost,127.0.0.1,::1
CSRF_TRUSTED_ORIGINS=https://127.0.0.1:8000,https://localhost:8000
```

- `LOCAL_HTTPS=True` turns on secure cookies for HTTPS without HSTS.
- `SECURE_SSL_REDIRECT=False` avoids redirect loops (you already open `https://`).

## Plain HTTP (optional)

```env
LOCAL_HTTPS=False
BASE_URL=http://127.0.0.1:8000
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
```

```bat
python manage.py runserver 127.0.0.1:8000
```

Open: **http://127.0.0.1:8000/**

## Service worker / offline reader

Browsers allow service workers on `https://` and `localhost`.  
Local HTTPS is recommended for offline reader caching.

## Production

Set `DEBUG=False`, `LOCAL_HTTPS=False`, real TLS (Nginx/Caddy), and live payment keys.
