# accounts/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.validators import MinLengthValidator, RegexValidator


class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('finance', 'Finance'),
        ('checker', 'Content Checker'),
        ('maker', 'Content Maker'),
        ('author', 'Author'),
        ('client', 'Client'),
    )
    
    # ============================================
    # PERSONAL INFORMATION
    # ============================================
    
    full_name = models.CharField(
        max_length=255, 
        blank=True, 
        default='',
        help_text="Full name of the user"
    )
    national_id = models.CharField(
        max_length=16, 
        unique=True, 
        null=True, 
        blank=True,
        validators=[
            RegexValidator(
                regex=r'^\d{16}$',
                message='National ID must be exactly 16 digits.'
            )
        ],
        help_text="16-digit National ID number"
    )
    national_id_verified = models.BooleanField(
        default=False,
        help_text="Whether the national ID has been verified"
    )
    phone = models.CharField(
        max_length=20, 
        blank=True, 
        default='',
        validators=[
            RegexValidator(
                regex=r'^09\d{8}$',
                message='Phone number must be 10 digits starting with 09.'
            )
        ],
        help_text="Phone number in format 09XXXXXXXX"
    )
    phone_verified = models.BooleanField(
        default=False,
        help_text="Whether the phone number has been verified"
    )
    address = models.TextField(
        blank=True, 
        default='',
        help_text="Physical address of the user"
    )
    
    # Date of Birth - CharField (accepts any format from Fayda)
    date_of_birth = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Date of birth (any format accepted from Fayda)"
    )
    
    # Gender - CharField (accepts any value from Fayda)
    gender = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Gender (any value accepted from Fayda)"
    )
    
    # ============================================
    # LOCATION
    # ============================================
    region = models.CharField(
        max_length=100, 
        blank=True, 
        default='',
        help_text="Region or state"
    )
    zone = models.CharField(
        max_length=100, 
        blank=True, 
        default='',
        help_text="Zone or sub-city"
    )
    woreda = models.CharField(
        max_length=100, 
        blank=True, 
        default='',
        help_text="Woreda or district"
    )
    
    # ============================================
    # ROLE AND STATUS
    # ============================================
    role = models.CharField(
        max_length=20, 
        choices=ROLE_CHOICES, 
        default='client',
        help_text="User role in the system"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether the user account is active"
    )
    email_verified = models.BooleanField(
        default=False,
        help_text="Whether the email has been verified"
    )
    email_verification_token = models.CharField(
        max_length=255, 
        blank=True, 
        default='',
        help_text="Token for email verification"
    )
    verification_token_expires = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Expiration time for verification token"
    )
    
    # ============================================
    # TRACKING
    # ============================================
    last_login_ip = models.GenericIPAddressField(
        null=True, 
        blank=True,
        help_text="IP address of last login"
    )
    last_seen = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Last time the user was seen"
    )
    profile_image = models.ImageField(
        upload_to='profiles/', 
        null=True, 
        blank=True,
        help_text="Profile image of the user"
    )
    bio = models.TextField(
        blank=True, 
        default='',
        help_text="Short biography of the user"
    )
    
    # ============================================
    # PAYMENT DETAILS FOR AUTHORS
    # ============================================
    
    # Telebirr
    telebirr_phone = models.CharField(
        max_length=20, 
        blank=True, 
        null=True, 
        help_text="Telebirr registered phone number"
    )
    telebirr_name = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        help_text="Name on Telebirr account"
    )
    
    # CBE
    cbe_account_number = models.CharField(
        max_length=50, 
        blank=True, 
        null=True, 
        help_text="CBE Birr account number"
    )
    cbe_account_name = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        help_text="Name on CBE account"
    )
    cbe_bank_branch = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        help_text="CBE bank branch"
    )
    
    # Bank Transfer (for other banks)
    bank_name = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text="Bank name for transfers"
    )
    bank_account_number = models.CharField(
        max_length=50, 
        blank=True, 
        null=True,
        help_text="Bank account number"
    )
    bank_account_name = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text="Name on bank account"
    )
    bank_branch = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text="Bank branch"
    )
    
    # Tax information
    tax_id_number = models.CharField(
        max_length=50, 
        blank=True, 
        null=True, 
        help_text="Tax Identification Number"
    )
    tax_registration_number = models.CharField(
        max_length=50, 
        blank=True, 
        null=True,
        help_text="Tax Registration Number"
    )
    
    # ============================================
    # TIMESTAMPS
    # ============================================
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the user was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the user was last updated"
    )
    
    # ============================================
    # SECURITY
    # ============================================
    locked_until = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Account lockout expiration time"
    )
    login_attempts = models.IntegerField(
        default=0,
        help_text="Number of failed login attempts"
    )
    
    # 2FA Fields
    two_factor_enabled = models.BooleanField(
        default=False,
        help_text="Whether 2FA is enabled for the user"
    )
    two_factor_verified = models.BooleanField(
        default=False,
        help_text="Whether 2FA has been verified during current session"
    )
    two_factor_secret = models.CharField(
        max_length=255, 
        blank=True, 
        default='',
        help_text="Secret key for TOTP 2FA"
    )
    two_factor_backup_codes = models.TextField(
        blank=True, 
        default='',
        help_text="Comma-separated backup codes for 2FA"
    )
    
    class Meta:
        db_table = 'users'
        indexes = [
            models.Index(fields=['role']),
            models.Index(fields=['email']),
            models.Index(fields=['is_active']),
            models.Index(fields=['phone']),
            models.Index(fields=['national_id']),
            models.Index(fields=['two_factor_enabled']),
            models.Index(fields=['two_factor_verified']),
            models.Index(fields=['telebirr_phone']),
            models.Index(fields=['cbe_account_number']),
        ]
        ordering = ['-date_joined']
    
    def __str__(self):
        return self.full_name or self.username
    
    def get_role_display(self):
        role_display = dict(self.ROLE_CHOICES)
        return role_display.get(self.role, self.role)
    
    def get_gender_display(self):
        """Return gender value as-is (since it's a CharField)"""
        return self.gender or ''
    
    # ============================================
    # PAYMENT METHODS
    # ============================================
    
    def get_payment_details(self, method):
        """Get payment details for a specific method"""
        if method == 'telebirr':
            return {
                'phone': self.telebirr_phone or self.phone,
                'name': self.telebirr_name or self.full_name or self.username,
            }
        elif method == 'cbe':
            return {
                'account_number': self.cbe_account_number,
                'account_name': self.cbe_account_name or self.full_name or self.username,
                'bank_branch': self.cbe_bank_branch,
            }
        elif method == 'bank_transfer':
            return {
                'bank_name': self.bank_name,
                'account_number': self.bank_account_number,
                'account_name': self.bank_account_name or self.full_name or self.username,
                'branch': self.bank_branch,
            }
        return {}
    
    def has_payment_method(self, method):
        """Check if user has a payment method configured"""
        if method == 'telebirr':
            return bool(self.telebirr_phone or self.phone)
        elif method == 'cbe':
            return bool(self.cbe_account_number)
        elif method == 'bank_transfer':
            return bool(self.bank_account_number)
        return False
    
    def get_available_payment_methods(self):
        """Get list of available payment methods for this user"""
        methods = []
        if self.has_payment_method('telebirr'):
            methods.append('telebirr')
        if self.has_payment_method('cbe'):
            methods.append('cbe')
        if self.has_payment_method('bank_transfer'):
            methods.append('bank_transfer')
        return methods
    
    @property
    def has_any_payment_method(self):
        """Check if user has any payment method configured"""
        return bool(self.get_available_payment_methods())
    
    # ============================================
    # 2FA METHODS
    # ============================================
    
    @property
    def is_2fa_enabled(self):
        """Check if 2FA is enabled"""
        return self.two_factor_enabled
    
    @property
    def is_2fa_verified(self):
        """Check if 2FA is verified"""
        return self.two_factor_verified
    
    @property
    def is_locked(self):
        """Check if account is locked"""
        if self.locked_until:
            return timezone.now() < self.locked_until
        return False
    
    def get_backup_codes_list(self):
        """Get backup codes as a list"""
        if self.two_factor_backup_codes:
            return [code.strip() for code in self.two_factor_backup_codes.split(',') if code.strip()]
        return []
    
    def set_backup_codes(self, codes):
        """Set backup codes from a list"""
        self.two_factor_backup_codes = ','.join(codes)
        self.save()
    
    def increment_login_attempts(self):
        """Increment login attempts"""
        self.login_attempts += 1
        if self.login_attempts >= 5:
            self.locked_until = timezone.now() + timezone.timedelta(minutes=30)
        self.save()
    
    def reset_login_attempts(self):
        """Reset login attempts"""
        self.login_attempts = 0
        self.locked_until = None
        self.save()


