import os
import secrets
import json
import requests
import logging
import traceback
from datetime import timedelta, datetime

logger = logging.getLogger(__name__)

from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods

from allauth.socialaccount import providers
from allauth.socialaccount.models import SocialApp

from .models import (
    User, Post, QandA, Review, FAQ, Business, Notification, Task
)
from .api.authentication import get_access_token, get_user_info
from .api.business_management import (
    get_business_accounts, store_business_data, get_locations
)
from .api.business_management import (
    get_business_accounts, store_business_data, get_locations, update_business_details
)
from .utils.model_interface import get_llm_model
from .utils.rag_utils import answer_question, add_to_knowledge_base
from .utils.seo_analyzer import analyze_website
from .utils.website_scraper import scrape_and_summarize_website
from .utils.embeddings import update_business_embedding
from .utils.file_processor import store_file_content, process_folder
from .utils.email_service import EmailService


def send_verification_email(business):
    """Send verification email to the business email address."""
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


def login(request):
    """
    Standard login view:
    - Checks if user is returning from OAuth (session flag).
    - Authenticates user via email/password.
    - Optionally sets a session expiry if 'Remember Me' is not selected.
    - Redirects to Google OAuth if user has no linked Google account.
    """
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

        # Try to find the user
        try:
            User.objects.get(email=email)
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
                return redirect(reverse('direct_google_oauth'))

            print("[DEBUG] Redirecting to dashboard")
            return redirect(reverse('index'))
        else:
            print("\n[ERROR] Authentication failed for user:", email)
            print("[ERROR] This might indicate an incorrect password")

            # Debug: check available auth backends
            from django.contrib.auth import get_backends
            backends = get_backends()
            print("[DEBUG] Available authentication backends:", [b.__class__.__name__ for b in backends])
            for backend in backends:
                try:
                    result = backend.authenticate(request, username=email, password=password)
                    print(f"[DEBUG] Attempt with {backend.__class__.__name__}: {'Success' if result else 'Failed'}")
                except Exception as e:
                    print(f"[DEBUG] Backend {backend.__class__.__name__} error: {str(e)}")

            messages.error(request, 'Invalid password. Please try again.')

    return render(request, 'login.html')


def register(request):
    """
    Standard registration view:
    - Validates if user is already authenticated.
    - Checks if passwords match.
    - Creates a new user if the email does not already exist.
    """
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
            print(f"\n[DEBUG] Starting user registration for email: {email}")
            user = User.objects.create_user(
                email=email,
                password=password,
                google_id=None  # Will be updated when connecting with Google
            )
            print(f"[DEBUG] User created successfully: {user.email}")
            messages.success(request, 'Registration successful! Please login.')
            return redirect('index')
        except Exception as e:
            messages.error(request, f'Registration failed: {str(e)}')
            return render(request, 'register.html')

    return render(request, 'register.html')


