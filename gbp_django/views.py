from django.shortcuts import render, redirect
from django.http import JsonResponse
from datetime import datetime, timedelta
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth import login as auth_login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.contrib import messages
from django.conf import settings
from allauth.socialaccount import providers
from allauth.utils import build_absolute_uri
from .api.authentication import get_access_token, get_user_info
from .models import (
    Business, User, Notification, Session,
    Post, BusinessAttribute, QandA, Review
)
from .api.business_management import get_business_accounts, store_business_data, get_locations
from .api.post_management import get_posts, store_posts
from .api.review_management import get_reviews, store_reviews
from .api.qa_management import get_questions_and_answers, store_questions_and_answers
from .api.media_management import get_photos, store_photos


def login(request):
    if request.user.is_authenticated:
        # If already authenticated and has Google OAuth, go to dashboard
        if request.user.socialaccount_set.filter(provider='google').exists():
            return redirect('index')
        # If authenticated but no Google OAuth, redirect to OAuth
        return redirect('google_oauth')

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
    code = request.GET.get('code')
    state = request.GET.get('state')
    stored_state = request.session.get('oauth_state')

    if not code or not state or state != stored_state:
        messages.error(request, 'Invalid OAuth state or missing code')
        return redirect('login')

    if not request.user.is_authenticated:
        messages.error(request, 'Please log in first')
        return redirect('login')

    try:
        # Get tokens using the authorization code
        from allauth.socialaccount.models import SocialApp
        google_app = SocialApp.objects.get(provider='google')
        
        tokens = get_access_token(
            code,
            google_app.client_id,
            google_app.secret,
            request.build_absolute_uri(reverse('google_oauth_callback'))
        )

        access_token = tokens.get('access_token')
        refresh_token = tokens.get('refresh_token')
        
        if not access_token:
            messages.error(request, 'Failed to get access token')
            return redirect('login')

        # Store tokens in session
        request.session['google_token'] = access_token
        if refresh_token:
            request.session['refresh_token'] = refresh_token

        # Get user info from Google
        user_info = get_user_info(access_token)
        
        # Update user's Google information
        user = request.user
        user.google_id = user_info.get('sub')
        user.name = user_info.get('name')
        user.profile_picture_url = user_info.get('picture')
        user.google_access_token = access_token
        user.google_refresh_token = refresh_token
        user.google_token_expiry = datetime.now() + timedelta(seconds=tokens.get('expires_in', 3600))
        # Update user's Google OAuth status
        user.is_google_linked = True
        user.save(update_fields=['google_id', 'name', 'profile_picture_url', 
                               'google_access_token', 'google_refresh_token', 
                               'google_token_expiry', 'is_google_linked'])

    except Exception as e:
        messages.error(request, f'OAuth error: {str(e)}')
        return redirect('login')

    try:
        print("\n[DEBUG] Starting OAuth callback process...")
        print(f"[DEBUG] User ID: {user.id}")
        print(f"[DEBUG] Access token present: {bool(access_token)}")
        
        print("\n[INFO] Fetching business accounts...")
        business_data = get_business_accounts(access_token)
        print(f"[DEBUG] Raw business data received: {business_data}")
        
        if business_data:
            print("\n[DEBUG] Processing business data storage...")
            stored_businesses = store_business_data(business_data, user.id, access_token)
            print(f"[DEBUG] Stored businesses count: {len(stored_businesses)}")
            print("[INFO] Business data stored successfully.")
            
            # Print detailed business information
            for business in stored_businesses:
                print(f"\n[DEBUG] Stored Business Details:")
                print(f"  Name: {business.business_name}")
                print(f"  ID: {business.business_id}")
                print(f"  Address: {business.address}")
                print(f"  Phone: {business.phone_number}")
                print(f"  Website: {business.website_url}")
                print(f"  Category: {business.category}")
                print(f"  Verified: {business.is_verified}")
                
            # Only fetch additional data if we have business data
            if business_data.get('accounts'):
                for account in business_data['accounts']:
                    print(f"[INFO] Fetching locations for account {account['name']}...")
                    locations = get_locations(access_token, account['name'])
                    print(f"[INFO] Locations fetched for account {account['name']}:", locations)
                    
                    if locations and locations.get('locations'):
                        for location in locations['locations']:
                            # Fetch and store posts
                            try:
                                print(f"[INFO] Fetching posts for location {location['name']}...")
                                posts_data = get_posts(access_token, account['name'], location['name'])
                                if posts_data:
                                    store_posts(posts_data, location['name'])
                                    print(f"[INFO] Posts stored for location {location['name']}.")
                            except Exception as e:
                                print(f"[ERROR] Failed to fetch/store posts: {str(e)}")

                            # Fetch and store reviews
                            try:
                                print(f"[INFO] Fetching reviews for location {location['name']}...")
                                reviews_data = get_reviews(access_token, account['name'], location['name'])
                                if reviews_data:
                                    store_reviews(reviews_data, location['name'])
                                    print(f"[INFO] Reviews stored for location {location['name']}.")
                            except Exception as e:
                                print(f"[ERROR] Failed to fetch/store reviews: {str(e)}")

                            # Fetch and store Q&A
                            try:
                                print(f"[INFO] Fetching Q&A for location {location['name']}...")
                                qa_data = get_questions_and_answers(access_token, account['name'], location['name'])
                                if qa_data:
                                    store_questions_and_answers(qa_data, location['name'])
                                    print(f"[INFO] Q&A stored for location {location['name']}.")
                            except Exception as e:
                                print(f"[ERROR] Failed to fetch/store Q&A: {str(e)}")

                            # Fetch and store photos
                            try:
                                print(f"[INFO] Fetching photos for location {location['name']}...")
                                photos_data = get_photos(access_token, account['name'], location['name'])
                                if photos_data:
                                    store_photos(photos_data, location['name'])
                                    print(f"[INFO] Photos stored for location {location['name']}.")
                            except Exception as e:
                                print(f"[ERROR] Failed to fetch/store photos: {str(e)}")
        else:
            print("[WARNING] No business data returned from API")
            messages.warning(request, "No business accounts were found. You may need to create a Google Business Profile first.")
    except Exception as e:
        print(f"[ERROR] Failed to fetch/store business data: {str(e)}")
        messages.error(request, "There was an error connecting to Google Business Profile. Please try again.")
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

    messages.success(request, 'Successfully connected with Google')
    return redirect('index')


