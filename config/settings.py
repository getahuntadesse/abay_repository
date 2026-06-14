"""
Django settings for config project.
Updated for MySQL (XAMPP) - Abay Repository
"""

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-8x!q9@3k#m$5n&7p%2w*e4r6t8y0u1i2o3p4a5s6d7f8g9h0j1k2l3z4x5c6v7b8'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    
    # Third party apps
    'crispy_forms',
    'crispy_bootstrap5',
    'widget_tweaks',  # Add this for form styling
    
    # Local apps
    'accounts',
    'books',
    'reviews',
    'payments',
    'royalties',
    'notifications',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
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

# ==================================================
# DATABASE CONFIGURATION - MYSQL (XAMPP)
# ==================================================

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'abay_repository',      # Database name
        'USER': 'root',                  # XAMPP default username
        'PASSWORD': '',                  # XAMPP default has no password
        'HOST': 'localhost',             # Or '127.0.0.1'
        'PORT': '3306',                  # Default MySQL port
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            'charset': 'utf8mb4',
        },
    }
}

# ==================================================
# PASSWORD VALIDATION
# ==================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# ==================================================
# INTERNATIONALIZATION
# ==================================================

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Addis_Ababa'
USE_I18N = True
USE_TZ = True

# ==================================================
# STATIC & MEDIA FILES
# ==================================================

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ==================================================
# CUSTOM USER MODEL
# ==================================================

AUTH_USER_MODEL = 'accounts.CustomUser'

# ==================================================
# LOGIN/REDIRECT SETTINGS
# ==================================================

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

# ==================================================
# DEFAULT PRIMARY KEY FIELD TYPE
# ==================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==================================================
# EMAIL CONFIGURATION
# ==================================================

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# ==================================================
# FILE UPLOAD SETTINGS
# ==================================================

DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000
FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB

# ==================================================
# SESSION SETTINGS
# ==================================================

SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# ==================================================
# CSRF & SECURITY
# ==================================================

CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]

# ==================================================
# CRISPY FORMS
# ==================================================

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# ==================================================
# MESSAGE STORAGE
# ==================================================

MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'

# ==================================================
# AUTHENTICATION BACKENDS
# ==================================================

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]