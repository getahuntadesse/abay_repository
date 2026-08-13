# accounts/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'accounts'

urlpatterns = [
    # ============================================
    # AUTHENTICATION
    # ============================================
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # ============================================
    # REGISTRATION
    # ============================================
    path('register/', views.register_view, name='register'),
    path('register/client/', views.register_view, name='register_client'),
    path('register/author/', views.register_author, name='register_author'),
    
    # ============================================
    # PASSWORD RESET
    # ============================================
    path('password-reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='accounts/password_reset.html',
             email_template_name='accounts/password_reset_email.html',
             subject_template_name='accounts/password_reset_subject.txt'
         ),
         name='password_reset'),
    path('password-reset/done/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='accounts/password_reset_done.html'
         ),
         name='password_reset_done'),
    path('password-reset/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='accounts/password_reset_confirm.html'
         ),
         name='password_reset_confirm'),
    path('password-reset/complete/', 
         auth_views.PasswordResetCompleteView.as_view(
             template_name='accounts/password_reset_complete.html'
         ),
         name='password_reset_complete'),
    
    # ============================================
    # DASHBOARD
    # ============================================
    path('dashboard/', views.dashboard_redirect, name='dashboard_redirect'),
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/finance/', views.finance_dashboard, name='finance_dashboard'),
    path('dashboard/author/', views.author_dashboard, name='author_dashboard'),
    path('dashboard/checker/', views.checker_dashboard, name='checker_dashboard'),
    path('dashboard/maker/', views.maker_dashboard, name='maker_dashboard'),
    path('dashboard/client/', views.client_dashboard, name='client_dashboard'),
    
    # ============================================
    # CHECKER REVIEW
    # ============================================
    path('checker/process-review/', views.process_checker_review, name='process_checker_review'),
    path('checker/view-book/<int:book_id>/', views.view_book_for_review, name='view_book_for_review'),
    
    # ============================================
    # PROFILE
    # ============================================
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    
    # ============================================
    # 2FA
    # ============================================
    path('2fa/setup/', views.setup_2fa, name='setup_2fa'),
    path('2fa/verify/', views.verify_2fa, name='verify_2fa'),
    path('2fa/disable/', views.disable_2fa, name='disable_2fa'),
    path('2fa/backup-codes/', views.backup_codes, name='backup_codes'),
    
    # ============================================
    # FAYDA OIDC
    # ============================================
    path('api/fayda/oidc/initiate/', views.oidc_initiate, name='oidc_initiate'),
    path('api/fayda/oidc/callback/', views.oidc_callback, name='oidc_callback'),
    path('callback/', views.oidc_callback_view, name='oidc_callback_view'),
]

# ============================================
# URL PATTERN NAMES REFERENCE
# ============================================
# 
# AUTHENTICATION:
# - accounts:login                  - Login page
# - accounts:logout                 - Logout
# - accounts:register               - Register as client
# - accounts:register_client        - Register as client
# - accounts:register_author        - Register as author
#
# PASSWORD RESET:
# - accounts:password_reset         - Request password reset
# - accounts:password_reset_done    - Reset email sent
# - accounts:password_reset_confirm - Confirm new password
# - accounts:password_reset_complete - Reset complete
#
# DASHBOARD:
# - accounts:dashboard_redirect     - Redirect to role-based dashboard
# - accounts:admin_dashboard        - Admin dashboard
# - accounts:finance_dashboard      - Finance dashboard
# - accounts:author_dashboard       - Author dashboard
# - accounts:checker_dashboard      - Checker dashboard
# - accounts:maker_dashboard        - Maker dashboard
# - accounts:client_dashboard       - Client dashboard
#
# PROFILE:
# - accounts:profile                - User profile
# - accounts:profile_edit           - Edit profile
#
# 2FA:
# - accounts:setup_2fa              - Setup 2FA
# - accounts:verify_2fa             - Verify 2FA
# - accounts:disable_2fa            - Disable 2FA
# - accounts:backup_codes           - Backup codes
#
# FAYDA OIDC:
# - accounts:oidc_initiate          - Initiate OIDC
# - accounts:oidc_callback          - OIDC callback (API)
# - accounts:oidc_callback_view     - OIDC callback (View)