@login_required
def index(request):
    print("\n[DEBUG] Loading dashboard index...")
    print(f"[DEBUG] User: {request.user.email}")
    
    # Check if user has completed Google OAuth and has valid tokens
    if not request.user.socialaccount_set.filter(provider='google').exists():
        print("[DEBUG] User has not completed Google OAuth")
        return redirect(reverse('google_oauth'))

    print("[DEBUG] Fetching businesses and related data...")
    # Get all businesses for the current user with related counts
    businesses = Business.objects.filter(user=request.user).prefetch_related(
        'post_set', 'businessattribute_set', 'qanda_set', 'review_set'
    )
    print(f"[DEBUG] Found {businesses.count()} businesses")

    if not businesses.exists():
        # Create a dummy business object that mimics the Business model
        dummy_business = Business(
            business_name="No Business Data Found",
            business_id="dummy-no-data",
            user=request.user,
            address="No data available",
            phone_number="No data available", 
            website_url="No data available",
            category="No data available",
            is_verified=False,
            email_settings="No data available",
            automation_status="No data available"
        )
        # Set counts directly since this is a dummy object
        dummy_business.posts_count = 0
        dummy_business.photos_count = 0
        dummy_business.qanda_count = 0
        dummy_business.reviews_count = 0
        dummy_business.no_data = True  # Special flag for template
        businesses = [dummy_business]
    else:
        # Get the OAuth-connected business (should be first)
        oauth_business = businesses.filter(
            user__socialaccount__provider='google'
        ).first()
        
        # Reorder businesses list to put OAuth business first
        if oauth_business:
            businesses = [oauth_business] + list(businesses.exclude(id=oauth_business.id))
    
    # Process business data
    for business in businesses:
        if not hasattr(business, 'no_data'):
            # Only query counts for real business instances
            business.posts_count = Post.objects.filter(business=business).count()
            business.photos_count = BusinessAttribute.objects.filter(business=business, key='photo').count()
            business.qanda_count = QandA.objects.filter(business=business).count()
            business.reviews_count = Review.objects.filter(business=business).count()
        
        # Set default values for empty fields
        business.email_settings = getattr(business, 'email_settings', 'Enabled')
        business.automation_status = getattr(business, 'automation_status', 'Active')
        business.address = business.address or 'No info'
        business.phone_number = business.phone_number or 'No info'
        business.website_url = business.website_url or 'No info'
        business.category = business.category or 'No info'
        business.is_verified = 'Verified' if business.is_verified else 'Not Verified'

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
@login_required
def get_verification_status(request, business_id):
    """API endpoint to check business verification status"""
    try:
        business = Business.objects.get(business_id=business_id, user=request.user)
        
        # Get the latest data from Google API
        access_token = request.user.google_access_token
        account_data = get_business_accounts(access_token)
        
        # Find matching business in API response
        business_data = next(
            (acc for acc in account_data.get('accounts', []) 
             if acc['name'] == business_id), 
            None
        )
        
        if not business_data:
            return JsonResponse({'error': 'Business not found'}, status=404)
            
        # Check various verification requirements
        status = {
            'business_name': bool(business_data.get('accountName')),
            'address': bool(business_data.get('address')),
            'phone': bool(business_data.get('primaryPhone')),
            'category': bool(business_data.get('primaryCategory')),
            'website': bool(business_data.get('websiteUrl')),
            'hours': bool(business_data.get('regularHours')),
            'photos': bool(business_data.get('photos')),
        }
        
        return JsonResponse(status)
        
    except Business.DoesNotExist:
        return JsonResponse({'error': 'Business not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
