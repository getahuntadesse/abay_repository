# accounts/urls.py
from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Registration
    path('register/client/', views.register_view, name='register_client'),
    path('register/author/', views.register_author, name='register_author'),
    
    # Dashboard
    path('dashboard/', views.dashboard_redirect, name='dashboard_redirect'),
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/finance/', views.finance_dashboard, name='finance_dashboard'),
    path('dashboard/author/', views.author_dashboard, name='author_dashboard'),
    path('dashboard/checker/', views.checker_dashboard, name='checker_dashboard'),
    path('dashboard/maker/', views.maker_dashboard, name='maker_dashboard'),
    path('dashboard/client/', views.client_dashboard, name='client_dashboard'),
    
    # Profile
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    
    # Checker Reviews
    path('review/book/<int:book_id>/', views.view_book_for_review, name='view_book_for_review'),
    path('review/process/', views.process_checker_review, name='process_checker_review'),
    
    # Maker Publishing
    path('publish/book/<int:book_id>/', views.publish_book, name='publish_book'),
    
    # 2FA - Simple placeholder URLs
    path('2fa/setup/', views.setup_2fa, name='2fa_setup'),
    path('2fa/verify/', views.verify_2fa, name='verify_2fa'),
    path('2fa/disable/', views.disable_2fa, name='2fa_disable'),
    path('2fa/backup-codes/', views.backup_codes, name='2fa_backup_codes'),
    
    # Fayda OIDC
    path('api/fayda/oidc/initiate/', views.oidc_initiate, name='oidc_initiate'),
    path('api/fayda/oidc/callback/', views.oidc_callback, name='oidc_callback'),
]