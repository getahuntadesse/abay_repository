from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages


@login_required
def dashboard_redirect(request):
    """Redirect users to their respective dashboards based on role."""
    user = request.user
    if user.is_superuser or user.role == 'admin':
        return redirect('dashboard:admin_dashboard')
    elif user.role == 'author':
        return redirect('dashboard:author_dashboard')
    elif user.role == 'checker':
        # Canonical checker dashboard lives in books app (has full context)
        return redirect('books:checker_dashboard')
    elif user.role == 'maker':
        # Canonical maker dashboard lives in books app (has full context)
        return redirect('books:maker_dashboard')
    elif user.role == 'finance':
        return redirect('accounts:finance_dashboard')
    else:
        return redirect('dashboard:client_dashboard')


@login_required
def admin_dashboard(request):
    """Admin Dashboard."""
    if not (request.user.is_superuser or request.user.role == 'admin'):
        messages.error(request, 'Access denied.')
        return redirect('dashboard:redirect')
    return redirect('accounts:admin_dashboard')


@login_required
def author_dashboard(request):
    """Author Dashboard."""
    if request.user.role != 'author':
        messages.error(request, 'Access denied.')
        return redirect('dashboard:redirect')
    return redirect('accounts:author_dashboard')


@login_required
def client_dashboard(request):
    """Client Dashboard."""
    if request.user.role != 'client':
        messages.error(request, 'Access denied.')
        return redirect('dashboard:redirect')
    return redirect('accounts:client_dashboard')


@login_required
def checker_dashboard(request):
    """Checker Dashboard — delegates to the canonical books:checker_dashboard view."""
    if request.user.role != 'checker':
        messages.error(request, 'Access denied.')
        return redirect('dashboard:redirect')
    # Redirect to books app which renders the template with full context
    return redirect('books:checker_dashboard')


@login_required
def maker_dashboard(request):
    """Maker Dashboard — delegates to the canonical books:maker_dashboard view."""
    if request.user.role != 'maker':
        messages.error(request, 'Access denied.')
        return redirect('dashboard:redirect')
    # Redirect to books app which renders the template with full context
    return redirect('books:maker_dashboard')