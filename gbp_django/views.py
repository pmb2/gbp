import requests
import time
from django.shortcuts import render, redirect
from django.http import JsonResponse
from datetime import datetime, timedelta
import secrets
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.contrib import messages
from django.conf import settings
from .utils.rag_utils import answer_question, add_to_knowledge_base

def send_verification_email(business):
    """Send verification email to business email address"""
    verification_url = f"{settings.SITE_URL}/api/business/verify-email/{business.email_verification_token}/"
    
    context = {
        'business_name': business.business_name,
        'verification_url': verification_url
    }
    
    html_message = render_to_string('emails/verify_business_email.html', context)
    plain_message = f"Please verify your business email by clicking: {verification_url}"
    
    send_mail(
        subject='Verify Your Business Email',
        message=plain_message,
        html_message=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[business.business_email],
        fail_silently=False,
    )
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
    print("\n[DEBUG] Starting login process...")
    print(f"[DEBUG] Request method: {request.method}")
    
    # Check if we're returning from OAuth
    if request.session.get('oauth_success'):
        print("[DEBUG] OAuth success flag found - redirecting to dashboard")
        request.session.pop('oauth_success', None)
        return redirect('index')

    if request.user.is_authenticated:
        print(f"[DEBUG] User already authenticated: {request.user.email}")
        return redirect('index')

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember', False)
        
        print(f"[DEBUG] Login attempt for email: {email}")
        print(f"[DEBUG] Remember me: {remember_me}")

        # Try to find the user first
        try:
            user_obj = User.objects.get(email=email)
            print(f"\n[DEBUG] Found user in database: {user_obj.email}")
            print(f"[DEBUG] Stored password hash: {user_obj.password[:20]}...")
            print(f"[DEBUG] Full stored hash: {user_obj.password}")
            print(f"[DEBUG] Hash algorithm: {user_obj.password.split('$')[0]}")
            print(f"[DEBUG] Hash iterations: {user_obj.password.split('$')[1]}")
            
            # Debug the authentication process
            from django.contrib.auth.hashers import check_password
            raw_valid = check_password(password, user_obj.password)
            print(f"[DEBUG] Raw password check result: {raw_valid}")
        except User.DoesNotExist:
            print(f"[DEBUG] No user found with email: {email}")
            messages.error(request, f'No account found with email: {email}')
            return render(request, 'login.html')

        # Attempt authentication
        user = authenticate(request, username=email, password=password)
        if user is not None:
            print(f"[DEBUG] User authenticated successfully: {user.email}")
            print(f"[DEBUG] User ID: {user.id}")
            print(f"[DEBUG] Has Google OAuth: {user.socialaccount_set.filter(provider='google').exists()}")
            
            auth_login(request, user)
            print("[DEBUG] User logged in successfully")

            # Set session expiry based on remember me
            if not remember_me:
                request.session.set_expiry(0)
                print("[DEBUG] Session expiry set to browser close")

            # Check if user needs Google OAuth
            if not user.socialaccount_set.filter(provider='google').exists():
                print("[DEBUG] User needs Google OAuth, redirecting")
                return redirect(reverse('google_oauth'))

            print("[DEBUG] Redirecting to dashboard")
            return redirect(reverse('index'))
        else:
            print("\n[ERROR] Authentication failed for user:", email)
            print("[ERROR] User exists but authentication failed")
            print("[ERROR] This might indicate an incorrect password")
            
            # Get the backend that was used
            from django.contrib.auth import get_backends
            backends = get_backends()
            print("[DEBUG] Available authentication backends:", [b.__class__.__name__ for b in backends])
            
            # Try each backend manually for debugging
            for backend in backends:
                try:
                    auth_attempt = backend.authenticate(request, username=email, password=password)
                    print(f"[DEBUG] Auth attempt with {backend.__class__.__name__}: {'Success' if auth_attempt else 'Failed'}")
                except Exception as e:
                    print(f"[DEBUG] Backend {backend.__class__.__name__} error: {str(e)}")
            
            messages.error(request, 'Invalid password. Please try again.')

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

        try:
            # Create new user
            print(f"\n[DEBUG] Starting user registration for email: {email}")
            print("[DEBUG] Creating user with hashed password...")
            
            user = User.objects.create_user(
                email=email,
                password=password,
                google_id=None  # Will be updated when connecting with Google
            )
            
            # Debug password hash
            print(f"[DEBUG] User created successfully")
            print(f"[DEBUG] Generated password hash: {user.password[:20]}...")
            print(f"[DEBUG] Password hash algorithm: {user.password.split('$')[0]}")
            print(f"[DEBUG] Password hash iterations: {user.password.split('$')[1]}")
            
            messages.success(request, 'Registration successful! Please login.')
            return redirect('login')
        except Exception as e:
            messages.error(request, f'Registration failed: {str(e)}')
            return render(request, 'register.html')

    return render(request, 'register.html')


