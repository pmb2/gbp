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
from .api.business_management import get_business_accounts, store_business_data, get_locations
from .api.post_management import get_posts, store_posts
from .api.review_management import get_reviews, store_reviews
from .api.qa_management import get_questions_and_answers, store_questions_and_answers
from .api.media_management import get_photos, store_photos


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
    # Get the app configuration directly from allauth
    from allauth.socialaccount.models import SocialApp
    try:
        app = SocialApp.objects.get(provider='google')
    except SocialApp.DoesNotExist:
        raise ValueError("Google SocialApp is not configured. Please add it in the admin interface.")

    provider = provider_class(request, app)

    # Get the app configuration directly from allauth
    from allauth.socialaccount.models import SocialApp
    try:
        app = SocialApp.objects.get(provider='google')
    except SocialApp.DoesNotExist:
        raise ValueError("Google SocialApp is not configured. Please add it in the admin interface.")

    # Construct OAuth URL
    callback_url = build_absolute_uri(request, reverse('google_oauth_callback'))
    scope = ' '.join(provider.get_default_scope())

    # Get state from session
    import string
    import random

    # Generate a random state string
    state = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    request.session['oauth_state'] = state

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
    if not request.user.is_authenticated:
        return redirect('login')

    user = request.user
    google_account = user.socialaccount_set.filter(provider='google').first()
    
    if google_account:
        # Update user's Google ID
        user.google_id = google_account.uid
        user.save()

    print("[INFO] Fetching business accounts...")
    access_token = request.user.socialaccount_set.filter(provider='google').first().socialtoken_set.first().token
    business_data = get_business_accounts(access_token)
    print("[INFO] Business accounts fetched:", business_data)
    store_business_data(business_data, user.id, access_token)
    print("[INFO] Business data stored successfully.")

    # Fetch additional data like posts, reviews, Q&A, and photos
    for account in business_data.get('accounts', []):
        print(f"[INFO] Fetching locations for account {account['name']}...")
        locations = get_locations(access_token, account['name'])
        print(f"[INFO] Locations fetched for account {account['name']}:", locations)
        for location in locations.get('locations', []):
            # Fetch and store posts
            print(f"[INFO] Fetching posts for location {location['name']}...")
            posts_data = get_posts(access_token, account['name'], location['name'])
            print(f"[INFO] Posts fetched for location {location['name']}:", posts_data)
            store_posts(posts_data, location['name'])
            print(f"[INFO] Posts stored for location {location['name']}.")

            # Fetch and store reviews
            print(f"[INFO] Fetching reviews for location {location['name']}...")
            reviews_data = get_reviews(access_token, account['name'], location['name'])
            print(f"[INFO] Reviews fetched for location {location['name']}:", reviews_data)
            store_reviews(reviews_data, location['name'])
            print(f"[INFO] Reviews stored for location {location['name']}.")

            # Fetch and store Q&A
            print(f"[INFO] Fetching Q&A for location {location['name']}...")
            qa_data = get_questions_and_answers(access_token, account['name'], location['name'])
            print(f"[INFO] Q&A fetched for location {location['name']}:", qa_data)
            store_questions_and_answers(qa_data, location['name'])
            print(f"[INFO] Q&A stored for location {location['name']}.")

            # Fetch and store photos
            print(f"[INFO] Fetching photos for location {location['name']}...")
            photos_data = get_photos(access_token, account['name'], location['name'])
            print(f"[INFO] Photos fetched for location {location['name']}:", photos_data)
            store_photos(photos_data, location['name'])
            print(f"[INFO] Photos stored for location {location['name']}.")

    return redirect(reverse('index'))


@login_required
def index(request):
    # Ensure user has completed Google OAuth
    if not request.user.socialaccount_set.filter(provider='google').exists():
        return redirect('/accounts/google/login/')

    # Get the OAuth-connected business first
    oauth_business = Business.objects.filter(
        user=request.user,
        user__socialaccount__provider='google'
    ).select_related('user').first()
    
    # Get other businesses
    other_businesses = list(Business.objects.filter(
        user=request.user
    ).exclude(id=oauth_business.id if oauth_business else None))
    
    # Combine the lists with OAuth business first
    businesses = [oauth_business] if oauth_business else []
    businesses.extend(other_businesses)
    
    users = User.objects.all()
    for business in businesses:
        business.posts_count = business.posts_count if hasattr(business, 'posts_count') else 'No info'
        business.photos_count = business.photos_count if hasattr(business, 'photos_count') else 'No info'
        business.qanda_count = business.qanda_count if hasattr(business, 'qanda_count') else 'No info'
        business.reviews_count = business.reviews_count if hasattr(business, 'reviews_count') else 'No info'
        business.email_settings = business.email_settings if hasattr(business, 'email_settings') else 'No info'
        business.automation_status = business.automation_status if hasattr(business, 'automation_status') else 'No info'
        business.address = business.address if business.address else 'No info'
        business.phone_number = business.phone_number if business.phone_number else 'No info'
        business.website_url = business.website_url if business.website_url else 'No info'
        business.category = business.category if business.category else 'No info'
        business.is_verified = 'Verified' if business.is_verified else 'Not Verified'
    users_with_ids = [{'email': user.email, 'id': user.id} for user in users]
    unread_notifications_count = int(Notification.get_user_notifications(request.user.id).count())

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
