# config/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from accounts.views import home_view
from config.views import admin_logs, admin_logs_export, admin_logs_stream, reader_service_worker

urlpatterns = [
    # ============================================
    # ADMIN
    # ============================================
    # Must be before admin.site.urls so /admin/logs/ is not swallowed
    path('admin/logs/', admin_logs, name='admin_logs_legacy'),
    path('admin/', admin.site.urls),
    
    # ============================================
    # HOME
    # ============================================
    path('', home_view, name='home'),
    path('reader-sw.js', reader_service_worker, name='reader_sw'),

    # Admin system logs API (used by admin dashboard)
    path('api/admin/logs/', admin_logs, name='admin_logs'),
    path('api/admin/logs/export/', admin_logs_export, name='admin_logs_export'),
    path('api/admin/logs/stream/', admin_logs_stream, name='admin_logs_stream'),
    
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
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    try:
        import debug_toolbar
        urlpatterns = [path('__debug__/', include(debug_toolbar.urls))] + urlpatterns
    except ImportError:
        pass
