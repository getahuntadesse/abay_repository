from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie, csrf_exempt
from django.views.decorators.debug import sensitive_post_parameters
from django.db import models
from django.db.models import Avg, Count, Q, Sum
from django.http import JsonResponse
from django.conf import settings
from datetime import timedelta, datetime
import json
import requests
import logging
import jwt
import base64
import time
import hashlib
import urllib
import os
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from decouple import config

from .forms import LoginForm, ClientRegistrationForm, AuthorRegistrationForm
from .models import CustomUser, AuthorProfile, ClientProfile
from books.models import Book, Genre
from reviews.models import QualityReview

# Set up logger
logger = logging.getLogger(__name__)

# ============================================
# FAYDA OIDC HELPERS - Matching Working OIDC App
# ============================================

def base64url_decode(input_str):
    """Decode base64url string with padding"""
    padding = '=' * (4 - (len(input_str) % 4))
    return base64.urlsafe_b64decode(input_str + padding)


def load_private_key_from_string(base64_key_str):
    """Load RSA private key from base64 encoded JWK string"""
    logger.info("Loading private key from base64 key string")
    try:
        # Decode the base64 string
        key_bytes = base64.b64decode(base64_key_str)
        jwk_data = json.loads(key_bytes)

        # Decode the base64url components
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
    """
    Generate signed JWT for Fayda client assertion.
    This matches the working OIDC app methodology exactly.
    """
    logger.info("Generating signed JWT for Fayda Assertion...")
    
    # Use the same approach as the working OIDC app - no kid header
    header = {
        "alg": "RS256",
        "typ": "JWT",
    }

    # Use the same approach as the working OIDC app
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


# ============================================
# ACCOUNT VIEWS
# ============================================

@sensitive_post_parameters()
@csrf_protect
@ensure_csrf_cookie
def login_view(request):
    """User login view - redirects based on role"""
    if request.user.is_authenticated:
        return redirect(role_based_redirect(request.user))
    
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            remember = form.cleaned_data.get('remember', False)
            
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                login(request, user)
                
                if not remember:
                    request.session.set_expiry(0)
                else:
                    request.session.set_expiry(1209600)
                
                messages.success(request, f'Welcome back, {user.full_name}!')
                
                return redirect(role_based_redirect(user))
            else:
                messages.error(request, 'Invalid username or password.')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = LoginForm()
    
    return render(request, 'accounts/login.html', {'form': form})


def role_based_redirect(user):
    """Return the appropriate dashboard URL based on user role"""
    role_redirects = {
        'admin': 'accounts:admin_dashboard',
        'author': 'accounts:author_dashboard',
        'checker': 'accounts:checker_dashboard',
        'maker': 'accounts:maker_dashboard',
        'client': 'accounts:client_dashboard',
    }
    return role_redirects.get(user.role, 'accounts:client_dashboard')


def logout_view(request):
    """User logout view"""
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('home')


@csrf_protect
@ensure_csrf_cookie
def register_view(request):
    """Client/Reader registration view"""
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')
    
    if request.method == 'POST':
        form = ClientRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Welcome to Abrehot Library, {user.full_name}!')
            return redirect('accounts:dashboard')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ClientRegistrationForm()
    
    return render(request, 'accounts/register_client.html', {'form': form})


@csrf_protect
@ensure_csrf_cookie
def register_author(request):
    """Author registration view with Fayda ID verification"""
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')
    
    verified_data = request.session.pop('fayda_verified_data', None)
    
    if request.method == 'POST':
        form = AuthorRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Welcome Author! {user.full_name}, your profile has been created.')
            return redirect('accounts:dashboard')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = AuthorRegistrationForm()
        if verified_data:
            form.initial = {
                'full_name': verified_data.get('full_name', ''),
                'national_id': verified_data.get('national_id', ''),
            }
    
    context = {
        'form': form,
        'verified_data': verified_data,
        'debug': settings.DEBUG,
    }
    return render(request, 'accounts/register_author.html', context)


