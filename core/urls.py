# core/urls.py
"""
URL configuration for core app.
"""

from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # CSP Report Endpoint
    path('csp-report/', views.csp_report, name='csp_report'),
    
    # Security Headers Check
    path('security-headers/', views.security_headers_check, name='security_headers_check'),
]