def direct_google_oauth(request):
    """
    Directly initiate Google OAuth process without an intermediate page.
    Stores a state token and sets the relevant OAuth scopes.
    """
    provider_class = providers.registry.get_class('google')

    # Get the app configuration
    try:
        app = SocialApp.objects.get(provider='google')
    except SocialApp.DoesNotExist:
        raise ValueError("Google SocialApp is not configured. Please add it in the admin interface.")

    # Store the action type
    request.session['oauth_action'] = 'add_business' if request.user.is_authenticated else 'login'

    callback_url = 'https://gbp.backus.agency/google/callback/'
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
    """
    Handle the callback from Google OAuth.
    Exchanges authorization code for tokens, fetches user info, and links or creates a user.
    Also retrieves business accounts/locations from Google and stores them locally.
    """
    try:
        logger.info("Starting Google OAuth callback...")
        logger.debug(f"GET params: {request.GET}")
        logger.debug(f"Session keys: {list(request.session.keys())}")

        code = request.GET.get('code')
        state = request.GET.get('state')
        stored_state = request.session.get('oauth_state')

        # Validate the OAuth state and authorization code
        if not code or not state or state != stored_state:
            print("[ERROR] OAuth validation failed")
            messages.error(request, 'Invalid OAuth state or missing code.')
            return redirect('login')

        print("🔑 Retrieving Google app credentials...")
        try:
            google_app = SocialApp.objects.get(provider='google')
            print("✅ Found Google app configuration")
        except SocialApp.DoesNotExist:
            print("❌ Google app configuration not found!")
            raise

        callback_uri = settings.GOOGLE_OAUTH2_REDIRECT_URI
        logger.debug(f"Using callback URI: {callback_uri}")

        # Exchange auth code for tokens
        tokens = get_access_token(
            code,
            google_app.client_id,
            google_app.secret,
            callback_uri
        )
        print("✅ Successfully retrieved tokens")
        access_token = tokens.get('access_token')
        refresh_token = tokens.get('refresh_token')

        if not access_token:
            messages.error(request, 'Failed to get access token.')
            return redirect('login')

        # Fetch user info from Google
        print("👤 Fetching Google user info...")
        user_info = get_user_info(access_token)
        google_email = user_info.get('email')
        google_id = user_info.get('sub')

        # Find or create the user
        user, created = User.objects.get_or_create(email=google_email)
        if created:
            print(f"[DEBUG] Created new user: {google_email}")
        else:
            print(f"[DEBUG] Found existing user: {google_email}")

        # Update user details
        user.google_id = google_id
        user.name = user_info.get('name')
        user.profile_picture_url = user_info.get('picture')
        user.google_access_token = access_token
        user.google_refresh_token = refresh_token
        user.google_token_expiry = timezone.now() + timedelta(seconds=tokens.get('expires_in', 3600))
        user.save()

        # Log in the user
        auth_login(request, user)
        print(f"[DEBUG] User logged in: {user.email}")

        # Fetch and store business data
        print("\n🏢 Starting business data collection...")
        print("🔍 Fetching business accounts from Google API...")
        business_data = get_business_accounts(access_token)
        print("✅ Initial API call successful")

        # Get detailed location data for each account
        if business_data and business_data.get('accounts'):
            for account in business_data['accounts']:
                print(f"\n📍 Fetching locations for account: {account.get('accountName')}")
                locations = get_locations(access_token, account['name'])
                if locations and locations.get('locations'):
                    account['locations'] = locations['locations']
                    print(f"✅ Found {len(locations['locations'])} location(s)")
                else:
                    account['locations'] = []
                    print("⚠️ No locations found for this account")

            # Store business data with updated account information
            stored_businesses = store_business_data(business_data, user.id, access_token)
            if stored_businesses:
                print(f"✅ Successfully stored {len(stored_businesses)} business(es)")
                messages.success(request, f"Successfully linked {len(stored_businesses)} business(es)")
            else:
                print("⚠️ No businesses were stored")
                messages.warning(request, "No businesses were found to import")
        else:
            print("⚠️ No business accounts found in Google API response")
            messages.warning(request, "No businesses were found in your Google account")

        # Clean up session flags
        request.session['google_token'] = access_token
        if refresh_token:
            request.session['refresh_token'] = refresh_token
        request.session.pop('oauth_state', None)

        return redirect('index')

    except SocialApp.DoesNotExist:
        print("[ERROR] Google SocialApp is not configured.")
        messages.error(request, "Google integration is not configured. Please contact support.")
        return redirect('login')

    except SocialApp.DoesNotExist:
        logger.error("Google SocialApp is not configured.")
        messages.error(request, "Google integration is not configured. Please contact support.")
        return redirect('login')

    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        logger.debug(traceback.format_exc())
        messages.error(request, "An error occurred during authentication. Please try again.")
        return redirect('login')


from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
import json

from .utils.email_service import EmailService
from .models import Notification, Business, KnowledgeFile
from .api.business_management import update_business_details


@login_required
def get_notifications(request):
    """
    Retrieve unread notifications for the current user.
    Returns a list of notification IDs, messages, timestamps, and 'timeAgo' formats.
    """
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
    """
    Mark all unread notifications as read for the current user.
    """
    Notification.objects.filter(
        user_id=request.user.id,
        read=False
    ).update(read=True)
    return JsonResponse({'status': 'success'})


