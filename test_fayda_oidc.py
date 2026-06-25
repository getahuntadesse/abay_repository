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


def debug_log(message, data=None, level='info'):
    """Helper function for debugging with timestamps"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    log_message = f"[{timestamp}] {message}"
    if data:
        log_message += f"\nData: {json.dumps(data, default=str, indent=2) if isinstance(data, dict) else data}"
    
    if level == 'error':
        logger.error(log_message)
    elif level == 'warning':
        logger.warning(log_message)
    else:
        logger.info(log_message)
    
    print(log_message)


def verify_private_key_pairing(private_key_b64, client_id, token_url):
    """
    Verify that the private key is correctly paired with the Client ID.
    This function tests the key by generating a JWT and attempting to validate it.
    """
    debug_log("=== VERIFYING PRIVATE KEY PAIRING ===")
    
    try:
        # 1. Decode and parse the private key
        decoded = base64.b64decode(private_key_b64)
        key_data = json.loads(decoded.decode('utf-8'))
        
        debug_log(f"Key components found: {list(key_data.keys())}")
        debug_log(f"Key ID (kid): {key_data.get('kid', 'Not found')}")
        debug_log(f"Key Type (kty): {key_data.get('kty', 'Not found')}")
        debug_log(f"Algorithm (alg): {key_data.get('alg', 'Not found')}")
        debug_log(f"Key Usage (use): {key_data.get('use', 'Not found')}")
        
        # 2. Reconstruct the private key
        def b64url_to_int(value):
            padding = 4 - (len(value) % 4)
            if padding != 4:
                value += '=' * padding
            value = value.replace('-', '+').replace('_', '/')
            return int.from_bytes(base64.b64decode(value), byteorder='big')
        
        private_key = rsa.RSAPrivateNumbers(
            p=b64url_to_int(key_data['p']),
            q=b64url_to_int(key_data['q']),
            d=b64url_to_int(key_data['d']),
            dmp1=b64url_to_int(key_data['dp']),
            dmq1=b64url_to_int(key_data['dq']),
            iqmp=b64url_to_int(key_data['qi']),
            public_numbers=rsa.RSAPublicNumbers(
                e=b64url_to_int(key_data['e']),
                n=b64url_to_int(key_data['n'])
            )
        ).private_key(default_backend())
        
        # 3. Generate a test JWT matching Fayda eSignet expectations
        now = datetime.utcnow()
        test_payload = {
            'iss': client_id,
            'sub': client_id,
            'aud': token_url,
            'iat': int(now.timestamp()) - 10,  # 10s back clock-skew protection
            'nbf': int(now.timestamp()) - 10,  # Mandatory for MOSIP
            'exp': int((now + timedelta(minutes=5)).timestamp()),
            'jti': str(int(time.time() * 1000))
        }
        
        # 4. Encode the test JWT
        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        headers = {}
        if 'kid' in key_data:
            headers['kid'] = key_data['kid']

        test_jwt = jwt.encode(test_payload, pem, algorithm='RS256', headers=headers)
        
        # 5. Verify the JWT can be decoded with the public key
        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        decoded_jwt = jwt.decode(test_jwt, options={"verify_signature": False})
        debug_log(f"Test JWT decoded successfully. Claims: {list(decoded_jwt.keys())}")
        
        try:
            jwt.decode(test_jwt, public_pem, algorithms=['RS256'])
            debug_log("✅ JWT signature verification successful! Private key is valid.")
            return True, "Private key is valid and correctly paired"
        except jwt.InvalidSignatureError:
            debug_log("❌ JWT signature verification failed!", level='error')
            return False, "Private key signature verification failed"
            
    except Exception as e:
        debug_log(f"❌ Private key verification failed: {str(e)}", level='error')
        return False, f"Private key verification failed: {str(e)}"


def verify_client_id_status(client_id):
    """Verify if the Client ID is active by checking its format and validity."""
    debug_log("=== VERIFYING CLIENT ID STATUS ===")
    
    if not client_id:
        return False, "Client ID is empty"
    
    if len(client_id) < 20:
        return False, f"Client ID length ({len(client_id)}) is too short"
    
    import re
    if not re.match(r'^[a-zA-Z0-9_-]+$', client_id):
        return False, f"Client ID contains invalid characters: {client_id}"
    
    debug_log(f"✅ Client ID format is valid. Length: {len(client_id)}")
    return True, f"Client ID format is valid (length: {len(client_id)})"


def verify_kid_match(key_data):
    """Verify the Key ID (kid) is present and formatted correctly."""
    debug_log("=== VERIFYING KEY ID (kid) ===")
    
    kid = key_data.get('kid')
    if not kid:
        return False, "Key ID (kid) is missing from the private key"
    
    if len(kid) < 10:
        return False, f"Key ID is too short: {kid}"
    
    import re
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    if not re.match(uuid_pattern, kid, re.IGNORECASE):
        debug_log(f"⚠️ Warning: Key ID is not a standard UUID format: {kid}", level='warning')
        return True, f"Key ID present (non-UUID format): {kid}"
    
    debug_log(f"✅ Key ID (kid) is valid: {kid}")
    return True, f"Key ID is valid UUID: {kid}"


def verify_credential_compatibility(client_id, private_key_b64):
    """Comprehensive verification of credentials."""
    debug_log("=== STARTING COMPREHENSIVE CREDENTIAL VERIFICATION ===")
    
    results = {
        'client_id_status': {'status': False, 'message': ''},
        'private_key_status': {'status': False, 'message': ''},
        'kid_status': {'status': False, 'message': ''},
        'pairing_status': {'status': False, 'message': ''}
    }
    
    client_status, client_msg = verify_client_id_status(client_id)
    results['client_id_status'] = {'status': client_status, 'message': client_msg}
    
    try:
        decoded = base64.b64decode(private_key_b64)
        key_data = json.loads(decoded.decode('utf-8'))
        results['private_key_status'] = {'status': True, 'message': 'Private key parsed successfully'}
        
        kid_status, kid_msg = verify_kid_match(key_data)
        results['kid_status'] = {'status': kid_status, 'message': kid_msg}
        
        token_url = config('FAYDA_TOKEN_URL')
        pairing_status, pairing_msg = verify_private_key_pairing(private_key_b64, client_id, token_url)
        results['pairing_status'] = {'status': pairing_status, 'message': pairing_msg}
        
    except Exception as e:
        results['private_key_status'] = {'status': False, 'message': f'Failed to parse private key: {str(e)}'}
    
    debug_log("\n=== CREDENTIAL VERIFICATION SUMMARY ===")
    for key, value in results.items():
        status_icon = "✅" if value['status'] else "❌"
        debug_log(f"{status_icon} {key.replace('_', ' ').title()}: {value['message']}")
    
    return results


def get_private_key_from_jwk(private_key_b64):
    """Convert the Base64 encoded JWK to a PEM private key."""
    if not private_key_b64:
        logger.error("Private key is empty or None")
        return None
    
    try:
        decoded = base64.b64decode(private_key_b64)
        key_data = json.loads(decoded.decode('utf-8'))
        
        def b64url_to_int(value):
            padding = 4 - (len(value) % 4)
            if padding != 4:
                value += '=' * padding
            value = value.replace('-', '+').replace('_', '/')
            return int.from_bytes(base64.b64decode(value), byteorder='big')
        
        private_key = rsa.RSAPrivateNumbers(
            p=b64url_to_int(key_data['p']),
            q=b64url_to_int(key_data['q']),
            d=b64url_to_int(key_data['d']),
            dmp1=b64url_to_int(key_data['dp']),
            dmq1=b64url_to_int(key_data['dq']),
            iqmp=b64url_to_int(key_data['qi']),
            public_numbers=rsa.RSAPublicNumbers(
                e=b64url_to_int(key_data['e']),
                n=b64url_to_int(key_data['n'])
            )
        ).private_key(default_backend())
        
        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        return pem
        
    except Exception as e:
        logger.error(f"Failed to get private key from JWK: {str(e)}")
        return None


def generate_client_assertion(client_id, token_url, private_key_b64):
    """
    Generate a client assertion JWT for Fayda OIDC client authentication.
    Complies with National-ID-Program-Ethiopia / MOSIP eSignet strict policies.
    """
    try:
        # Extract the Key ID (kid) from the base64 JWK data
        decoded = base64.b64decode(private_key_b64)
        key_data = json.loads(decoded.decode('utf-8'))
        kid = key_data.get('kid')
        
        # Get the private key in PEM format
        private_key_pem = get_private_key_from_jwk(private_key_b64)
        if not private_key_pem:
            logger.error("Failed to get private key")
            return None
        
        # Generate timestamps with clock skew buffer for UAT alignment
        now = datetime.utcnow()
        iat_time = int(now.timestamp()) - 10  # 10 second fallback for timing sync
        exp_time = int((now + timedelta(minutes=5)).timestamp())
        
        # Strict Fayda / MOSIP payload configuration
        payload = {
            'iss': client_id,
            'sub': client_id,
            'aud': token_url,      # Must match token endpoint
            'iat': iat_time,
            'nbf': iat_time,       # Mandatory for eSignet
            'exp': exp_time,
            'jti': str(int(time.time() * 1000))
        }
        
        # Set up header parameters including the mandatory 'kid'
        headers = {}
        if kid:
            headers['kid'] = kid
        
        # Encode the JWT with RS256 algorithm
        client_assertion = jwt.encode(
            payload,
            private_key_pem,
            algorithm='RS256',
            headers=headers
        )
        
        logger.info(f"Client assertion generated successfully with kid: {kid}")
        return client_assertion
        
    except Exception as e:
        logger.error(f"Failed to generate client assertion: {str(e)}")
        return None


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
    """Handle OIDC callback from Fayda."""
    code = request.GET.get('code')
    state = request.GET.get('state')
    error = request.GET.get('error')
    error_description = request.GET.get('error_description')
    
    if error:
        messages.error(request, f'Fayda authentication error: {error_description or error}')
        return redirect('accounts:register_author')
    
    if not code or not state:
        messages.error(request, 'Missing authorization code or state parameter.')
        return redirect('accounts:register_author')
    
    session_state = request.session.get('fayda_state')
    if state != session_state:
        logger.warning(f"OIDC state mismatch: received {state}, expected {session_state}")
        messages.error(request, 'Invalid state parameter. Please try again.')
        return redirect('accounts:register_author')
    
    try:
        client_id = config('FAYDA_CLIENT_ID')
        token_url = config('FAYDA_TOKEN_URL')
        userinfo_url = config('FAYDA_USERINFO_URL')
        redirect_uri = config('FAYDA_REDIRECT_URI')
        private_key_b64 = config('FAYDA_PRIVATE_KEY_B64')
        
        debug_log(f"=== Starting OIDC Callback Processing ===")
        
        verification_results = verify_credential_compatibility(client_id, private_key_b64)
        all_verified = all([v['status'] for v in verification_results.values()])
        if all_verified:
            debug_log("✅ All credential checks passed!")
        else:
            debug_log("⚠️ Some credential checks failed. Please review the logs above.", level='warning')
        
        client_assertion = generate_client_assertion(client_id, token_url, private_key_b64)
        
        if not client_assertion:
            debug_log("ERROR: Failed to generate client assertion", level='error')
            messages.error(request, 'Failed to generate authentication token. Please contact support.')
            return redirect('accounts:register_author')
        
        token_data = {
            'grant_type': 'authorization_code',
            'code': code,
            'client_id': client_id,
            'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
            'client_assertion': client_assertion,
            'redirect_uri': redirect_uri
        }
        
        token_response = requests.post(
            token_url,
            data=token_data,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            timeout=30
        )
        
        if not token_response.ok:
            error_msg = token_response.text
            try:
                error_data = token_response.json()
                error_msg = error_data.get('error_description', error_data.get('error', 'Unknown error'))
            except:
                pass
            
            messages.error(request, f'Token exchange failed: {error_msg}')
            return redirect('accounts:register_author')
        
        token_response_data = token_response.json()
        access_token = token_response_data.get('access_token')
        
        if not access_token:
            messages.error(request, 'No access token received from Fayda.')
            return redirect('accounts:register_author')
        
        userinfo_response = requests.get(
            userinfo_url,
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            },
            timeout=10
        )
        
        if not userinfo_response.ok:
            messages.error(request, 'Failed to retrieve user information from Fayda.')
            return redirect('accounts:register_author')
        
        userinfo = userinfo_response.json()
        
        user_data = {
            'full_name': userinfo.get('name', userinfo.get('full_name', '')),
            'date_of_birth': userinfo.get('birthdate', userinfo.get('date_of_birth', '')),
            'gender': userinfo.get('gender', ''),
            'region': userinfo.get('region', userinfo.get('region_name', '')),
            'zone': userinfo.get('zone', userinfo.get('zone_name', '')),
            'woreda': userinfo.get('woreda', userinfo.get('woreda_name', '')),
            'address': userinfo.get('address', ''),
            'national_id': request.session.get('fayda_national_id', '')
        }
        
        if not user_data['full_name']:
            messages.error(request, 'Could not retrieve full name from Fayda.')
            return redirect('accounts:register_author')
        
        request.session['fayda_verified_data'] = user_data
        
        request.session.pop('fayda_state', None)
        request.session.pop('fayda_national_id', None)
        request.session.pop('fayda_nonce', None)
        
        messages.success(request, f'Fayda verification successful! Welcome {user_data["full_name"]}. Please complete your registration.')
        return redirect('accounts:register_author')
        
    except requests.exceptions.Timeout:
        messages.error(request, 'Fayda service timeout. Please try again.')
    except requests.exceptions.ConnectionError:
        messages.error(request, 'Could not connect to Fayda service. Please try again later.')
    except Exception as e:
        messages.error(request, f'Authentication failed: {str(e)}')
    
    return redirect('accounts:register_author')


@csrf_exempt
def oidc_initiate(request):
    """Initiate OIDC flow with Fayda eSignet using UAT credentials."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed. Use POST.'}, status=405)
    
    try:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON payload.'}, status=400)
        
        national_id = data.get('national_id')
        state = data.get('state')
        nonce = data.get('nonce')
        
        if not national_id:
            return JsonResponse({'success': False, 'message': 'National ID is required.'}, status=400)
        
        national_id_clean = national_id.replace('-', '').replace(' ', '')
        if len(national_id_clean) != 16 or not national_id_clean.isdigit():
            return JsonResponse({'success': False, 'message': 'Invalid National ID format. Must be 16 digits.'}, status=400)
        
        if not state or len(state) < 10:
            return JsonResponse({'success': False, 'message': 'Invalid state parameter.'}, status=400)
        
        if not nonce or len(nonce) < 10:
            return JsonResponse({'success': False, 'message': 'Invalid nonce parameter.'}, status=400)
        
        client_id = config('FAYDA_CLIENT_ID')
        auth_url = config('FAYDA_AUTH_URL')
        redirect_uri = config('FAYDA_REDIRECT_URI')
        
        request.session['fayda_national_id'] = national_id_clean
        request.session['fayda_state'] = state
        request.session['fayda_nonce'] = nonce
        
        authorization_url = (
            f"{auth_url}"
            f"?response_type=code"
            f"&client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&state={state}"
            f"&nonce={nonce}"
            f"&scope=openid profile eKYC"
        )
        
        return JsonResponse({
            'success': True,
            'authorization_url': authorization_url,
            'message': 'Redirect to Fayda for authentication'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'An error occurred: {str(e)}'}, status=500)


