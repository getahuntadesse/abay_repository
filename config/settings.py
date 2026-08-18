"""
Django settings for abay_repository project.
"""

import os
from pathlib import Path
from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# =============================================
# 1. SECRET KEY & DEBUG SETTINGS
# =============================================

SECRET_KEY = config('SECRET_KEY', default='django-insecure-9!@#x$%^&*()_+=-qwertyuiop[]{}|;:,.<>/')

DEBUG = config('DEBUG', default=True, cast=bool)

# Always include local hosts in development; merge with .env values
_allowed = config('ALLOWED_HOSTS', default='localhost,127.0.0.1,::1').split(',')
_allowed = [h.strip() for h in _allowed if h.strip()]
if DEBUG:
    for h in ('localhost', '127.0.0.1', '::1', 'testserver'):
        if h not in _allowed:
            _allowed.append(h)
ALLOWED_HOSTS = _allowed

CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='http://localhost:8000,http://127.0.0.1:8000,http://localhost:3000,http://127.0.0.1:3000',
).split(',')
CSRF_TRUSTED_ORIGINS = [o.strip() for o in CSRF_TRUSTED_ORIGINS if o.strip()]

# =============================================
# 1.5. BASE URL SETTINGS
# =============================================

BASE_URL = config('BASE_URL', default='https://127.0.0.1:8000')

# =============================================
# 2. APPLICATION DEFINITION
# =============================================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django_extensions', 
    
    # Third-party apps
    'corsheaders',
    'crispy_forms',
    'crispy_bootstrap5',
    
    # 2FA Apps
    'django_otp',
    'django_otp.plugins.otp_static',
    'django_otp.plugins.otp_email',
    
    # Local apps
    'accounts',
    'books',
    'core',
    'payments',
    'notifications',
    'dashboard',
    'reviews',
]

# Django Debug Toolbar (development only)
if DEBUG:
    INSTALLED_APPS += ['debug_toolbar']

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'core.middleware.SecurityHeadersMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Debug Toolbar middleware must be early (after SecurityMiddleware ideally)
if DEBUG:
    MIDDLEWARE.insert(1, 'debug_toolbar.middleware.DebugToolbarMiddleware')

INTERNAL_IPS = config(
    'INTERNAL_IPS',
    default='127.0.0.1,localhost',
).split(',')
INTERNAL_IPS = [ip.strip() for ip in INTERNAL_IPS if ip.strip()]
# Docker / some proxies
if DEBUG:
    try:
        import socket
        hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
        INTERNAL_IPS += [ip[:-1] + '1' for ip in ips if '.' in ip]
    except Exception:
        pass

# Toolbar panels / show callback — hide on AJAX, only when DEBUG
DEBUG_TOOLBAR_CONFIG = {
    'SHOW_TOOLBAR_CALLBACK': lambda request: bool(
        DEBUG and not request.headers.get('x-requested-with') == 'XMLHttpRequest'
        and (
            request.META.get('REMOTE_ADDR') in INTERNAL_IPS
            or request.META.get('REMOTE_ADDR') in ('127.0.0.1', '::1')
            or getattr(request, 'user', None) and getattr(request.user, 'is_superuser', False)
        )
    ),
    'SHOW_COLLAPSED': True,
    'IS_RUNNING_TESTS': False,
}


ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# =============================================
# 3. DATABASE CONFIGURATION
# =============================================

DATABASES = {
    'default': {
        'ENGINE': config('DB_ENGINE', default='django.db.backends.mysql'),
        'NAME': config('DB_NAME', default='abay_repository'),
        'USER': config('DB_USER', default='root'),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='3306'),
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            'charset': 'utf8mb4',
        },
        'CONN_MAX_AGE': 600,
        'ATOMIC_REQUESTS': True,
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# =============================================
# 4. AUTH USER MODEL
# =============================================

AUTH_USER_MODEL = 'accounts.CustomUser'

# =============================================
# 5. PASSWORD VALIDATION
# =============================================

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 10,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

try:
    import argon2
    PASSWORD_HASHERS.insert(0, 'django.contrib.auth.hashers.Argon2PasswordHasher')
except ImportError:
    pass

