# accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import CustomUser, AuthorProfile, ClientProfile


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = CustomUser
        fields = '__all__'


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'full_name', 'phone', 'role')


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm
    
    # List display fields
    list_display = [
        'id', 
        'username', 
        'email', 
        'full_name', 
        'role_badge',
        'payment_methods_status',
        'is_active_badge', 
        'is_staff', 
        'date_joined'
    ]
    
    # List filter
    list_filter = [
        'role', 
        'is_active', 
        'is_staff', 
        'is_superuser',
        'email_verified',
        'phone_verified',
        'two_factor_enabled',
        'date_joined'
    ]
    
    # Search fields
    search_fields = [
        'username', 
        'email', 
        'full_name', 
        'phone',
        'national_id',
        'telebirr_phone',
        'cbe_account_number',
        'id'
    ]
    
    # Ordering
    ordering = ('-date_joined',)
    
    # Fields that should be read-only (can't be edited)
    readonly_fields = (
        'last_login', 
        'date_joined', 
        'created_at', 
        'updated_at',
        'last_seen'
    )
    
    # Fieldsets for detail/edit view
    fieldsets = (
        (None, {
            'fields': ('username', 'password')
        }),
        (_('Personal Information'), {
            'fields': (
                'full_name', 
                'email', 
                'phone', 
                'national_id', 
                'national_id_verified',
                'date_of_birth',
                'gender',
                'address',
                'bio', 
                'profile_image'
            )
        }),
        (_('Location'), {
            'fields': ('region', 'zone', 'woreda'),
            'classes': ('collapse',)
        }),
        (_('Role & Permissions'), {
            'fields': (
                'role', 
                'is_active', 
                'is_staff', 
                'is_superuser',
                'groups', 
                'user_permissions'
            ),
            'description': 'Select the user role. Admin has full access, Maker publishes books, Checker reviews books, Author uploads books, Client reads books.'
        }),
        (_('Verification'), {
            'fields': (
                'email_verified', 
                'email_verification_token',
                'verification_token_expires',
                'phone_verified'
            ),
            'classes': ('collapse',)
        }),
        (_('Security'), {
            'fields': (
                'login_attempts', 
                'locked_until', 
                'two_factor_enabled',
                'two_factor_verified',
                'two_factor_secret',
                'two_factor_backup_codes',
                'last_login_ip'
            ),
            'classes': ('collapse',)
        }),
        # =============================================
        # PAYMENT DETAILS FOR AUTHORS
        # =============================================
        (_('Payment Details - Telebirr'), {
            'fields': ('telebirr_phone', 'telebirr_name'),
            'classes': ('collapse',),
            'description': 'Telebirr payment details for author payouts'
        }),
        (_('Payment Details - CBE Birr'), {
            'fields': ('cbe_account_number', 'cbe_account_name', 'cbe_bank_branch'),
            'classes': ('collapse',),
            'description': 'CBE Birr payment details for author payouts'
        }),
        (_('Payment Details - Bank Transfer'), {
            'fields': ('bank_name', 'bank_account_number', 'bank_account_name', 'bank_branch'),
            'classes': ('collapse',),
            'description': 'Bank transfer details for author payouts'
        }),
        (_('Tax Information'), {
            'fields': ('tax_id_number', 'tax_registration_number'),
            'classes': ('collapse',),
            'description': 'Tax identification information'
        }),
        (_('Important Dates'), {
            'fields': ('last_login', 'date_joined', 'last_seen', 'created_at', 'updated_at'),
            'classes': ('collapse',),
            'description': 'These dates are automatically set and cannot be edited.'
        }),
    )
    
    # Fields for adding a new user
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username', 
                'email', 
                'full_name', 
                'phone',
                'role', 
                'password1', 
                'password2',
                'is_active', 
                'is_staff', 
                'is_superuser'
            )
        }),
    )
    
    # Custom actions
    actions = [
        'make_active', 
        'make_inactive', 
        'make_admin', 
        'make_maker', 
        'make_checker', 
        'make_author',
        'make_client'
    ]
    
    # Override get_form to ensure non-editable fields are excluded
    def get_form(self, request, obj=None, **kwargs):
        """
        Override get_form to exclude non-editable fields from the form.
        """
        form = super().get_form(request, obj, **kwargs)
        # Remove non-editable fields from the form if they exist
        non_editable_fields = ['created_at', 'updated_at']
        for field in non_editable_fields:
            if field in form.base_fields:
                del form.base_fields[field]
        return form
    
    def role_badge(self, obj):
        """Display role with color coded badge"""
        role_colors = {
            'admin': '#dc3545',      # Red
            'maker': '#0d6efd',      # Blue
            'checker': '#fd7e14',    # Orange
            'author': '#28a745',     # Green
            'client': '#6c757d',     # Gray
        }
        role_labels = {
            'admin': '👑 Admin',
            'maker': '🔧 Maker',
            'checker': '🔍 Checker',
            'author': '✍️ Author',
            'client': '📖 Client',
        }
        color = role_colors.get(obj.role, '#6c757d')
        label = role_labels.get(obj.role, obj.role)
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 12px; font-size: 12px; font-weight: 600;">{}</span>',
            color,
            label
        )
    role_badge.short_description = 'Role'
    
    def is_active_badge(self, obj):
        """Display active status with color coded badge"""
        if obj.is_active:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; '
                'border-radius: 12px; font-size: 12px; font-weight: 600;">✅ Active</span>'
            )
        return format_html(
            '<span style="background-color: #dc3545; color: white; padding: 3px 10px; '
            'border-radius: 12px; font-size: 12px; font-weight: 600;">❌ Inactive</span>'
        )
    is_active_badge.short_description = 'Status'
    
    def payment_methods_status(self, obj):
        """Display available payment methods with icons"""
        methods = []
        # Check if payment methods exist using the model's method
        if hasattr(obj, 'has_payment_method'):
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
        
        # Fallback: check fields directly
        if not methods:
            if obj.telebirr_phone:
                methods.append(format_html(
                    '<span style="color: #28a745; margin-right: 5px;">📱 Telebirr</span>'
                ))
            if obj.cbe_account_number:
                methods.append(format_html(
                    '<span style="color: #0d6efd; margin-right: 5px;">🏦 CBE</span>'
                ))
            if obj.bank_account_number:
                methods.append(format_html(
                    '<span style="color: #6c757d; margin-right: 5px;">🏛️ Bank</span>'
                ))
        
        if not methods:
            return format_html('<span style="color: #dc3545;">⚠️ No payment method</span>')
        
        return format_html(' '.join(methods))
    payment_methods_status.short_description = 'Payment Methods'
    
    # Actions implementation
    def make_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} user(s) activated.")
    make_active.short_description = "✅ Activate selected users"
    
    def make_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} user(s) deactivated.")
    make_inactive.short_description = "❌ Deactivate selected users"
    
    def make_admin(self, request, queryset):
        updated = queryset.update(role='admin', is_staff=True, is_superuser=True)
        self.message_user(request, f"{updated} user(s) set to Admin.")
    make_admin.short_description = "👑 Set role to Admin"
    
    def make_maker(self, request, queryset):
        updated = queryset.update(role='maker', is_staff=True, is_superuser=False)
        self.message_user(request, f"{updated} user(s) set to Maker.")
    make_maker.short_description = "🔧 Set role to Maker"
    
    def make_checker(self, request, queryset):
        updated = queryset.update(role='checker', is_staff=True, is_superuser=False)
        self.message_user(request, f"{updated} user(s) set to Checker.")
    make_checker.short_description = "🔍 Set role to Checker"
    
    def make_author(self, request, queryset):
        updated = queryset.update(role='author', is_staff=False, is_superuser=False)
        self.message_user(request, f"{updated} user(s) set to Author.")
    make_author.short_description = "✍️ Set role to Author"
    
    def make_client(self, request, queryset):
        updated = queryset.update(role='client', is_staff=False, is_superuser=False)
        self.message_user(request, f"{updated} user(s) set to Client.")
    make_client.short_description = "📖 Set role to Client"
    
    # Override save to handle superuser status
    def save_model(self, request, obj, form, change):
        if obj.role == 'admin':
            obj.is_staff = True
            obj.is_superuser = True
        elif obj.role in ['maker', 'checker']:
            obj.is_staff = True
            obj.is_superuser = False
        else:
            obj.is_staff = False
            obj.is_superuser = False
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related()