def direct_google_oauth(request):
    """
    Directly initiate Google OAuth process without intermediate page
    """
    # Initialize provider with request
    provider_class = providers.registry.get_class('google')
    
    # Get the app configuration
    from allauth.socialaccount.models import SocialApp
    try:
        app = SocialApp.objects.get(provider='google')
    except SocialApp.DoesNotExist:
        raise ValueError("Google SocialApp is not configured. Please add it in the admin interface.")

    # Construct OAuth URL
    callback_url = build_absolute_uri(request, reverse('google_oauth_callback'))
    scope = ' '.join([
        'openid',
        'https://www.googleapis.com/auth/business.manage',
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/userinfo.profile',
    ])

    # Generate and store state
    state = secrets.token_urlsafe(16)
    request.session['oauth_state'] = state
    request.session['oauth_in_progress'] = True

    # Construct the authorization URL with all required scopes
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
    print("\n[DEBUG] Starting Google OAuth callback...")
    print(f"[DEBUG] Session contents: {dict(request.session)}")
    print(f"[DEBUG] User authenticated: {request.user.is_authenticated}")
    
    code = request.GET.get('code')
    state = request.GET.get('state')
    stored_state = request.session.get('oauth_state')

    if not code or not state or state != stored_state:
        print("[ERROR] OAuth validation failed")
        messages.error(request, 'Invalid OAuth state or missing code')
        return redirect('login')

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
        
    # Now get user info using the access token
    user_info = get_user_info(access_token)
    google_email = user_info.get('email')
    google_id = user_info.get('sub')
    
    print(f"[DEBUG] Google user info: {google_email}")
    
    # Try to find existing user
    try:
        user = User.objects.get(email=google_email)
        print(f"[DEBUG] Found existing user: {user.email}")
        
        # Update Google credentials
        user.google_id = google_id
        user.name = user_info.get('name')
        user.profile_picture_url = user_info.get('picture')
        user.google_access_token = access_token
        user.google_refresh_token = refresh_token
        user.google_token_expiry = datetime.now() + timedelta(seconds=tokens.get('expires_in', 3600))
        user.save()
        
    except User.DoesNotExist:
        print(f"[DEBUG] Creating new user for: {google_email}")
        # Create new user
        user = User.objects.create_user(
            email=google_email,
            google_id=google_id,
            password=None,  # No password for OAuth users
            name=user_info.get('name'),
            profile_picture_url=user_info.get('picture'),
            google_access_token=access_token,
            google_refresh_token=refresh_token,
            google_token_expiry=datetime.now() + timedelta(seconds=tokens.get('expires_in', 3600))
        )
    
    # Log the user in
    auth_login(request, user)
    print(f"[DEBUG] User logged in: {user.email}")
    
    print(f"[DEBUG] Code present: {bool(code)}")
    print(f"[DEBUG] State present: {bool(state)}")
    print(f"[DEBUG] Stored state present: {bool(stored_state)}")
    print(f"[DEBUG] State match: {state == stored_state}")

    if not code or not state or state != stored_state:
        print("[ERROR] OAuth validation failed")
        messages.error(request, 'Invalid OAuth state or missing code')
        return redirect('login')

    # Get tokens using the authorization code
    from allauth.socialaccount.models import SocialApp
    google_app = SocialApp.objects.get(provider='google')

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

        # Fetch and store business data immediately after getting tokens
        try:
            print("[INFO] Fetching business accounts...")
            business_data = get_business_accounts(access_token)
                
            print("[INFO] Storing business data...")
            stored_businesses = store_business_data(business_data, request.user.id, access_token)
                
            # Fetch additional data for each business
            for business in stored_businesses:
                if business.is_verified:
                    try:
                        print(f"[INFO] Fetching additional data for {business.business_name}")
                        locations = get_locations(access_token, business.business_id)
                            
                        if locations.get('locations'):
                            for location in locations['locations']:
                                # Store business attributes
                                attributes = {
                                    'opening_hours': location.get('regularHours', {}),
                                    'special_hours': location.get('specialHours', {}),
                                    'service_area': location.get('serviceArea', {}),
                                    'labels': location.get('labels', []),
                                    'profile_state': location.get('profile', {}).get('state', 'COMPLETE'),
                                    'business_type': location.get('metadata', {}).get('businessType', ''),
                                    'year_established': location.get('metadata', {}).get('yearEstablished', ''),
                                    'employee_count': location.get('metadata', {}).get('employeeCount', '')
                                }
                                    
                                for key, value in attributes.items():
                                    BusinessAttribute.objects.update_or_create(
                                        business=business,
                                        key=key,
                                        defaults={'value': str(value)}
                                    )
                                        
                                # Store additional location-specific attributes
                                BusinessAttribute.objects.update_or_create(
                                    business=business,
                                    key='location_name',
                                    defaults={'value': location.get('locationName', '')}
                                )
                                    
                                BusinessAttribute.objects.update_or_create(
                                    business=business,
                                    key='primary_category',
                                    defaults={'value': location.get('primaryCategory', {}).get('displayName', '')}
                                )
                                    
                                BusinessAttribute.objects.update_or_create(
                                    business=business,
                                    key='additional_categories',
                                    defaults={'value': str(location.get('additionalCategories', []))}
                                )
                    except Exception as e:
                        print(f"[ERROR] Failed to store additional data: {str(e)}")
                        continue
                
            if stored_businesses:
                print(f"[INFO] Stored {len(stored_businesses)} businesses")
                    
                # Fetch additional data for verified businesses
                for business in stored_businesses:
                    if business.is_verified:
                        try:
                            print(f"[INFO] Fetching additional data for {business.business_name}")
                            locations = get_locations(access_token, business.business_id)
                                
                            if locations.get('locations'):
                                for location in locations['locations']:
                                    # Store business attributes
                                    attributes = {
                                        'opening_hours': location.get('regularHours', {}),
                                        'special_hours': location.get('specialHours', {}),
                                        'service_area': location.get('serviceArea', {}),
                                        'labels': location.get('labels', []),
                                        'profile_state': location.get('profile', {}).get('state', 'COMPLETE'),
                                        'business_type': location.get('metadata', {}).get('businessType', ''),
                                        'year_established': location.get('metadata', {}).get('yearEstablished', ''),
                                        'employee_count': location.get('metadata', {}).get('employeeCount', '')
                                    }
                                        
                                    for key, value in attributes.items():
                                        BusinessAttribute.objects.update_or_create(
                                            business=business,
                                            key=key,
                                            defaults={'value': str(value)}
                                        )
                        except Exception as e:
                            print(f"[ERROR] Failed to fetch additional data: {str(e)}")
                            continue
            else:
                print("[WARNING] No businesses stored")
                messages.warning(request, "No business accounts were found. A placeholder business has been created.")
        except Exception as e:
            print(f"[ERROR] Failed to process business data: {str(e)}")
            messages.error(request, "Failed to process business data. Please try again.")

        # Store tokens and update session flags
        request.session['google_token'] = access_token
        if refresh_token:
            request.session['refresh_token'] = refresh_token
        request.session['oauth_success'] = True
        request.session.pop('oauth_in_progress', None)
        request.session.pop('oauth_state', None)
        print("[DEBUG] Updated session flags - oauth_success=True, cleared oauth_in_progress and oauth_state")

        # Get user info from Google
        user_info = get_user_info(access_token)
        google_email = user_info.get('email')
        
        # Update user's Google information
        user = request.user
        user.google_id = user_info.get('sub')
        user.name = user_info.get('name')
        
        # Update any existing unverified businesses with this Google email
        Business.objects.filter(
            user=user,
            is_verified=False
        ).update(google_email=google_email)
        user.profile_picture_url = user_info.get('picture')
        user.google_access_token = access_token
        user.google_refresh_token = refresh_token
        user.google_token_expiry = datetime.now() + timedelta(seconds=tokens.get('expires_in', 3600))
        user.save()

        # Create social account connection
        from allauth.socialaccount.models import SocialAccount, SocialApp, SocialToken
        google_app = SocialApp.objects.get(provider='google')
        
        # Create or update social account
        social_account, created = SocialAccount.objects.get_or_create(
            user=user,
            provider='google',
            defaults={
                'uid': user_info.get('sub'),
                'extra_data': user_info
            }
        )
        
        if not created:
            social_account.extra_data = user_info
            social_account.save()

        # Create or update social token
        SocialToken.objects.update_or_create(
            account=social_account,
            app=google_app,
            defaults={
                'token': access_token,
                'token_secret': '',  # Not used for OAuth2
                'expires_at': user.google_token_expiry
            }
        )

        print("[DEBUG] Social account and token created/updated successfully")

        # Fetch and store business data
        try:
            business_data = get_business_accounts(access_token)
            stored_businesses = store_business_data(business_data, user.id, access_token)
                
            if stored_businesses:
                for business in stored_businesses:
                    if business.is_verified:
                        # Store additional data for verified businesses
                        try:
                            locations = get_locations(access_token, business.business_id)
                            if locations.get('locations'):
                                for location in locations['locations']:
                                    # Store business attributes
                                    for key, value in location.items():
                                        if key not in ['name', 'locationName', 'address']:
                                            BusinessAttribute.objects.update_or_create(
                                                business=business,
                                                key=key,
                                                defaults={'value': str(value)}
                                            )
                        except Exception as e:
                            print(f"[ERROR] Failed to store additional business data: {str(e)}")
                            continue
                    
                messages.success(request, f"Successfully added {len(stored_businesses)} business(es) to your account.")
            else:
                messages.warning(request, "No business accounts were found. A placeholder business has been created.")
                
            return redirect('index')
                
        except Exception as e:
            print(f"[ERROR] Failed to process business data: {str(e)}")
            messages.error(request, "Failed to process business data. Please try again.")
            return redirect('index')

    except Exception as e:
        messages.error(request, f'OAuth error: {str(e)}')
        return redirect('login')

    try:
        print("\n[DEBUG] Starting OAuth callback process...")
        print(f"[DEBUG] User ID: {user.id}")
        print(f"[DEBUG] Access token present: {bool(access_token)}")
            
        print("\n[INFO] Fetching business accounts...")
        business_data = get_business_accounts(access_token)
        if not business_data:
            print("[WARNING] No business data returned from API")
            messages.warning(request, "No business accounts were found. You may need to create a Google Business Profile first.")
            return redirect('index')
            
        print(f"[DEBUG] Raw business data received: {business_data}")
        
        print("\n[DEBUG] Processing business data storage...")
        stored_businesses = store_business_data(business_data, user.id, access_token)
        
        # Store additional business attributes
        for business in stored_businesses:
            try:
                locations = get_locations(access_token, business.business_id)
                if locations.get('locations'):
                    for location in locations['locations']:
                        # Store business attributes
                        BusinessAttribute.objects.update_or_create(
                            business=business,
                            key='opening_hours',
                            defaults={'value': str(location.get('regularHours', {}))}
                        )
                        BusinessAttribute.objects.update_or_create(
                            business=business,
                            key='special_hours',
                            defaults={'value': str(location.get('specialHours', {}))}
                        )
                        BusinessAttribute.objects.update_or_create(
                            business=business,
                            key='service_area',
                            defaults={'value': str(location.get('serviceArea', {}))}
                        )
                        BusinessAttribute.objects.update_or_create(
                            business=business,
                            key='labels',
                            defaults={'value': str(location.get('labels', []))}
                        )
            except Exception as e:
                print(f"[ERROR] Failed to store business attributes: {str(e)}")
                continue
            
            # Print existing businesses for debugging
            print("\n[DEBUG] Current businesses for user:")
            existing_businesses = Business.objects.filter(user=user)
            for b in existing_businesses:
                print(f"- {b.business_name} (ID: {b.business_id}, Verified: {b.is_verified})")

            # Create or update business records
            if not stored_businesses:
                print("\n[DEBUG] No existing businesses found, creating new business record")
                timestamp = int(time.time())
                business_id = f"gbp-oauth-{user.id}-{timestamp}"
                print(f"[DEBUG] Generated OAuth business ID: {business_id}")
                
                business_name = user_info.get('name', 'New Business')
                print(f"[DEBUG] Using business name: {business_name}")
                
                new_business = Business.objects.create(
                    business_id=business_id,
                    user=user,
                    business_name=business_name,
                    business_email=user.email,
                    is_verified=False,
                    email_verification_pending=True,
                    email_verification_token=secrets.token_urlsafe(32),
                    address='Pending verification',
                    phone_number='Pending verification',
                    website_url='Pending verification',
                    category='Pending verification'
                )
                print(f"[DEBUG] Created new business record: {new_business.business_id}")
                
                # Create notification for new business
                Notification.objects.create(
                    user=user,
                    message=f"Please verify your business profile to unlock all features."
                )
                
                stored_businesses = [new_business]
                
            print(f"[DEBUG] Stored businesses count: {len(stored_businesses)}")
            print("[INFO] Business data stored successfully.")
                
            # Create success notification
            Notification.objects.create(
                user=user,
                message=f"Successfully added {len(stored_businesses)} business(es) to your account."
            )
            
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

            try:
                # Only fetch additional data if we have business data
                if not business_data.get('accounts'):
                    print("[WARNING] No business data returned from API")
                    messages.warning(request, "No business accounts were found. You may need to create a Google Business Profile first.")
                    return redirect('index')

                messages.success(request, 'Successfully connected with Google')
                return redirect('index')
                
            except Exception as e:
                print(f"[ERROR] Failed to fetch additional data: {str(e)}")
                messages.warning(request, "Connected successfully but failed to fetch some data. Please try refreshing.")
                return redirect('index')

    except Exception as e:
        print(f"[ERROR] Failed to fetch/store business data: {str(e)}")
        messages.error(request, "There was an error connecting to Google Business Profile. Please try again.")
        return redirect('index')

    # Start new try block for locations
    try:
        if 'account' not in locals():
            print("[WARNING] No account data available")
            return redirect('index')
            
        print(f"[INFO] Fetching locations for account {account['name']}...")
        locations = get_locations(access_token, account['name'])
        print(f"[INFO] Locations fetched for account {account['name']}:", locations)
        
        try:
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
            # Store success flag in session
            request.session['oauth_success'] = True
            return redirect('index')
            
        except Exception as e:
            print(f"[ERROR] Failed to fetch additional data: {str(e)}")
            messages.warning(request, "Connected successfully but failed to fetch some data. Please try refreshing.")
            return redirect('index')
            
    except Exception as e:
        print(f"[ERROR] Failed to fetch location data: {str(e)}")
        messages.error(request, "There was an error connecting to Google Business Profile. Please try again.")
        return redirect('index')


