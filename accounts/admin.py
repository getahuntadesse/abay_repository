# accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import CustomUser, AuthorProfile, ClientProfile


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = [
        'id', 
        'username', 
        'email', 
        'full_name', 
        'role', 
        'payment_methods_status',
        'is_active', 
        'is_staff', 
        'date_joined'
    ]
    list_filter = [
        'role', 
        'is_active', 
        'is_staff', 
        'email_verified',
        'two_factor_enabled'
    ]
    search_fields = [
        'username', 
        'email', 
        'full_name', 
        'phone',
        'telebirr_phone',
        'cbe_account_number'
    ]
    
    fieldsets = UserAdmin.fieldsets + (
        ('Personal Information', {
            'fields': (
                'full_name', 
                'phone', 
                'national_id', 
                'role', 
                'bio', 
                'profile_image',
                'date_of_birth',
                'gender'
            )
        }),
        ('Location', {
            'fields': ('region', 'zone', 'woreda', 'address'),
            'classes': ('collapse',)
        }),
        ('Verification', {
            'fields': (
                'email_verified', 
                'national_id_verified', 
                'phone_verified', 
                'email_verification_token',
                'verification_token_expires'
            ),
            'classes': ('collapse',)
        }),
        ('Security', {
            'fields': (
                'login_attempts', 
                'locked_until', 
                'two_factor_enabled',
                'two_factor_verified',
                'two_factor_secret',
                'two_factor_backup_codes',
                'last_login_ip',
                'last_seen'
            ),
            'classes': ('collapse',)
        }),
        # =============================================
        # PAYMENT DETAILS FOR AUTHORS
        # =============================================
        ('Payment Details - Telebirr', {
            'fields': ('telebirr_phone', 'telebirr_name'),
            'classes': ('collapse',),
            'description': 'Telebirr payment details for author payouts'
        }),
        ('Payment Details - CBE Birr', {
            'fields': ('cbe_account_number', 'cbe_account_name', 'cbe_bank_branch'),
            'classes': ('collapse',),
            'description': 'CBE Birr payment details for author payouts'
        }),
        ('Payment Details - Bank Transfer', {
            'fields': ('bank_name', 'bank_account_number', 'bank_account_name', 'bank_branch'),
            'classes': ('collapse',),
            'description': 'Bank transfer details for author payouts'
        }),
        ('Tax Information', {
            'fields': ('tax_id_number', 'tax_registration_number'),
            'classes': ('collapse',),
            'description': 'Tax identification information'
        }),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Additional Information', {
            'fields': ('full_name', 'phone', 'email', 'role')
        }),
    )
    
    def payment_methods_status(self, obj):
        """Display available payment methods with icons"""
        methods = []
        if obj.has_payment_method('telebirr'):
            methods.append(format_html(
                '<span style="color: #28a745; margin-right: 5px;">📱 Telebirr</span>'
            ))
        if obj.has_payment_method('cbe'):
            methods.append(format_html(
                '<span style="color: #0d6efd; margin-right: 5px;">🏦 CBE</span>'
            ))
        if obj.has_payment_method('bank_transfer'):
            methods.append(format_html(
                '<span style="color: #6c757d; margin-right: 5px;">🏛️ Bank</span>'
            ))
        
        if not methods:
            return format_html('<span style="color: #dc3545;">⚠️ No payment method</span>')
        
        return format_html(' '.join(methods))
    payment_methods_status.short_description = 'Payment Methods'
    
    def get_queryset(self, request):
        return super().get_queryset(request)


@admin.register(AuthorProfile)
class AuthorProfileAdmin(admin.ModelAdmin):
    list_display = [
        'id', 
        'user', 
        'author_pseudonym',
        'verification_status_colored', 
        'total_books_published', 
        'total_royalties_earned',
        'pending_payout',
        'created_at'
    ]
    list_filter = [
        'verification_status', 
        'agreement_signed', 
        'created_at',
        'updated_at'
    ]
    search_fields = [
        'user__email', 
        'user__full_name', 
        'author_pseudonym',
        'user__telebirr_phone',
        'user__cbe_account_number'
    ]
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Author Information', {
            'fields': ('user', 'author_pseudonym', 'bio', 'website', 'author_image')
        }),
        ('Social Media', {
            'fields': ('facebook_url', 'twitter_url', 'instagram_url', 'linkedin_url'),
            'classes': ('collapse',)
        }),
        ('Banking Details', {
            'fields': ('bank_account_name', 'bank_account_number', 'bank_name', 'tax_id', 'tin_number'),
            'classes': ('collapse',)
        }),
        ('Verification', {
            'fields': (
                'verification_status', 
                'agreement_signed', 
                'agreement_signed_at', 
                'verified_by', 
                'verified_at', 
                'verification_documents',
                'agreement_version',
                'author_signature'
            )
        }),
        ('Earnings & Commission', {
            'fields': (
                'commission_rate', 
                'total_royalties_earned', 
                'total_paid', 
                'pending_payout',
                'last_payment_date'
            ),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('total_books_published', 'total_downloads', 'average_rating'),
            'classes': ('collapse',)
        }),
    )
    
    def verification_status_colored(self, obj):
        """Display verification status with color coding"""
        colors = {
            'not_submitted': '#6c757d',
            'pending': '#ffc107',
            'verified': '#28a745',
            'rejected': '#dc3545',
        }
        color = colors.get(obj.verification_status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            color,
            obj.get_verification_status_display()
        )
    verification_status_colored.short_description = 'Verification Status'


@admin.register(ClientProfile)
class ClientProfileAdmin(admin.ModelAdmin):
    list_display = [
        'id', 
        'user', 
        'phone_number',
        'wallet_balance',
        'total_purchases', 
        'total_spent', 
        'newsletter_subscribed',
        'created_at'
    ]
    list_filter = [
        'national_id_verified', 
        'newsletter_subscribed', 
        'created_at',
        'updated_at'
    ]
    search_fields = [
        'user__email', 
        'user__full_name', 
        'phone_number',
        'user__phone'
    ]
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Client Information', {
            'fields': ('user', 'phone_number')
        }),
        ('Wallet & Purchases', {
            'fields': ('wallet_balance', 'total_purchases', 'total_spent')
        }),
        ('Preferences', {
            'fields': ('preferred_genres', 'newsletter_subscribed')
        }),
        ('Verification', {
            'fields': ('national_id_verified',),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


# =============================================
# CUSTOM ADMIN SITE CONFIGURATION
# =============================================

# Set admin site headers
admin.site.site_header = 'Abay Repository Admin'
admin.site.site_title = 'Abay Repository'
admin.site.index_title = 'Dashboard'

# Register CustomUser with the custom admin
# The @admin.register decorator already handles this