class AuthorProfile(models.Model):
    VERIFICATION_STATUS = (
        ('not_submitted', 'Not Submitted'),
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    )
    
    user = models.OneToOneField(
        CustomUser, 
        on_delete=models.CASCADE, 
        related_name='author_profile',
        help_text="The user associated with this author profile"
    )
    
    # Author Information
    bio = models.TextField(
        blank=True, 
        default='',
        help_text="Detailed author biography"
    )
    website = models.URLField(
        blank=True, 
        default='',
        help_text="Author's personal website"
    )
    author_pseudonym = models.CharField(
        max_length=100, 
        blank=True, 
        default='',
        help_text="Pen name or pseudonym"
    )
    
    # Social Media
    facebook_url = models.URLField(
        blank=True, 
        default='',
        help_text="Facebook profile URL"
    )
    twitter_url = models.URLField(
        blank=True, 
        default='',
        help_text="Twitter/X profile URL"
    )
    instagram_url = models.URLField(
        blank=True, 
        default='',
        help_text="Instagram profile URL"
    )
    linkedin_url = models.URLField(
        blank=True, 
        default='',
        help_text="LinkedIn profile URL"
    )
    
    # Banking Information
    bank_account_name = models.CharField(
        max_length=100, 
        blank=True, 
        default='',
        help_text="Name on bank account"
    )
    bank_account_number = models.CharField(
        max_length=50, 
        blank=True, 
        default='',
        help_text="Bank account number"
    )
    bank_name = models.CharField(
        max_length=100, 
        blank=True, 
        default='',
        help_text="Name of the bank"
    )
    tax_id = models.CharField(
        max_length=50, 
        blank=True, 
        default='',
        help_text="Tax identification number"
    )
    tin_number = models.CharField(
        max_length=20, 
        blank=True, 
        default='',
        help_text="TIN number"
    )
    
    # Profile Image
    author_image = models.ImageField(
        upload_to='authors/', 
        null=True, 
        blank=True,
        help_text="Author profile image"
    )
    
    # Verification
    agreement_signed = models.BooleanField(
        default=False,
        help_text="Whether the author has signed the agreement"
    )
    agreement_signed_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When the agreement was signed"
    )
    verification_status = models.CharField(
        max_length=20, 
        choices=VERIFICATION_STATUS, 
        default='not_submitted',
        help_text="Verification status of the author"
    )
    verification_documents = models.TextField(
        blank=True, 
        default='',
        help_text="Documents submitted for verification"
    )
    verified_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When the author was verified"
    )
    verified_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='verified_authors',
        help_text="Who verified the author"
    )
    
    # Commission and Earnings
    commission_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=70.00,
        help_text="Commission rate percentage"
    )
    total_royalties_earned = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        help_text="Total royalties earned"
    )
    total_paid = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        help_text="Total amount paid to author"
    )
    pending_payout = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        help_text="Pending payout amount"
    )
    last_payment_date = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Date of last payment"
    )
    
    # Statistics
    total_books_published = models.IntegerField(
        default=0,
        help_text="Total number of books published"
    )
    total_downloads = models.IntegerField(
        default=0,
        help_text="Total downloads of author's books"
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the profile was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the profile was last updated"
    )
    
    # Additional Fields
    agreement_version = models.CharField(
        max_length=20, 
        default='1.0',
        help_text="Version of the agreement signed"
    )
    author_signature = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text="Digital signature of the author"
    )
    average_rating = models.DecimalField(
        max_digits=3, 
        decimal_places=2, 
        default=0.00,
        help_text="Average rating of the author"
    )
    
    class Meta:
        db_table = 'author_profiles'
        indexes = [
            models.Index(fields=['verification_status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['user_id']),
        ]
    
    def __str__(self):
        return f"Author Profile: {self.user.full_name}"
    
    @property
    def is_verified(self):
        """Check if author is verified"""
        return self.verification_status == 'verified'
    
    @property
    def is_pending(self):
        """Check if verification is pending"""
        return self.verification_status == 'pending'
    
    def get_total_earnings(self):
        """Get total earnings including pending"""
        return self.total_royalties_earned + self.pending_payout


class ClientProfile(models.Model):
    user = models.OneToOneField(
        CustomUser, 
        on_delete=models.CASCADE, 
        related_name='client_profile',
        help_text="The user associated with this client profile"
    )
    
    phone_number = models.CharField(
        max_length=20, 
        blank=True, 
        default='',
        help_text="Client's phone number"
    )
    national_id_verified = models.BooleanField(
        default=False,
        help_text="Whether the national ID has been verified"
    )
    wallet_balance = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        help_text="Wallet balance"
    )
    total_purchases = models.IntegerField(
        default=0,
        help_text="Total number of purchases"
    )
    total_spent = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        help_text="Total amount spent"
    )
    preferred_genres = models.TextField(
        blank=True, 
        default='',
        help_text="Comma-separated list of preferred genres"
    )
    newsletter_subscribed = models.BooleanField(
        default=True,
        help_text="Whether the client is subscribed to newsletter"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the profile was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the profile was last updated"
    )
    
    class Meta:
        db_table = 'clients'
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['user_id']),
        ]
    
    def __str__(self):
        return f"Client Profile: {self.user.full_name}"
    
    @property
    def is_verified(self):
        """Check if client is verified"""
        return self.national_id_verified
    
    def get_preferred_genres_list(self):
        """Get preferred genres as a list"""
        if self.preferred_genres:
            return [g.strip() for g in self.preferred_genres.split(',') if g.strip()]
        return []