from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
import json
from .models import Notification, Business
from .api.business_management import update_business_details

@login_required
@login_required
def get_notifications(request):
    notifications = Notification.objects.filter(
        user_id=request.user.id,
        read=False
    ).order_by('-created_at').values(
        'id', 
        'message', 
        'created_at'
    )
    
    formatted_notifications = []
    for notification in notifications:
        formatted_notifications.append({
            'id': notification['id'],
            'message': notification['message'],
            'created_at': notification['created_at'].strftime('%b %d, %Y %H:%M'),
            'timeAgo': get_time_ago(notification['created_at'])
        })
    
    return JsonResponse({'notifications': formatted_notifications})

@login_required
@require_http_methods(["POST"])
def mark_all_notifications_read(request):
    Notification.objects.filter(
        user_id=request.user.id,
        read=False
    ).update(read=True)
    return JsonResponse({'status': 'success'})

def get_time_ago(timestamp):
    """Helper function to format time ago string"""
    now = timezone.now()
    diff = now - timestamp
    
    if diff.days > 7:
        return timestamp.strftime('%b %d, %Y')
    elif diff.days > 0:
        return f"{diff.days}d ago"
    elif diff.seconds > 3600:
        return f"{diff.seconds // 3600}h ago"
    elif diff.seconds > 60:
        return f"{diff.seconds // 60}m ago"
    else:
        return "Just now"

