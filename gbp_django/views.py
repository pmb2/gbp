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
    
    if request.user.is_authenticated:
        print(f"[DEBUG] User already authenticated: {request.user.email}")
        # If already authenticated and has Google OAuth, go to dashboard
        if request.user.socialaccount_set.filter(provider='google').exists():
            print("[DEBUG] User has Google OAuth, redirecting to dashboard")
            return redirect('index')
        # If authenticated but no Google OAuth, redirect to OAuth
        print("[DEBUG] User needs Google OAuth, redirecting to OAuth")
        return redirect('google_oauth')

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember', False)
        
        print(f"[DEBUG] Login attempt for email: {email}")
        print(f"[DEBUG] Remember me: {remember_me}")

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
            print("[ERROR] Authentication failed")
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
    print("\n[DEBUG] Starting Google OAuth callback...")
    
    code = request.GET.get('code')
    state = request.GET.get('state')
    stored_state = request.session.get('oauth_state')
    
    print(f"[DEBUG] Code present: {bool(code)}")
    print(f"[DEBUG] State present: {bool(state)}")
    print(f"[DEBUG] Stored state present: {bool(stored_state)}")
    print(f"[DEBUG] State match: {state == stored_state}")

    if not code or not state or state != stored_state:
        print("[ERROR] OAuth validation failed")
        messages.error(request, 'Invalid OAuth state or missing code')
        return redirect('login')

    if not request.user.is_authenticated:
        print("[ERROR] User not authenticated")
        messages.error(request, 'Please log in first')
        return redirect('login')
        
    print(f"[DEBUG] Authenticated user: {request.user.email}")

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
        user.save()

        # Create social account connection
        from allauth.socialaccount.models import SocialAccount, SocialApp
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

        print("[DEBUG] Social account created/updated successfully")

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
            
            # Create a new business record if none were stored
            if not stored_businesses:
                business_id = f"business-{user.id}-{int(time.time())}"
                new_business = Business.objects.create(
                    user=user,
                    business_name=user_info.get('name', 'New Business'),
                    business_id=business_id,
                    business_email=user.email,
                    is_verified=False,
                    email_verification_pending=True,
                    email_verification_token=secrets.token_urlsafe(32),
                    address='Pending verification',
                    phone_number='Pending verification',
                    website_url='Pending verification',
                    category='Pending verification'
                )
                
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


from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
import json
from .models import Notification, Business
from .api.business_management import update_business_details

@login_required
def get_notifications(request):
    notifications = Notification.objects.filter(
        user=request.user,
        read=False
    ).values('id', 'message', 'created_at')
    return JsonResponse({'notifications': list(notifications)})

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
    
    # Check if user has completed Google OAuth and has valid tokens
    if not request.user.socialaccount_set.filter(provider='google').exists():
        print("[DEBUG] User has not completed Google OAuth")
        return redirect(reverse('google_oauth'))

    print("[DEBUG] Fetching businesses and related data...")
    # Create dummy businesses if none exist
    if not Business.objects.filter(user=request.user).exists():
        dummy_businesses = [
            {
                'business_name': 'Dummy Business A',
                'business_id': 'dummy-business-a',
                'is_verified': False,
                'address': '123 Test St, Suite A',
                'phone_number': '(555) 000-0001',
                'website_url': 'No info',
                'category': 'No info',
                'profile_completion': 60
            },
            {
                'business_name': 'Dummy Business B',
                'business_id': 'dummy-business-b',
                'is_verified': True,
                'address': '456 Test Ave, Suite B',
                'phone_number': '(555) 000-0002',
                'website_url': 'https://dummy-b.example.com',
                'category': 'Test Business B',
                'profile_completion': 100
            },
            {
                'business_name': 'Dummy Business C',
                'business_id': 'dummy-business-c',
                'is_verified': False,
                'address': 'No info',
                'phone_number': 'No info',
                'website_url': 'No info',
                'category': 'No info',
                'profile_completion': 20
            }
        ]
        
        for business_data in dummy_businesses:
            Business.objects.create(
                user=request.user,
                business_email='dummy@example.com',  # Add required field
                **business_data
            )

    # Get all businesses for the current user with related counts
    businesses = Business.objects.filter(user=request.user).prefetch_related(
        'post_set', 'businessattribute_set', 'qanda_set', 'review_set'
    ).order_by('is_verified')  # Show unverified first
    print(f"[DEBUG] Found {businesses.count()} businesses")

    # Calculate profile completion for each business
    for business in businesses:
        business.profile_completion = business.calculate_profile_completion()
        
        # Set counts
        business.posts_count = business.post_set.count()
        business.photos_count = business.businessattribute_set.filter(key='photo').count()
        business.qanda_count = business.qanda_set.count()
        business.reviews_count = business.review_set.count()
    
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

    try:
        unread_notifications_count = Notification.objects.filter(
            user=request.user,
            read=False
        ).count()
    except:
        unread_notifications_count = 0

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
        
        # For dummy businesses, return mock verification status
        if business_id.startswith('dummy-'):
            # Default status for unrecognized dummy business
            status = {
                'business_name': True,
                'address': False,
                'phone': False,
                'category': False,
                'website': False,
                'hours': False,
                'photos': False
            }
            
            # Specific dummy business profiles
            if business_id == 'dummy-business-a':
                status.update({
                    'address': True,
                    'phone': True,
                    'category': False,
                    'website': False
                })
            elif business_id == 'dummy-business-b':
                status.update({
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