@csrf_exempt
def oidc_callback(request):
    """Handle OIDC callback from Fayda using UAT credentials via JSON endpoint."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed. Use POST.'}, status=405)
    
    try:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON payload.'}, status=400)
        
        code = data.get('code')
        state = data.get('state')
        
        if not code or not state:
            return JsonResponse({'success': False, 'message': 'Missing code or state parameter.'}, status=400)
        
        session_state = request.session.get('fayda_state')
        if state != session_state:
            return JsonResponse({'success': False, 'message': 'Invalid state parameter. Possible CSRF attack.'}, status=400)
        
        client_id = config('FAYDA_CLIENT_ID')
        token_url = config('FAYDA_TOKEN_URL')
        userinfo_url = config('FAYDA_USERINFO_URL')
        redirect_uri = config('FAYDA_REDIRECT_URI')
        private_key_b64 = config('FAYDA_PRIVATE_KEY_B64')
        
        client_assertion = generate_client_assertion(client_id, token_url, private_key_b64)
        
        if not client_assertion:
            return JsonResponse({'success': False, 'message': 'Failed to generate client assertion.'}, status=500)
        
        token_response = requests.post(
            token_url,
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'client_id': client_id,
                'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
                'client_assertion': client_assertion,
                'redirect_uri': redirect_uri
            },
            headers={
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            timeout=15
        )
        
        if not token_response.ok:
            return JsonResponse({'success': False, 'message': 'Failed to exchange authorization code. Please try again.'}, status=400)
        
        token_data = token_response.json()
        access_token = token_data.get('access_token')
        
        if not access_token:
            return JsonResponse({'success': False, 'message': 'No access token received from Fayda.'}, status=400)
        
        userinfo_response = requests.get(
            userinfo_url,
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            },
            timeout=10
        )
        
        if not userinfo_response.ok:
            return JsonResponse({'success': False, 'message': 'Failed to retrieve user information from Fayda.'}, status=400)
        
        userinfo = userinfo_response.json()
        
        user_data = {
            'full_name': userinfo.get('name', userinfo.get('full_name', '')),
            'date_of_birth': userinfo.get('birthdate', userinfo.get('date_of_birth', '')),
            'gender': userinfo.get('gender', ''),
            'region': userinfo.get('region', userinfo.get('region_name', '')),
            'zone': userinfo.get('zone', userinfo.get('zone_name', '')),
            'woreda': userinfo.get('woreda', userinfo.get('woreda_name', '')),
            'address': userinfo.get('address', '')
        }
        
        if not user_data['full_name']:
            return JsonResponse({'success': False, 'message': 'Could not retrieve full name from Fayda.'}, status=400)
        
        request.session.pop('fayda_state', None)
        request.session.pop('fayda_national_id', None)
        request.session.pop('fayda_nonce', None)
        
        return JsonResponse({
            'success': True,
            'message': 'Verification successful',
            'data': user_data
        })
        
    except requests.exceptions.Timeout:
        return JsonResponse({'success': False, 'message': 'Fayda service timeout. Please try again.'}, status=503)
    except requests.exceptions.ConnectionError:
        return JsonResponse({'success': False, 'message': 'Could not connect to Fayda service. Please try again later.'}, status=503)
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'An error occurred: {str(e)}'}, status=500)


@login_required
def dashboard_redirect(request):
    return redirect(role_based_redirect(request.user))


@login_required
def admin_dashboard(request):
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
    if request.user.role != 'checker':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('accounts:dashboard')
    
    pending_books = Book.objects.filter(status='pending_review').order_by('created_at')
    reviewed_books = QualityReview.objects.filter(reviewer=request.user, review_type='checker').select_related('book', 'book__author').order_by('-created_at')[:20]
    
    context = {
        'user': request.user,
        'pending_books': pending_books,
        'reviewed_books': reviewed_books,
        'total_pending': pending_books.count(),
        'total_reviewed': reviewed_books.count(),
        'avg_score': reviewed_books.aggregate(avg=Avg('overall_score'))['avg'] or 0,
        'reviewed_this_month': QualityReview.objects.filter(reviewer=request.user, review_type='checker', created_at__year=timezone.now().year, created_at__month=timezone.now().month).count(),
        'scoring_criteria': {
            'excellent': {'min': 9, 'max': 10, 'label': 'Excellent', 'description': 'Exceptional quality'},
            'good': {'min': 7, 'max': 8, 'label': 'Good', 'description': 'Good quality'},
            'average': {'min': 5, 'max': 6, 'label': 'Average', 'description': 'Acceptable'},
            'below_average': {'min': 3, 'max': 4, 'label': 'Below Average', 'description': 'Major issues'},
            'poor': {'min': 0, 'max': 2, 'label': 'Poor', 'description': 'Unacceptable'},
        },
        'recommendation_guide': {
            'approved': {'min_score': 7.0, 'label': '✅ Pass to Maker', 'description': 'Score ≥ 7.0'},
            'needs_revision': {'min_score': 5.0, 'max_score': 6.9, 'label': '🔄 Request Revision', 'description': 'Score 5.0-6.9'},
            'rejected': {'max_score': 4.9, 'label': '❌ Reject', 'description': 'Score < 5.0'},
        }
    }
    return render(request, 'dashboard/checker_dashboard.html', context)


@login_required
def process_checker_review(request):
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
                float(content_quality), float(editorial_quality), float(technical_quality),
                float(copyright_compliance) if copyright_compliance else 0,
                float(community_guidelines) if community_guidelines else 0,
            ]
            overall_score = sum(scores) / len(scores)
            
            book.status = 'checker_approved' if recommendation == 'approved' else ('needs_revision' if recommendation == 'needs_revision' else 'rejected')
            book.checker_reviewed_at = timezone.now()
            book.save()
            
            quality_review, created = QualityReview.objects.update_or_create(
                book=book, reviewer=request.user, review_type='checker',
                defaults={
                    'content_quality': float(content_quality), 'editorial_quality': float(editorial_quality),
                    'technical_quality': float(technical_quality), 'overall_score': round(overall_score, 1),
                    'comments': comments, 'recommendation': recommendation, 'updated_at': timezone.now(),
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
    if request.user.role != 'checker':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('accounts:dashboard')
    
    book = get_object_or_404(Book, id=book_id, status='pending_review')
    return render(request, 'reviews/review_book.html', {'user': request.user, 'book': book})


@login_required
def maker_dashboard(request):
    if request.user.role != 'maker':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('accounts:dashboard')
    
    pending_books = Book.objects.filter(status='checker_approved').order_by('checker_reviewed_at')
    published_books = Book.objects.filter(status='published', published_at__month=timezone.now().month).order_by('-published_at')[:10]
    
    context = {
        'user': request.user,
        'pending_books': pending_books,
        'published_books': published_books,
        'pending_count': pending_books.count(),
        'approved_count': Book.objects.filter(status='published', published_at__month=timezone.now().month).count(),
        'published_count': Book.objects.filter(status='published', published_at__month=timezone.now().month).count(),
        'total_published': Book.objects.filter(status='published').count(),
    }
    return render(request, 'dashboard/maker_dashboard.html', context)


@login_required
def publish_book(request, book_id):
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
        
    return render(request, 'books/publish_confirm.html', {'user': request.user, 'book': book})


@login_required
def client_dashboard(request):
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
    return render(request, 'accounts/profile.html', {'user': request.user})


@login_required
def profile_edit(request):
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