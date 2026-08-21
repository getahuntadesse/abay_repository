# Abay Repository – Deployment Guide

Production deployment with **MySQL** and multi-gateway payments (Telebirr, Chapa, PayPal).

---

## 1. Server requirements

| Component | Version / notes |
|-----------|-----------------|
| OS | Ubuntu 22.04 LTS (recommended) or similar |
| Python | 3.10+ |
| MySQL | 8.0+ |
| Nginx | reverse proxy + SSL |
| Optional | Redis (cache / Channels) |

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip python3-dev \
  build-essential default-libmysqlclient-dev pkg-config \
  nginx mysql-server certbot python3-certbot-nginx
```

---

## 2. MySQL database

```bash
sudo mysql -u root
```

In the MySQL shell:

```sql
-- If root uses auth_socket, set password auth:
ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'Abrehot@2026';
FLUSH PRIVILEGES;

CREATE DATABASE abay_repository CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- Optional dedicated user (more secure than root in production):
-- CREATE USER 'abay'@'localhost' IDENTIFIED BY 'Abrehot@2026';
-- GRANT ALL PRIVILEGES ON abay_repository.* TO 'abay'@'localhost';
-- FLUSH PRIVILEGES;
EXIT;
```

Test connection:

```bash
mysql -u root -p'Abrehot@2026' -e "SHOW DATABASES;"
```

---

## 3. Application setup

```bash
# Clone / copy project
cd /var/www
# git clone https://github.com/getahuntadesse/abay_repository.git
# or upload the integrated package
cd abay_repository

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Environment
cp .env.example .env
nano .env   # set SECRET_KEY, domain, payment keys, DB password
```

Minimum `.env` database section:

```env
DB_ENGINE=django.db.backends.mysql
DB_NAME=abay_repository
DB_USER=root
DB_PASSWORD=Abrehot@2026
DB_HOST=localhost
DB_PORT=3306
```

Generate a strong `SECRET_KEY`:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

## 4. Django migrate & static files

```bash
source venv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings

python manage.py makemigrations
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

If `manage.py` is missing from a partial copy, use the one from the full GitHub repo.

---

## 5. Gunicorn (app server)

Create `/etc/systemd/system/abay.service`:

```ini
[Unit]
Description=Abay Repository Gunicorn
After=network.target mysql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/abay_repository
Environment="PATH=/var/www/abay_repository/venv/bin"
EnvironmentFile=/var/www/abay_repository/.env
ExecStart=/var/www/abay_repository/venv/bin/gunicorn \
    --workers 3 \
    --bind 127.0.0.1:8000 \
    --timeout 120 \
    config.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable abay
sudo systemctl start abay
sudo systemctl status abay
```

---

## 6. Nginx + HTTPS

`/etc/nginx/sites-available/abay`:

```nginx
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

    location /static/ {
        alias /var/www/abay_repository/staticfiles/;
    }
    location /media/ {
        alias /var/www/abay_repository/media/;
    }
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/abay /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

Update `.env`:

```env
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com
BASE_URL=https://your-domain.com
CSRF_TRUSTED_ORIGINS=https://your-domain.com,https://www.your-domain.com
```

Restart:

```bash
sudo systemctl restart abay
```

---

## 7. Payment webhooks (required)

Register these **HTTPS** URLs with the providers:

| Gateway | URL |
|---------|-----|
| Telebirr | `https://your-domain.com/payments/webhook/telebirr/` |
| Chapa | `https://your-domain.com/payments/webhook/chapa/` |
| PayPal capture | `https://your-domain.com/payments/paypal/capture/` (called after return) |

Fill Telebirr / Chapa / PayPal keys in `.env` (see `PAYMENTS_INTEGRATION.md`).

---

## 8. Quick local test (development)

```bash
cd abay_repository
source venv/bin/activate
cp .env.example .env
# DB_PASSWORD=Abrehot@2026 already in example

# Create DB if needed
mysql -u root -p'Abrehot@2026' -e "CREATE DATABASE IF NOT EXISTS abay_repository CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

Open http://127.0.0.1:8000

---

## 9. Checklist

- [ ] MySQL database `abay_repository` exists
- [ ] `.env` has correct `DB_*` and a strong `SECRET_KEY`
- [ ] `migrate` and `collectstatic` succeeded
- [ ] Gunicorn + Nginx running
- [ ] HTTPS certificate valid
- [ ] Telebirr / Chapa / PayPal credentials set
- [ ] Webhook URLs registered and reachable from the internet
- [ ] One test purchase per payment method in staging

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `Access denied for user 'root'` | Confirm password; use `mysql_native_password` for root |
| `mysqlclient` build fails | Install `default-libmysqlclient-dev` and `pkg-config` |
| 502 Bad Gateway | Check `systemctl status abay` and Gunicorn logs |
| Webhook not received | Ensure public HTTPS; whitelist URL on Telebirr/Chapa portals |
| CSRF errors | Add domain to `CSRF_TRUSTED_ORIGINS` |

