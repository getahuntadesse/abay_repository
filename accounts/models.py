from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('checker', 'Content Checker'),
        ('maker', 'Content Maker'),
        ('author', 'Author'),
        ('client', 'Client'),
    )
    
    GENDER_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),
    )
    
    # Personal Information
    full_name = models.CharField(max_length=255, blank=True, default='')
    national_id = models.CharField(max_length=16, unique=True, null=True, blank=True)
    national_id_verified = models.BooleanField(default=False)
    phone = models.CharField(max_length=20, blank=True, default='')
    phone_verified = models.BooleanField(default=False)
    address = models.TextField(blank=True, default='')
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, default='')
    
    # Location
    region = models.CharField(max_length=100, blank=True, default='')
    zone = models.CharField(max_length=100, blank=True, default='')
    woreda = models.CharField(max_length=100, blank=True, default='')
    
    # Role and Status
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='client')
    is_active = models.BooleanField(default=True)
    email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(max_length=255, blank=True, default='')
    verification_token_expires = models.DateTimeField(null=True, blank=True)
    
    # Tracking
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    profile_image = models.ImageField(upload_to='profiles/', null=True, blank=True)
    bio = models.TextField(blank=True, default='')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Security
    locked_until = models.DateTimeField(null=True, blank=True)
    login_attempts = models.IntegerField(default=0)
    two_factor_enabled = models.BooleanField(default=False)
    two_factor_secret = models.CharField(max_length=255, blank=True, default='')
    
    class Meta:
        db_table = 'users'
        indexes = [
            models.Index(fields=['role']),
            models.Index(fields=['email']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return self.full_name or self.username
    
    def get_role_display(self):
        role_display = dict(self.ROLE_CHOICES)
        return role_display.get(self.role, self.role)
    
    def get_gender_display(self):
        gender_display = dict(self.GENDER_CHOICES)
        return gender_display.get(self.gender, '')


class AuthorProfile(models.Model):
    VERIFICATION_STATUS = (
        ('not_submitted', 'Not Submitted'),
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    )
    
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='author_profile')
    
    # Author Information
    bio = models.TextField(blank=True, default='')
    website = models.URLField(blank=True, default='')
    author_pseudonym = models.CharField(max_length=100, blank=True, default='')
    
    # Social Media
    facebook_url = models.URLField(blank=True, default='')
    twitter_url = models.URLField(blank=True, default='')
    instagram_url = models.URLField(blank=True, default='')
    linkedin_url = models.URLField(blank=True, default='')
    
    # Banking Information
    bank_account_name = models.CharField(max_length=100, blank=True, default='')
    bank_account_number = models.CharField(max_length=50, blank=True, default='')
    bank_name = models.CharField(max_length=100, blank=True, default='')
    tax_id = models.CharField(max_length=50, blank=True, default='')
    tin_number = models.CharField(max_length=20, blank=True, default='')
    
    # Profile Image
    author_image = models.ImageField(upload_to='authors/', null=True, blank=True)
    
    # Verification
    agreement_signed = models.BooleanField(default=False)
    agreement_signed_at = models.DateTimeField(null=True, blank=True)
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_STATUS, default='not_submitted')
    verification_documents = models.TextField(blank=True, default='')
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_authors')
    
    # Commission and Earnings
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=70.00)
    total_royalties_earned = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    pending_payout = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    last_payment_date = models.DateTimeField(null=True, blank=True)
    
    # Statistics
    total_books_published = models.IntegerField(default=0)
    total_downloads = models.IntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Additional Fields
    agreement_version = models.CharField(max_length=20, default='1.0')
    author_signature = models.CharField(max_length=100, blank=True, null=True)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    
    class Meta:
        db_table = 'author_profiles'
    
    def __str__(self):
        return f"Author Profile: {self.user.full_name}"


class ClientProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='client_profile')
    
    phone_number = models.CharField(max_length=20, blank=True, default='')
    national_id_verified = models.BooleanField(default=False)
    wallet_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_purchases = models.IntegerField(default=0)
    total_spent = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    preferred_genres = models.TextField(blank=True, default='')
    newsletter_subscribed = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'clients'
    
    def __str__(self):
        return f"Client Profile: {self.user.full_name}"