@csrf_exempt
def oidc_callback_view(request):
    """
    Handle OIDC callback from Fayda via GET request.
    This view receives the authorization code from Fayda after authentication
    and processes it to get user information.
    """
    # Get parameters from the URL
    code = request.GET.get('code')
    state = request.GET.get('state')
    error = request.GET.get('error')
    error_description = request.GET.get('error_description')
    
    # Check for errors from Fayda
    if error:
        messages.error(request, f'Fayda authentication error: {error_description or error}')
        return redirect('accounts:register_author')
    
    # Validate required parameters
    if not code or not state:
        messages.error(request, 'Missing authorization code or state parameter.')
        return redirect('accounts:register_author')
    
    # Verify state matches session
    session_state = request.session.get('fayda_state')
    if state != session_state:
        logger.warning(f"OIDC state mismatch: received {state}, expected {session_state}")
        messages.error(request, 'Invalid state parameter. Please try again.')
        return redirect('accounts:register_author')
    
    try:
        # Get OIDC configuration
        client_id = config('FAYDA_CLIENT_ID')
        token_url = config('FAYDA_TOKEN_URL')
        userinfo_url = config('FAYDA_USERINFO_URL')
        redirect_uri = config('FAYDA_REDIRECT_URI')
        private_key_b64 = config('FAYDA_PRIVATE_KEY_B64')
        
        logger.info(f"=== Processing OIDC Callback ===")
        logger.info(f"Client ID: {client_id[:10] if client_id else 'None'}...")
        logger.info(f"Code: {code[:20]}...")
        
        # Get code verifier from session
        code_verifier = request.session.get('fayda_code_verifier', '')
        
        # Generate signed JWT for client assertion - MATCHING WORKING APP
        signed_jwt = generate_signed_jwt(client_id, token_url, private_key_b64)
        
        if not signed_jwt:
            logger.error("Failed to generate signed JWT")
            messages.error(request, 'Failed to generate authentication token.')
            return redirect('accounts:register_author')
        
        logger.info("Signed JWT generated successfully")
        
        # Exchange code for token - MATCHING THE WORKING OIDC APP EXACTLY
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
            timeout=30
        )
        
        logger.info(f"Token response status: {token_response.status_code}")
        logger.info(f"Token response body: {token_response.text[:500]}")
        
        if not token_response.ok:
            logger.error(f"Token exchange failed: {token_response.status_code}")
            try:
                error_data = token_response.json()
                logger.error(f"Error details: {error_data}")
                error_msg = error_data.get('error_description', error_data.get('error', 'Unknown error'))
            except:
                error_msg = token_response.text[:200]
            
            messages.error(request, f'Token exchange failed: {error_msg}')
            return redirect('accounts:register_author')
        
        token_data = token_response.json()
        access_token = token_data.get('access_token')
        
        if not access_token:
            logger.error(f"No access token received")
            messages.error(request, 'No access token received from Fayda.')
            return redirect('accounts:register_author')
        
        logger.info("Access token received successfully")
        
        # Get user information
        userinfo_response = requests.get(
            userinfo_url,
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10
        )
        
        if not userinfo_response.ok:
            logger.error(f"Userinfo request failed: {userinfo_response.status_code} - {userinfo_response.text}")
            messages.error(request, 'Failed to retrieve user information from Fayda.')
            return redirect('accounts:register_author')
        
        # Decode user info (it's a JWT) - MATCHING WORKING APP
        try:
            decoded_user_info = jwt.decode(
                userinfo_response.text,
                options={"verify_signature": False},
                algorithms=["RS256"]
            )
            logger.info(f"Userinfo decoded successfully")
        except Exception as e:
            logger.error(f"Failed to decode userinfo JWT: {str(e)}")
            messages.error(request, 'Failed to decode user information.')
            return redirect('accounts:register_author')
        
        # Map userinfo to our format
        user_data = {
            'full_name': decoded_user_info.get('name', ''),
            'date_of_birth': decoded_user_info.get('birthdate', ''),
            'gender': decoded_user_info.get('gender', ''),
            'region': decoded_user_info.get('region', ''),
            'zone': decoded_user_info.get('zone', ''),
            'woreda': decoded_user_info.get('woreda', ''),
            'address': decoded_user_info.get('address', ''),
            'phone': decoded_user_info.get('phone_number', ''),
            'email': decoded_user_info.get('email', ''),
            'nationality': decoded_user_info.get('nationality', ''),
            'individual_id': decoded_user_info.get('individual_id', ''),
            'national_id': request.session.get('fayda_national_id', '')
        }
        
        logger.info(f"OIDC callback successful for user: {user_data['full_name']}")
        
        # Store verified data in session for the registration form
        request.session['fayda_verified_data'] = user_data
        
        # Clear session data
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
    except Exception as e:
        logger.error(f"Callback processing error: {str(e)}")
        import traceback
        traceback.print_exc()
        messages.error(request, f'Authentication failed: {str(e)}')
    
    return redirect('accounts:register_author')