def get_time_ago(timestamp):
    """
    Helper function to produce a 'time ago' format for timestamps.
    E.g. '2h ago', '5m ago', or a date if over 7 days old.
    """
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
    """
    Update business details. If the business ID starts with 'dummy-business-', restrict updates
    until verification is completed. Otherwise, attempt to update both Google and local DB.
    """
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

        # Attempt to update on Google side
        try:
            update_business_details(
                access_token=request.user.google_access_token,
                account_id=business.business_id,
                location_id=business.business_id,
                update_data=data
            )
        except requests.exceptions.RequestException as e:
            # Log the error details
            print(f"API Error: {str(e)}")
            if hasattr(e, 'response') and e.response is not None and hasattr(e.response, 'json'):
                error_details = e.response.json()
                print(f"Error details: {error_details}")

            return JsonResponse({
                'status': 'error',
                'message': 'Failed to update Google Business Profile. Please check the API logs for details.'
            }, status=400)

        # Update local database fields
        business.business_name = data.get('business_name', business.business_name)
        business.address = data.get('address', business.address)
        business.phone_number = data.get('phone', business.phone_number)
        business.website_url = data.get('website', business.website_url)
        business.category = data.get('category', business.category)

        # Update website summary if URL changed
        old_website_url = business.website_url
        new_website_url = data.get('website')
        if new_website_url and new_website_url != old_website_url:
            try:
                summary = scrape_and_summarize_website(new_website_url)
                business.website_summary = summary
            except Exception as e:
                print(f"Error scraping website: {e}")
                business.website_summary = "Error scraping website"

        business.save()

        # Retrieve updated business
        updated_business = Business.objects.get(business_id=business_id, user=request.user)

        return JsonResponse({
            'status': 'success',
            'data': {
                'business_name': updated_business.business_name,
                'address': updated_business.address,
                'phone': updated_business.phone_number,
                'website': updated_business.website_url,
                'category': updated_business.category,
                'website_summary': updated_business.website_summary
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
        print(f"Unexpected error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'An unexpected error occurred'
        }, status=500)


def dismiss_notification(request, notification_id):
    """
    Mark a specific notification as read/acknowledged by ID.
    """
    if request.method == 'POST':
        try:
            notification = Notification.objects.get(id=notification_id, user=request.user)
            notification.mark_as_read()
            return JsonResponse({'status': 'success'})
        except Notification.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Notification not found'}, status=404)
    return JsonResponse({'status': 'error'}, status=405)


@login_required
@require_http_methods(["POST"])
def update_automation_settings(request, business_id):
    """
    Update the automation settings for a specific feature (qa, posts, reviews) of a given business.
    The 'feature' should be one of ['qa', 'posts', 'reviews'] and the 'level' should be one of ['manual', 'approval', 'auto'].
    """
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

        # Update the appropriate automation field
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
        })


