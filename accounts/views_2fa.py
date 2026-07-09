# accounts/views_2fa.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import login
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.cache import never_cache
from django.conf import settings
from django.core.mail import send_mail
from django.http import JsonResponse
from django_otp import devices_for_user
from django_otp.plugins.otp_email.models import EmailDevice
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice
from .models import CustomUser
import logging
import random
import string

logger = logging.getLogger(__name__)


def send_otp_email(user, token):
    """Send OTP verification code to user's email"""
    try:
        subject = 'Your Abrehot Library Verification Code'
        message = f"""
        Hello {user.full_name or user.username},

        Your verification code is: {token}

        This code will expire in 10 minutes.

        If you did not request this code, please ignore this email.

        Best regards,
        Abrehot Library Team
        """
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        logger.info(f"OTP email sent to {user.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send OTP email: {str(e)}")
        return False


@login_required
@csrf_protect
@ensure_csrf_cookie
@never_cache
def setup_2fa(request):
    """Setup Two-Factor Authentication for the user"""
    user = request.user
    
    # Check if 2FA is already enabled
    if user.two_factor_enabled:
        messages.info(request, 'Two-Factor Authentication is already enabled.')
        return redirect('accounts:profile')
    
    if request.method == 'POST':
        # Create an email device for the user
        device = EmailDevice.objects.filter(user=user).first()
        if not device:
            device = EmailDevice.objects.create(
                user=user,
                name='Email OTP Device',
                confirmed=False
            )
        
        # Generate and send OTP
        token = device.generate_token()
        send_otp_email(user, token)
        
        # Store device ID in session for verification
        request.session['2fa_device_id'] = device.id
        request.session['2fa_setup'] = True
        
        messages.info(request, 'A verification code has been sent to your email. Please enter it to confirm.')
        return redirect('accounts:verify_2fa_setup')
    
    context = {
        'user': user,
    }
    return render(request, 'accounts/2fa_setup.html', context)


@login_required
@csrf_protect
@ensure_csrf_cookie
@never_cache
def verify_2fa_setup(request):
    """Verify the 2FA setup with OTP code"""
    user = request.user
    
    # Check if user is in setup mode
    if not request.session.get('2fa_setup', False):
        messages.error(request, 'Please start the 2FA setup process first.')
        return redirect('accounts:2fa_setup')
    
    device_id = request.session.get('2fa_device_id')
    if not device_id:
        messages.error(request, 'No device found for verification.')
        return redirect('accounts:2fa_setup')
    
    device = get_object_or_404(EmailDevice, id=device_id, user=user)
    
    if request.method == 'POST':
        token = request.POST.get('token', '').strip()
        
        if not token:
            messages.error(request, 'Please enter the verification code.')
            return redirect('accounts:verify_2fa_setup')
        
        # Verify the token
        if device.verify_token(token):
            # Confirm the device
            device.confirmed = True
            device.save()
            
            # Enable 2FA for the user
            user.two_factor_enabled = True
            user.save()
            
            # Generate backup codes
            static_device, created = StaticDevice.objects.get_or_create(user=user)
            if created or not static_device.token_set.exists():
                # Generate 10 backup codes
                for _ in range(10):
                    token_str = ''.join(random.choices(string.digits, k=8))
                    StaticToken.objects.create(device=static_device, token=token_str)
            
            # Clear session
            request.session.pop('2fa_device_id', None)
            request.session.pop('2fa_setup', None)
            
            messages.success(request, 'Two-Factor Authentication has been enabled successfully!')
            logger.info(f"2FA enabled for user {user.username}")
            return redirect('accounts:profile')
        else:
            messages.error(request, 'Invalid verification code. Please try again.')
    
    context = {
        'user': user,
        'device': device,
    }
    return render(request, 'accounts/2fa_verify_setup.html', context)


@login_required
@csrf_protect
@ensure_csrf_cookie
@never_cache
def verify_2fa(request):
    """Verify 2FA during login"""
    # Check if user is in login verification mode
    user_id = request.session.get('pre_2fa_user_id')
    if not user_id:
        messages.error(request, 'Session expired. Please try again.')
        return redirect('accounts:login')
    
    user = get_object_or_404(CustomUser, id=user_id)
    
    if request.method == 'POST':
        token = request.POST.get('token', '').strip()
        
        if not token:
            messages.error(request, 'Please enter the verification code.')
            return redirect('accounts:verify_2fa')
        
        # Find the user's email device
        device = EmailDevice.objects.filter(user=user, confirmed=True).first()
        if not device:
            messages.error(request, 'No 2FA device found. Please contact support.')
            return redirect('accounts:login')
        
        # Verify the token
        if device.verify_token(token):
            # Login the user
            login(request, user)
            
            # Set session expiry based on remember me
            remember = request.session.get('pre_2fa_remember', False)
            if not remember:
                request.session.set_expiry(0)
            else:
                request.session.set_expiry(1209600)  # 2 weeks
            
            # Clear session data
            request.session.pop('pre_2fa_user_id', None)
            request.session.pop('pre_2fa_remember', None)
            
            messages.success(request, f'Welcome back, {user.full_name}!')
            logger.info(f"User {user.username} logged in with 2FA")
            
            # Redirect based on role
            from .views import role_based_redirect
            return redirect(role_based_redirect(user))
        else:
            messages.error(request, 'Invalid verification code. Please try again.')
    
    context = {
        'user': user,
    }
    return render(request, 'accounts/2fa_verify.html', context)


@login_required
def disable_2fa(request):
    """Disable Two-Factor Authentication for the user"""
    user = request.user
    
    if request.method == 'POST':
        # Delete all 2FA devices
        devices = devices_for_user(user)
        for device in devices:
            device.delete()
        
        # Disable 2FA for the user
        user.two_factor_enabled = False
        user.save()
        
        messages.success(request, 'Two-Factor Authentication has been disabled.')
        logger.info(f"2FA disabled for user {user.username}")
        return redirect('accounts:profile')
    
    context = {
        'user': user,
    }
    return render(request, 'accounts/2fa_disable.html', context)


@login_required
def backup_codes(request):
    """View and generate backup codes for 2FA"""
    user = request.user
    
    if not user.two_factor_enabled:
        messages.error(request, 'Two-Factor Authentication is not enabled.')
        return redirect('accounts:2fa_setup')
    
    # Get or create static device
    static_device, created = StaticDevice.objects.get_or_create(user=user)
    
    # Get existing tokens
    existing_tokens = static_device.token_set.all()
    
    # Check if we need to generate new tokens
    if request.method == 'POST':
        # Delete existing tokens and generate new ones
        static_device.token_set.all().delete()
        tokens = []
        for _ in range(10):
            token_str = ''.join(random.choices(string.digits, k=8))
            StaticToken.objects.create(device=static_device, token=token_str)
            tokens.append(token_str)
        
        messages.success(request, 'New backup codes generated successfully! Please save them.')
        
        # Return JSON response for AJAX
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'tokens': tokens,
                'message': 'New backup codes generated successfully!'
            })
        
        return redirect('accounts:2fa_backup_codes')
    
    # Get tokens for display
    tokens = [token.token for token in existing_tokens]
    
    context = {
        'user': user,
        'tokens': tokens,
        'has_tokens': len(tokens) > 0,
        'token_count': len(tokens),
    }
    return render(request, 'accounts/2fa_backup_codes.html', context)