@csrf_exempt
def oidc_initiate(request):
    """
    Initiate OIDC flow with Fayda eSignet using UAT credentials.
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
        
        # Get OIDC configuration
        client_id = config('FAYDA_CLIENT_ID')
        auth_url = config('FAYDA_AUTH_URL')
        redirect_uri = config('FAYDA_REDIRECT_URI')
        
        # Generate PKCE
        code_verifier, code_challenge = generate_pkce()
        request.session['fayda_code_verifier'] = code_verifier
        
        # Store in session for callback verification
        request.session['fayda_national_id'] = national_id_clean
        request.session['fayda_state'] = state
        request.session['fayda_nonce'] = nonce
        
        # Build claims - MATCHING WORKING APP
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
        
        # Build the authorization URL with PKCE - MATCHING WORKING APP
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
        )
        
        logger.info(f"OIDC initiated for national_id: {national_id_clean[:4] if national_id_clean else 'None'}****")
        
        return JsonResponse({
            'success': True,
            'authorization_url': authorization_url,
            'message': 'Redirect to Fayda for authentication'
        })
        
    except Exception as e:
        logger.error(f"OIDC initiate error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        }, status=500)


@csrf_exempt
def oidc_callback(request):
    """
    Handle OIDC callback from Fayda - API endpoint for frontend JavaScript.
    This exchanges the authorization code for user information.
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
        
        # Verify state matches session
        session_state = request.session.get('fayda_state')
        if state != session_state:
            logger.warning(f"OIDC state mismatch: received {state}, expected {session_state}")
            return JsonResponse({
                'success': False,
                'message': 'Invalid state parameter. Possible CSRF attack.'
            }, status=400)
        
        # Get configuration
        client_id = config('FAYDA_CLIENT_ID')
        token_url = config('FAYDA_TOKEN_URL')
        userinfo_url = config('FAYDA_USERINFO_URL')
        redirect_uri = config('FAYDA_REDIRECT_URI')
        private_key_b64 = config('FAYDA_PRIVATE_KEY_B64')
        
        # Get code verifier from session
        code_verifier = request.session.get('fayda_code_verifier', '')
        
        # Generate signed JWT for client assertion - MATCHING WORKING APP
        signed_jwt = generate_signed_jwt(client_id, token_url, private_key_b64)
        
        if not signed_jwt:
            return JsonResponse({
                'success': False,
                'message': 'Failed to generate client assertion.'
            }, status=500)
        
        # Exchange code for token - MATCHING THE WORKING OIDC APP EXACTLY
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
            timeout=30
        )
        
        logger.info(f"Token response status: {token_response.status_code}")
        
        if not token_response.ok:
            logger.error(f"Token exchange failed: {token_response.status_code} - {token_response.text}")
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
        
        # Get user information
        userinfo_response = requests.get(
            userinfo_url,
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10
        )
        
        if not userinfo_response.ok:
            logger.error(f"Userinfo request failed: {userinfo_response.status_code} - {userinfo_response.text}")
            return JsonResponse({
                'success': False,
                'message': 'Failed to retrieve user information from Fayda.'
            }, status=400)
        
        # Decode user info (it's a JWT) - MATCHING WORKING APP
        try:
            decoded_user_info = jwt.decode(
                userinfo_response.text,
                options={"verify_signature": False},
                algorithms=["RS256"]
            )
        except Exception as e:
            logger.error(f"Failed to decode userinfo JWT: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': 'Failed to decode user information.'
            }, status=400)
        
        # Map userinfo to our format
        user_data = {
            'full_name': decoded_user_info.get('name', ''),
            'date_of_birth': decoded_user_info.get('birthdate', ''),
            'gender': decoded_user_info.get('gender', ''),
            'region': decoded_user_info.get('region', ''),
            'zone': decoded_user_info.get('zone', ''),
            'woreda': decoded_user_info.get('woreda', ''),
            'address': decoded_user_info.get('address', ''),
            'phone': decoded_user_info.get('phone_number', ''),
            'email': decoded_user_info.get('email', ''),
            'nationality': decoded_user_info.get('nationality', ''),
            'individual_id': decoded_user_info.get('individual_id', ''),
        }
        
        logger.info(f"OIDC callback successful for user: {user_data['full_name']}")
        
        # Clear session data
        request.session.pop('fayda_state', None)
        request.session.pop('fayda_national_id', None)
        request.session.pop('fayda_nonce', None)
        request.session.pop('fayda_code_verifier', None)
        
        return JsonResponse({
            'success': True,
            'message': 'Verification successful',
            'data': user_data
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
    except Exception as e:
        logger.error(f"OIDC callback error: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        }, status=500)


@login_required
def dashboard_redirect(request):
    """Redirect users to their respective dashboards based on role"""
    return redirect(role_based_redirect(request.user))


@login_required
def admin_dashboard(request):
    """Admin dashboard view"""
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('accounts:dashboard')
    
    today = timezone.now().date()
    week_start = today - timedelta(days=7)
    month_start = today.replace(day=1)
    
    telebirr_sales = 0
    cbe_sales = 0
    total_sales = 0
    today_sales = 0
    week_sales = 0
    month_sales = 0
    monthly_sales = 0
    
    try:
        from payments.models import Purchase, PaymentTransaction
        
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
            telebirr_sales = sum_amount(completed_purchases.filter(payment_method__icontains='telebirr'))
            cbe_sales = sum_amount(completed_purchases.filter(Q(payment_method__icontains='cbe') | Q(payment_method__icontains='cbe_birr')))
        elif hasattr(PaymentTransaction, 'payment_method'):
            completed_transactions = PaymentTransaction.objects.filter(status='completed')
            telebirr_sales = sum_amount(completed_transactions.filter(payment_method__icontains='telebirr'))
            cbe_sales = sum_amount(completed_transactions.filter(Q(payment_method__icontains='cbe') | Q(payment_method__icontains='cbe_birr')))
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
    }
    return render(request, 'dashboard/admin_dashboard.html', context)


@login_required
def author_dashboard(request):
    """Author dashboard view"""
    if request.user.role != 'author':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('accounts:dashboard')
    
    books = Book.objects.filter(author=request.user)
    
    context = {
        'user': request.user,
        'total_books': books.count(),
        'published_books': books.filter(status='published').count(),
        'pending_review': books.filter(status='pending_review').count(),
        'in_review': books.filter(status='in_review').count(),
        'needs_revision': books.filter(status='needs_revision').count(),
        'recent_books': books.order_by('-created_at')[:10],
        'total_downloads': books.aggregate(total=Sum('downloads_count'))['total'] or 0,
        'total_earned': 0,
        'pending_earnings': 0,
    }
    return render(request, 'dashboard/author_dashboard.html', context)


@login_required
def checker_dashboard(request):
    """Checker dashboard view"""
    if request.user.role != 'checker':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('accounts:dashboard')
    
    pending_books = Book.objects.filter(status='pending_review').order_by('created_at')
    reviewed_books = QualityReview.objects.filter(reviewer=request.user, review_type='checker').select_related('book', 'book__author').order_by('-created_at')[:20]
    
    total_pending = pending_books.count()
    total_reviewed = reviewed_books.count()
    avg_score = reviewed_books.aggregate(avg=Avg('overall_score'))['avg'] or 0
    
    current_month = timezone.now().month
    current_year = timezone.now().year
    reviewed_this_month = QualityReview.objects.filter(reviewer=request.user, review_type='checker', created_at__year=current_year, created_at__month=current_month).count()
    
    scoring_criteria = {
        'excellent': {'min': 9, 'max': 10, 'label': 'Excellent', 'description': 'Exceptional quality, ready for publication with no issues'},
        'good': {'min': 7, 'max': 8, 'label': 'Good', 'description': 'Good quality, minor improvements recommended'},
        'average': {'min': 5, 'max': 6, 'label': 'Average', 'description': 'Acceptable but needs significant improvements'},
        'below_average': {'min': 3, 'max': 4, 'label': 'Below Average', 'description': 'Major issues, needs substantial revision'},
        'poor': {'min': 0, 'max': 2, 'label': 'Poor', 'description': 'Unacceptable quality, recommend rejection'},
    }
    
    recommendation_guide = {
        'approved': {'min_score': 7.0, 'label': '✅ Pass to Maker', 'description': 'Score ≥ 7.0, meets all quality standards'},
        'needs_revision': {'min_score': 5.0, 'max_score': 6.9, 'label': '🔄 Request Revision', 'description': 'Score 5.0-6.9, needs improvements but has potential'},
        'rejected': {'max_score': 4.9, 'label': '❌ Reject', 'description': 'Score < 5.0, serious quality issues or guideline violations'},
    }
    
    context = {
        'user': request.user,
        'pending_books': pending_books,
        'reviewed_books': reviewed_books,
        'total_pending': total_pending,
        'total_reviewed': total_reviewed,
        'avg_score': avg_score,
        'reviewed_this_month': reviewed_this_month,
        'scoring_criteria': scoring_criteria,
        'recommendation_guide': recommendation_guide,
    }
    return render(request, 'dashboard/checker_dashboard.html', context)


@login_required
def process_checker_review(request):
    """Process the checker's review submission"""
    if request.user.role != 'checker':
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('accounts:dashboard')
    
    if request.method == 'POST':
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
            overall_score = sum(scores) / len(scores)
            
            if recommendation == 'approved':
                book.status = 'checker_approved'
            elif recommendation == 'needs_revision':
                book.status = 'needs_revision'
            else:
                book.status = 'rejected'
            
            book.checker_reviewed_at = timezone.now()
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
                    'comments': comments,
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
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')
    
    return redirect('accounts:checker_dashboard')


@login_required
def view_book_for_review(request, book_id):
    """View book details for review"""
    if request.user.role != 'checker':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('accounts:dashboard')
    
    book = get_object_or_404(Book, id=book_id, status='pending_review')
    
    context = {
        'user': request.user,
        'book': book,
    }
    return render(request, 'reviews/review_book.html', context)


@login_required
def maker_dashboard(request):
    """Maker dashboard view"""
    if request.user.role != 'maker':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('accounts:dashboard')
    
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
    """Publish a book (Maker action)"""
    if request.user.role != 'maker':
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('accounts:dashboard')
    
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
    """Client dashboard view"""
    if request.user.role != 'client':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('accounts:dashboard')
    
    from payments.models import Purchase
    from books.models import Wishlist
    
    purchases = Purchase.objects.filter(client=request.user, status='completed')
    
    context = {
        'user': request.user,
        'purchases_count': purchases.count(),
        'recent_purchases': purchases.order_by('-created_at')[:10],
        'wishlist_count': Wishlist.objects.filter(client=request.user).count(),
        'total_spent': purchases.aggregate(total=Sum('amount'))['total'] or 0,
    }
    return render(request, 'dashboard/client_dashboard.html', context)


@login_required
def profile_view(request):
    """User profile view"""
    return render(request, 'accounts/profile.html', {'user': request.user})


@login_required
def profile_edit(request):
    """Edit user profile"""
    if request.method == 'POST':
        user = request.user
        user.full_name = request.POST.get('full_name', user.full_name)
        user.phone = request.POST.get('phone', user.phone)
        user.address = request.POST.get('address', user.address)
        user.region = request.POST.get('region', user.region)
        user.zone = request.POST.get('zone', user.zone)
        user.woreda = request.POST.get('woreda', user.woreda)
        
        if request.FILES.get('profile_image'):
            user.profile_image = request.FILES['profile_image']
        
        user.save()
        messages.success(request, 'Profile updated successfully!')
        return redirect('accounts:profile')
    
    return render(request, 'accounts/profile_edit.html', {'user': request.user})