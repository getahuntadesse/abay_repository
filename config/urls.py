# config/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.views.generic import RedirectView

# Import views
from books.views import HomeView
from . import views as config_views
from accounts import views as accounts_views

urlpatterns = [
    # Custom Admin URLs
    path('admin/analytics/', config_views.admin_analytics, name='admin_analytics'),
    path('admin/logs/', config_views.admin_logs, name='admin_logs'),
    
    # Default Admin Panel
    path('admin/', admin.site.urls),
    
    # Home Page
    path('', HomeView.as_view(), name='home'),
    
    # Redirect /payment to /payments/dashboard/
    path('payment/', RedirectView.as_view(url='/payments/dashboard/', permanent=False), name='payment_redirect'),
    
    # OIDC Callback
    path('callback/', accounts_views.oidc_callback_view, name='oidc_callback'),
    
    # App URL Includes
    path('accounts/', include('accounts.urls')),
    path('books/', include('books.urls')),
    path('reviews/', include('reviews.urls')),
    path('payments/', include('payments.urls')),
    
    # Password Reset URLs
    path('password-reset/', auth_views.PasswordResetView.as_view(template_name='registration/password_reset_form.html'), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'), name='password_reset_complete'),
]

# Debug Toolbar
if settings.DEBUG:
    try:
        import debug_toolbar
        urlpatterns = [path('__debug__/', include(debug_toolbar.urls))] + urlpatterns
    except ImportError:
        pass

# Static and media file serving
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Custom error handlers for production
if not settings.DEBUG:
    handler404 = 'config.views.handler404'
    handler500 = 'config.views.handler500'
    handler403 = 'config.views.handler403'