@login_required
@require_http_methods(["POST"])
def update_business(request, business_id):
    if business_id.startswith('dummy-business-'):
        return JsonResponse({
            'status': 'verification_required',
            'message': 'This business needs to be verified before making updates.',
            'action': 'verify'
        }, status=403)
    try:
        data = json.loads(request.body.decode('utf-8'))
        business = Business.objects.get(business_id=business_id, user=request.user)
        
        # Validate required fields
        required_fields = ['business_name', 'address', 'phone', 'website', 'category']
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            return JsonResponse({
                'status': 'error',
                'message': f'Missing required fields: {", ".join(missing_fields)}'
            }, status=400)

        try:
            # Update Google Business Profile via API
            update_result = update_business_details(
                access_token=request.user.google_access_token,
                account_id=business.business_id,
                location_id=business.business_id,
                update_data=data
            )
            
            # Update local database
            business.business_name = data.get('business_name', business.business_name)
            business.address = data.get('address', business.address)
            business.phone_number = data.get('phone', business.phone_number)
            business.website_url = data.get('website', business.website_url)
            business.category = data.get('category', business.category)
            business.save()
            
            return JsonResponse({
                'status': 'success',
                'data': {
                    'business_name': business.business_name,
                    'address': business.address,
                    'phone': business.phone_number,
                    'website': business.website_url,
                    'category': business.category
                }
            })
            
        except requests.exceptions.RequestException as e:
            # Log the error details
            print(f"API Error: {str(e)}")
            if hasattr(e.response, 'json'):
                error_details = e.response.json()
                print(f"Error details: {error_details}")
            
            return JsonResponse({
                'status': 'error',
                'message': 'Failed to update Google Business Profile. Please check the API logs for details.'
            }, status=400)
            
    except Business.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Business not found'
        }, status=404)
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'An unexpected error occurred'
        }, status=500)

