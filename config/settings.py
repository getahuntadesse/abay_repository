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

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1,::1').split(',')

CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='http://localhost:3000,http://127.0.0.1:3000,https://esignet.ida.fayda.et').split(',')

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
    #'royalties',
    'notifications',
    'dashboard',
    'reviews',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

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
# 3. DATABASE CONFIGURATION - FROM .env
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

# Password hashing
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

# Try to use Argon2 if available
try:
    import argon2
    PASSWORD_HASHERS.insert(0, 'django.contrib.auth.hashers.Argon2PasswordHasher')
except ImportError:
    pass

# =============================================
# 6. AUTHENTICATION & SESSION
# =============================================

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

SESSION_COOKIE_AGE = 86400
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = False
SESSION_COOKIE_SAMESITE = 'Lax'  # Changed from Strict for OIDC
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = True

CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = False
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_USE_SESSIONS = True

# =============================================
# 7. SECURE SSL/HTTPS
# =============================================

SECURE_SSL_REDIRECT = False
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
X_FRAME_OPTIONS = 'DENY'

# =============================================
# 8. CORS
# =============================================

CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='http://localhost:3000,http://127.0.0.1:3000,https://esignet.ida.fayda.et').split(',')
CORS_ALLOW_CREDENTIALS = True
CORS_PREFLIGHT_MAX_AGE = 86400

# =============================================
# 9. FILE UPLOAD
# =============================================

FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880
FILE_UPLOAD_PERMISSIONS = 0o644

# =============================================
# 10. STATIC & MEDIA
# =============================================

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# =============================================
# 11. INTERNATIONALIZATION
# =============================================

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Addis_Ababa'
USE_I18N = True
USE_TZ = True

# =============================================
# 12. EMAIL
# =============================================

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_USE_SSL = config('EMAIL_USE_SSL', default=False, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@abay.abrehot.org.et')

# =============================================
# 13. CRISPY FORMS
# =============================================

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# =============================================
# 14. CACHING
# =============================================

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

# =============================================
# 15. 2FA EMAIL SETTINGS
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
# 16. LOGGING
# =============================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
        'secure': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'django.log'),
            'maxBytes': 10485760,
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'security': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'security.log'),
            'maxBytes': 10485760,
            'backupCount': 10,
            'formatter': 'secure',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.security': {
            'handlers': ['security'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# =============================================
# 17. FAYDA OIDC SETTINGS - Using .env variables
# =============================================

# Fayda OIDC Configuration - Direct from .env
FAYDA_CLIENT_ID = config('FAYDA_CLIENT_ID', default='')
FAYDA_AUTH_URL = config('FAYDA_AUTH_URL', default='')
FAYDA_TOKEN_URL = config('FAYDA_TOKEN_URL', default='')
FAYDA_USERINFO_URL = config('FAYDA_USERINFO_URL', default='')
FAYDA_REDIRECT_URI = config('FAYDA_REDIRECT_URI', default='http://localhost:3000/callback/')
FAYDA_PRIVATE_KEY_B64 = config('FAYDA_PRIVATE_KEY_B64', default='')
FAYDA_ALGORITHM = config('FAYDA_ALGORITHM', default='RS256')
FAYDA_CLIENT_ASSERTION_TYPE = config('FAYDA_CLIENT_ASSERTION_TYPE', default='urn:ietf:params:oauth:client-assertion-type:jwt-bearer')
FAYDA_EXPIRATION_TIME = config('FAYDA_EXPIRATION_TIME', default=15, cast=int)
FAYDA_TEST_NATIONAL_ID = config('FAYDA_TEST_NATIONAL_ID', default='')
FAYDA_TEST_OTP = config('FAYDA_TEST_OTP', default='')

# =============================================
# 18. TELEBIRR SETTINGS
# =============================================

TELEBIRR_BASE_URL = config('TELEBIRR_BASE_URL', default='https://196.188.120.3:38443/apiaccess/payment/gateway')
TELEBIRR_FABRIC_APP_ID = config('TELEBIRR_FABRIC_APP_ID', default='c4182ef8-9249-458a-985e-06d191f4d505')
TELEBIRR_APP_SECRET = config('TELEBIRR_APP_SECRET', default='fad0f06383c6297f545876694b974599')
TELEBIRR_MERCHANT_APP_ID = config('TELEBIRR_MERCHANT_APP_ID', default='930231098009602')
TELEBIRR_MERCHANT_CODE = config('TELEBIRR_MERCHANT_CODE', default='101011')
TELEBIRR_PRIVATE_KEY = config('TELEBIRR_PRIVATE_KEY', default='')
TELEBIRR_PUBLIC_KEY = config('TELEBIRR_PUBLIC_KEY', default='')
TELEBIRR_VERIFY_SSL = config('TELEBIRR_VERIFY_SSL', default=False, cast=bool)
TELEBIRR_ENABLED = config('TELEBIRR_ENABLED', default=False, cast=bool)
USE_SIMULATED_PAYMENT = config('USE_SIMULATED_PAYMENT', default=True, cast=bool)

# For backward compatibility
TELEBIRR_APP_ID = TELEBIRR_FABRIC_APP_ID
TELEBIRR_APP_KEY = TELEBIRR_APP_SECRET
TELEBIRR_SHORT_CODE = TELEBIRR_MERCHANT_CODE
TELEBIRR_API_URL = TELEBIRR_BASE_URL

# =============================================
# 19. CBE BIRR SETTINGS
# =============================================

CBE_MERCHANT_ID = config('CBE_MERCHANT_ID', default='')
CBE_TERMINAL_ID = config('CBE_TERMINAL_ID', default='')
CBE_PUBLIC_KEY = config('CBE_PUBLIC_KEY', default='')
CBE_API_URL = config('CBE_API_URL', default='')

# =============================================
# 20. CUSTOM SETTINGS
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

# =============================================
# 21. ENSURE DIRECTORIES
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
# 22. LOAD ENVIRONMENT VARIABLES
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
# 23. STARTUP MESSAGE
# =============================================

print("")
print("============================================================")
print("               ABREHOT LIBRARY - Django Settings")
print("============================================================")
print(f" DEBUG: {str(DEBUG):<8}")
print(f" SECRET_KEY: {'SET' if SECRET_KEY else 'NOT SET':<8}")
print(f" DATABASE: MySQL")
print(f" DB_NAME: {DATABASES['default']['NAME']:<8}")
print(f" DB_HOST: {DATABASES['default']['HOST']:<8}")
print(f" AUTH_USER_MODEL: CustomUser")
print(f" TIME_ZONE: {TIME_ZONE:<8}")
print(f" 2FA: Enabled (Email-based)")
print(f" FAYDA_CLIENT_ID: {'SET' if FAYDA_CLIENT_ID else 'NOT SET':<8}")
print(f" FAYDA_REDIRECT_URI: {FAYDA_REDIRECT_URI}")
print(f" TELEBIRR_APP_ID: {'SET' if TELEBIRR_APP_ID else 'NOT SET':<8}")
print(f" CBE_MERCHANT_ID: {'SET' if CBE_MERCHANT_ID else 'NOT SET':<8}")
print(f" APP_NAME: {APP_NAME:<8}")
print("============================================================")
print("")