#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
echo "Abay Repository - Local HTTPS (development)"
python -m pip install -q django-extensions Werkzeug pyOpenSSL
mkdir -p certs
if [ ! -f certs/localhost.crt ]; then
  python scripts/generate_local_cert.py
fi
if [ ! -f .env ] && [ -f .env.localhost ]; then
  cp .env.localhost .env
fi
echo "Starting https://127.0.0.1:8000/"
exec python manage.py runserver_plus \
  --cert-file certs/localhost.crt \
  --key-file certs/localhost.key \
  127.0.0.1:8000