def dismiss_notification(request, notification_id):
    if request.method == 'POST':
        notification = Notification.objects.get(
            id=notification_id,
            user=request.user
        )
        notification.mark_as_read()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=405)

@login_required
@login_required
@require_http_methods(["POST"])
def update_automation_settings(request, business_id):
    try:
        data = json.loads(request.body)
        business = Business.objects.get(business_id=business_id, user=request.user)
        
        feature = data.get('feature')
        level = data.get('level')
        
        if feature not in ['qa', 'posts', 'reviews'] or level not in ['manual', 'approval', 'auto']:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid feature or automation level'
            }, status=400)
            
        # Update the appropriate field
        if feature == 'qa':
            business.qa_automation = level
        elif feature == 'posts':
            business.posts_automation = level
        elif feature == 'reviews':
            business.reviews_automation = level
            
        business.save()
        
        return JsonResponse({
            'status': 'success',
            'data': {
                'feature': feature,
                'level': level
            }
        })
        
    except Business.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Business not found'
        }, status=404)
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

def bulk_upload_businesses(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)
        
    if 'file' not in request.FILES:
        return JsonResponse({'error': 'No file uploaded'}, status=400)
        
    file = request.FILES['file']
    
    # Validate file type
    if not file.name.endswith(('.csv', '.xlsx')):
        return JsonResponse({'error': 'Invalid file type. Please upload CSV or Excel file'}, status=400)
        
    # Validate file size (5MB limit)
    if file.size > 5 * 1024 * 1024:
        return JsonResponse({'error': 'File size exceeds 5MB limit'}, status=400)
    
    try:
        # Process CSV/Excel file
        if file.name.endswith('.csv'):
            import csv
            decoded_file = file.read().decode('utf-8').splitlines()
            reader = csv.DictReader(decoded_file)
        else:
            import pandas as pd
            reader = pd.read_excel(file).to_dict('records')
            
        processed = 0
        for row in reader:
            # Validate required fields
            required_fields = ['Business Name', 'Email', 'Address', 'Phone', 'Website', 'Category']
            if not all(field in row for field in required_fields):
                continue
                
            # Create business record
            business = Business.objects.create(
                user=request.user,
                business_name=row['Business Name'],
                business_email=row['Email'],
                address=row['Address'],
                phone_number=row['Phone'],
                website_url=row['Website'],
                category=row['Category'],
                email_verification_pending=True,
                email_verification_token=secrets.token_urlsafe(32)
            )
            
            # Send verification email
            send_verification_email(business)
            processed += 1
            
        return JsonResponse({
            'status': 'success',
            'processed': processed,
            'message': f'Successfully processed {processed} businesses'
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'error': str(e)
        }, status=500)

