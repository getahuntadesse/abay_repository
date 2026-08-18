@echo off
cd /d "%~dp0"
echo ============================================
echo  Abay Repository - Local HTTPS (development)
echo ============================================

if not exist "venv\Scripts\activate.bat" (
  echo [info] No venv\ found - using system Python
) else (
  call venv\Scripts\activate.bat
)

echo.
echo Installing HTTPS dev packages if needed...
python -m pip install -q django-extensions Werkzeug pyOpenSSL

if not exist "certs\localhost.crt" (
  echo Generating self-signed certificate...
  if not exist "scripts\generate_local_cert.py" (
    echo ERROR: scripts\generate_local_cert.py missing
    pause
    exit /b 1
  )
  python scripts\generate_local_cert.py
)

if not exist ".env" (
  if exist ".env.localhost" (
    echo Creating .env from .env.localhost ...
    copy /Y .env.localhost .env >nul
  )
)

echo.
echo Starting HTTPS server at https://127.0.0.1:8000/
echo Accept the browser warning for the self-signed certificate.
echo Press CTRL+BREAK to stop.
echo.

python manage.py runserver_plus --cert-file certs\localhost.crt --key-file certs\localhost.key 127.0.0.1:8000
pause
