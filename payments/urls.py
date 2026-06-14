from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('initiate/', views.initiate_payment, name='initiate'),
    path('telebirr/webhook/', views.telebirr_webhook, name='telebirr_webhook'),
    path('cbe/webhook/', views.cbe_birr_webhook, name='cbe_webhook'),
    path('success/', views.payment_success, name='success'),
    path('cancel/', views.payment_cancel, name='cancel'),
    path('history/', views.payment_history, name='history'),
]