@login_required
def verify_business_email(request, token):
    try:
        business = Business.objects.get(
            email_verification_token=token,
            email_verification_pending=True
        )
        
        business.email_verification_pending = False
        business.email_verified_at = timezone.now()
        business.save()
        
        messages.success(request, 'Email verified successfully!')
        return redirect('index')
        
    except Business.DoesNotExist:
        messages.error(request, 'Invalid or expired verification token')
        return redirect('index')

def index(request):
    print("\n[DEBUG] Loading dashboard index...")
    print(f"[DEBUG] User: {request.user.email}")
    
    print("[DEBUG] Fetching businesses and related data...")
    # Check if we just completed OAuth successfully
    oauth_success = request.session.pop('oauth_success', False)
    
    # If we just completed OAuth successfully, continue to dashboard
    if oauth_success:
        print("[DEBUG] OAuth just completed successfully - continuing to dashboard")

    # Get all businesses for the current user with related counts
    businesses = Business.objects.filter(user=request.user).prefetch_related(
        'post_set', 'businessattribute_set', 'qanda_set', 'review_set'
    ).order_by('-is_connected', '-is_verified')  # Show connected but unverified first
    
    print(f"\n[DEBUG] Found {businesses.count()} businesses")
    print("[DEBUG] Business details:")
    for business in businesses:
        print(f"\nBusiness: {business.business_name}")
        print(f"ID: {business.business_id}")
        print(f"Verified: {business.is_verified}")
        print(f"Completion: {business.calculate_profile_completion()}%")
        print(f"Email: {business.business_email}")
        print(f"Address: {business.address}")
        print(f"Phone: {business.phone_number}")
        print(f"Website: {business.website_url}")
        print(f"Category: {business.category}")

    # Calculate profile completion for each business
    for business in businesses:
        business.profile_completion = business.calculate_profile_completion()
        
        # Set counts
        business.posts_count = business.post_set.count()
        business.photos_count = business.businessattribute_set.filter(key='photo').count()
        business.qanda_count = business.qanda_set.count()
        business.reviews_count = business.review_set.count()
    
    # Calculate business statistics
    stats = {
        'step1_count': 0,  # Not Verified (0%)
        'step2_count': 0,  # Getting Started (1-40%)
        'step3_count': 0,  # In Progress (41-80%)
        'step4_count': 0,  # Complete (81-100%)
        'total_businesses': len(businesses),
        'total_completion': 0
    }
    
    for business in businesses:
        completion = business.calculate_profile_completion()
        if not business.is_verified:
            stats['step1_count'] += 1
        elif completion <= 40:
            stats['step2_count'] += 1
        elif completion <= 80:
            stats['step3_count'] += 1
        else:
            stats['step4_count'] += 1
        stats['total_completion'] += completion
    
    stats['average_completion'] = round(stats['total_completion'] / stats['total_businesses'] if stats['total_businesses'] > 0 else 0)
    
    # Sort businesses by completion score (after calculating all scores)
    businesses = sorted(businesses, key=lambda x: (x.is_verified, x.profile_completion))

    # Get the OAuth-connected business (should be first)
    oauth_business = next(
        (b for b in businesses if b.user.socialaccount_set.filter(provider='google').exists()),
        None
    )
    
    # Reorder businesses list to put OAuth business first
    if oauth_business:
        businesses = [oauth_business] + [b for b in businesses if b != oauth_business]
    
    # Process business data
    for business in businesses:
        if not hasattr(business, 'no_data'):
            # Only query counts for real business instances
            business.posts_count = Post.objects.filter(business=business).count()
            business.photos_count = BusinessAttribute.objects.filter(business=business, key='photo').count()
            business.qanda_count = QandA.objects.filter(business=business).count()
            business.reviews_count = Review.objects.filter(business=business).count()
        
        # Set default values for empty fields
        business.email_settings = getattr(business, 'email_settings', {
            'enabled': True,
            'compliance_alerts': True,
            'content_approval': True,
            'weekly_summary': True,
            'verification_reminders': True
        })
        business.automation_status = getattr(business, 'automation_status', 'Active')
        business.address = business.address or 'No info'
        business.phone_number = business.phone_number or 'No info'
        business.website_url = business.website_url or 'No info'
        business.category = business.category or 'No info'
        business.is_verified = 'Verified' if business.is_verified else 'Not Verified'

    users = User.objects.all()
    users_with_ids = [{'email': user.email, 'id': user.id} for user in users]
    unread_notifications_count = Notification.get_user_notifications(request.user.id).count()

    try:
        unread_notifications_count = Notification.objects.filter(
            user=request.user,
            read=False
        ).count()
    except:
        unread_notifications_count = 0

    return render(request, 'index.html', {
        'dashboard_data': {
            'businesses': businesses, 
            'users': users_with_ids,
            'stats': stats
        },
        'unread_notifications_count': unread_notifications_count
    })