@login_required
@require_http_methods(["GET"])
def get_seo_health(request, business_id):
    """
    API endpoint to get SEO health data for a business.
    The business must have a valid 'website_url' set.
    """
    try:
        business = Business.objects.get(business_id=business_id, user=request.user)
        if not business.website_url:
            return JsonResponse({
                'status': 'error',
                'message': 'No website URL found for this business'
            }, status=400)

        seo_data = analyze_website(business.website_url)
        return JsonResponse({
            'status': 'success',
            **seo_data  # Expand the SEO data dictionary into the JSON response
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
@require_http_methods(["GET"])
def generate_content(request):
    """
    Generate content using LLM and RAG with task-specific prompts.
    Task types: [POST, PHOTO, REVIEW, QA, COMPLIANCE].
    """
    try:
        business_id = request.GET.get('business_id')
        task_type = request.GET.get('task_type', 'POST')  # Default to 'POST' if not provided

        if not business_id:
            return JsonResponse({
                'status': 'error',
                'message': 'Business ID is required'
            }, status=400)

        # Get business context
        business = Business.objects.get(business_id=business_id)
        if not business:
            return JsonResponse({
                'status': 'error',
                'message': 'Business not found'
            }, status=404)

        # Get LLM model
        model = get_llm_model()

        # Define prompts and templates for different task types
        prompts = {
            'POST': (
                f"Generate a social media post for {business.business_name} in the {business.category} category. "
                f"Include details about the business, its location, and services. Keep it concise and engaging. "
                f"Use a friendly and professional tone. Focus on attracting new customers and highlighting key features."
            ),
            'PHOTO': (
                f"Generate a caption for a photo of {business.business_name} in the {business.category} category. "
                f"Describe the photo and its relevance to the business. Keep it short and engaging. "
                f"Use a tone that encourages interaction and highlights the visual appeal."
            ),
            'REVIEW': (
                f"Generate a response to a customer review for {business.business_name} in the {business.category} category. "
                f"Acknowledge the customer's feedback and address any concerns. Keep it professional and courteous. "
                f"Use a tone that shows appreciation and encourages further engagement."
            ),
            'QA': (
                f"Generate a question and answer pair for {business.business_name} in the {business.category} category. "
                f"The question should be relevant to the business and its services. The answer should be informative and helpful. "
                f"Use a tone that is clear, concise, and professional."
            ),
            'COMPLIANCE': (
                f"Generate a compliance check report for {business.business_name} in the {business.category} category. "
                f"Identify any potential compliance issues and suggest solutions. Keep it concise and informative. "
                f"Use a tone that is professional and objective."
            )
        }

        prompt = prompts.get(task_type, prompts['POST'])
        response = answer_question(query=prompt, business_id=business_id)

        return JsonResponse({
            'status': 'success',
            'content': response,
            'metadata': {
                'model': model.__class__.__name__,
                'business_name': business.business_name,
                'timestamp': timezone.now().isoformat()
            }
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


def bulk_upload_businesses(request):
    """
    Allows bulk creation of Business records by uploading CSV or XLSX files.
    Validates file type, size, and required fields.
    Creates each Business record, generates embeddings, and sends a verification email.
    """
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
            file_content = file.read()
            if not file_content:
                return JsonResponse({
                    'status': 'error',
                    'error': 'Empty or invalid file uploaded'
                }, status=400)

            try:
                decoded_file = file_content.decode('utf-8').splitlines()
                reader = csv.DictReader(decoded_file)
            except UnicodeDecodeError:
                return JsonResponse({
                    'status': 'error',
                    'error': 'Invalid CSV file encoding. Please ensure the file is UTF-8 encoded.'
                }, status=400)
        else:
            try:
                import pandas as pd
                reader = pd.read_excel(file).to_dict('records')
            except Exception as e:
                return JsonResponse({
                    'status': 'error',
                    'error': f'Error reading Excel file: {str(e)}'
                }, status=400)

        processed = 0
        for row in reader:
            # Validate required fields
            required_fields = ['Business Name', 'Email', 'Address', 'Phone', 'Website', 'Category']
            if not all(field in row for field in required_fields):
                continue

            # Create the business record
            business = Business.objects.create(
                user=request.user,
                business_name=row['Business Name'],
                business_email=row['Email'],
                address=row['Address'],
                phone_number=row['Phone'],
                website_url=row['Website'],
                category=row['Category'],
                email_verification_pending=True,
                email_verification_token=secrets.token_urlsafe(32),
                embedding=None  # Initialize embedding as null
            )

            # Generate embedding for business profile
            update_business_embedding(business)

            # Send verification email
            send_verification_email(business)
            processed += 1

        return JsonResponse({
            'status': 'success',
            'processed': processed,
            'message': f'Successfully processed {processed} businesses'
        })

    except Exception as e:
        print(f"Error in bulk upload: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'error': str(e)
        }, status=500)


@login_required
def verify_business_email(request, token):
    """
    Endpoint to verify a business email based on the token sent via email.
    Updates the business record to mark the email as verified.
    """
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
    """
    Main dashboard view ('index'):
      - Checks if OAuth success flag is set.
      - Fetches all businesses for current user and calculates stats.
      - Orders businesses by verification status & completion score.
      - Renders 'index.html' with relevant data and stats.
    """
    print("\n[DEBUG] Loading dashboard index...")
    print(f"[DEBUG] User: {request.user.email if request.user.is_authenticated else 'Anonymous'}")

    # Check if we just completed OAuth successfully
    oauth_success = request.session.pop('oauth_success', False)
    if oauth_success:
        print("[DEBUG] OAuth just completed successfully - continuing to dashboard")

    if not request.user.is_authenticated:
        print("[DEBUG] User is not authenticated, redirecting to login")
        return redirect('login')

    print("[DEBUG] Fetching businesses and related data...")
    businesses = Business.objects.filter(user=request.user).prefetch_related(
        'post_set', 'qanda_set', 'review_set', 'knowledge_files'
    ).order_by('-is_connected', '-is_verified')

    print(f"[DEBUG] Found {businesses.count()} businesses for user {request.user.email}")

    processed_businesses = []
    for business in businesses:
        # Compute profile completion, if needed
        if not hasattr(business, '_processed'):
            business.profile_completion = business.calculate_profile_completion()
            business.posts_count = business.post_set.count()
            business.photos_count = business.knowledge_files.filter(file_type__startswith='image/').count()
            business.qanda_count = business.qanda_set.count()
            business.reviews_count = business.review_set.count()
            business._processed = True
        processed_businesses.append(business)

    businesses = processed_businesses

    # Calculate statistics
    stats = {
        'step1_count': 0,  # Not Verified (0%)
        'step2_count': 0,  # Getting Started (1-40%)
        'step3_count': 0,  # In Progress (41-80%)
        'step4_count': 0,  # Complete (81-100%)
        'total_businesses': len(businesses),
        'total_completion': 0
    }

    for biz in businesses:
        completion = biz.profile_completion
        if not biz.is_verified:
            stats['step1_count'] += 1
        elif completion <= 40:
            stats['step2_count'] += 1
        elif completion <= 80:
            stats['step3_count'] += 1
        else:
            stats['step4_count'] += 1
        stats['total_completion'] += completion

    stats['average_completion'] = round(
        stats['total_completion'] / stats['total_businesses'] if stats['total_businesses'] > 0 else 0
    )

    # Sort businesses by verification status and completion score
    businesses = sorted(businesses, key=lambda x: (x.is_verified, x.profile_completion))

    # Get the OAuth-connected business (first)
    oauth_business = next(
        (b for b in businesses if b.user.socialaccount_set.filter(provider='google').exists()),
        None
    )
    # Move OAuth business to the front of the list
    if oauth_business:
        businesses = [oauth_business] + [b for b in businesses if b != oauth_business]

    # Process business data further
    for biz in businesses:
        # Only query counts for actual businesses
        if not hasattr(biz, 'no_data'):
            biz.posts_count = Post.objects.filter(business=biz).count()
            biz.photos_count = biz.knowledge_files.filter(file_type__startswith='image/').count()
            biz.qanda_count = QandA.objects.filter(business=biz).count()
            biz.reviews_count = Review.objects.filter(business=biz).count()

        # Ensure no empty fields
        biz.email_settings = getattr(biz, 'email_settings', {
            'enabled': True,
            'compliance_alerts': True,
            'content_approval': True,
            'weekly_summary': True,
            'verification_reminders': True
        })
        biz.automation_status = getattr(biz, 'automation_status', 'Active')
        biz.address = biz.address or 'No info'
        biz.phone_number = biz.phone_number or 'No info'
        biz.website_url = biz.website_url or 'No info'
        biz.category = biz.category or 'No info'
        biz.is_verified = 'Verified' if biz.is_verified else 'Not Verified'

    # Gather user info and unread notification count
    users = User.objects.all()
    users_with_ids = [{'email': u.email, 'id': u.id} for u in users]
    try:
        unread_notifications_count = Notification.objects.filter(user=request.user, read=False).count()
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
    """
    Log out the currently authenticated user and redirect to the login page.
    """
    logout(request)
    return redirect(reverse('login'))


@require_http_methods(["POST"])
def submit_feedback(request):
    """
    Handle feedback submissions with basic validation.
    Feedback is forwarded via EmailService, including metadata about the type and user email.
    """
    try:
        data = json.loads(request.body)
        feedback_type = data.get('type', 'suggestion')
        message = data.get('message', '')
        if request.user.is_authenticated:
            user_email = data.get('email', request.user.email)
        else:
            user_email = data.get('email', 'anonymous@user.com')

        if not message:
            return JsonResponse({
                'status': 'error',
                'message': 'Message is required'
            }, status=400)

        # Forward feedback using EmailService
        EmailService.forward_feedback(
            user_email,
            feedback_type,
            f"Feedback Type: {feedback_type}\n\n{message}\n\nSubmitted by: {user_email}"
        )

        return JsonResponse({
            'status': 'success',
            'message': 'Feedback submitted successfully'
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON format'
        }, status=400)
    except Exception as e:
        print(f"Error sending feedback: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'Failed to send feedback'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def chat_message(request, business_id):
    """
    Handle chat messages for a given business ID, returning an LLM/RAG-based response.
    Optionally includes previous chat history for context.
    """
    try:
        data = json.loads(request.body)
        message = data.get('message')
        chat_history = data.get('history', [])

        if not message:
            return JsonResponse({
                'status': 'error',
                'message': 'No message provided'
            }, status=400)

        # Get business context
        business = Business.objects.get(business_id=business_id)
        if not business:
            return JsonResponse({
                'status': 'error',
                'message': 'Business not found'
            }, status=404)

        # Get LLM model
        model = get_llm_model()

        # Use RAG for answering
        response = answer_question(
            query=message,
            business_id=business_id,
            chat_history=chat_history
        )

        # Store interaction in the FAQ model (for future retrieval/context)
        try:
            add_to_knowledge_base(
                business_id=business_id,
                question=message,
                answer=response
            )
        except Exception as e:
            print(f"[ERROR] Failed to store chat interaction: {str(e)}")

        return JsonResponse({
            'status': 'success',
            'response': response,
            'metadata': {
                'model': model.__class__.__name__,
                'business_name': business.business_name,
                'timestamp': timezone.now().isoformat()
            }
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
@require_http_methods(["GET", "DELETE"])
def get_memories(request, business_id):
    """
    Retrieve or delete chat memories for a given business, stored in the FAQ table.
    Only the last 10 interactions are returned.
    """
    try:
        business = Business.objects.get(business_id=business_id, user=request.user)

        # Fetch recent chat interactions from FAQ
        memories = FAQ.objects.filter(
            business=business,
            deleted_at__isnull=True
        ).order_by('-created_at')[:10]

        memory_list = [{
            'id': memory.id,
            'content': f"Q: {memory.question}\nA: {memory.answer}",
            'created_at': memory.created_at.isoformat()
        } for memory in memories]

        return JsonResponse({
            'status': 'success',
            'memories': memory_list
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


def preview_file(request, business_id, file_id):
    try:
        knowledge_file = KnowledgeFile.objects.get(
            id=file_id,
            business__business_id=business_id,
            business__user=request.user,
            deleted_at__isnull=True
        )

        if request.method == "GET":
            # Fetch the first few chunks for preview
            preview_chunks = knowledge_file.chunks.order_by('position')[:5]
            preview_content = '\n\n'.join([chunk.content for chunk in preview_chunks])

            response_data = {
                'status': 'success',
                'file': {
                    'id': knowledge_file.id,
                    'name': knowledge_file.file_name,
                    'content': preview_content,  # Use the preview content
                    'type': knowledge_file.file_type,
                    'created_at': knowledge_file.uploaded_at.isoformat(),
                    'size': knowledge_file.file_size
                }
            }
            return JsonResponse(response_data)

        elif request.method == "DELETE":
            knowledge_file.deleted_at = timezone.now()
            knowledge_file.save(update_fields=['deleted_at'])
            remaining_files = KnowledgeFile.objects.filter(
                business__business_id=business_id,
                deleted_at__isnull=True
            ).count()
            return JsonResponse({
                'status': 'success',
                'message': 'File deleted successfully',
                'remaining_files': remaining_files
            })
        else:
            return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    except KnowledgeFile.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'File not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def add_knowledge(request, business_id):
    """
    Add new knowledge to the business knowledge base. Handles both multipart form-data for file uploads
    or JSON requests for question/answer pairs.
    """
    if request.method == 'POST':
        try:
            # Validate business ownership
            try:
                business = Business.objects.get(business_id=business_id, user=request.user)
            except Business.DoesNotExist:
                print("[ERROR] Business not found or access denied")
                return JsonResponse({
                    'status': 'error',
                    'message': 'Business not found or access denied'
                }, status=404)

            print(f"request.FILES keys: {list(request.FILES.keys())}")
            if request.FILES.getlist('files'):
                files = request.FILES.getlist('files')
                print(f"[INFO] Received {len(files)} files for upload")
                results = []
                errors = []

                for file in files:
                    print(f"[INFO] Processing file: {file.name}")
                    try:
                        result = store_file_content(business_id, file, file.name)
                        print(f"[DEBUG] Result for {file.name}: {result}")
                        results.append(result)
                    except Exception as e:
                        print(f"[ERROR] Error processing file {file.name}: {str(e)}")
                        errors.append({'file': file.name, 'error': str(e)})
                        continue

                if errors:
                    response_data = {
                        'status': 'error',
                        'message': 'Errors occurred while processing files',
                        'files': results,
                        'errors': errors
                    }
                else:
                    response_data = {
                        'status': 'success',
                        'message': f'Processed {len(results)} files successfully',
                        'files': results
                    }

                print(f"[INFO] Upload response data: {response_data}")
                return JsonResponse(response_data)
            else:
                print("[ERROR] No files uploaded in request")
                return JsonResponse({'status': 'error', 'message': 'No files uploaded'}, status=400)

        except Business.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Business not found or access denied'}, status=404)
        except Exception as e:
            print(f"[ERROR] Unexpected error in add_knowledge: {str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    else:
        print(f"[ERROR] Method not allowed: {request.method}")
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)


@login_required
@require_http_methods(["POST"])
def create_task(request, business_id):
    """
    Create or update a scheduled task (e.g., posting content, sending reviews, etc.) for a business.
    Frequency can be DAILY, WEEKLY, MONTHLY, or CUSTOM (requires custom_time).
    """
    try:
        data = json.loads(request.body)
        task_type = data.get('task_type')
        frequency = data.get('frequency')
        custom_time = data.get('custom_time')
        content = data.get('content', '')

        if not task_type or not frequency:
            return JsonResponse({
                'status': 'error',
                'message': 'Task type and frequency are required'
            }, status=400)

        business = Business.objects.get(business_id=business_id, user=request.user)

        # Calculate next_run based on frequency
        next_run = timezone.now()
        if frequency == 'CUSTOM' and custom_time:
            next_run = datetime.strptime(custom_time, '%Y-%m-%dT%H:%M')
        elif frequency == 'DAILY':
            next_run += timedelta(days=1)
        elif frequency == 'WEEKLY':
            next_run += timedelta(weeks=1)
        elif frequency == 'MONTHLY':
            next_run += timedelta(days=30)
        else:
            # If custom time is not provided for CUSTOM frequency
            if frequency == 'CUSTOM':
                return JsonResponse({
                    'status': 'error',
                    'message': 'Custom time is required for custom frequency'
                }, status=400)

        # Create the task
        task = Task.objects.create(
            business=business,
            task_type=task_type,
            frequency=frequency,
            next_run=next_run,
            content=content,
            status='PENDING'
        )

        return JsonResponse({
            'status': 'success',
            'message': 'Task created successfully',
            'task_id': task.id
        })

        return JsonResponse({
            'status': 'success',
            'message': 'Task created successfully',
            'task_id': task.id
        })

    except Business.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Business not found'
        }, status=404)
    except Task.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Task not found'
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


def root_view(request):
    """
    Root view that handles the base URL '/'.
    Redirects to the dashboard if authenticated, else redirects to login.
    If the user doesn't have a Google provider, redirects to Google login.
    """
    if request.user.is_authenticated:
        if not request.user.socialaccount_set.filter(provider='google').exists():
            return redirect('/accounts/google/login/')
        return redirect(reverse('index'))
    return redirect(reverse('login'))


@login_required
def get_verification_status(request, business_id):
    """
    API endpoint to check whether a business is verified and what elements of the business profile are complete.
    If business is a dummy placeholder, returns predefined status. Otherwise,
    queries the Google API for real-time verification/fields status.
    """
    try:
        business = Business.objects.get(business_id=business_id, user=request.user)

        status = {
            'business_name': False,
            'address': False,
            'phone': False,
            'category': False,
            'website': False,
            'hours': False,
            'photos': False
        }

        # If no Google provider, check for dummy business
        if not business.user.socialaccount_set.filter(provider='google').exists():
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

        # For real businesses, fetch data from Google
        access_token = request.user.google_access_token
        account_data = get_business_accounts(access_token)
        business_data = next(
            (acc for acc in account_data.get('accounts', []) if acc['name'] == business_id),
            None
        )

        if not business_data:
            return JsonResponse({'error': 'Business not found'}, status=404)

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
