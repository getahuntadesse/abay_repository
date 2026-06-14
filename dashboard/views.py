from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages


@login_required
def dashboard_redirect(request):
    """Redirect users to their respective dashboards based on role"""
    if request.user.is_superuser or request.user.role == 'admin':
        return redirect('dashboard:admin_dashboard')
    elif request.user.role == 'author':
        return redirect('dashboard:author_dashboard')
    elif request.user.role == 'checker':
        return redirect('dashboard:checker_dashboard')
    elif request.user.role == 'maker':
        return redirect('dashboard:maker_dashboard')
    else:
        return redirect('dashboard:client_dashboard')


@login_required
def admin_dashboard(request):
    """Admin Dashboard"""
    if not (request.user.is_superuser or request.user.role == 'admin'):
        messages.error(request, 'Access denied.')
        return redirect('dashboard:redirect')
    return render(request, 'dashboard/admin_dashboard.html')


@login_required
def author_dashboard(request):
    """Author Dashboard"""
    if request.user.role != 'author':
        messages.error(request, 'Access denied.')
        return redirect('dashboard:redirect')
    return render(request, 'dashboard/author_dashboard.html')


@login_required
def client_dashboard(request):
    """Client Dashboard"""
    if request.user.role != 'client':
        messages.error(request, 'Access denied.')
        return redirect('dashboard:redirect')
    return render(request, 'dashboard/client_dashboard.html')


@login_required
def checker_dashboard(request):
    """Checker Dashboard"""
    if request.user.role != 'checker':
        messages.error(request, 'Access denied.')
        return redirect('dashboard:redirect')
    return render(request, 'dashboard/checker_dashboard.html')


@login_required
def maker_dashboard(request):
    """Maker Dashboard"""
    if request.user.role != 'maker':
        messages.error(request, 'Access denied.')
        return redirect('dashboard:redirect')
    return render(request, 'dashboard/maker_dashboard.html')