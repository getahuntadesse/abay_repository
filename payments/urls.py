# payments/urls.py - Production ready with multi-gateway checkout
from django.urls import path
from . import views
from . import views_checkout

app_name = 'payments'

urlpatterns = [
    # Dashboard & history
    path('dashboard/', views.payment_dashboard, name='dashboard'),
    path('history/', views.payment_history, name='payment_history'),

    # Legacy purchase endpoint (kept for compatibility)
    path('purchase/<int:book_id>/', views.purchase_book, name='purchase_book'),
    path('download/<int:book_id>/', views.download_book, name='download_book'),  # redirects to reader

    # ===== New unified create-order (returns checkOutUrl) =====
    path('create/order/', views_checkout.create_order, name='create_order'),
    path('create/order', views_checkout.create_order),  # no trailing slash alias

    # Gateway callbacks / returns
    path('telebirr/notify/', views_checkout.telebirr_notify, name='telebirr_notify'),
    path('chapa/callback/', views_checkout.chapa_callback, name='chapa_callback'),
    path('chapa/webhook/', views_checkout.chapa_webhook, name='chapa_webhook'),
    path('paypal/return/', views_checkout.paypal_return, name='paypal_return'),
    path('paypal/create-order/', views_checkout.paypal_create_order_js, name='paypal_create_order_js'),
    path('paypal/capture-order/', views_checkout.paypal_capture_order_js, name='paypal_capture_order_js'),
    path('return/', views_checkout.payment_return, name='payment_return'),

    # Legacy callbacks (still routed)
    path('callback/', views.payment_callback, name='payment_callback'),
    # path('simulate/<str:transaction_id>/', views.simulate_payment, name='simulate_payment'),  # DISABLED

    # Author payments
    path('author/', views.author_payments, name='author_payments'),
    path('author/<int:author_id>/', views.author_payment_detail, name='author_detail'),
    path('author/<int:author_id>/process/', views.process_author_payment, name='process_author'),
    path('payment/<int:payment_id>/', views.payment_detail, name='payment_detail'),
    path('calculate_all/', views.calculate_all_payments, name='calculate_all'),
    path('api/process_batch/', views.process_batch_payment, name='process_batch'),
]
