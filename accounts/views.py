from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from .forms import RegisterForm

# Home page view
def home_view(request):
    return render(request, 'home.html')

# Register page view (processes registration and passes both forms to combined auth page)
def register_view(request):
    if request.method == 'POST':
        register_form = RegisterForm(request.POST)
        if register_form.is_valid():
            user = register_form.save()
            messages.success(request, 'Registration successful! Please sign in with your new account.')
            return redirect('login')
        else:
            login_form = AuthenticationForm()
            return render(request, 'login.html', {'form': login_form, 'register_form': register_form})
    else:
        return redirect('login')

# Login page view with role-based redirection and combined auth form support
def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            
            # Redirect user based on their role
            if user.role == 'donor':
                return redirect('donor_dashboard')
            elif user.role == 'ngo':
                return redirect('ngo_dashboard')
            elif user.role == 'beneficiary':
                return redirect('beneficiary_dashboard')
            else:
                return redirect('home')
        else:
            register_form = RegisterForm()
            return render(request, 'login.html', {'form': form, 'register_form': register_form})
    else:
        form = AuthenticationForm()
        register_form = RegisterForm()
    return render(request, 'login.html', {'form': form, 'register_form': register_form})

# Logout view
def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('home')

# Donor Dashboard view
@login_required
def donor_dashboard(request):
    if request.user.role != 'donor':
        messages.error(request, 'Access denied. Redirected to your correct dashboard.')
        return redirect_user_dashboard(request.user)
    return render(request, 'donor_dashboard.html', {'user': request.user})

# NGO Dashboard view
@login_required
def ngo_dashboard(request):
    if request.user.role != 'ngo':
        messages.error(request, 'Access denied. Redirected to your correct dashboard.')
        return redirect_user_dashboard(request.user)
    return render(request, 'ngo_dashboard.html', {'user': request.user})

# Beneficiary Dashboard view
@login_required
def beneficiary_dashboard(request):
    if request.user.role != 'beneficiary':
        messages.error(request, 'Access denied. Redirected to your correct dashboard.')
        return redirect_user_dashboard(request.user)
    return render(request, 'beneficiary_dashboard.html', {'user': request.user})

# Helper function to redirect user to their proper dashboard
def redirect_user_dashboard(user):
    if user.role == 'donor':
        return redirect('donor_dashboard')
    elif user.role == 'ngo':
        return redirect('ngo_dashboard')
    elif user.role == 'beneficiary':
        return redirect('beneficiary_dashboard')
    return redirect('home')
