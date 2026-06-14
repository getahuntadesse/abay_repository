from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import authenticate
from django.utils import timezone
from .models import CustomUser, AuthorProfile, ClientProfile


class LoginForm(forms.Form):
    """Login form for user authentication"""
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your username or email',
            'autofocus': True
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password'
        })
    )
    remember = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')
        
        if username and password:
            user = authenticate(username=username, password=password)
            if not user:
                raise forms.ValidationError('Invalid username or password.')
            if not user.is_active:
                raise forms.ValidationError('This account is inactive.')
        return cleaned_data


class ClientRegistrationForm(UserCreationForm):
    """Client/Reader registration form"""
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email'
        })
    )
    full_name = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your full name'
        })
    )
    phone = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your phone number'
        })
    )
    newsletter_subscribed = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    terms_accepted = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'full_name', 'phone', 'password1', 'password2']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Choose a username'
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Enter password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Confirm password'
        })
    
    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            if not phone.startswith('09'):
                raise forms.ValidationError('Phone number must start with 09')
            if len(phone) != 10:
                raise forms.ValidationError('Phone number must be exactly 10 digits')
            if not phone.isdigit():
                raise forms.ValidationError('Phone number must contain only digits')
        return phone
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError('A user with this email already exists.')
        return email
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if CustomUser.objects.filter(username=username).exists():
            raise forms.ValidationError('A user with this username already exists.')
        return username
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.full_name = self.cleaned_data['full_name']
        user.phone = self.cleaned_data['phone']
        user.role = 'client'
        if commit:
            user.save()
            
            # Create client profile
            ClientProfile.objects.create(
                user=user,
                phone_number=user.phone,
                newsletter_subscribed=self.cleaned_data.get('newsletter_subscribed', True)
            )
        return user


class AuthorRegistrationForm(UserCreationForm):
    """Author registration form with Fayda ID verification"""
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email'
        })
    )
    full_name = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your full name',
            'readonly': 'readonly'
        })
    )
    phone = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your phone number'
        })
    )
    national_id = forms.CharField(
        max_length=16,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '1234-5678-9012-3456',
            'autocomplete': 'off'
        })
    )
    bio = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Tell us about yourself and your writing journey'
        })
    )
    author_pseudonym = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Pen name (optional)'
        })
    )
    website = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'Your website or blog'
        })
    )
    bank_account_name = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Account holder name'
        })
    )
    bank_account_number = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Account number'
        })
    )
    bank_name = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Bank name'
        })
    )
    agreement_signed = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='I agree to the Author Terms and Conditions'
    )
    
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'full_name', 'phone', 'national_id', 
                  'password1', 'password2', 'bio', 'author_pseudonym', 'website',
                  'bank_account_name', 'bank_account_number', 'bank_name', 'agreement_signed']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Choose a username'
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Enter password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Confirm password'
        })
    
    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            if not phone.startswith('09'):
                raise forms.ValidationError('Phone number must start with 09')
            if len(phone) != 10:
                raise forms.ValidationError('Phone number must be exactly 10 digits')
        return phone
    
    def clean_national_id(self):
        national_id = self.cleaned_data.get('national_id')
        national_id = national_id.replace(' ', '').replace('-', '')
        if len(national_id) != 16:
            raise forms.ValidationError('National ID must be 16 digits')
        if not national_id.isdigit():
            raise forms.ValidationError('National ID must contain only digits')
        if CustomUser.objects.filter(national_id=national_id).exists():
            raise forms.ValidationError('This National ID is already registered.')
        return national_id
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError('A user with this email already exists.')
        return email
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if CustomUser.objects.filter(username=username).exists():
            raise forms.ValidationError('A user with this username already exists.')
        return username
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.full_name = self.cleaned_data['full_name']
        user.phone = self.cleaned_data['phone']
        user.national_id = self.cleaned_data['national_id'].replace(' ', '').replace('-', '')
        user.role = 'author'
        
        if commit:
            user.save()
            
            # Create author profile
            AuthorProfile.objects.create(
                user=user,
                bio=self.cleaned_data.get('bio', ''),
                author_pseudonym=self.cleaned_data.get('author_pseudonym', ''),
                website=self.cleaned_data.get('website', ''),
                bank_account_name=self.cleaned_data.get('bank_account_name', ''),
                bank_account_number=self.cleaned_data.get('bank_account_number', ''),
                bank_name=self.cleaned_data.get('bank_name', ''),
                agreement_signed=self.cleaned_data.get('agreement_signed', False),
                agreement_signed_at=timezone.now(),
                verification_status='pending'
            )
        
        return user