@admin.register(AuthorProfile)
class AuthorProfileAdmin(admin.ModelAdmin):
    list_display = [
        'id', 
        'user_link', 
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
        'user__cbe_account_number',
        'user__username'
    ]
    
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        (_('Author Information'), {
            'fields': ('user', 'author_pseudonym', 'bio', 'website', 'author_image')
        }),
        (_('Social Media'), {
            'fields': ('facebook_url', 'twitter_url', 'instagram_url', 'linkedin_url'),
            'classes': ('collapse',)
        }),
        (_('Banking Details'), {
            'fields': ('bank_account_name', 'bank_account_number', 'bank_name', 'tax_id', 'tin_number'),
            'classes': ('collapse',)
        }),
        (_('Verification'), {
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
        (_('Earnings & Commission'), {
            'fields': (
                'commission_rate', 
                'total_royalties_earned', 
                'total_paid', 
                'pending_payout',
                'last_payment_date'
            ),
            'classes': ('collapse',)
        }),
        (_('Statistics'), {
            'fields': ('total_books_published', 'total_downloads', 'average_rating'),
            'classes': ('collapse',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def user_link(self, obj):
        """Display user with link to admin change page"""
        url = f"/admin/accounts/customuser/{obj.user.id}/change/"
        return format_html(
            '<a href="{}" style="font-weight: 600;">{} ({})</a>',
            url,
            obj.user.full_name or obj.user.username,
            obj.user.email
        )
    user_link.short_description = 'User'
    
    def verification_status_colored(self, obj):
        """Display verification status with color coding"""
        colors = {
            'not_submitted': '#6c757d',
            'pending': '#ffc107',
            'verified': '#28a745',
            'rejected': '#dc3545',
        }
        labels = {
            'not_submitted': '📋 Not Submitted',
            'pending': '⏳ Pending',
            'verified': '✅ Verified',
            'rejected': '❌ Rejected',
        }
        color = colors.get(obj.verification_status, '#6c757d')
        label = labels.get(obj.verification_status, obj.verification_status)
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 3px 10px; '
            'border-radius: 12px; font-size: 11px; font-weight: 600; display: inline-block;">{}</span>',
            color,
            'white' if obj.verification_status != 'pending' else 'black',
            label
        )
    verification_status_colored.short_description = 'Verification'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'verified_by')


@admin.register(ClientProfile)
class ClientProfileAdmin(admin.ModelAdmin):
    list_display = [
        'id', 
        'user_link', 
        'phone_number',
        'wallet_balance_display',
        'total_purchases', 
        'total_spent_display', 
        'newsletter_subscribed_badge',
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
        'user__phone',
        'user__username'
    ]
    
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        (_('Client Information'), {
            'fields': ('user', 'phone_number')
        }),
        (_('Wallet & Purchases'), {
            'fields': ('wallet_balance', 'total_purchases', 'total_spent')
        }),
        (_('Preferences'), {
            'fields': ('preferred_genres', 'newsletter_subscribed')
        }),
        (_('Verification'), {
            'fields': ('national_id_verified',),
            'classes': ('collapse',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def user_link(self, obj):
        """Display user with link to admin change page"""
        url = f"/admin/accounts/customuser/{obj.user.id}/change/"
        return format_html(
            '<a href="{}" style="font-weight: 600;">{} ({})</a>',
            url,
            obj.user.full_name or obj.user.username,
            obj.user.email
        )
    user_link.short_description = 'User'
    
    def wallet_balance_display(self, obj):
        """Display wallet balance with currency"""
        return format_html(
            '<strong style="color: #28a745;">{:.2f} ETB</strong>',
            obj.wallet_balance
        )
    wallet_balance_display.short_description = 'Balance'
    
    def total_spent_display(self, obj):
        """Display total spent with currency"""
        return format_html(
            '<strong>{:.2f} ETB</strong>',
            obj.total_spent
        )
    total_spent_display.short_description = 'Total Spent'
    
    def newsletter_subscribed_badge(self, obj):
        """Display newsletter subscription status"""
        if obj.newsletter_subscribed:
            return format_html(
                '<span style="color: #28a745;">✅ Subscribed</span>'
            )
        return format_html(
            '<span style="color: #6c757d;">❌ Unsubscribed</span>'
        )
    newsletter_subscribed_badge.short_description = 'Newsletter'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


# =============================================
# CUSTOM ADMIN SITE CONFIGURATION
# =============================================

# Set admin site headers
admin.site.site_header = 'Abay Repository Admin'
admin.site.site_title = 'Abay Repository'
admin.site.index_title = 'Dashboard'