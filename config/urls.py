# config/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from accounts.views import home_view
from config.views import admin_logs
from books.views import reader_service_worker

urlpatterns = [
    # ============================================
    # ADMIN
    # ============================================
    path('admin/logs/', admin_logs, name='admin_logs'),  # must be before admin.site
    path('sw.js', reader_service_worker, name='reader_sw_root'),
    # SAR 6.3: non-obvious admin path (set ADMIN_URL_PATH in .env, default obfuscated)
    path(
        getattr(settings, 'ADMIN_URL_PATH', 'secure-abay-admin') + '/',
        admin.site.urls,
    ),
    # Legacy /admin/ redirects away (do not expose admin there)
    path('admin/', RedirectView.as_view(url='/', permanent=False)),
    
    # ============================================
    # HOME
    # ============================================
    path('', home_view, name='home'),
    
    # ============================================
    # APPS
    # ============================================
    path('books/', include('books.urls')),
    path('accounts/', include('accounts.urls')),
    path('payments/', include('payments.urls')),
    path('notifications/', include('notifications.urls')),
    path('reviews/', include('reviews.urls')),
    
    # ============================================
    # FAVICON
    # ============================================
    path('favicon.ico', RedirectView.as_view(url='/static/favicon.ico')),
]

# ============================================
# SERVE MEDIA & STATIC FILES IN DEVELOPMENT
# ============================================
from config.views import secure_media_serve
from django.urls import re_path
# Always use secure media handler (never execute SVG/HTML from /media/)
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', secure_media_serve, name='secure_media'),
]
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)