def logout_view(request):
    logout(request)
    return redirect(reverse('login'))


@require_http_methods(["POST"])
def submit_feedback(request):
    try:
        data = json.loads(request.body)
        feedback_type = data.get('type', 'Not specified')
        message = data.get('message', '')
        user_email = request.user.email if request.user.is_authenticated else 'Anonymous'

        # Construct email
        subject = f'GBP Automation Pro Feedback - {feedback_type}'
        email_body = f"""
New feedback received:

Type: {feedback_type}
From: {user_email}
Message:
{message}
        """

        # Send email
        send_mail(
            subject=subject,
            message=email_body,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[settings.FEEDBACK_EMAIL],
            fail_silently=False,
        )

        return JsonResponse({'status': 'success'})
    except Exception as e:
        print(f"Error sending feedback: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'Failed to send feedback'
        }, status=500)

@login_required
@require_http_methods(["POST"])
def chat_message(request, business_id):
    """Handle chat messages using RAG"""
    try:
        data = json.loads(request.body)
        message = data.get('message')
        
        if not message:
            return JsonResponse({
                'status': 'error',
                'message': 'No message provided'
            }, status=400)
            
        # Get response using RAG
        response = answer_question(message, business_id)
        
        return JsonResponse({
            'status': 'success',
            'response': response
        })
        
    except Business.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Business not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
