# accounts/views_oidc.py
import logging
import os
import json
import base64
import hashlib
import urllib
import re

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
from datetime import datetime, timedelta
import jwt
import requests
from decouple import config
from dotenv import load_dotenv

load_dotenv()

# ============================================
# FAYDA OIDC CONFIGURATION
# ============================================

CLIENT_ID = config('FAYDA_CLIENT_ID', default='')
REDIRECT_URI = config('FAYDA_REDIRECT_URI', default='http://localhost:3000/callback/')
AUTHORIZATION_ENDPOINT = config('FAYDA_AUTH_URL', default='')
TOKEN_ENDPOINT = config('FAYDA_TOKEN_URL', default='')
USERINFO_ENDPOINT = config('FAYDA_USERINFO_URL', default='')
PRIVATE_KEY = config('FAYDA_PRIVATE_KEY_B64', default='')
EXPIRATION_TIME = timedelta(minutes=15)
ALGORITHM = config('FAYDA_ALGORITHM', default='RS256')
CLIENT_ASSERTION_TYPE = config('FAYDA_CLIENT_ASSERTION_TYPE', default='urn:ietf:params:oauth:client-assertion-type:jwt-bearer')

# Initialize logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(message)s',
)

# ============================================
# PKCE HELPERS
# ============================================

def generate_pkce():
    """Generate PKCE code verifier and challenge"""
    code_verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b'=').decode('utf-8')
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode('utf-8')).digest()
    ).rstrip(b'=').decode('utf-8')
    return code_verifier, code_challenge


def base64url_decode(input_str):
    """Decode base64url string with padding"""
    padding = '=' * (4 - (len(input_str) % 4))
    return base64.urlsafe_b64decode(input_str + padding)


def load_private_key_from_string(base64_key_str):
    """Load RSA private key from base64 encoded JWK string"""
    logging.info("Loading private key from base64 key string")
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
        logging.info("Private Key Loaded Successfully")
        return private_key

    except Exception as e:
        logging.error(f"Failed to load private key: {e}")
        raise


def generate_signed_jwt(client_id):
    """Generate signed JWT for Fayda client assertion"""
    logging.info("Generating signed JWT ...")
    header = {
        "alg": ALGORITHM,
        "typ": "JWT",
    }

    payload = {
        "iss": client_id,
        "sub": client_id,
        "aud": TOKEN_ENDPOINT,
        "exp": datetime.utcnow() + EXPIRATION_TIME,
        "iat": datetime.utcnow(),
    }

    private_key = load_private_key_from_string(PRIVATE_KEY)

    signed_jwt = jwt.encode(payload, private_key, algorithm=ALGORITHM, headers=header)
    logging.info("Signed JWT generated.")
    return signed_jwt


# ============================================
# FAYDA OIDC VIEWS
# ============================================

