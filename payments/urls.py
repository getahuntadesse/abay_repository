# payments/urls.py - Multi-gateway (Telebirr, Chapa, PayPal)
from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.payment_dashboard, name='dashboard'),
    path('history/', views.payment_history, name='payment_history'),

    # Purchase
    path('purchase/<int:book_id>/', views.purchase_book, name='purchase_book'),
    path('download/<int:book_id>/', views.download_book, name='download_book'),

    # Return / simulate (legacy)
    path('callback/', views.payment_callback, name='payment_callback'),
    path('return/', views.payment_return, name='payment_return'),
    path('simulate/<str:transaction_id>/', views.simulate_payment, name='simulate_payment'),

    # Production webhooks
    path('webhook/telebirr/', views.telebirr_webhook, name='webhook_telebirr'),
    path('webhook/chapa/', views.chapa_webhook, name='webhook_chapa'),
    path('webhook/paypal/', views.paypal_webhook, name='webhook_paypal'),
    path('paypal/capture/', views.paypal_capture_view, name='paypal_capture'),
    path('paypal/return/', views.paypal_return, name='paypal_return'),

    # Author payments
    path('author/', views.author_payments, name='author_payments'),
    path('author/<int:author_id>/', views.author_payment_detail, name='author_detail'),
    path('author/<int:author_id>/process/', views.process_author_payment, name='process_author'),
    path('author/<int:author_id>/payout-info/', views.author_payout_info, name='author_payout_info'),
    path('author/<int:author_id>/mark-paid/', views.mark_author_payments_paid, name='mark_author_paid'),

    # Payment details
    path('payment/<int:payment_id>/', views.payment_detail, name='payment_detail'),

    # Admin actions
    path('calculate_all/', views.calculate_all_payments, name='calculate_all'),
    path('api/process_batch/', views.process_batch_payment, name='process_batch'),
    path('finance/confirm-purchase/', views.finance_confirm_purchase, name='finance_confirm_purchase'),

    # Finance officer settings & reports
    path('finance/settings/', views.finance_settings_view, name='finance_settings'),
    path('finance/reports/', views.finance_reports_view, name='finance_reports'),
    path('finance/reports/<int:report_id>/', views.finance_report_detail, name='finance_report_detail'),
    path('finance/reports/<int:report_id>/export/<str:fmt>/', views.finance_report_export, name='finance_report_export'),
    path('finance/export/<str:fmt>/', views.finance_export_current, name='finance_export_current'),
]
