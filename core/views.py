# core/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.cache import cache
from django.utils import timezone
from django.http import JsonResponse
from django.contrib.auth.forms import AuthenticationForm
from django.conf import settings
import logging
import hashlib
from datetime import timedelta

logger = logging.getLogger(__name__)

class SecureLoginView:
    def get(self, request):
        # Check if IP is banned
        ip = self.get_client_ip(request)
        if self.is_ip_banned(ip):
            return render(request, 'accounts/blocked.html', {
                'reason': 'Too many failed login attempts. Please try again later.'
            })
        
        form = AuthenticationForm()
        return render(request, 'accounts/login.html', {'form': form})
    
    def post(self, request):
        ip = self.get_client_ip(request)
        
        # Check if IP is banned
        if self.is_ip_banned(ip):
            return render(request, 'accounts/blocked.html', {
                'reason': 'Too many failed login attempts. Please try again later.'
            })
        
        form = AuthenticationForm(request, data=request.POST)
        
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            
            if user is not None and user.is_active:
                # Reset login attempts
                self.reset_login_attempts(ip)
                login(request, user)
                
                # Log successful login
                logger.info(f"Successful login: User={username}, IP={ip}")
                
                # Update last login
                user.last_login = timezone.now()
                user.save()
                
                # Redirect to next or dashboard
                next_url = request.GET.get('next', '/dashboard/')
                return redirect(next_url)
        
        # Failed login attempt
        self.increment_login_attempts(ip)
        logger.warning(f"Failed login attempt: Username={request.POST.get('username')}, IP={ip}")
        
        messages.error(request, 'Invalid username or password. Please try again.')
        return render(request, 'accounts/login.html', {'form': form})
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def increment_login_attempts(self, ip):
        key = f"login_attempts_{ip}"
        attempts = cache.get(key, 0)
        cache.set(key, attempts + 1, 1800)  # 30 minutes
    
    def reset_login_attempts(self, ip):
        key = f"login_attempts_{ip}"
        cache.delete(key)
        cache.delete(f"ip_banned_{ip}")
    
    def is_ip_banned(self, ip):
        key = f"ip_banned_{ip}"
        return cache.get(key, False)