@csrf_exempt
def oidc_initiate(request):
    """
    Initiate Fayda OIDC flow for author registration.
    This is called from the registration page via AJAX.
    Endpoint: /accounts/api/fayda/oidc/initiate/
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

        # Clean national ID
        national_id_clean = re.sub(r'[^0-9]', '', national_id)
        if len(national_id_clean) != 16:
            return JsonResponse({
                'success': False,
                'message': 'National ID must be exactly 16 digits.'
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

        # Validate configuration
        if not CLIENT_ID or not AUTHORIZATION_ENDPOINT or not REDIRECT_URI:
            return JsonResponse({
                'success': False,
                'message': 'Fayda is not configured. Please contact support.'
            }, status=400)

        # Generate PKCE
        code_verifier, code_challenge = generate_pkce()
        request.session['fayda_code_verifier'] = code_verifier
        request.session['fayda_national_id'] = national_id_clean
        request.session['fayda_state'] = state
        request.session['fayda_nonce'] = nonce

        # Build claims
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

        # Build authorization URL
        authorization_url = (
            f"{AUTHORIZATION_ENDPOINT}"
            f"?claims_locales=en"
            f"&response_type=code"
            f"&client_id={CLIENT_ID}"
            f"&redirect_uri={REDIRECT_URI}"
            f"&scope=openid profile email"
            f"&acr_values=mosip:idp:acr:generated-code:biometrics"
            f"&code_challenge={code_challenge}"
            f"&code_challenge_method=S256"
            f"&claims={encoded_claims}"
            f"&state={state}"
            f"&nonce={nonce}"
        )

        logging.info(f"Fayda initiate successful for national_id: {national_id_clean[:4]}****")

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
        logging.error(f"Fayda initiate error: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        }, status=500)


@csrf_exempt
def oidc_callback(request):
    """
    Handle OIDC callback from Fayda.
    This is the endpoint that Fayda redirects to after authentication.
    Redirects to the author registration form with pre-filled data.
    """
    if request.method == "GET":
        code = request.GET.get('code')
        state = request.GET.get('state')
        error = request.GET.get('error')
        error_description = request.GET.get('error_description')
        
        # Check for errors from Fayda
        if error:
            logging.error(f"Fayda OIDC error: {error} - {error_description}")
            messages.error(request, f'Fayda authentication error: {error_description or error}')
            return redirect('accounts:register_author')
        
        if not code:
            messages.error(request, 'Authorization code not provided.')
            return redirect('accounts:register_author')
        
        # Verify state matches session
        session_state = request.session.get('fayda_state')
        if state != session_state:
            logging.warning(f"State mismatch: received {state}, expected {session_state}")
            messages.error(request, 'Invalid state parameter. Please try again.')
            return redirect('accounts:register_author')
        
        # Get code verifier from session
        code_verifier = request.session.get('fayda_code_verifier', '')
        
        try:
            signed_jwt = generate_signed_jwt(CLIENT_ID)
            
            payload = {
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': REDIRECT_URI,
                'client_id': CLIENT_ID,
                'client_assertion_type': CLIENT_ASSERTION_TYPE,
                'client_assertion': signed_jwt,
                'code_verifier': code_verifier,
            }

            logging.info(f"Token request payload: {payload}")

            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            
            # Exchange code for token
            response = requests.post(TOKEN_ENDPOINT, data=payload, headers=headers, timeout=30)

            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data.get('access_token')
                logging.info(f"Access token obtained: {access_token[:20]}...")
                
                # Get user information
                userinfo_headers = {'Authorization': f'Bearer {access_token}'}
                userinfo_response = requests.get(USERINFO_ENDPOINT, headers=userinfo_headers, timeout=10)

                if userinfo_response.status_code == 200:
                    user_info_response = userinfo_response.text
                    try:
                        # Decode the JWT
                        decoded_user_info = jwt.decode(
                            user_info_response, 
                            options={"verify_signature": False}, 
                            algorithms=["RS256"]
                        )
                        
                        # Extract user data from Fayda response
                        user_data = {
                            'full_name': decoded_user_info.get('name', ''),
                            'email': decoded_user_info.get('email', ''),
                            'phone': decoded_user_info.get('phone_number', ''),
                            'picture': decoded_user_info.get('picture', ''),
                            'gender': decoded_user_info.get('gender', ''),
                            'date_of_birth': decoded_user_info.get('birthdate', ''),
                            'address': decoded_user_info.get('address', ''),
                            'nationality': decoded_user_info.get('nationality', ''),
                            'individual_id': decoded_user_info.get('individual_id', ''),
                            'national_id': request.session.get('fayda_national_id', ''),
                        }
                        
                        logging.info(f"Fayda user data extracted: {user_data['full_name']} ({user_data['email']})")
                        
                        # Store verified data in session for the registration form
                        request.session['fayda_verified_data'] = user_data
                        request.session['fayda_verified'] = True
                        
                        # Clear session data
                        request.session.pop('fayda_state', None)
                        request.session.pop('fayda_code_verifier', None)
                        request.session.pop('fayda_nonce', None)
                        request.session.pop('fayda_national_id', None)
                        
                        messages.success(request, f'Fayda verification successful! Welcome {user_data["full_name"]}.')
                        return redirect('accounts:register_author')
                        
                    except jwt.InvalidTokenError as e:
                        logging.error(f"Invalid JWT token: {str(e)}")
                        messages.error(request, 'Failed to decode user information from Fayda.')
                    except Exception as e:
                        logging.error(f"Failed to decode userinfo: {str(e)}")
                        messages.error(request, 'Failed to process user information.')
                else:
                    logging.error(f"Userinfo request failed: {userinfo_response.status_code}")
                    messages.error(request, 'Failed to retrieve user information from Fayda.')
            else:
                logging.error(f"Token exchange failed: {response.status_code}")
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error_description', error_data.get('error', 'Unknown error'))
                except:
                    error_msg = response.text[:200]
                messages.error(request, f'Token exchange failed: {error_msg}')
                
        except requests.exceptions.Timeout:
            logging.error("Fayda service timeout")
            messages.error(request, 'Fayda service timeout. Please try again.')
        except requests.exceptions.ConnectionError:
            logging.error("Could not connect to Fayda service")
            messages.error(request, 'Could not connect to Fayda service. Please try again later.')
        except Exception as e:
            logging.error(f"Callback error: {str(e)}")
            import traceback
            traceback.print_exc()
            messages.error(request, f'Authentication failed: {str(e)}')
        
        return redirect('accounts:register_author')
    
    return JsonResponse({"error": "Method not allowed"}, status=405)


# ============================================
# HOME VIEW (Alias for testing)
# ============================================

def home(request):
    """
    Home page with Fayda login option (for testing).
    This function is used as a fallback for views that import 'home'.
    """
    code_verifier, code_challenge = generate_pkce()
    request.session['fayda_code_verifier'] = code_verifier
    
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
    
    # Generate state and nonce
    state = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b'=').decode('utf-8')
    nonce = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b'=').decode('utf-8')
    
    request.session['fayda_state'] = state
    request.session['fayda_nonce'] = nonce
    
    auth_url = (
        f"{AUTHORIZATION_ENDPOINT}?"
        f"claims_locales=en&"
        f"response_type=code&"
        f"client_id={CLIENT_ID}&"
        f"redirect_uri={REDIRECT_URI}&"
        f"scope=openid profile email&"
        f"acr_values=mosip:idp:acr:generated-code:biometrics&"
        f"code_challenge={code_challenge}&"
        f"code_challenge_method=S256&"
        f"claims={encoded_claims}&"
        f"state={state}&"
        f"nonce={nonce}"
    )
    
    context = {
        'auth_url': auth_url,
        'title': 'Fayda OIDC Login'
    }
    return render(request, 'oidc_app/home.html', context)