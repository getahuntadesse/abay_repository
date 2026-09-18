# accounts/urls.py
from django.urls import path, reverse_lazy
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
    # FORGOT PASSWORD (email reset – not logged in)
    # ============================================
    path(
        'password-reset/',
        views.AbayPasswordResetView.as_view(),
        name='password_reset',
    ),
    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='accounts/password_reset_done.html',
        ),
        name='password_reset_done',
    ),
    path(
        'password-reset/<uidb64>/<token>/',
        views.AbayPasswordResetConfirmView.as_view(),
        name='password_reset_confirm',
    ),
    path(
        'password-reset/complete/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='accounts/password_reset_complete.html',
        ),
        name='password_reset_complete',
    ),

    # ============================================
    # CHANGE PASSWORD (logged in – all dashboards)
    # ============================================
    path(
        'password-change/',
        auth_views.PasswordChangeView.as_view(
            template_name='accounts/password_change.html',
            success_url=reverse_lazy('accounts:password_change_done'),
        ),
        name='password_change',
    ),
    path(
        'password-change/done/',
        auth_views.PasswordChangeDoneView.as_view(
            template_name='accounts/password_change_done.html',
        ),
        name='password_change_done',
    ),

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
