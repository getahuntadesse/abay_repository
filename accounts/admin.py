from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, AuthorProfile, ClientProfile

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ['id', 'username', 'email', 'full_name', 'role', 'is_active', 'is_staff', 'date_joined']
    list_filter = ['role', 'is_active', 'is_staff', 'email_verified']
    search_fields = ['username', 'email', 'full_name', 'phone']
    
    fieldsets = UserAdmin.fieldsets + (
        ('Additional Information', {
            'fields': ('full_name', 'phone', 'national_id', 'role', 'bio', 'profile_image')
        }),
        ('Location', {
            'fields': ('region', 'zone', 'woreda', 'address'),
            'classes': ('collapse',)
        }),
        ('Verification', {
            'fields': ('email_verified', 'national_id_verified', 'phone_verified', 'email_verification_token'),
            'classes': ('collapse',)
        }),
        ('Security', {
            'fields': ('login_attempts', 'locked_until', 'two_factor_enabled', 'last_login_ip'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Additional Information', {
            'fields': ('full_name', 'phone', 'email', 'role')
        }),
    )


@admin.register(AuthorProfile)
class AuthorProfileAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'verification_status', 'total_books_published', 'total_royalties_earned', 'created_at']
    list_filter = ['verification_status', 'agreement_signed', 'created_at']
    search_fields = ['user__email', 'user__full_name', 'author_pseudonym']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Author Information', {
            'fields': ('user', 'author_pseudonym', 'bio', 'website')
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
            'fields': ('verification_status', 'agreement_signed', 'agreement_signed_at', 
                      'verified_by', 'verified_at', 'verification_documents')
        }),
        ('Earnings', {
            'fields': ('commission_rate', 'total_royalties_earned', 'total_paid', 'pending_payout'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('total_books_published', 'total_downloads', 'average_rating'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ClientProfile)
class ClientProfileAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'total_purchases', 'total_spent', 'newsletter_subscribed', 'created_at']
    list_filter = ['national_id_verified', 'newsletter_subscribed', 'created_at']
    search_fields = ['user__email', 'user__full_name', 'phone_number']
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