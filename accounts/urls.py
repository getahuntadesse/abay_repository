from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('register/author/', views.register_author, name='register_author'),
    path('register/client/', views.register_view, name='register_client'),
    
    # Fayda OIDC Verification
    path('api/fayda/oidc/initiate/', views.oidc_initiate, name='fayda_oidc_initiate'),
    path('api/fayda/oidc/callback/', views.oidc_callback, name='fayda_oidc_callback'),
    path('api/fayda/verify/', views.verify_fayda_id, name='verify_fayda_id'),
    
    # Dashboards
    path('dashboard/', views.dashboard_redirect, name='dashboard'),
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/author/', views.author_dashboard, name='author_dashboard'),
    path('dashboard/checker/', views.checker_dashboard, name='checker_dashboard'),
    path('dashboard/maker/', views.maker_dashboard, name='maker_dashboard'),
    path('dashboard/client/', views.client_dashboard, name='client_dashboard'),
    
    # Checker Actions
    path('checker/process-review/', views.process_checker_review, name='process_checker_review'),
    path('checker/review-book/<int:book_id>/', views.view_book_for_review, name='view_book_for_review'),
    
    # Maker Actions
    path('maker/publish/<int:book_id>/', views.publish_book, name='publish_book'),
    
    # Profile
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
]