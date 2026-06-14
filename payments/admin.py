from django.contrib import admin
from .models import Purchase  # Remove PaymentTransaction if it doesn't exist

@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ['id', 'transaction_id', 'book', 'client', 'amount', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['transaction_id', 'book__title', 'client__email']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Transaction Information', {
            'fields': ('transaction_id', 'book', 'client', 'amount')
        }),
        ('Status', {
            'fields': ('status', 'completed_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )