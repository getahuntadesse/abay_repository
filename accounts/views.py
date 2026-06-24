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
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from decouple import config

from .forms import LoginForm, ClientRegistrationForm, AuthorRegistrationForm
from .models import CustomUser, AuthorProfile, ClientProfile
from books.models import Book, Genre
from reviews.models import QualityReview

# Set up logger
logger = logging.getLogger(__name__)


def decode_private_key_from_b64(private_key_b64):
    """
    Decode the Base64 encoded private key from the Fayda UAT credentials.
    The private key is stored as a Base64 encoded JSON string containing RSA key components.
    """
    try:
        # Decode Base64
        decoded = base64.b64decode(private_key_b64)
        key_data = json.loads(decoded.decode('utf-8'))
        
        # Reconstruct the private key from components
        private_key = rsa.RSAPrivateNumbers(
            p=int(key_data['p'], 36),
            q=int(key_data['q'], 36),
            d=int(key_data['d'], 36),
            dmp1=int(key_data['dp'], 36),
            dmq1=int(key_data['dq'], 36),
            iqmp=int(key_data['qi'], 36),
            public_numbers=rsa.RSAPublicNumbers(
                e=int(key_data['e'], 36),
                n=int(key_data['n'], 36)
            )
        ).private_key(default_backend())
        
        return private_key
    except Exception as e:
        logger.error(f"Failed to decode private key: {str(e)}")
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
    
    return render(request, 'accounts/register_author.html', {'form': form})