# =============================================
# 6. AUTHENTICATION & SESSION SECURITY - FIXED
# =============================================

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

# Session Cookie Security (hardened)
SESSION_COOKIE_AGE = 3600 * 8  # 8 hours
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=False, cast=bool)
SESSION_COOKIE_SAMESITE = 'Lax'
# __Host- prefix only works over HTTPS with Secure + Path=/
SESSION_COOKIE_NAME = 'sessionid'
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = True
SESSION_ENGINE = 'django.contrib.sessions.backends.db'

# CSRF Cookie Security
# CSRF_USE_SESSIONS requires SessionMiddleware before CsrfViewMiddleware (already set).
# Use cookie-based CSRF in DEBUG so error pages still work if host is rejected early.
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=False, cast=bool)
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_USE_SESSIONS = not DEBUG  # True in production, False in local dev
CSRF_FAILURE_VIEW = 'django.views.csrf.csrf_failure'

# =============================================
# 7. SECURE SSL/HTTPS SETTINGS - FIXED
# =============================================

# Force HTTPS redirect — NEVER enable on local runserver (HTTP only)
# In production set DEBUG=False; the block below will force this True.
SECURE_SSL_REDIRECT = False if DEBUG else config('SECURE_SSL_REDIRECT', default=True, cast=bool)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# HTTP Strict Transport Security (HSTS)
SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=31536000, cast=int)  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = config('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=True, cast=bool)
SECURE_HSTS_PRELOAD = config('SECURE_HSTS_PRELOAD', default=True, cast=bool)

# Additional Security Headers
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# X-Frame-Options (prevent clickjacking)
X_FRAME_OPTIONS = 'DENY'

# =============================================
# 8. ENVIRONMENT-BASED SECURITY OVERRIDES
# =============================================

# Production security settings (enabled when DEBUG=False)
if not DEBUG:
    # Force secure cookies in production
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    CSRF_USE_SESSIONS = True
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_NAME = 'abay_session'
    SESSION_COOKIE_PATH = '/'

    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
else:
    # Development: plain HTTP runserver — never redirect to HTTPS
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    CSRF_USE_SESSIONS = False
    SECURE_SSL_REDIRECT = False
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False
    SESSION_COOKIE_NAME = 'sessionid'

# ------------------------------------------------------------
# Local development host + optional local HTTPS (runserver_plus)
# Set LOCAL_HTTPS=True in .env when serving with SSL certs.
# ------------------------------------------------------------
LOCAL_HTTPS = config('LOCAL_HTTPS', default=True, cast=bool)  # localhost HTTPS via runserver_plus

if DEBUG:
    for h in ('localhost', '127.0.0.1', '::1', 'testserver'):
        if h not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(h)
    for o in (
        'http://localhost:8000',
        'http://127.0.0.1:8000',
        'https://localhost:8000',
        'https://127.0.0.1:8000',
        'http://localhost:3000',
        'http://127.0.0.1:3000',
        'https://localhost:3000',
        'https://127.0.0.1:3000',
    ):
        if o not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(o)

    # Never send HSTS on local (breaks browser until cleared)
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

    if LOCAL_HTTPS:
        # Serving https://127.0.0.1:8000/ via runserver_plus
        SESSION_COOKIE_SECURE = True
        CSRF_COOKIE_SECURE = True
        # Already on HTTPS — do not 301 again
        SECURE_SSL_REDIRECT = False
        if not BASE_URL.startswith('https'):
            BASE_URL = config('BASE_URL', default='https://127.0.0.1:8000')
    else:
        SESSION_COOKIE_SECURE = False
        CSRF_COOKIE_SECURE = False
        SECURE_SSL_REDIRECT = False

# =============================================
# 9. CORS
# =============================================

CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='http://localhost:3000,http://127.0.0.1:3000,https://esignet.ida.fayda.et').split(',')
CORS_ALLOW_CREDENTIALS = True
CORS_PREFLIGHT_MAX_AGE = 86400

# =============================================
# 10. FILE UPLOAD
# =============================================

FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
FILE_UPLOAD_PERMISSIONS = 0o644

