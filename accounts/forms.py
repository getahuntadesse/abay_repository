# accounts/forms.py
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import authenticate
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import CustomUser, AuthorProfile, ClientProfile
from datetime import date, datetime
import logging

logger = logging.getLogger(__name__)


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
            self.user_cache = user
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
    gender = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'Select Gender'),
            ('Male', 'Male'),
            ('Female', 'Female'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Gender'
    )

    terms_accepted = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='I have read and agree to the Terms and Conditions and Privacy Policy of Abay Repository'
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
            phone = ''.join(filter(str.isdigit, phone))
            if not phone.startswith('09'):
                raise forms.ValidationError('Phone number must start with 09')
            if len(phone) != 10:
                raise forms.ValidationError('Phone number must be exactly 10 digits')
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
        gender = self.cleaned_data.get('gender') or ''
        if gender in ('Male', 'Female', 'M', 'F'):
            user.gender = 'Male' if gender in ('Male', 'M') else 'Female'
        else:
            user.gender = ''
        if commit:
            user.save()
            ClientProfile.objects.create(
                user=user,
                phone_number=user.phone,
                newsletter_subscribed=self.cleaned_data.get('newsletter_subscribed', True)
            )
        return user


class AuthorRegistrationForm(UserCreationForm):
    """
    Author registration form with Fayda ID verification.
    All fields are populated from Fayda - no manual entry.
    Date of Birth is a CharField (accepts any format).
    Gender is a CharField (accepts any value).
    """
    
    # ============================================
    # FIELDS POPULATED FROM FAYDA (Read-only)
    # ============================================
    
    profile_image = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'readonly': True,
            'disabled': True,
            'style': 'display: none;'
        })
    )
    
    full_name = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'readonly': True,
            'style': 'background-color: #e9ecef; cursor: not-allowed;'
        })
    )
    national_id = forms.CharField(
        max_length=16,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'readonly': True,
            'style': 'background-color: #e9ecef; cursor: not-allowed;'
        })
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'readonly': True,
            'style': 'background-color: #e9ecef; cursor: not-allowed;'
        })
    )
    phone = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'readonly': True,
            'style': 'background-color: #e9ecef; cursor: not-allowed;'
        })
    )
    
    address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'readonly': True,
            'style': 'background-color: #e9ecef; cursor: not-allowed;'
        })
    )
    
    region = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'readonly': True,
            'style': 'background-color: #e9ecef; cursor: not-allowed;'
        })
    )
    zone = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'readonly': True,
            'style': 'background-color: #e9ecef; cursor: not-allowed;'
        })
    )
    woreda = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'readonly': True,
            'style': 'background-color: #e9ecef; cursor: not-allowed;'
        })
    )
    
    # Date of Birth - CharField (accepts any format from Fayda)
    # IMPORTANT: This is a CharField, NOT a DateField
    date_of_birth = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'readonly': True,
            'style': 'background-color: #e9ecef; cursor: not-allowed;'
        }),
        help_text='Imported from Fayda'
    )
    
    # Gender - CharField (accepts any value from Fayda)
    # IMPORTANT: This is a CharField, NOT a ChoiceField
    gender = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'readonly': True,
            'style': 'background-color: #e9ecef; cursor: not-allowed;'
        }),
        help_text='Imported from Fayda'
    )
    
    # ============================================
    # USER-ENTERED FIELDS
    # ============================================
    
    username = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Choose a username'
        })
    )
    password1 = forms.CharField(
        required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter password'
        })
    )
    password2 = forms.CharField(
        required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm password'
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
    
    agreement_signed = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='I have read and agree to the Terms and Conditions and Privacy Policy of Abay Repository'
    )
    
    class Meta:
        model = CustomUser
        fields = [
            'full_name', 'national_id', 'email', 'phone', 
            'address', 'region', 'zone', 'woreda',
            'date_of_birth', 'gender', 'profile_image',
            'username', 'password1', 'password2',
            'bio', 'author_pseudonym', 'website',
            'agreement_signed'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget = forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter password'
        })
        self.fields['password2'].widget = forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm password'
        })
    
    # ============================================
    # VALIDATION METHODS
    # ============================================
    
    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            phone = ''.join(filter(str.isdigit, phone))
            if not phone.startswith('09'):
                raise ValidationError('Phone number must start with 09')
            if len(phone) != 10:
                raise ValidationError('Phone number must be exactly 10 digits')
        return phone
    
    def clean_national_id(self):
        national_id = self.cleaned_data.get('national_id')
        if national_id:
            national_id = ''.join(filter(str.isdigit, national_id))
            if len(national_id) != 16:
                raise ValidationError('National ID must be 16 digits')
            if CustomUser.objects.filter(national_id=national_id).exists():
                raise ValidationError('This National ID is already registered.')
        return national_id
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and CustomUser.objects.filter(email=email).exists():
            raise ValidationError('A user with this email already exists.')
        return email
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username and CustomUser.objects.filter(username=username).exists():
            raise ValidationError('A user with this username already exists.')
        return username
    
    # ============================================
    # CLEAN DATE OF BIRTH - NO VALIDATION
    # ============================================
    
    def clean_date_of_birth(self):
        """
        Date of birth - accept any value as-is.
        No validation or formatting applied.
        This is a CharField, so it accepts any string.
        """
        dob = self.cleaned_data.get('date_of_birth')
        logger.info(f"DOB received in form: '{dob}' (type: {type(dob)})")
        
        # If it's None or empty, return empty string
        if not dob:
            return ''
        
        # Convert to string if needed
        if not isinstance(dob, str):
            dob = str(dob)
        
        # Just return the value as-is - NO VALIDATION
        return dob
    
    # ============================================
    # CLEAN GENDER - NO VALIDATION
    # ============================================
    
    def clean_gender(self):
        """
        Gender - accept any value as-is.
        No validation applied.
        This is a CharField, so it accepts any string.
        """
        gender = self.cleaned_data.get('gender')
        logger.info(f"Gender received in form: '{gender}' (type: {type(gender)})")
        
        if not gender:
            return ''
        
        # Convert to string if needed
        if not isinstance(gender, str):
            gender = str(gender)
        
        # Just return the value as-is - NO VALIDATION
        return gender.strip()
    
    # ============================================
    # SAVE METHOD
    # ============================================
    
    def save(self, commit=True):
        try:
            user = super().save(commit=False)
            
            user.email = self.cleaned_data.get('email', '')
            user.full_name = self.cleaned_data.get('full_name', '')
            user.phone = self.cleaned_data.get('phone', '')
            user.national_id = self.cleaned_data.get('national_id', '')
            user.address = self.cleaned_data.get('address', '')
            user.region = self.cleaned_data.get('region', '')
            user.zone = self.cleaned_data.get('zone', '')
            user.woreda = self.cleaned_data.get('woreda', '')
            
            # Gender - store as string
            user.gender = self.cleaned_data.get('gender', '')
            
            # Date of Birth - store as string (CharField)
            dob = self.cleaned_data.get('date_of_birth', '')
            logger.info(f"Saving DOB as string: '{dob}'")
            user.date_of_birth = dob  # Store as string
            
            user.role = 'author'
            
            if self.cleaned_data.get('profile_image'):
                user.profile_image = self.cleaned_data['profile_image']
            
            user.telebirr_phone = user.phone
            
            if commit:
                user.save()
                logger.info(f"User saved with DOB: '{user.date_of_birth}'")
                logger.info(f"User saved with Gender: '{user.gender}'")
                
                AuthorProfile.objects.create(
                    user=user,
                    bio=self.cleaned_data.get('bio', ''),
                    author_pseudonym=self.cleaned_data.get('author_pseudonym', ''),
                    website=self.cleaned_data.get('website', ''),
                    agreement_signed=self.cleaned_data.get('agreement_signed', False),
                    agreement_signed_at=timezone.now() if self.cleaned_data.get('agreement_signed') else None,
                    verification_status='pending'
                )
                
                logger.info(f"Author user created: {user.username}")
                return user
                
        except Exception as e:
            logger.error(f"Error in AuthorRegistrationForm.save: {str(e)}")
            import traceback
            traceback.print_exc()
            raise e
        
        return user