@require_http_methods(["POST"]) 
def add_knowledge(request, business_id):
    """Add new knowledge to the business knowledge base"""
    try:
        data = json.loads(request.body)
        question = data.get('question')
        answer = data.get('answer')
        
        if not question or not answer:
            return JsonResponse({
                'status': 'error',
                'message': 'Question and answer are required'
            }, status=400)
            
        # Add to knowledge base
        faq = add_to_knowledge_base(business_id, question, answer)
        
        return JsonResponse({
            'status': 'success',
            'data': {
                'id': faq.id,
                'question': faq.question,
                'answer': faq.answer
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

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
        
        # Check verification status for any business
        status = {
            'business_name': False,
            'address': False,
            'phone': False,
            'category': False,
            'website': False,
            'hours': False,
            'photos': False
        }

        if not business.user.socialaccount_set.filter(provider='google').exists():
            # For dummy/test businesses, return predefined status
            if business_id == 'dummy-business-a':
                status.update({
                    'address': True,
                    'phone': True
                })
            elif business_id == 'dummy-business-b':
                status.update({
                    'business_name': True,
                    'address': True,
                    'phone': True,
                    'category': True,
                    'website': True,
                    'hours': True,
                    'photos': True
                })
            elif business_id == 'dummy-business-c':
                status.update({
                    'business_name': True
                })
            
            return JsonResponse(status)

        # For real businesses, get the latest data from Google API
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
