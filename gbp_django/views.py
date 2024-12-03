from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth import login as auth_login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.contrib import messages
from allauth.socialaccount.models import SocialAccount, SocialApp
from allauth.socialaccount.providers.google.provider import GoogleProvider
from allauth.socialaccount.providers.oauth2.views import OAuth2Adapter, OAuth2View
from allauth.socialaccount import providers
from allauth.utils import build_absolute_uri
from allauth.socialaccount.helpers import complete_social_login
import allauth.socialaccount.providers.google.provider
from .models import Business, User, Notification, Session
from .api.business_management import get_business_accounts, store_business_data


def login(request):
    if request.user.is_authenticated:
        # Check if user needs Google OAuth
        if not request.user.socialaccount_set.filter(provider='google').exists():
            return redirect('/accounts/google/login/')
        return redirect(reverse('index'))  # This will now go to /dashboard/

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember', False)

        user = authenticate(request, username=email, password=password)
        if user is not None:
            auth_login(request, user)

            # Set session expiry based on remember me
            if not remember_me:
                request.session.set_expiry(0)

            # Check if user needs Google OAuth
            if not user.socialaccount_set.filter(provider='google').exists():
                return redirect(reverse('google_oauth'))

            return redirect(reverse('index'))
        else:
            messages.error(request, 'Invalid login credentials')

    return render(request, 'login.html')


def register(request):
    if request.user.is_authenticated:
        return redirect(reverse('index'))

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        if password != confirm_password:
            messages.error(request, 'Passwords do not match')
            return render(request, 'register.html')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered')
            return render(request, 'register.html')

        # Create new user
        user = User.objects.create_user(
            email=email,
            password=password,
            google_id=None  # Will be updated when connecting with Google
        )

        # Log user in
        auth_login(request, user)

        # Redirect to Google OAuth
        return redirect('/accounts/google/login/')

    return render(request, 'register.html')


@login_required
def direct_google_oauth(request):
    """
    Directly initiate Google OAuth process without intermediate page
    """
    # Initialize provider with request
    provider_class = providers.registry.get_class('google')
    provider = provider_class(request)

    # Get the app configuration directly from allauth
    from allauth.socialaccount.models import SocialApp
    app = SocialApp.objects.get_current('google', request)

    # Construct OAuth URL
    callback_url = build_absolute_uri(request, reverse('google_oauth_callback'))
    scope = ' '.join(provider.get_default_scope())

    # Get state from session
    from allauth.socialaccount.helpers import complete_social_login
    from allauth.socialaccount.providers.oauth2.views import OAuth2View
    oauth2_view = OAuth2View()
    state = oauth2_view.get_state(request)

    # Construct the authorization URL
    authorize_url = (
        'https://accounts.google.com/o/oauth2/v2/auth?'
        f'client_id={app.client_id}&'
        f'redirect_uri={callback_url}&'
        'response_type=code&'
        f'scope={scope}&'
        'access_type=offline&'
        f'state={state}&'
        'prompt=consent'
    )

    return redirect(authorize_url)


def google_oauth_callback(request):
    """Handle the callback from Google OAuth"""
    user = request.user

    # Update user's Google ID if not set
    if not user.google_id and user.socialaccount_set.filter(provider='google').exists():
        google_account = user.socialaccount_set.filter(provider='google').first()
        user.google_id = google_account.uid
        user.save()

    return redirect(reverse('index'))


@login_required
def index(request):
    # Ensure user has completed Google OAuth
    if not request.user.socialaccount_set.filter(provider='google').exists():
        return redirect('/accounts/google/login/')

    # Prioritize businesses associated with the logged-in user's Google account
    google_business = Business.objects.filter(user=request.user, user__socialaccount__provider='google').first()
    if google_business:
        other_businesses = Business.objects.filter(user=request.user).exclude(id=google_business.id)
        businesses = [google_business] + list(other_businesses)
    else:
        businesses = Business.objects.filter(user=request.user)
    users = User.objects.all()
    users_with_ids = [{'email': user.email, 'id': user.id} for user in users]
    unread_notifications_count = Notification.get_user_notifications(request.user.id).count()

    return render(request, 'index.html', {
        'dashboard_data': {'businesses': businesses, 'users': users_with_ids},
        'unread_notifications_count': unread_notifications_count
    })


def logout_view(request):
    logout(request)
    return redirect(reverse('login'))


def root_view(request):
    """
    Root view that handles the base URL '/'.
    Redirects to dashboard if authenticated, login page if not.
    """
    if request.user.is_authenticated:
        # Check if user needs Google OAuth
        if not request.user.socialaccount_set.filter(provider='google').exists():
            return redirect('/accounts/google/login/')
        return redirect(reverse('index'))
    return redirect(reverse('login'))
