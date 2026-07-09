# accounts/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie, csrf_exempt
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.cache import never_cache
from django.db.models import Avg, Count, Q, Sum, Max
from django.http import JsonResponse
from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
from datetime import datetime, timedelta, date
import json
import requests
import logging
import jwt
import base64
import hashlib
import urllib
import os
import re
import uuid
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa

from .forms import LoginForm, ClientRegistrationForm, AuthorRegistrationForm
from .models import CustomUser, AuthorProfile, ClientProfile
from books.models import Book, Genre
from reviews.models import QualityReview

# Set up logger
logger = logging.getLogger(__name__)

# ============================================
# FAYDA OIDC HELPERS
# ============================================

def base64url_decode(input_str):
    """Decode base64url string with padding"""
    padding = '=' * (4 - (len(input_str) % 4))
    return base64.urlsafe_b64decode(input_str + padding)


def load_private_key_from_string(base64_key_str):
    """Load RSA private key from base64 encoded JWK string"""
    logger.info("Loading private key from base64 key string")
    try:
        key_bytes = base64.b64decode(base64_key_str)
        jwk_data = json.loads(key_bytes)

        n = int.from_bytes(base64url_decode(jwk_data['n']), 'big')
        e = int.from_bytes(base64url_decode(jwk_data['e']), 'big')
        d = int.from_bytes(base64url_decode(jwk_data['d']), 'big')

        p = int.from_bytes(base64url_decode(jwk_data['p']), 'big') if 'p' in jwk_data else None
        q = int.from_bytes(base64url_decode(jwk_data['q']), 'big') if 'q' in jwk_data else None
        dmp1 = int.from_bytes(base64url_decode(jwk_data['dp']), 'big') if 'dp' in jwk_data else None
        dmq1 = int.from_bytes(base64url_decode(jwk_data['dq']), 'big') if 'dq' in jwk_data else None
        iqmp = int.from_bytes(base64url_decode(jwk_data['qi']), 'big') if 'qi' in jwk_data else None

        public_numbers = rsa.RSAPublicNumbers(e, n)

        if p and q and dmp1 and dmq1 and iqmp:
            private_numbers = rsa.RSAPrivateNumbers(
                p=p,
                q=q,
                d=d,
                dmp1=dmp1,
                dmq1=dmq1,
                iqmp=iqmp,
                public_numbers=public_numbers
            )
        else:
            private_numbers = rsa.RSAPrivateNumbers(
                p=None,
                q=None,
                d=d,
                dmp1=None,
                dmq1=None,
                iqmp=None,
                public_numbers=public_numbers
            )

        private_key = private_numbers.private_key(default_backend())
        logger.info("Private Key Loaded Successfully")
        return private_key

    except Exception as e:
        logger.error(f"Failed to load private key: {e}")
        raise


def generate_signed_jwt(client_id, token_endpoint, private_key_b64):
    """Generate signed JWT for Fayda client assertion"""
    logger.info("Generating signed JWT for Fayda Assertion...")
    
    header = {
        "alg": "RS256",
        "typ": "JWT",
    }

    payload = {
        "iss": client_id,
        "sub": client_id,
        "aud": token_endpoint,
        "exp": datetime.utcnow() + timedelta(minutes=15),
        "iat": datetime.utcnow(),
    }

    private_key = load_private_key_from_string(private_key_b64)
    signed_jwt = jwt.encode(payload, private_key, algorithm="RS256", headers=header)
    logger.info("Signed JWT generated successfully.")
    return signed_jwt


def generate_pkce():
    """Generate PKCE code verifier and challenge"""
    code_verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b'=').decode('utf-8')
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode('utf-8')).digest()
    ).rstrip(b'=').decode('utf-8')
    return code_verifier, code_challenge


def process_fayda_picture(picture_data):
    """
    Process and normalize Fayda picture data.
    Returns a properly formatted data URL or None.
    """
    if not picture_data:
        logger.warning("No picture data provided")
        return None
    
    logger.info(f"Processing picture data, type: {type(picture_data)}")
    
    # If it's already a valid data URL, return it
    if isinstance(picture_data, str) and picture_data.startswith('data:image') and ';base64,' in picture_data:
        # Validate it has actual data after the comma
        try:
            header, data = picture_data.split(',', 1)
            if data and len(data) > 10:
                # Try to decode to ensure it's valid base64
                base64.b64decode(data)
                logger.info("Picture is a valid data URL")
                return picture_data
        except Exception as e:
            logger.error(f"Invalid data URL: {str(e)}")
    
    # If it's a URL, try to download and convert
    if isinstance(picture_data, str) and picture_data.startswith(('http://', 'https://')):
        logger.info(f"Picture is a URL, downloading...")
        try:
            response = requests.get(picture_data, timeout=15)
            if response.status_code == 200:
                content_type = response.headers.get('content-type', 'image/jpeg')
                image_b64 = base64.b64encode(response.content).decode('utf-8')
                data_url = f"data:{content_type};base64,{image_b64}"
                logger.info("Successfully downloaded and converted URL to data URL")
                return data_url
            else:
                logger.error(f"Failed to download picture: HTTP {response.status_code}")
        except Exception as e:
            logger.error(f"Error downloading picture: {str(e)}")
    
    # Try to decode as base64
    if isinstance(picture_data, str):
        try:
            # Clean the string
            cleaned_data = re.sub(r'\s+', '', picture_data)
            
            # Check if it's valid base64
            image_data = base64.b64decode(cleaned_data)
            if image_data and len(image_data) > 100:
                # Determine image type
                mime_type = 'image/jpeg'
                if len(image_data) >= 4:
                    if image_data[:4] in [b'\xff\xd8\xff\xe0', b'\xff\xd8\xff\xe1']:
                        mime_type = 'image/jpeg'
                    elif image_data[:4] == b'\x89PNG':
                        mime_type = 'image/png'
                    elif image_data[:3] == b'GIF':
                        mime_type = 'image/gif'
                    elif image_data[:4] == b'RIFF' and len(image_data) > 12 and image_data[8:12] == b'WEBP':
                        mime_type = 'image/webp'
                
                data_url = f"data:{mime_type};base64,{base64.b64encode(image_data).decode('utf-8')}"
                logger.info(f"Successfully converted base64 to data URL: {mime_type}")
                return data_url
        except Exception as e:
            logger.error(f"Error decoding base64: {str(e)}")
    
    # If it's a string that looks like base64
    if isinstance(picture_data, str) and len(picture_data) > 50:
        # Check if it's mostly base64 characters
        if re.match(r'^[A-Za-z0-9+/=]+$', picture_data[:50]):
            try:
                image_data = base64.b64decode(picture_data)
                if image_data and len(image_data) > 100:
                    data_url = f"data:image/jpeg;base64,{base64.b64encode(image_data).decode('utf-8')}"
                    logger.info("Converted raw base64 to data URL")
                    return data_url
            except Exception as e:
                logger.error(f"Error decoding raw base64: {str(e)}")
    
    # If picture_data is a dict, try to extract picture
    if isinstance(picture_data, dict):
        for key in ['picture', 'image', 'photo', 'profile_picture', 'url', 'value']:
            if key in picture_data and picture_data[key]:
                logger.info(f"Found picture in dict key: {key}")
                return process_fayda_picture(picture_data[key])
    
    # If it's a list, try to get first item
    if isinstance(picture_data, list) and picture_data:
        logger.info("Picture is a list, using first item")
        return process_fayda_picture(picture_data[0])
    
    logger.warning("Could not process picture data into a valid format")
    return None


