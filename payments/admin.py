# payments/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Purchase, Payment, PaymentBatch, PaymentTransaction, FinanceSettings, FinanceReport


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = (
        'id', 
        'user', 
        'book', 
        'amount', 
        'status', 
        'created_at',
        'payment_method',
        'transaction_id'
    )
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('user__username', 'user__email', 'book__title', 'transaction_id')
    readonly_fields = ('transaction_id', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Purchase Information', {
            'fields': ('user', 'book', 'amount', 'status')
        }),
        ('Payment Details', {
            'fields': ('payment_method', 'transaction_id', 'transaction_reference')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ('user', 'book', 'amount')
        return self.readonly_fields


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'author',
        'book',
        'gross_amount',
        'author_royalty',
        'final_amount',
        'status',
        'created_at',
        'tax_rate',
        'is_taxable'
    )
    list_filter = ('status', 'is_taxable', 'created_at', 'tax_rate')
    search_fields = ('author__username', 'author__email', 'book__title')
    readonly_fields = (
        'created_at', 
        'updated_at',
        'author_royalty',
        'abrehot_share',
        'tax_amount',
        'final_amount'
    )
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Payment Information', {
            'fields': ('author', 'book', 'purchase', 'gross_amount', 'status')
        }),
        ('Royalty Breakdown', {
            'fields': ('author_royalty', 'abrehot_share', 'abrehot_share_rate', 'royalty_rate')
        }),
        ('Tax Information', {
            'fields': ('tax_rate', 'tax_amount', 'is_taxable')
        }),
        ('Final Amount', {
            'fields': ('final_amount',)
        }),
        ('Transaction Details', {
            'fields': ('transaction_reference', 'paid_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ('author', 'book', 'purchase', 'gross_amount')
        return self.readonly_fields
    
    def view_purchase_link(self, obj):
        if obj.purchase:
            url = reverse('admin:payments_purchase_change', args=[obj.purchase.id])
            return format_html('<a href="{}">View Purchase #{}</a>', url, obj.purchase.id)
        return '-'
    view_purchase_link.short_description = 'Purchase'
    
    def view_book_link(self, obj):
        if obj.book:
            url = reverse('admin:books_book_change', args=[obj.book.id])
            return format_html('<a href="{}">{}</a>', url, obj.book.title)
        return '-'
    view_book_link.short_description = 'Book'


@admin.register(PaymentBatch)
class PaymentBatchAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'batch_reference',
        'payment_method',
        'total_amount',
        'total_payments',
        'status',
        'processed_by',
        'created_at'
    )
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('batch_reference', 'processed_by__username', 'notes')
    readonly_fields = ('batch_reference', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Batch Information', {
            'fields': ('batch_reference', 'payment_method', 'status')
        }),
        ('Summary', {
            'fields': ('total_amount', 'total_payments')
        }),
        ('Processing Details', {
            'fields': ('processed_by', 'processed_at', 'notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ('batch_reference',)
        return self.readonly_fields


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'batch',
        'payment',
        'amount',
        'status',
        'created_at',
        'transaction_reference'
    )
    list_filter = ('status', 'created_at')
    search_fields = ('batch__batch_reference', 'payment__author__username', 'transaction_reference')
    readonly_fields = ('created_at',)  # <-- FIXED: Only 'created_at' is read-only
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Transaction Information', {
            'fields': ('batch', 'payment', 'amount', 'status')
        }),
        ('Reference Details', {
            'fields': ('transaction_reference', 'response_data', 'error_message')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(FinanceSettings)
class FinanceSettingsAdmin(admin.ModelAdmin):
    list_display = ('id', 'royalty_rate', 'platform_rate', 'tax_rate_default', 'tax_threshold', 'updated_at')

@admin.register(FinanceReport)
class FinanceReportAdmin(admin.ModelAdmin):
    list_display = ('title', 'period_type', 'period_start', 'period_end', 'total_gross', 'generated_at')
    list_filter = ('period_type',)
