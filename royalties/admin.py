from django.contrib import admin
from .models import PaymentRequest, Royalty

@admin.register(PaymentRequest)
class PaymentRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'author', 'amount', 'payment_method', 'status', 'requested_at']
    list_filter = ['status', 'payment_method', 'requested_at']
    search_fields = ['author__email', 'author__full_name', 'transaction_reference']
    readonly_fields = ['requested_at', 'approved_at', 'processed_at', 'completed_at']
    
    fieldsets = (
        ('Request Information', {
            'fields': ('author', 'amount', 'currency', 'payment_method')
        }),
        ('Payment Details', {
            'fields': ('bank_account_name', 'bank_account_number', 'bank_name', 'telebirr_phone', 'chapa_email'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('status', 'admin_notes', 'user_notes', 'transaction_reference')
        }),
        ('Approval', {
            'fields': ('approved_by', 'approved_at', 'processed_by', 'processed_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_requests', 'mark_as_processed']
    
    def approve_requests(self, request, queryset):
        from django.utils import timezone
        queryset.update(status='approved', approved_at=timezone.now(), approved_by=request.user)
        self.message_user(request, f"{queryset.count()} payment request(s) approved.")
    approve_requests.short_description = "Approve selected payment requests"
    
    def mark_as_processed(self, request, queryset):
        from django.utils import timezone
        queryset.update(status='processed', processed_at=timezone.now(), processed_by=request.user)
        self.message_user(request, f"{queryset.count()} payment request(s) marked as processed.")
    mark_as_processed.short_description = "Mark as processed"


@admin.register(Royalty)
class RoyaltyAdmin(admin.ModelAdmin):
    list_display = ['id', 'book', 'author', 'net_payment', 'status', 'period_start', 'period_end']
    list_filter = ['status', 'payment_date']
    search_fields = ['book__title', 'author__email', 'payment_reference']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Royalty Information', {
            'fields': ('book', 'author', 'purchase')
        }),
        ('Sales Data', {
            'fields': ('total_sales', 'total_revenue', 'platform_fee', 'tax_amount', 'gross_amount')
        }),
        ('Commission', {
            'fields': ('commission_rate', 'commission_amount', 'net_payment')
        }),
        ('Period', {
            'fields': ('period_start', 'period_end')
        }),
        ('Payment', {
            'fields': ('status', 'payment_date', 'payment_reference', 'notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_paid']
    
    def mark_as_paid(self, request, queryset):
        from django.utils import timezone
        queryset.update(status='paid', payment_date=timezone.now())
        self.message_user(request, f"{queryset.count()} royalty(s) marked as paid.")
    mark_as_paid.short_description = "Mark as paid"