def validate_picture_data_url(data_url):
    """
    Validate that a string is a properly formatted data URL.
    Returns True if valid, False otherwise.
    """
    if not data_url or not isinstance(data_url, str):
        return False
    
    # Check if it starts with the correct prefix
    if not data_url.startswith('data:image'):
        logger.warning(f"Invalid data URL prefix")
        return False
    
    # Check if it contains the base64 marker
    if ';base64,' not in data_url:
        logger.warning(f"Missing base64 marker in data URL")
        return False
    
    # Split and check if there's data after the comma
    try:
        header, data = data_url.split(',', 1)
        if not data or len(data) < 10:
            logger.warning("No data or too short after comma in data URL")
            return False
        
        # Try to decode the base64 data
        try:
            decoded = base64.b64decode(data)
            if len(decoded) < 100:  # Too small to be a valid image
                logger.warning(f"Decoded image too small: {len(decoded)} bytes")
                return False
            logger.info(f"Valid data URL with {len(decoded)} bytes of image data")
            return True
        except Exception as e:
            logger.error(f"Failed to decode base64 data: {str(e)}")
            return False
            
    except Exception as e:
        logger.error(f"Error validating data URL: {str(e)}")
        return False


def save_fayda_picture(user, picture_data):
    """
    Save the Fayda profile picture to the user's profile.
    Returns True if successful, False otherwise.
    """
    if not picture_data:
        logger.info("No picture data provided to save")
        return False
    
    logger.info(f"Attempting to save picture for user {user.username}")
    
    try:
        # Process the picture to get a clean data URL
        processed_picture = process_fayda_picture(picture_data)
        
        if not processed_picture:
            logger.warning("Could not process picture data")
            return False
        
        # Validate the processed picture
        if not validate_picture_data_url(processed_picture):
            logger.warning("Processed picture failed validation")
            return False
        
        # Extract the actual image data from the data URL
        try:
            header, encoded = processed_picture.split(',', 1)
            image_data = base64.b64decode(encoded)
            
            if not image_data:
                logger.error("No image data after decoding")
                return False
            
            # Determine file extension
            mime_type = header.split(':')[1].split(';')[0]
            extension = 'jpg'
            if 'jpeg' in mime_type or 'jpg' in mime_type:
                extension = 'jpg'
            elif 'png' in mime_type:
                extension = 'png'
            elif 'gif' in mime_type:
                extension = 'gif'
            elif 'webp' in mime_type:
                extension = 'webp'
            
            # Create a unique filename
            filename = f"fayda_{user.username}_{uuid.uuid4().hex[:8]}.{extension}"
            
            # Save to user profile
            if hasattr(user, 'profile_image'):
                # Delete old image if exists
                if user.profile_image:
                    try:
                        user.profile_image.delete(save=False)
                    except:
                        pass
                
                user.profile_image.save(filename, ContentFile(image_data), save=True)
                logger.info(f"Successfully saved Fayda picture for user {user.username} ({len(image_data)} bytes)")
                return True
            else:
                logger.warning("User model does not have profile_image field")
                return False
                
        except Exception as e:
            logger.error(f"Error extracting image from data URL: {str(e)}")
            return False
            
    except Exception as e:
        logger.error(f"Error saving Fayda picture: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


# ============================================
# SECURITY HELPERS
# ============================================

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def is_ip_blocked(ip):
    key = f"blocked_ip_{ip}"
    return cache.get(key, False)


def get_login_attempts(ip):
    key = f"login_attempts_{ip}"
    return cache.get(key, 0)


def increment_login_attempts(ip):
    key = f"login_attempts_{ip}"
    attempts = cache.get(key, 0) + 1
    cache.set(key, attempts, 1800)
    if attempts >= 10:
        cache.set(f"blocked_ip_{ip}", True, 3600)
        logger.warning(f"IP {ip} blocked due to too many failed login attempts")
    return attempts


def reset_login_attempts(ip):
    cache.delete(f"login_attempts_{ip}")
    cache.delete(f"blocked_ip_{ip}")


def validate_password_strength(password):
    errors = []
    if len(password) < 10:
        errors.append("Password must be at least 10 characters long.")
    if not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter.")
    if not re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter.")
    if not re.search(r'[0-9]', password):
        errors.append("Password must contain at least one number.")
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        errors.append("Password must contain at least one special character.")
    return errors


def sanitize_input(input_value):
    if input_value is None:
        return ''
    input_value = str(input_value)
    input_value = re.sub(r'[<>]', '', input_value)
    input_value = re.sub(r'[;]', '', input_value)
    input_value = re.sub(r'--', '', input_value)
    return input_value.strip()


# ============================================
# ROLE-BASED REDIRECT HELPER
# ============================================

def role_based_redirect(user):
    role_redirects = {
        'admin': 'accounts:admin_dashboard',
        'finance': 'accounts:finance_dashboard',
        'author': 'accounts:author_dashboard',
        'checker': 'accounts:checker_dashboard',
        'maker': 'accounts:maker_dashboard',
        'client': 'accounts:client_dashboard',
    }
    return role_redirects.get(user.role, 'accounts:client_dashboard')


# ============================================
# ACCOUNT VIEWS
# ============================================

@sensitive_post_parameters()
@csrf_protect
@ensure_csrf_cookie
@never_cache
def login_view(request):
    if request.user.is_authenticated:
        return redirect(role_based_redirect(request.user))
    
    client_ip = get_client_ip(request)
    if is_ip_blocked(client_ip):
        logger.warning(f"Blocked IP attempted login: {client_ip}")
        messages.error(request, 'Too many failed login attempts. Please try again later.')
        return render(request, 'accounts/login.html', {'form': LoginForm()})
    
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = sanitize_input(form.cleaned_data.get('username'))
            password = form.cleaned_data.get('password')
            remember = form.cleaned_data.get('remember', False)
            
            attempts = get_login_attempts(client_ip)
            if attempts >= 5:
                messages.error(request, f'Too many failed attempts. Please wait {30 - (attempts - 5) * 3} minutes.')
                return render(request, 'accounts/login.html', {'form': form})
            
            user = authenticate(request, username=username, password=password)
            
            if user is not None and user.is_active:
                reset_login_attempts(client_ip)
                
                if user.two_factor_enabled:
                    request.session['pre_2fa_user_id'] = user.id
                    request.session['pre_2fa_remember'] = remember
                    messages.warning(request, '2FA is not fully implemented yet. Please contact support.')
                    login(request, user)
                    messages.success(request, f'Welcome back, {user.full_name}!')
                    return redirect(role_based_redirect(user))
                else:
                    login(request, user)
                    if not remember:
                        request.session.set_expiry(0)
                    else:
                        request.session.set_expiry(1209600)
                    logger.info(f"Successful login: User={username}, IP={client_ip}")
                    messages.success(request, f'Welcome back, {user.full_name}!')
                    return redirect(role_based_redirect(user))
            else:
                attempts = increment_login_attempts(client_ip)
                remaining = 5 - attempts
                logger.warning(f"Failed login attempt: Username={username}, IP={client_ip}, Attempts={attempts}")
                if remaining <= 0:
                    messages.error(request, 'Too many failed attempts. Please try again later.')
                else:
                    messages.error(request, f'Invalid username or password. {remaining} attempts remaining.')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = LoginForm()
    
    return render(request, 'accounts/login.html', {'form': form})


@never_cache
def logout_view(request):
    if request.user.is_authenticated:
        username = request.user.username
        client_ip = get_client_ip(request)
        logger.info(f"User logged out: {username}, IP={client_ip}")
        request.session.flush()
        logout(request)
        messages.info(request, 'You have been logged out successfully.')
    return redirect('home')


@csrf_protect
@ensure_csrf_cookie
@never_cache
def register_view(request):
    if request.user.is_authenticated:
        return redirect(role_based_redirect(request.user))

    if request.method == 'POST':
        form = ClientRegistrationForm(request.POST)
        password = request.POST.get('password1', '')
        password_errors = validate_password_strength(password)
        if password_errors:
            for error in password_errors:
                form.add_error('password1', error)
            messages.error(request, 'Password does not meet security requirements.')
        elif form.is_valid():
            user = form.save()
            client_ip = get_client_ip(request)
            logger.info(f"New user registered: {user.username}, IP={client_ip}")
            login(request, user)
            messages.success(request, f'Welcome to Abrehot Library, {user.full_name}!')
            return redirect(role_based_redirect(user))
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ClientRegistrationForm()

    return render(request, 'accounts/register_client.html', {'form': form})


@csrf_protect
@ensure_csrf_cookie
@never_cache
def register_author(request):
    """
    Author registration view with Fayda verification requirement.
    """
    if request.user.is_authenticated:
        return redirect(role_based_redirect(request.user))

    verified_data = request.session.get('fayda_verified_data', None)
    is_verified = request.session.get('fayda_verified', False)
    stored_picture = request.session.get('fayda_picture', '')
    
    logger.info(f"Register author - verified: {is_verified}")
    
    # Process the picture for display if it exists
    display_picture = ''
    if stored_picture:
        display_picture = stored_picture
        logger.info(f"Using stored_picture for display, length: {len(stored_picture)}")
    elif verified_data and verified_data.get('picture'):
        # Process the picture and store it in session for display
        raw_picture = verified_data.get('picture')
        logger.info(f"Processing picture from verified_data, type: {type(raw_picture)}")
        
        if raw_picture:
            processed = process_fayda_picture(raw_picture)
            if processed and validate_picture_data_url(processed):
                display_picture = processed
                request.session['fayda_picture'] = processed
                logger.info("Picture processed and stored in session")
            else:
                logger.warning("Failed to process picture from verified_data")
    
    if not is_verified and not verified_data:
        form = AuthorRegistrationForm()
        messages.error(request, 'Please verify your identity with Fayda before registering as an author.')
        return render(request, 'accounts/register_author.html', {
            'form': form,
            'verified_data': None,
            'fayda_picture': '',
            'debug': settings.DEBUG,
            'verification_required': True
        })

    if request.method == 'POST':
        logger.info("POST request received for author registration")
        
        form = AuthorRegistrationForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                user = form.save()
                client_ip = get_client_ip(request)
                logger.info(f"New author registered: {user.username}, IP={client_ip}")
                
                # Save the Fayda picture if available
                picture_to_save = display_picture or stored_picture
                if picture_to_save:
                    logger.info("Attempting to save Fayda picture")
                    save_fayda_picture(user, picture_to_save)
                
                login(request, user)
                
                # Clean up session
                request.session.pop('fayda_verified_data', None)
                request.session.pop('fayda_verified', None)
                request.session.pop('fayda_picture', None)
                request.session.pop('fayda_state', None)
                request.session.pop('fayda_national_id', None)
                request.session.pop('fayda_nonce', None)
                request.session.pop('fayda_code_verifier', None)
                
                messages.success(request, f'Welcome Author! {user.full_name}, your profile has been created.')
                return redirect(role_based_redirect(user))
            except Exception as e:
                logger.error(f"Error saving author: {str(e)}")
                import traceback
                traceback.print_exc()
                messages.error(request, f'An error occurred while creating your account. Please try again.')
        else:
            logger.error(f"Form errors: {form.errors.as_json()}")
            messages.error(request, 'Please correct the errors below.')
    else:
        form = AuthorRegistrationForm()
        if verified_data:
            dob = verified_data.get('date_of_birth', '')
            gender = verified_data.get('gender', '')
            
            initial_data = {
                'full_name': verified_data.get('full_name', ''),
                'national_id': verified_data.get('national_id', ''),
                'email': verified_data.get('email', ''),
                'phone': verified_data.get('phone', ''),
                'address': verified_data.get('address', ''),
                'region': verified_data.get('region', ''),
                'zone': verified_data.get('zone', ''),
                'woreda': verified_data.get('woreda', ''),
                'date_of_birth': dob,
                'gender': gender,
            }
            form = AuthorRegistrationForm(initial=initial_data)

    context = {
        'form': form,
        'verified_data': verified_data,
        'fayda_picture': display_picture,  # Pass the processed picture to template
        'debug': settings.DEBUG,
        'verification_required': False,
    }
    return render(request, 'accounts/register_author.html', context)


@login_required
def dashboard_redirect(request):
    return redirect(role_based_redirect(request.user))


# ============================================
# 2FA VIEWS - PLACEHOLDER FUNCTIONS
# ============================================

@login_required
def setup_2fa(request):
    """Setup Two-Factor Authentication - Placeholder"""
    messages.info(request, '2FA setup feature is coming soon.')
    return redirect('accounts:profile')


@login_required
def verify_2fa(request):
    """Verify Two-Factor Authentication - Placeholder"""
    messages.info(request, '2FA verification feature is coming soon.')
    return redirect('accounts:profile')


@login_required
def disable_2fa(request):
    """Disable Two-Factor Authentication - Placeholder"""
    messages.info(request, '2FA disable feature is coming soon.')
    return redirect('accounts:profile')


@login_required
def backup_codes(request):
    """View backup codes for 2FA - Placeholder"""
    messages.info(request, '2FA backup codes feature is coming soon.')
    return redirect('accounts:profile')


# ============================================
# FAYDA OIDC VIEWS
# ============================================

@csrf_exempt
def oidc_initiate(request):
    """
    Initiate OIDC flow with Fayda eSignet.
    """
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Method not allowed. Use POST.'
        }, status=405)
    
    try:
        data = json.loads(request.body)
        national_id = data.get('national_id')
        state = data.get('state')
        nonce = data.get('nonce')
        
        if not national_id:
            return JsonResponse({
                'success': False,
                'message': 'National ID is required.'
            }, status=400)
        
        national_id_clean = national_id.replace('-', '').replace(' ', '')
        if len(national_id_clean) != 16 or not national_id_clean.isdigit():
            return JsonResponse({
                'success': False,
                'message': 'Invalid National ID format. Must be 16 digits.'
            }, status=400)
        
        if not state or len(state) < 10:
            return JsonResponse({
                'success': False,
                'message': 'Invalid state parameter.'
            }, status=400)
        
        if not nonce or len(nonce) < 10:
            return JsonResponse({
                'success': False,
                'message': 'Invalid nonce parameter.'
            }, status=400)
        
        client_id = getattr(settings, 'FAYDA_CLIENT_ID', None)
        auth_url = getattr(settings, 'FAYDA_AUTH_URL', None)
        redirect_uri = getattr(settings, 'FAYDA_REDIRECT_URI', None)
        
        if not all([client_id, auth_url, redirect_uri]):
            logger.error("Fayda configuration missing")
            return JsonResponse({
                'success': False,
                'message': 'Fayda is not properly configured. Please contact support.'
            }, status=500)
        
        code_verifier, code_challenge = generate_pkce()
        request.session['fayda_code_verifier'] = code_verifier
        request.session['fayda_national_id'] = national_id_clean
        request.session['fayda_state'] = state
        request.session['fayda_nonce'] = nonce
        
        claims = {
            "userinfo": {
                "name": {"essential": True},
                "phone_number": {"essential": True},
                "email": {"essential": True},
                "picture": {"essential": True},
                "gender": {"essential": True},
                "birthdate": {"essential": True},
                "address": {"essential": True},
                "nationality": {"essential": True},
                "individual_id": {"essential": True}
            },
            "id_token": {}
        }
        encoded_claims = urllib.parse.quote(json.dumps(claims))
        
        authorization_url = (
            f"{auth_url}"
            f"?claims_locales=en"
            f"&response_type=code"
            f"&client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&scope=openid profile email"
            f"&acr_values=mosip:idp:acr:generated-code:biometrics"
            f"&code_challenge={code_challenge}"
            f"&code_challenge_method=S256"
            f"&claims={encoded_claims}"
            f"&state={state}"
            f"&nonce={nonce}"
        )
        
        logger.info(f"Authorization URL generated successfully")
        
        return JsonResponse({
            'success': True,
            'authorization_url': authorization_url,
            'message': 'Redirect to Fayda for authentication'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid JSON payload.'
        }, status=400)
    except Exception as e:
        logger.error(f"OIDC initiate error: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        }, status=500)


@csrf_exempt
def oidc_callback(request):
    """
    Handle OIDC callback from Fayda - API endpoint for frontend JavaScript.
    """
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Method not allowed. Use POST.'
        }, status=405)
    
    try:
        data = json.loads(request.body)
        code = data.get('code')
        state = data.get('state')
        
        if not code or not state:
            return JsonResponse({
                'success': False,
                'message': 'Missing code or state parameter.'
            }, status=400)
        
        session_state = request.session.get('fayda_state')
        if state != session_state:
            logger.warning(f"OIDC state mismatch: received {state}, expected {session_state}")
            return JsonResponse({
                'success': False,
                'message': 'Invalid state parameter. Possible CSRF attack.'
            }, status=400)
        
        client_id = getattr(settings, 'FAYDA_CLIENT_ID', None)
        token_url = getattr(settings, 'FAYDA_TOKEN_URL', None)
        userinfo_url = getattr(settings, 'FAYDA_USERINFO_URL', None)
        redirect_uri = getattr(settings, 'FAYDA_REDIRECT_URI', None)
        private_key_b64 = getattr(settings, 'FAYDA_PRIVATE_KEY_B64', None)
        
        if not all([client_id, token_url, userinfo_url, redirect_uri, private_key_b64]):
            return JsonResponse({
                'success': False,
                'message': 'Fayda is not properly configured.'
            }, status=500)
        
        code_verifier = request.session.get('fayda_code_verifier', '')
        signed_jwt = generate_signed_jwt(client_id, token_url, private_key_b64)
        
        if not signed_jwt:
            return JsonResponse({
                'success': False,
                'message': 'Failed to generate client assertion.'
            }, status=500)
        
        token_response = requests.post(
            token_url,
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': redirect_uri,
                'client_id': client_id,
                'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
                'client_assertion': signed_jwt,
                'code_verifier': code_verifier,
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=30,
            verify=True
        )
        
        if not token_response.ok:
            logger.error(f"Token exchange failed: {token_response.status_code}")
            try:
                error_data = token_response.json()
                error_msg = error_data.get('error_description', error_data.get('error', 'Unknown error'))
            except:
                error_msg = token_response.text[:200]
            return JsonResponse({
                'success': False,
                'message': f'Token exchange failed: {error_msg}'
            }, status=400)
        
        token_data = token_response.json()
        access_token = token_data.get('access_token')
        
        if not access_token:
            return JsonResponse({
                'success': False,
                'message': 'No access token received from Fayda.'
            }, status=400)
        
        userinfo_response = requests.get(
            userinfo_url,
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10,
            verify=True
        )
        
        if not userinfo_response.ok:
            logger.error(f"Userinfo request failed: {userinfo_response.status_code}")
            return JsonResponse({
                'success': False,
                'message': 'Failed to retrieve user information from Fayda.'
            }, status=400)
        
        decoded_user_info = None
        try:
            decoded_user_info = jwt.decode(
                userinfo_response.text,
                options={"verify_signature": False},
                algorithms=["RS256"]
            )
            logger.info("Decoded userinfo as JWT")
        except:
            try:
                decoded_user_info = userinfo_response.json()
                logger.info("Decoded userinfo as JSON")
            except Exception as e:
                logger.error(f"Failed to decode userinfo: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'message': 'Failed to decode user information.'
                }, status=400)
        
        logger.info(f"Decoded userinfo keys: {list(decoded_user_info.keys())}")
        
        # Extract date of birth
        dob = ''
        possible_dob_fields = ['birthdate', 'date_of_birth', 'dob', 'birthDate', 'birth_date']
        for field in possible_dob_fields:
            if field in decoded_user_info and decoded_user_info[field]:
                dob = decoded_user_info[field]
                logger.info(f"Found DOB in field '{field}': '{dob}'")
                break
        
        if dob is not None:
            if isinstance(dob, (date, datetime)):
                dob = dob.strftime('%Y-%m-%d')
            else:
                dob = str(dob)
        
        # Extract gender
        gender = ''
        possible_gender_fields = ['gender', 'sex', 'gender_code', 'genderCode']
        for field in possible_gender_fields:
            if field in decoded_user_info and decoded_user_info[field]:
                gender = decoded_user_info[field]
                logger.info(f"Found gender in field '{field}': '{gender}'")
                break
        
        if gender is not None:
            gender = str(gender)
        
        # Extract and process picture - CRITICAL: Get the raw picture and process it
        picture = ''
        picture_original = decoded_user_info.get('picture', '')
        
        if picture_original:
            logger.info(f"Original picture found, type: {type(picture_original)}")
            if isinstance(picture_original, str):
                logger.info(f"Original picture preview: {picture_original[:200]}...")
            
            # Process the picture
            processed_picture = process_fayda_picture(picture_original)
            if processed_picture:
                # Validate the processed picture
                if validate_picture_data_url(processed_picture):
                    picture = processed_picture
                    logger.info(f"Picture processed successfully, length: {len(picture)}")
                else:
                    logger.warning("Processed picture failed validation")
            else:
                logger.warning("Could not process picture")
        
        user_data = {
            'full_name': decoded_user_info.get('name', decoded_user_info.get('full_name', '')),
            'national_id': request.session.get('fayda_national_id', ''),
            'email': decoded_user_info.get('email', ''),
            'phone': decoded_user_info.get('phone_number', decoded_user_info.get('phone', '')),
            'address': decoded_user_info.get('address', ''),
            'region': decoded_user_info.get('region', ''),
            'zone': decoded_user_info.get('zone', ''),
            'woreda': decoded_user_info.get('woreda', ''),
            'date_of_birth': dob,
            'gender': gender,
            'nationality': decoded_user_info.get('nationality', ''),
            'individual_id': decoded_user_info.get('individual_id', ''),
            'picture': picture,
        }
        
        logger.info(f"Picture stored in user_data: {bool(picture)}")
        
        # Store in session
        request.session['fayda_verified_data'] = user_data
        request.session['fayda_verified'] = True
        
        # Store picture separately for template access
        if picture:
            request.session['fayda_picture'] = picture
            logger.info("Picture stored in session['fayda_picture']")
        else:
            # Remove any existing picture from session
            request.session.pop('fayda_picture', None)
            logger.warning("No picture to store in session")
        
        # Clean up
        request.session.pop('fayda_state', None)
        request.session.pop('fayda_national_id', None)
        request.session.pop('fayda_nonce', None)
        request.session.pop('fayda_code_verifier', None)
        
        return JsonResponse({
            'success': True,
            'message': 'Verification successful',
            'data': user_data,
            'picture_available': bool(picture)
        })
        
    except requests.exceptions.Timeout:
        return JsonResponse({
            'success': False,
            'message': 'Fayda service timeout. Please try again.'
        }, status=503)
    except requests.exceptions.ConnectionError:
        return JsonResponse({
            'success': False,
            'message': 'Could not connect to Fayda service. Please try again later.'
        }, status=503)
    except requests.exceptions.SSLError:
        logger.error("SSL error connecting to Fayda")
        return JsonResponse({
            'success': False,
            'message': 'SSL error connecting to Fayda. Please check your configuration.'
        }, status=500)
    except Exception as e:
        logger.error(f"OIDC callback error: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        }, status=500)


@csrf_exempt
def oidc_callback_view(request):
    """
    Handle OIDC callback from Fayda via GET request.
    This is the endpoint that Fayda redirects to after authentication.
    """
    code = request.GET.get('code')
    state = request.GET.get('state')
    error = request.GET.get('error')
    error_description = request.GET.get('error_description')
    
    logger.info(f"=== OIDC Callback GET Received ===")
    logger.info(f"Code: {code[:20] if code else 'None'}...")
    logger.info(f"State: {state[:10] if state else 'None'}...")
    
    if error:
        logger.error(f"Fayda OIDC error: {error} - {error_description}")
        messages.error(request, f'Fayda authentication error: {error_description or error}')
        return redirect('accounts:register_author')
    
    if not code:
        messages.error(request, 'Authorization code not provided.')
        return redirect('accounts:register_author')
    
    if not state:
        messages.error(request, 'State parameter not provided.')
        return redirect('accounts:register_author')
    
    session_state = request.session.get('fayda_state')
    if state != session_state:
        logger.warning(f"OIDC state mismatch: received {state}, expected {session_state}")
        messages.error(request, 'Invalid state parameter.')
        return redirect('accounts:register_author')
    
    try:
        client_id = getattr(settings, 'FAYDA_CLIENT_ID', None)
        token_url = getattr(settings, 'FAYDA_TOKEN_URL', None)
        userinfo_url = getattr(settings, 'FAYDA_USERINFO_URL', None)
        redirect_uri = getattr(settings, 'FAYDA_REDIRECT_URI', None)
        private_key_b64 = getattr(settings, 'FAYDA_PRIVATE_KEY_B64', None)
        
        if not all([client_id, token_url, userinfo_url, redirect_uri, private_key_b64]):
            logger.error("Fayda configuration missing")
            messages.error(request, 'Fayda is not properly configured.')
            return redirect('accounts:register_author')
        
        code_verifier = request.session.get('fayda_code_verifier', '')
        signed_jwt = generate_signed_jwt(client_id, token_url, private_key_b64)
        
        if not signed_jwt:
            messages.error(request, 'Failed to generate authentication token.')
            return redirect('accounts:register_author')
        
        logger.info("Exchanging code for token...")
        token_response = requests.post(
            token_url,
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': redirect_uri,
                'client_id': client_id,
                'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
                'client_assertion': signed_jwt,
                'code_verifier': code_verifier,
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=30,
            verify=True
        )
        
        if not token_response.ok:
            try:
                error_data = token_response.json()
                error_msg = error_data.get('error_description', error_data.get('error', 'Unknown error'))
            except:
                error_msg = token_response.text[:200]
            logger.error(f"Token exchange failed: {error_msg}")
            messages.error(request, f'Token exchange failed: {error_msg}')
            return redirect('accounts:register_author')
        
        token_data = token_response.json()
        access_token = token_data.get('access_token')
        
        if not access_token:
            messages.error(request, 'No access token received from Fayda.')
            return redirect('accounts:register_author')
        
        logger.info("Fetching user info...")
        userinfo_response = requests.get(
            userinfo_url,
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10,
            verify=True
        )
        
        if not userinfo_response.ok:
            logger.error(f"Userinfo request failed: {userinfo_response.status_code}")
            messages.error(request, 'Failed to retrieve user information from Fayda.')
            return redirect('accounts:register_author')
        
        decoded_user_info = None
        try:
            decoded_user_info = jwt.decode(
                userinfo_response.text,
                options={"verify_signature": False},
                algorithms=["RS256"]
            )
            logger.info("Decoded userinfo as JWT")
        except:
            try:
                decoded_user_info = userinfo_response.json()
                logger.info("Decoded userinfo as JSON")
            except:
                logger.error("Failed to decode userinfo")
                messages.error(request, 'Failed to decode user information.')
                return redirect('accounts:register_author')
        
        logger.info(f"Decoded userinfo keys: {list(decoded_user_info.keys())}")
        
        # Extract date of birth
        dob = ''
        possible_dob_fields = ['birthdate', 'date_of_birth', 'dob', 'birthDate', 'birth_date']
        for field in possible_dob_fields:
            if field in decoded_user_info and decoded_user_info[field]:
                dob = decoded_user_info[field]
                logger.info(f"Found DOB in field '{field}': '{dob}'")
                break
        
        if dob is not None:
            if isinstance(dob, (date, datetime)):
                dob = dob.strftime('%Y-%m-%d')
            else:
                dob = str(dob)
        
        # Extract gender
        gender = ''
        possible_gender_fields = ['gender', 'sex', 'gender_code', 'genderCode']
        for field in possible_gender_fields:
            if field in decoded_user_info and decoded_user_info[field]:
                gender = decoded_user_info[field]
                logger.info(f"Found gender in field '{field}': '{gender}'")
                break
        
        if gender is not None:
            gender = str(gender)
        
        # Extract and process picture
        picture = ''
        picture_original = decoded_user_info.get('picture', '')
        
        if picture_original:
            logger.info(f"Original picture found, type: {type(picture_original)}")
            if isinstance(picture_original, str):
                logger.info(f"Original picture preview: {picture_original[:200]}...")
            
            # Process the picture
            processed_picture = process_fayda_picture(picture_original)
            if processed_picture:
                if validate_picture_data_url(processed_picture):
                    picture = processed_picture
                    logger.info(f"Picture processed successfully, length: {len(picture)}")
                else:
                    logger.warning("Processed picture failed validation")
            else:
                logger.warning("Could not process picture")
        
        user_data = {
            'full_name': decoded_user_info.get('name', decoded_user_info.get('full_name', '')),
            'national_id': request.session.get('fayda_national_id', ''),
            'email': decoded_user_info.get('email', ''),
            'phone': decoded_user_info.get('phone_number', decoded_user_info.get('phone', '')),
            'address': decoded_user_info.get('address', ''),
            'region': decoded_user_info.get('region', ''),
            'zone': decoded_user_info.get('zone', ''),
            'woreda': decoded_user_info.get('woreda', ''),
            'date_of_birth': dob,
            'gender': gender,
            'nationality': decoded_user_info.get('nationality', ''),
            'individual_id': decoded_user_info.get('individual_id', ''),
            'picture': picture,
        }
        
        logger.info(f"Picture stored in user_data: {bool(picture)}")
        
        # Store in session
        request.session['fayda_verified_data'] = user_data
        request.session['fayda_verified'] = True
        
        # Store picture separately for template access
        if picture:
            request.session['fayda_picture'] = picture
            logger.info("Picture stored in session['fayda_picture']")
        else:
            request.session.pop('fayda_picture', None)
            logger.warning("No picture to store in session")
        
        # Clean up
        request.session.pop('fayda_state', None)
        request.session.pop('fayda_national_id', None)
        request.session.pop('fayda_nonce', None)
        request.session.pop('fayda_code_verifier', None)
        
        messages.success(request, f'Fayda verification successful! Welcome {user_data["full_name"]}.')
        return redirect('accounts:register_author')
        
    except requests.exceptions.Timeout:
        logger.error("Fayda service timeout")
        messages.error(request, 'Fayda service timeout. Please try again.')
    except requests.exceptions.ConnectionError:
        logger.error("Could not connect to Fayda service")
        messages.error(request, 'Could not connect to Fayda service. Please try again later.')
    except requests.exceptions.SSLError as e:
        logger.error(f"SSL error: {e}")
        messages.error(request, 'SSL error connecting to Fayda. Please check your configuration.')
    except Exception as e:
        logger.error(f"Callback processing error: {str(e)}")
        import traceback
        traceback.print_exc()
        messages.error(request, f'Authentication failed: {str(e)}')
    
    return redirect('accounts:register_author')


# ============================================
# DASHBOARD VIEWS
# ============================================

@login_required
def admin_dashboard(request):
    """Admin dashboard with comprehensive payment data"""
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect(role_based_redirect(request.user))

    today = timezone.now().date()
    week_start = today - timedelta(days=7)
    month_start = today.replace(day=1)

    # Initialize payment variables
    telebirr_sales = 0
    cbe_sales = 0
    total_sales = 0
    today_sales = 0
    week_sales = 0
    month_sales = 0
    monthly_sales = 0
    total_royalties = 0
    pending_payouts = 0
    completed_payouts = 0
    payment_methods = {}
    recent_transactions = []
    author_earnings = []

    try:
        from payments.models import Purchase, PaymentTransaction, Payment
        
        completed_purchases = Purchase.objects.filter(status='completed')
        
        def sum_amount(qs):
            result = qs.aggregate(total=Sum('amount'))['total']
            return result if result is not None else 0

        total_sales = sum_amount(completed_purchases)
        today_sales = sum_amount(completed_purchases.filter(created_at__date=today))
        week_sales = sum_amount(completed_purchases.filter(created_at__date__gte=week_start, created_at__date__lte=today))
        month_sales = sum_amount(completed_purchases.filter(created_at__date__gte=month_start, created_at__date__lte=today))
        monthly_sales = month_sales

        if hasattr(Purchase, 'payment_method'):
            methods = Purchase.objects.filter(status='completed').values_list('payment_method', flat=True).distinct()
            for method in methods:
                if method:
                    method_total = sum_amount(completed_purchases.filter(payment_method__icontains=method))
                    payment_methods[method] = float(method_total)
            
            telebirr_sales = sum_amount(completed_purchases.filter(payment_method__icontains='telebirr'))
            cbe_sales = sum_amount(completed_purchases.filter(Q(payment_method__icontains='cbe') | Q(payment_method__icontains='cbe_birr')))
        
        if hasattr(Payment, 'objects'):
            total_royalties = Payment.objects.aggregate(total=Sum('final_amount'))['total'] or 0
            pending_payouts = Payment.objects.filter(status__in=['calculated', 'pending']).aggregate(total=Sum('final_amount'))['total'] or 0
            completed_payouts = Payment.objects.filter(status='paid').aggregate(total=Sum('final_amount'))['total'] or 0
            recent_transactions = Payment.objects.all().order_by('-created_at')[:10]
            author_earnings = Payment.objects.values('author__username', 'author__full_name').annotate(
                total_earned=Sum('final_amount')
            ).order_by('-total_earned')[:10]

    except ImportError:
        pass
    except Exception as e:
        logger.error(f"Error fetching payment data: {str(e)}")

    context = {
        'user': request.user,
        'total_users': CustomUser.objects.count(),
        'total_authors': CustomUser.objects.filter(role='author').count(),
        'total_readers': CustomUser.objects.filter(role='client').count(),
        'total_books': Book.objects.count(),
        'published_books': Book.objects.filter(status='published').count(),
        'pending_books': Book.objects.filter(status='pending_review').count(),
        'total_downloads': Book.objects.aggregate(total=Sum('downloads_count'))['total'] or 0,
        'total_revenue': total_sales,
        'total_sales': total_sales,
        'monthly_sales': monthly_sales,
        'telebirr_sales': telebirr_sales,
        'cbe_sales': cbe_sales,
        'today_sales': today_sales,
        'week_sales': week_sales,
        'month_sales': month_sales,
        'total_royalties': total_royalties,
        'pending_payouts': pending_payouts,
        'completed_payouts': completed_payouts,
        'recent_transactions': recent_transactions,
        'author_earnings': author_earnings,
        'payment_methods': payment_methods,
    }
    return render(request, 'dashboard/admin_dashboard.html', context)


@login_required
def finance_dashboard(request):
    """Finance dashboard for managing author payments."""
    if request.user.role != 'finance' and request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect(role_based_redirect(request.user))

    author_payments = []
    recent_transactions_data = []
    total_revenue = 0
    total_paid = 0
    pending_payouts = 0
    total_authors = 0
    total_transactions = 0
    pending_count = 0
    paid_this_month = 0
    telebirr_percentage = 0
    cbe_percentage = 0

    try:
        from payments.models import Payment, Purchase, PaymentTransaction
        
        all_payments = Payment.objects.all()
        
        total_revenue = all_payments.aggregate(total=Sum('final_amount'))['total'] or 0
        total_paid = all_payments.filter(status='paid').aggregate(total=Sum('final_amount'))['total'] or 0
        pending_payouts = all_payments.filter(status__in=['calculated', 'pending']).aggregate(total=Sum('final_amount'))['total'] or 0
        
        author_data = all_payments.values(
            'author__id', 'author__username', 'author__full_name', 'author__phone'
        ).annotate(
            total_amount=Sum('final_amount'),
            latest_date=Max('created_at')
        ).order_by('-latest_date')
        
        for author in author_data[:50]:
            latest_payment = all_payments.filter(author_id=author['author__id']).order_by('-created_at').first()
            author_payments.append({
                'author_id': author['author__id'],
                'author_name': author['author__full_name'] or author['author__username'],
                'author_username': author['author__username'],
                'phone': author['author__phone'] or 'N/A',
                'amount': author['total_amount'] or 0,
                'status': latest_payment.status if latest_payment else 'pending',
                'payment_method': 'telebirr',
                'date': author['latest_date'] or timezone.now(),
            })
        
        total_authors = CustomUser.objects.filter(role='author').count()
        total_transactions = all_payments.count()
        pending_count = all_payments.filter(status__in=['calculated', 'pending']).count()
        
        month_start = timezone.now().replace(day=1)
        paid_this_month = all_payments.filter(
            status='paid',
            created_at__gte=month_start
        ).aggregate(total=Sum('final_amount'))['total'] or 0
        
        telebirr_count = PaymentTransaction.objects.filter(payment_method__icontains='telebirr').count()
        cbe_count = PaymentTransaction.objects.filter(payment_method__icontains='cbe').count()
        total_methods = telebirr_count + cbe_count
        telebirr_percentage = round((telebirr_count / total_methods * 100) if total_methods > 0 else 0)
        cbe_percentage = round((cbe_count / total_methods * 100) if total_methods > 0 else 0)
        
        recent_transactions = all_payments.select_related('author').order_by('-created_at')[:20]
        for tx in recent_transactions:
            recent_transactions_data.append({
                'author_name': tx.author.full_name or tx.author.username,
                'amount': tx.final_amount or 0,
                'status': tx.status,
                'payment_method': 'telebirr',
                'date': tx.created_at,
            })

    except ImportError as e:
        logger.warning(f"Payment models not available: {e}")
        total_authors = CustomUser.objects.filter(role='author').count()
    except Exception as e:
        logger.error(f"Error in finance dashboard: {str(e)}")

    context = {
        'user': request.user,
        'author_payments': author_payments,
        'recent_transactions': recent_transactions_data,
        'total_revenue': total_revenue,
        'total_paid': total_paid,
        'pending_payouts': pending_payouts,
        'total_authors': total_authors,
        'total_transactions': total_transactions,
        'pending_count': pending_count,
        'paid_this_month': paid_this_month,
        'telebirr_percentage': telebirr_percentage,
        'cbe_percentage': cbe_percentage,
    }
    return render(request, 'dashboard/finance_dashboard.html', context)


@login_required
def author_dashboard(request):
    if request.user.role != 'author':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect(role_based_redirect(request.user))

    user = request.user
    books = Book.objects.filter(author=user).order_by('-created_at')
    
    total_books = books.count()
    published_books = books.filter(status='published').count()
    pending_review = books.filter(status='pending_review').count()
    in_review = books.filter(status='in_review').count()
    needs_revision = books.filter(status='needs_revision').count()
    rejected = books.filter(status='rejected').count()
    checker_approved = books.filter(status='checker_approved').count()
    total_downloads = books.aggregate(total=Sum('downloads_count'))['total'] or 0
    recent_books = books[:10]
    
    try:
        for book in recent_books:
            quality_review = QualityReview.objects.filter(book=book, review_type='checker').first()
            book.quality_review_score = quality_review.overall_score if quality_review else None
    except Exception as e:
        logger.error(f"Error fetching quality reviews: {str(e)}")
    
    total_earned = 0
    total_paid = 0
    pending_earnings = 0
    total_tax = 0
    
    try:
        from payments.models import Payment
        payments = Payment.objects.filter(author=user)
        total_earned = payments.aggregate(total=Sum('final_amount'))['total'] or 0
        total_paid = payments.filter(status='paid').aggregate(total=Sum('final_amount'))['total'] or 0
        pending_earnings = payments.filter(status__in=['calculated', 'pending']).aggregate(total=Sum('final_amount'))['total'] or 0
        total_tax = payments.aggregate(total=Sum('tax_amount'))['total'] or 0
    except ImportError:
        pass
    except Exception as e:
        logger.error(f"Error fetching payment data: {str(e)}")
    
    try:
        author_profile = AuthorProfile.objects.get(user=user)
    except AuthorProfile.DoesNotExist:
        author_profile = None

    context = {
        'user': user,
        'author_profile': author_profile,
        'total_books': total_books,
        'published_books': published_books,
        'pending_review': pending_review,
        'in_review': in_review,
        'needs_revision': needs_revision,
        'rejected': rejected,
        'checker_approved': checker_approved,
        'total_downloads': total_downloads,
        'recent_books': recent_books,
        'total_earned': total_earned,
        'total_paid': total_paid,
        'pending_earnings': pending_earnings,
        'total_tax': total_tax,
    }
    return render(request, 'dashboard/author_dashboard.html', context)


@login_required
def checker_dashboard(request):
    if request.user.role != 'checker':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect(role_based_redirect(request.user))

    pending_books = Book.objects.filter(status='pending_review').order_by('created_at')
    reviewed_books = QualityReview.objects.filter(reviewer=request.user, review_type='checker').select_related('book', 'book__author').order_by('-created_at')[:20]

    total_pending = pending_books.count()
    total_reviewed = reviewed_books.count()
    avg_score = reviewed_books.aggregate(avg=Avg('overall_score'))['avg'] or 0

    current_month = timezone.now().month
    current_year = timezone.now().year
    reviewed_this_month = QualityReview.objects.filter(reviewer=request.user, review_type='checker', created_at__year=current_year, created_at__month=current_month).count()

    context = {
        'user': request.user,
        'pending_books': pending_books,
        'reviewed_books': reviewed_books,
        'total_pending': total_pending,
        'total_reviewed': total_reviewed,
        'avg_score': avg_score,
        'reviewed_this_month': reviewed_this_month,
    }
    return render(request, 'dashboard/checker_dashboard.html', context)


@login_required
def process_checker_review(request):
    if request.user.role != 'checker':
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect(role_based_redirect(request.user))

    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('accounts:checker_dashboard')

    book_id = request.POST.get('book_id')
    content_quality = request.POST.get('content_quality')
    editorial_quality = request.POST.get('editorial_quality')
    technical_quality = request.POST.get('technical_quality')
    copyright_compliance = request.POST.get('copyright_compliance')
    community_guidelines = request.POST.get('community_guidelines')
    comments = request.POST.get('comments')
    recommendation = request.POST.get('recommendation')

    if not all([book_id, content_quality, editorial_quality, technical_quality, recommendation]):
        messages.error(request, 'Please fill in all required fields.')
        return redirect('accounts:checker_dashboard')

    try:
        book = Book.objects.get(id=book_id)
        scores = [
            float(content_quality),
            float(editorial_quality),
            float(technical_quality),
            float(copyright_compliance) if copyright_compliance else 0,
            float(community_guidelines) if community_guidelines else 0,
        ]
        for score in scores:
            if score < 0 or score > 10:
                messages.error(request, 'Scores must be between 0 and 10.')
                return redirect('accounts:checker_dashboard')

        overall_score = sum(scores) / len(scores)

        if recommendation == 'approved':
            book.status = 'checker_approved'
        elif recommendation == 'needs_revision':
            book.status = 'needs_revision'
        else:
            book.status = 'rejected'

        book.checker_reviewed_at = timezone.now()
        book.checker_score = round(overall_score, 1)
        book.save()

        quality_review, created = QualityReview.objects.update_or_create(
            book=book,
            reviewer=request.user,
            review_type='checker',
            defaults={
                'content_quality': float(content_quality),
                'editorial_quality': float(editorial_quality),
                'technical_quality': float(technical_quality),
                'overall_score': round(overall_score, 1),
                'comments': sanitize_input(comments),
                'recommendation': recommendation,
                'updated_at': timezone.now(),
            }
        )

        if created:
            quality_review.created_at = timezone.now()
            quality_review.save()

        messages.success(request, f'Review for "{book.title}" submitted successfully!')
    except Book.DoesNotExist:
        messages.error(request, 'Book not found.')
    except ValueError:
        messages.error(request, 'Invalid score values.')
    except Exception as e:
        logger.error(f"Error processing review: {str(e)}")
        messages.error(request, f'An error occurred: {str(e)}')

    return redirect('accounts:checker_dashboard')


@login_required
def view_book_for_review(request, book_id):
    if request.user.role != 'checker':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect(role_based_redirect(request.user))

    book = get_object_or_404(Book, id=book_id, status='pending_review')
    context = {
        'user': request.user,
        'book': book,
    }
    return render(request, 'reviews/review_book.html', context)


@login_required
def maker_dashboard(request):
    if request.user.role != 'maker':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect(role_based_redirect(request.user))

    pending_books = Book.objects.filter(status='checker_approved').order_by('checker_reviewed_at')
    published_books = Book.objects.filter(status='published', published_at__month=timezone.now().month).order_by('-published_at')[:10]

    pending_count = pending_books.count()
    approved_count = Book.objects.filter(status='published', published_at__month=timezone.now().month).count()
    total_published = Book.objects.filter(status='published').count()

    context = {
        'user': request.user,
        'pending_books': pending_books,
        'published_books': published_books,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'published_count': approved_count,
        'total_published': total_published,
    }
    return render(request, 'dashboard/maker_dashboard.html', context)


@login_required
def publish_book(request, book_id):
    if request.user.role != 'maker':
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect(role_based_redirect(request.user))

    book = get_object_or_404(Book, id=book_id, status='checker_approved')

    if request.method == 'POST':
        book.status = 'published'
        book.published_at = timezone.now()
        book.maker_approved_at = timezone.now()
        book.save()
        messages.success(request, f'Book "{book.title}" has been published successfully!')
        return redirect('accounts:maker_dashboard')

    context = {
        'user': request.user,
        'book': book,
    }
    return render(request, 'books/publish_confirm.html', context)


@login_required
def client_dashboard(request):
    if request.user.role != 'client':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect(role_based_redirect(request.user))

    try:
        from payments.models import Purchase
        from books.models import Wishlist

        purchases = Purchase.objects.filter(user=request.user, status='completed')
        wishlist_count = Wishlist.objects.filter(user=request.user).count()
        total_spent = purchases.aggregate(total=Sum('amount'))['total'] or 0

        context = {
            'user': request.user,
            'purchases_count': purchases.count(),
            'recent_purchases': purchases.order_by('-created_at')[:10],
            'wishlist_count': wishlist_count,
            'total_spent': total_spent,
        }
    except ImportError:
        context = {
            'user': request.user,
            'purchases_count': 0,
            'recent_purchases': [],
            'wishlist_count': 0,
            'total_spent': 0,
        }
    except Exception as e:
        logger.error(f"Error in client_dashboard: {str(e)}")
        context = {
            'user': request.user,
            'purchases_count': 0,
            'recent_purchases': [],
            'wishlist_count': 0,
            'total_spent': 0,
        }

    return render(request, 'dashboard/client_dashboard.html', context)


@login_required
def profile_view(request):
    return render(request, 'accounts/profile.html', {'user': request.user})


@login_required
def profile_edit(request):
    if request.method == 'POST':
        user = request.user
        user.full_name = sanitize_input(request.POST.get('full_name', user.full_name))
        user.phone = sanitize_input(request.POST.get('phone', user.phone))
        user.address = sanitize_input(request.POST.get('address', user.address))
        user.region = sanitize_input(request.POST.get('region', user.region))
        user.zone = sanitize_input(request.POST.get('zone', user.zone))
        user.woreda = sanitize_input(request.POST.get('woreda', user.woreda))

        if request.FILES.get('profile_image'):
            if request.FILES['profile_image'].size > 5 * 1024 * 1024:
                messages.error(request, 'Profile image size must be less than 5MB.')
                return render(request, 'accounts/profile_edit.html', {'user': user})
            user.profile_image = request.FILES['profile_image']

        user.save()
        messages.success(request, 'Profile updated successfully!')
        return redirect('accounts:profile')

    return render(request, 'accounts/profile_edit.html', {'user': request.user})