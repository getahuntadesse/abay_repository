from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('redirect/', views.dashboard_redirect, name='redirect'),
    path('author/', views.author_dashboard, name='author_dashboard'),
    path('client/', views.client_dashboard, name='client_dashboard'),
    path('checker/', views.checker_dashboard, name='checker_dashboard'),
    path('maker/', views.maker_dashboard, name='maker_dashboard'),
    path('admin/', views.admin_dashboard, name='admin_dashboard'),  # Add this line
]