# =============================================
# 11. STATIC & MEDIA
# =============================================

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# =============================================
# 12. INTERNATIONALIZATION
# =============================================

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Addis_Ababa'
USE_I18N = True
USE_TZ = True

# =============================================
# 13. EMAIL
# =============================================

# Use SMTP in production; console backend in development for easy debugging.
# Override via EMAIL_BACKEND in .env for special cases.
if DEBUG:
    EMAIL_BACKEND = config(
        'EMAIL_BACKEND',
        default='django.core.mail.backends.console.EmailBackend'
    )
else:
    EMAIL_BACKEND = config(
        'EMAIL_BACKEND',
        default='django.core.mail.backends.smtp.EmailBackend'
    )

EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_USE_SSL = config('EMAIL_USE_SSL', default=False, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@abay.abrehot.org.et')

# =============================================
# 14. CRISPY FORMS
# =============================================

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# =============================================
# 15. CACHING
# =============================================

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

# =============================================
# 16. 2FA EMAIL SETTINGS
# =============================================

OTP_EMAIL_SUBJECT = "Your Abay Repository Verification Code"
OTP_EMAIL_SENDER = config('DEFAULT_FROM_EMAIL', default='noreply@abay.abrehot.org.et')
OTP_EMAIL_TOKEN_VALIDITY = 300
OTP_EMAIL_THROTTLE_FACTOR = 1

OTP_EMAIL_BODY_TEMPLATE = """
Hello {username},

You are receiving this email because you need to verify your identity to access Abay Repository.

Your verification code is: {token}

This code will expire in 5 minutes.

If you did not request this code, please ignore this email.

Best regards,
Abay Repository Team
"""

# =============================================
# 17. LOGGING - UPDATED
# =============================================

# Create logs directory if it doesn't exist
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR, mode=0o755)

