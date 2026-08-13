# config/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from accounts.views import home_view

urlpatterns = [
    # ============================================
    # ADMIN
    # ============================================
    path('admin/', admin.site.urls),
    
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
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)