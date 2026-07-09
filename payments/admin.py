# payments/admin.py - Simplified Version
from django.contrib import admin
from .models import Purchase, Payment, PaymentBatch, PaymentTransaction


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'book', 'amount', 'status', 'created_at')
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('user__username', 'book__title', 'transaction_id')
    readonly_fields = ('transaction_id', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'author', 'book', 'final_amount', 'status', 'created_at')
    list_filter = ('status', 'is_taxable', 'created_at')
    search_fields = ('author__username', 'book__title')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'


@admin.register(PaymentBatch)
class PaymentBatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'batch_reference', 'total_amount', 'total_payments', 'status', 'created_at')
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('batch_reference', 'processed_by__username')
    readonly_fields = ('batch_reference', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'batch', 'payment', 'amount', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('batch__batch_reference', 'payment__author__username')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'