@csrf_exempt
def oidc_initiate(request):
    """
    Initiate OIDC flow with Fayda eSignet using UAT credentials.
    This endpoint generates the authorization URL for redirecting to Fayda.
    """
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Method not allowed. Use POST.'
        }, status=405)
    
    try:
        # Parse the request body
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid JSON payload.'
            }, status=400)
        
        national_id = data.get('national_id')
        state = data.get('state')
        nonce = data.get('nonce')
        
        # Validate national ID format
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
        
        # Validate state
        if not state or len(state) < 10:
            return JsonResponse({
                'success': False,
                'message': 'Invalid state parameter.'
            }, status=400)
        
        # Validate nonce
        if not nonce or len(nonce) < 10:
            return JsonResponse({
                'success': False,
                'message': 'Invalid nonce parameter.'
            }, status=400)
        
        # Get OIDC configuration from environment (UAT)
        client_id = config('FAYDA_CLIENT_ID')
        auth_url = config('FAYDA_AUTH_URL')
        redirect_uri = config('FAYDA_REDIRECT_URI')
        
        # Store in session for callback verification
        request.session['fayda_national_id'] = national_id_clean
        request.session['fayda_state'] = state
        request.session['fayda_nonce'] = nonce
        
        # Build the authorization URL with all required parameters
        authorization_url = (
            f"{auth_url}"
            f"?response_type=code"
            f"&client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&state={state}"
            f"&nonce={nonce}"
            f"&scope=openid profile eKYC"
        )
        
        logger.info(f"OIDC initiated for national_id: {national_id_clean[:4]}****, state: {state[:8]}...")
        
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
    Handle OIDC callback from Fayda using UAT credentials.
    Exchanges the authorization code for user information.
    """
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Method not allowed. Use POST.'
        }, status=405)
    
    try:
        # Parse the request body
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid JSON payload.'
            }, status=400)
        
        code = data.get('code')
        state = data.get('state')
        
        if not code or not state:
            return JsonResponse({
                'success': False,
                'message': 'Missing code or state parameter.'
            }, status=400)
        
        # Verify state matches session (CSRF protection)
        session_state = request.session.get('fayda_state')
        if state != session_state:
            logger.warning(f"OIDC state mismatch: received {state}, expected {session_state}")
            return JsonResponse({
                'success': False,
                'message': 'Invalid state parameter. Possible CSRF attack.'
            }, status=400)
        
        # For development mock mode
        if code == 'mock_code' and settings.DEBUG:
            national_id = request.session.get('fayda_national_id', '3126894653473958')
            return mock_fayda_verification(national_id)
        
        # Get OIDC configuration from environment (UAT)
        client_id = config('FAYDA_CLIENT_ID')
        token_url = config('FAYDA_TOKEN_URL')
        userinfo_url = config('FAYDA_USERINFO_URL')
        redirect_uri = config('FAYDA_REDIRECT_URI')
        private_key_b64 = config('FAYDA_PRIVATE_KEY_B64')
        algorithm = config('FAYDA_ALGORITHM', default='RS256')
        client_assertion_type = config('FAYDA_CLIENT_ASSERTION_TYPE', default='urn:ietf:params:oauth:client-assertion-type:jwt-bearer')
        
        # Decode private key
        private_key = decode_private_key_from_b64(private_key_b64)
        if not private_key:
            return JsonResponse({
                'success': False,
                'message': 'Failed to load private key for authentication.'
            }, status=500)
        
        # Generate client assertion JWT
        now = datetime.utcnow()
        assertion_payload = {
            'iss': client_id,
            'sub': client_id,
            'aud': token_url,
            'iat': int(now.timestamp()),
            'exp': int((now + timedelta(minutes=5)).timestamp()),
            'jti': str(int(time.time() * 1000))
        }
        
        # Sign the JWT with the private key
        client_assertion = jwt.encode(
            assertion_payload,
            private_key,
            algorithm=algorithm,
            headers={'kid': '0b194df4-7149-4146-97c5-78fdf0d4fb1d'}
        )
        
        # Step 1: Exchange code for access token using client assertion
        token_response = requests.post(
            token_url,
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'client_id': client_id,
                'client_assertion_type': client_assertion_type,
                'client_assertion': client_assertion,
                'redirect_uri': redirect_uri
            },
            timeout=15
        )
        
        if not token_response.ok:
            logger.error(f"Token exchange failed: {token_response.status_code} - {token_response.text}")
            return JsonResponse({
                'success': False,
                'message': 'Failed to exchange authorization code. Please try again.'
            }, status=400)
        
        token_data = token_response.json()
        access_token = token_data.get('access_token')
        id_token = token_data.get('id_token')
        
        if not access_token:
            return JsonResponse({
                'success': False,
                'message': 'No access token received from Fayda.'
            }, status=400)
        
        # Step 2: Get user information using access token
        userinfo_response = requests.get(
            userinfo_url,
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            },
            timeout=10
        )
        
        if not userinfo_response.ok:
            logger.error(f"Userinfo request failed: {userinfo_response.status_code} - {userinfo_response.text}")
            return JsonResponse({
                'success': False,
                'message': 'Failed to retrieve user information from Fayda.'
            }, status=400)
        
        userinfo = userinfo_response.json()
        
        # Step 3: Map userinfo to our format
        user_data = {
            'full_name': userinfo.get('name', userinfo.get('full_name', '')),
            'date_of_birth': userinfo.get('birthdate', userinfo.get('date_of_birth', '')),
            'gender': userinfo.get('gender', ''),
            'region': userinfo.get('region', userinfo.get('region_name', '')),
            'zone': userinfo.get('zone', userinfo.get('zone_name', '')),
            'woreda': userinfo.get('woreda', userinfo.get('woreda_name', '')),
            'address': userinfo.get('address', '')
        }
        
        # Validate that we got the required data
        if not user_data['full_name']:
            return JsonResponse({
                'success': False,
                'message': 'Could not retrieve full name from Fayda.'
            }, status=400)
        
        logger.info(f"OIDC callback successful for user: {user_data['full_name']}")
        
        # Clear session data
        request.session.pop('fayda_state', None)
        request.session.pop('fayda_national_id', None)
        request.session.pop('fayda_nonce', None)
        
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
        return JsonResponse({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        }, status=500)


@csrf_exempt
def verify_fayda_id(request):
    """
    Securely verify Fayda National ID through the official API.
    This endpoint is called from the frontend JavaScript.
    """
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Method not allowed. Use POST.'
        }, status=405)
    
    try:
        # Parse the request body
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid JSON payload.'
            }, status=400)
        
        national_id = data.get('national_id')
        
        # Validate national ID format
        if not national_id:
            return JsonResponse({
                'success': False,
                'message': 'National ID is required.'
            }, status=400)
        
        # Remove any hyphens or spaces
        national_id_clean = national_id.replace('-', '').replace(' ', '')
        
        if len(national_id_clean) != 16 or not national_id_clean.isdigit():
            return JsonResponse({
                'success': False,
                'message': 'Invalid National ID format. Must be 16 digits.'
            }, status=400)
        
        # Get credentials from environment variables
        client_id = config('FAYDA_CLIENT_ID', default=None)
        client_secret = config('FAYDA_CLIENT_SECRET', default=None)
        api_base_url = config('FAYDA_API_URL', default='https://id.et/api')
        
        if not client_id or not client_secret:
            # If credentials are not configured, use mock mode for development
            if settings.DEBUG:
                return mock_fayda_verification(national_id_clean)
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Fayda service is not configured. Please contact support.'
                }, status=503)
        
        # Step 1: Get OAuth2 access token
        token_response = requests.post(
            f'{api_base_url}/oauth2/token',
            data={
                'grant_type': 'client_credentials',
                'client_id': client_id,
                'client_secret': client_secret,
                'scope': 'national_id_verification'
            },
            timeout=10
        )
        
        if not token_response.ok:
            return JsonResponse({
                'success': False,
                'message': 'Failed to authenticate with Fayda service. Please try again later.'
            }, status=503)
        
        token_data = token_response.json()
        access_token = token_data.get('access_token')
        
        if not access_token:
            return JsonResponse({
                'success': False,
                'message': 'Could not obtain access token from Fayda.'
            }, status=500)
        
        # Step 2: Verify the National ID
        verify_response = requests.post(
            f'{api_base_url}/verify/national-id',
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            },
            json={
                'national_id': national_id_clean,
                'return_fields': ['full_name', 'date_of_birth', 'gender', 'region', 'zone', 'woreda', 'address']
            },
            timeout=10
        )
        
        if not verify_response.ok:
            error_message = 'National ID verification failed.'
            try:
                error_data = verify_response.json()
                error_message = error_data.get('message', error_message)
            except:
                pass
            
            return JsonResponse({
                'success': False,
                'message': error_message
            }, status=verify_response.status_code)
        
        user_data = verify_response.json()
        
        # Validate that we got the required data
        if not user_data.get('full_name'):
            return JsonResponse({
                'success': False,
                'message': 'Could not retrieve user information from Fayda. Please try again.'
            }, status=400)
        
        # Return successful verification with user data
        return JsonResponse({
            'success': True,
            'message': 'Verification successful',
            'data': {
                'full_name': user_data.get('full_name', ''),
                'date_of_birth': user_data.get('date_of_birth', ''),
                'gender': user_data.get('gender', ''),
                'region': user_data.get('region', ''),
                'zone': user_data.get('zone', ''),
                'woreda': user_data.get('woreda', ''),
                'address': user_data.get('address', '')
            }
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
        logger.error(f"Fayda verification error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'An unexpected error occurred: {str(e)}'
        }, status=500)


def mock_fayda_verification(national_id):
    """
    Mock Fayda API response for development purposes.
    This should only be used when DEBUG=True and Fayda credentials are not configured.
    """
    import random
    
    # Generate mock data based on the national ID
    gender = 'Male' if int(national_id[-1]) % 2 == 0 else 'Female'
    
    male_names = ['Abebe Kebede', 'Alemu Desta', 'Bekele Tadesse', 'Dawit Haile', 
                  'Fikre Mekonnen', 'Girma Assefa', 'Haile Wondimu', 'Kebede Lemma', 
                  'Mekonnen Alemu', 'Solomon Tekle']
    female_names = ['Abebech Alemu', 'Alemitu Desta', 'Birtukan Fikre', 'Chaltu Hailu', 
                    'Dinkinesh Kebede', 'Eden Mekonnen', 'Frehiwot Assefa', 'Genet Tadesse', 
                    'Hiwot Wondimu', 'Kalkidan Lemma']
    
    regions = ['Addis Ababa', 'Afar', 'Amhara', 'Benishangul-Gumuz', 'Dire Dawa', 
               'Gambela', 'Harari', 'Oromia', 'Sidama', 'Somali', 'South West Ethiopia', 
               'Southern Nations, Nationalities, and Peoples', 'Tigray']
    
    zones = ['Bole', 'Kirkos', 'Lideta', 'Gulele', 'Arada', 'Addis Ketema', 
             'Akaky Kaliti', 'Kolfe Keranio', 'Nifas Silk-Lafto', 'Yeka']
    
    name_index = int(national_id[-4:-2]) % 10
    region_index = int(national_id[8:10]) % len(regions)
    zone_index = int(national_id[10:12]) % len(zones)
    
    full_name = male_names[name_index] if gender == 'Male' else female_names[name_index]
    region = regions[region_index]
    zone = zones[zone_index]
    woreda = f'Woreda {int(national_id[12:14]) % 21 + 1}'
    
    # Generate a date of birth (between 1970-2000)
    year = random.randint(1970, 2000)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    date_of_birth = f'{year}-{month:02d}-{day:02d}'
    
    return JsonResponse({
        'success': True,
        'message': 'Verification successful (MOCK - Development Only)',
        'data': {
            'full_name': full_name,
            'date_of_birth': date_of_birth,
            'gender': gender,
            'region': region,
            'zone': zone,
            'woreda': woreda,
            'address': f'{zone} Subcity, {woreda}'
        }
    })


@login_required
def dashboard_redirect(request):
    """Redirect users to their respective dashboards based on role"""
    return redirect(role_based_redirect(request.user))


@login_required
def admin_dashboard(request):
    """
    Admin dashboard view with comprehensive analytics and payment data.
    """
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('accounts:dashboard')
    
    # Date ranges for analytics
    today = timezone.now().date()
    week_start = today - timedelta(days=7)
    month_start = today.replace(day=1)
    
    # Initialize payment data with defaults
    telebirr_sales = 0
    cbe_sales = 0
    total_sales = 0
    today_sales = 0
    week_sales = 0
    month_sales = 0
    monthly_sales = 0
    
    # Try to import payment models and get real data
    try:
        from payments.models import Purchase, PaymentTransaction
        
        completed_purchases = Purchase.objects.filter(status='completed')
        
        def sum_amount(qs):
            result = qs.aggregate(total=Sum('amount'))['total']
            return result if result is not None else 0
        
        total_sales = sum_amount(completed_purchases)
        
        today_purchases = completed_purchases.filter(created_at__date=today)
        today_sales = sum_amount(today_purchases)
        
        week_purchases = completed_purchases.filter(
            created_at__date__gte=week_start,
            created_at__date__lte=today
        )
        week_sales = sum_amount(week_purchases)
        
        month_purchases = completed_purchases.filter(
            created_at__date__gte=month_start,
            created_at__date__lte=today
        )
        month_sales = sum_amount(month_purchases)
        monthly_sales = month_sales
        
        if hasattr(Purchase, 'payment_method'):
            telebirr_purchases = completed_purchases.filter(payment_method__icontains='telebirr')
            telebirr_sales = sum_amount(telebirr_purchases)
            
            cbe_purchases = completed_purchases.filter(
                Q(payment_method__icontains='cbe') | Q(payment_method__icontains='cbe_birr')
            )
            cbe_sales = sum_amount(cbe_purchases)
        elif hasattr(PaymentTransaction, 'payment_method'):
            completed_transactions = PaymentTransaction.objects.filter(status='completed')
            telebirr_sales = sum_amount(completed_transactions.filter(payment_method__icontains='telebirr'))
            cbe_sales = sum_amount(completed_transactions.filter(
                Q(payment_method__icontains='cbe') | Q(payment_method__icontains='cbe_birr')
            ))
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
    """Checker dashboard view - Review and validate book submissions"""
    if request.user.role != 'checker':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('accounts:dashboard')
    
    pending_books = Book.objects.filter(status='pending_review').order_by('created_at')
    
    reviewed_books = QualityReview.objects.filter(
        reviewer=request.user, 
        review_type='checker'
    ).select_related('book', 'book__author').order_by('-created_at')[:20]
    
    total_pending = pending_books.count()
    total_reviewed = reviewed_books.count()
    avg_score = reviewed_books.aggregate(avg=Avg('overall_score'))['avg'] or 0
    
    current_month = timezone.now().month
    current_year = timezone.now().year
    reviewed_this_month = QualityReview.objects.filter(
        reviewer=request.user,
        review_type='checker',
        created_at__year=current_year,
        created_at__month=current_month
    ).count()
    
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
    
    published_books = Book.objects.filter(
        status='published',
        published_at__month=timezone.now().month
    ).order_by('-published_at')[:10]
    
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