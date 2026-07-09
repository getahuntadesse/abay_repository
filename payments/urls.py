# payments/urls.py
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
    path('callback/', views.payment_callback, name='payment_callback'),
    
    # Author Payments
    path('author/', views.author_payments, name='author_payments'),
    path('author/<int:author_id>/', views.author_payment_detail, name='author_detail'),
    path('author/<int:author_id>/process/', views.process_author_payment, name='process_author'),
    
    # Payment Details
    path('payment/<int:payment_id>/', views.payment_detail, name='payment_detail'),
    
    # Admin Actions
    path('calculate_all/', views.calculate_all_payments, name='calculate_all'),
    path('api/process_batch/', views.process_batch_payment, name='process_batch'),
]