# Main log file path
LOG_FILE_PATH = os.path.join(BASE_DIR, 'logs.txt')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    
    # Formatters
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name} - {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'simple': {
            'format': '[{asctime}] {levelname} - {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'detailed': {
            'format': '[{asctime}] {levelname} {name} {module}.{funcName}:{lineno} - {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'payment': {
            'format': '[{asctime}] PAYMENT {levelname} - {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'auth': {
            'format': '[{asctime}] AUTH {levelname} - {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'secure': {
            'format': '[{asctime}] SECURITY {levelname} - {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
    },
    
    # Filters
    'filters': {
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
    },
    
    # Handlers
    'handlers': {
        # Main log file handler - writes to logs.txt
        'main_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_FILE_PATH,
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        # Auth log handler
        'auth_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_FILE_PATH,
            'maxBytes': 10485760,
            'backupCount': 5,
            'formatter': 'auth',
            'encoding': 'utf-8',
        },
        # Payment log handler
        'payment_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_FILE_PATH,
            'maxBytes': 10485760,
            'backupCount': 5,
            'formatter': 'payment',
            'encoding': 'utf-8',
        },
        # Security log handler
        'security_file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'security.log'),
            'maxBytes': 10485760,
            'backupCount': 10,
            'formatter': 'secure',
            'encoding': 'utf-8',
        },
        # Django log file (separate for detailed debugging)
        'django_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'django.log'),
            'maxBytes': 10485760,
            'backupCount': 10,
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        # Console handler for development
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        # Error handler
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_FILE_PATH,
            'maxBytes': 10485760,
            'backupCount': 5,
            'formatter': 'detailed',
            'encoding': 'utf-8',
        },
    },
    
    # Loggers
    'loggers': {
        # Root logger - catches everything
        '': {
            'handlers': ['main_file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        # Django base logger
        'django': {
            'handlers': ['main_file', 'django_file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        # Django request logger
        'django.request': {
            'handlers': ['main_file', 'error_file', 'console'],
            'level': 'ERROR',
            'propagate': False,
        },
        # Django security logger
        'django.security': {
            'handlers': ['security_file', 'main_file'],
            'level': 'WARNING',
            'propagate': False,
        },
        # Django DB backend logger
        'django.db.backends': {
            'handlers': ['main_file'],
            'level': 'WARNING',
            'propagate': False,
        },
        # Django server logger
        'django.server': {
            'handlers': ['main_file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        # Accounts app - authentication logging
        'accounts': {
            'handlers': ['auth_file', 'main_file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        # Books app logging
        'books': {
            'handlers': ['main_file', 'console'],
            'level': 'DEBUG',
            'propagate': True,
        },
        # Payments app - payment transaction logging
        'payments': {
            'handlers': ['payment_file', 'main_file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        # Workflow logging
        'workflow': {
            'handlers': ['main_file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        # Core app logging
        'core': {
            'handlers': ['main_file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        # Notifications logging
        'notifications': {
            'handlers': ['main_file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        # Reviews logging
        'reviews': {
            'handlers': ['main_file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# =============================================
# 18. FAYDA UAT OIDC SETTINGS
# =============================================
# Values can be overridden via .env. Redirect URI MUST match Fayda portal exactly.

FAYDA_CLIENT_ID = config(
    'FAYDA_CLIENT_ID',
    default='crXYIYg2cJiNTaw5t-peoPzCRo-3JATNfBd5A86U8t0',
)
FAYDA_AUTH_URL = config(
    'FAYDA_AUTH_URL',
    default='https://esignet.ida.fayda.et/authorize',
)
FAYDA_TOKEN_URL = config(
    'FAYDA_TOKEN_URL',
    default='https://esignet.ida.fayda.et/v1/esignet/oauth/v2/token',
)
FAYDA_USERINFO_URL = config(
    'FAYDA_USERINFO_URL',
    default='https://esignet.ida.fayda.et/v1/esignet/oidc/userinfo',
)
# CRITICAL: must match EXACTLY what is registered in the Fayda portal
FAYDA_REDIRECT_URI = config(
    'FAYDA_REDIRECT_URI',
    default='http://localhost:3000/callback',
)
FAYDA_PRIVATE_KEY_B64 = config('FAYDA_PRIVATE_KEY_B64', default='')
FAYDA_ALGORITHM = config('FAYDA_ALGORITHM', default='RS256')
FAYDA_CLIENT_ASSERTION_TYPE = config(
    'FAYDA_CLIENT_ASSERTION_TYPE',
    default='urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
)
FAYDA_EXPIRATION_TIME = config('FAYDA_EXPIRATION_TIME', default=15, cast=int)
FAYDA_TEST_NATIONAL_ID = config('FAYDA_TEST_NATIONAL_ID', default='3126894653473958')
FAYDA_TEST_OTP = config('FAYDA_TEST_OTP', default='111111')

# =============================================
# 19. TELEBIRR SETTINGS
# =============================================

TELEBIRR_BASE_URL = config('TELEBIRR_BASE_URL', default='https://196.188.120.3:38443/apiaccess/payment/gateway')
TELEBIRR_FABRIC_APP_ID = config('TELEBIRR_FABRIC_APP_ID', default='c4182ef8-9249-458a-985e-06d191f4d505')
TELEBIRR_APP_SECRET = config('TELEBIRR_APP_SECRET', default='fad0f06383c6297f545876694b974599')
TELEBIRR_MERCHANT_APP_ID = config('TELEBIRR_MERCHANT_APP_ID', default='930231098009602')
TELEBIRR_MERCHANT_CODE = config('TELEBIRR_MERCHANT_CODE', default='101011')
TELEBIRR_PRIVATE_KEY = config('TELEBIRR_PRIVATE_KEY', default='')
TELEBIRR_PUBLIC_KEY = config('TELEBIRR_PUBLIC_KEY', default='')
TELEBIRR_VERIFY_SSL = config('TELEBIRR_VERIFY_SSL', default=False, cast=bool)
TELEBIRR_ENABLED = config('TELEBIRR_ENABLED', default=True, cast=bool)
USE_SIMULATED_PAYMENT = False

TELEBIRR_APP_ID = TELEBIRR_FABRIC_APP_ID
TELEBIRR_APP_KEY = TELEBIRR_APP_SECRET
TELEBIRR_SHORT_CODE = TELEBIRR_MERCHANT_CODE
TELEBIRR_API_URL = TELEBIRR_BASE_URL

TELEBIRR_CALLBACK_URL = config('TELEBIRR_CALLBACK_URL', default=f"{BASE_URL}/books/telebirr/callback/")
TELEBIRR_RETURN_URL = config('TELEBIRR_RETURN_URL', default=f"{BASE_URL}/books/telebirr/return/")

# =============================================
# 20. CBE BIRR SETTINGS
# =============================================

CBE_MERCHANT_ID = config('CBE_MERCHANT_ID', default='')
CBE_TERMINAL_ID = config('CBE_TERMINAL_ID', default='')
CBE_PUBLIC_KEY = config('CBE_PUBLIC_KEY', default='')
CBE_API_URL = config('CBE_API_URL', default='')

# =============================================
# 21. CUSTOM SETTINGS
# =============================================

APP_NAME = config('APP_NAME', default='Abay Repository')
APP_VERSION = config('APP_VERSION', default='1.0.0')
SITE_URL = config('SITE_URL', default='http://localhost:3000')

ROYALTY_COMMISSION_RATE = 30
MINIMUM_PAYOUT_AMOUNT = 100

MAX_BOOK_TITLE_LENGTH = 255
MAX_BOOK_DESCRIPTION_LENGTH = 5000
BOOKS_PER_PAGE = 12

MIN_CHECKER_SCORE = 0
MAX_CHECKER_SCORE = 10
PASSING_CHECKER_SCORE = 7

ROYALTY_RATE = config('ROYALTY_RATE', default=70, cast=int)
TAX_THRESHOLD = config('TAX_THRESHOLD', default=500, cast=int)

# =============================================
# 22. ENSURE DIRECTORIES
# =============================================

LOGS_DIR = os.path.join(BASE_DIR, 'logs')
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR, mode=0o755)

TMP_DIR = os.path.join(BASE_DIR, 'tmp')
if not os.path.exists(TMP_DIR):
    os.makedirs(TMP_DIR, mode=0o755)

STATIC_ROOT_DIR = os.path.join(BASE_DIR, 'staticfiles')
if not os.path.exists(STATIC_ROOT_DIR):
    os.makedirs(STATIC_ROOT_DIR, mode=0o755)

MEDIA_ROOT_DIR = os.path.join(BASE_DIR, 'media')
if not os.path.exists(MEDIA_ROOT_DIR):
    os.makedirs(MEDIA_ROOT_DIR, mode=0o755)

# =============================================
# 23. LOAD ENVIRONMENT VARIABLES
# =============================================

try:
    from dotenv import load_dotenv
    env_path = BASE_DIR / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded environment variables from: {env_path}")
except ImportError:
    pass

# =============================================
# 24. STARTUP MESSAGE
# =============================================



# =============================================
# PAYMENT GATEWAYS (Telebirr / Chapa / PayPal)
# =============================================

TELEBIRR_CONFIG = {
    "BASE_URL": config(
        "TELEBIRR_BASE_URL",
        default="https://developerportal.ethiotelebirr.et:38443/apiaccess/payment/gateway",
    ),
    "PRODUCTION_BASE_URL": config(
        "TELEBIRR_PRODUCTION_BASE_URL",
        default="https://superapp.ethiomobilemoney.et:38443/apiaccess/payment/gateway",
    ),
    "FABRIC_APP_ID": config("TELEBIRR_FABRIC_APP_ID", default=""),
    "APP_SECRET": config("TELEBIRR_APP_SECRET", default=""),
    "MERCHANT_APP_ID": config("TELEBIRR_MERCHANT_APP_ID", default=""),
    "MERCHANT_CODE": config("TELEBIRR_MERCHANT_CODE", default=""),
    "PRIVATE_KEY": config("TELEBIRR_PRIVATE_KEY", default=""),
    "PUBLIC_KEY": config("TELEBIRR_PUBLIC_KEY", default=""),
    "NOTIFY_URL": config("TELEBIRR_NOTIFY_URL", default=f"{BASE_URL}/payments/telebirr/notify/"),
    "RETURN_URL": config("TELEBIRR_RETURN_URL", default=f"{BASE_URL}/payments/return/"),
    "TOKEN_PATH": config("TELEBIRR_TOKEN_PATH", default="/payment/v1/token"),
    "TIMEOUT": 30,
}

CHAPA_CONFIG = {
    # Live secret key from https://dashboard.chapa.co (CHASECK_LIVE-... for production)
    "SECRET_KEY": config("CHAPA_SECRET_KEY", default=""),
    "PUBLIC_KEY": config("CHAPA_PUBLIC_KEY", default=""),
    "WEBHOOK_SECRET": config("CHAPA_WEBHOOK_SECRET", default=""),  # optional; defaults to SECRET_KEY
    "CURRENCY": config("CHAPA_CURRENCY", default="ETB"),
    "CALLBACK_URL": config("CHAPA_CALLBACK_URL", default=f"{BASE_URL}/payments/chapa/callback/"),
    "RETURN_URL": config("CHAPA_RETURN_URL", default=f"{BASE_URL}/payments/return/"),
}

PAYPAL_CONFIG = {
    "CLIENT_ID": config("PAYPAL_CLIENT_ID", default=""),
    "CLIENT_SECRET": config("PAYPAL_CLIENT_SECRET", default=""),
    "MODE": config("PAYPAL_MODE", default="sandbox"),  # sandbox | live
    "RETURN_URL": config("PAYPAL_RETURN_URL", default=f"{BASE_URL}/payments/paypal/return/"),
    "CANCEL_URL": config("PAYPAL_CANCEL_URL", default=f"{BASE_URL}/payments/return/"),
    "CURRENCY": config("PAYPAL_CURRENCY", default="USD"),
    "TIMEOUT": 30,
}

# =============================================
# 24. STARTUP SUMMARY (via logging, not print)
# =============================================

import logging as _startup_logging
_startup_log = _startup_logging.getLogger('django.server')
_startup_log.info(
    "Abay Repository starting | DEBUG=%s | DB=%s@%s | EMAIL=%s | HSTS=%ss",
    DEBUG,
    DATABASES['default']['NAME'],
    DATABASES['default']['HOST'],
    EMAIL_BACKEND.split('.')[-1],
    SECURE_HSTS_SECONDS,
)

# =============================================
# 25. CREATE LOGS.TXT IF NOT EXISTS
# =============================================

if not os.path.exists(LOG_FILE_PATH):
    try:
        with open(LOG_FILE_PATH, 'w', encoding='utf-8') as f:
            from datetime import datetime
            f.write(f"# Abay Repository Log File\n")
            f.write(f"# Created: {datetime.now().isoformat()}\n")
            f.write(f"# {'='*60}\n\n")
            f.write(f"# Logging started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# {'='*60}\n\n")
    except Exception as e:
        print(f"Warning: Could not create log file: {e}")
# Ensure PayPal config picks up env even if defined earlier empty
try:
    PAYPAL_CONFIG = dict(PAYPAL_CONFIG)
    PAYPAL_CONFIG['CLIENT_ID'] = PAYPAL_CONFIG.get('CLIENT_ID') or config('PAYPAL_CLIENT_ID', default='')
    PAYPAL_CONFIG['CLIENT_SECRET'] = PAYPAL_CONFIG.get('CLIENT_SECRET') or config('PAYPAL_CLIENT_SECRET', default='')
    PAYPAL_CONFIG['MODE'] = PAYPAL_CONFIG.get('MODE') or config('PAYPAL_MODE', default='sandbox')
    PAYPAL_CONFIG['CURRENCY'] = PAYPAL_CONFIG.get('CURRENCY') or config('PAYPAL_CURRENCY', default='USD')
except NameError:
    PAYPAL_CONFIG = {
        'CLIENT_ID': config('PAYPAL_CLIENT_ID', default=''),
        'CLIENT_SECRET': config('PAYPAL_CLIENT_SECRET', default=''),
        'MODE': config('PAYPAL_MODE', default='sandbox'),
        'CURRENCY': config('PAYPAL_CURRENCY', default='USD'),
    }

CHAPA_REQUIRE_WEBHOOK_SIGNATURE = config('CHAPA_REQUIRE_WEBHOOK_SIGNATURE', default=True, cast=bool)
