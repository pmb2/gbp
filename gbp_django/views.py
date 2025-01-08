from datetime import timedelta
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import (
    login as auth_login, authenticate, logout
)
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
import requests
import secrets

from allauth.socialaccount import providers
from allauth.socialaccount.models import SocialApp
from allauth.utils import build_absolute_uri

from .api.authentication import get_access_token, get_user_info
from .api.business_management import (
    get_business_accounts, store_business_data, update_business_details
)
from .models import (
    Business, User, Notification, Post, BusinessAttribute, QandA, Review, FAQ
)
from .utils.email_service import EmailService
from .utils.file_processor import store_file_content, process_folder
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
from django.contrib.auth.hashers import check_password, make_password
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
                    print(
                        f"[DEBUG] Auth attempt with {backend.__class__.__name__}: {'Success' if auth_attempt else 'Failed'}")
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
            return redirect('index')
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

    # Store the action type (login or add_business)
    request.session['oauth_action'] = 'add_business' if request.user.is_authenticated else 'login'

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
    try:
        print("\n[DEBUG] Starting Google OAuth callback...")

        code = request.GET.get('code')
        state = request.GET.get('state')
        stored_state = request.session.get('oauth_state')

        # Validate the OAuth state and authorization code
        if not code or not state or state != stored_state:
            print("[ERROR] OAuth validation failed")
            messages.error(request, 'Invalid OAuth state or missing code.')
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
            messages.error(request, 'Failed to get access token.')
            return redirect('login')

        # Fetch user info from Google
        user_info = get_user_info(access_token)
        google_email = user_info.get('email')
        google_id = user_info.get('sub')

        print(f"[DEBUG] Fetched Google user info: {google_email}")

        # Find or create the user
        user, created = User.objects.get_or_create(email=google_email)
        if created:
            print(f"[DEBUG] Created new user: {google_email}")
        else:
            print(f"[DEBUG] Found existing user: {google_email}")

        # Update user details and credentials
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
        print("[INFO] Fetching business accounts...")
        business_data = get_business_accounts(access_token)
        stored_businesses = store_business_data(business_data, user.id, access_token)

        if stored_businesses:
            print(f"[INFO] Stored {len(stored_businesses)} business(es).")
            messages.success(request, f"Successfully linked {len(stored_businesses)} business(es).")
        else:
            print("[WARNING] No businesses found; creating placeholder.")
            messages.warning(request, "No businesses were found. A placeholder has been created.")

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

    except Exception as e:
        print(f"[ERROR] OAuth callback error: {e}")
        messages.error(request, "An error occurred during authentication. Please try again.")
        return redirect('login')


from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from .utils.email_service import EmailService
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
            file_content = file.read()
            if file_content is None:
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
                email_verification_token=secrets.token_urlsafe(32),
                embedding=None  # Initialize embedding as null
            )

            # Generate embedding for business profile
            from .utils.embeddings import update_business_embedding
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

    stats['average_completion'] = round(
        stats['total_completion'] / stats['total_businesses'] if stats['total_businesses'] > 0 else 0)

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

        # Forward feedback using email service
        EmailService.forward_feedback(user_email, feedback_type, message)
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
    """Handle chat messages and file uploads using RAG"""
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


from .utils.file_processor import store_file_content, process_folder

@login_required
@require_http_methods(["GET", "DELETE"])
def preview_file(request, business_id, file_id):
    """Preview or delete file content"""
    try:
        faq = FAQ.objects.get(
            id=file_id,
            business__business_id=business_id,
            business__user=request.user,
            deleted_at__isnull=True
        )
        
        if request.method == "GET":
            return JsonResponse({
                'name': faq.file_path.split('/')[-1] if faq.file_path else 'Unknown',
                'content': faq.answer
            })
        else:  # DELETE
            faq.deleted_at = timezone.now()
            faq.save()
            return JsonResponse({'status': 'success'})
            
    except FAQ.DoesNotExist:
        return JsonResponse({
            'error': 'File not found'
        }, status=404)

def add_knowledge(request, business_id):
    """Add new knowledge to the business knowledge base with enhanced error handling"""
    if request.method == 'POST':
        try:
            # Validate business ownership and status
            try:
                business = Business.objects.get(business_id=business_id, user=request.user)
            except Business.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Business not found or access denied'
                }, status=404)

            if not business.is_verified:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Business must be verified to upload files'
                }, status=403)

            # Validate file upload
            if 'files[]' not in request.FILES:
                return JsonResponse({
                    'status': 'error',
                    'message': 'No files were uploaded'
                }, status=400)

            files = request.FILES.getlist('files[]')
            if not files:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Empty file list'
                }, status=400)

            # Process files with detailed error tracking
            results = []
            errors = []
            
            for file in files:
                try:
                    # Validate filename
                    if not file.name:
                        raise ValueError("Invalid filename")

                    # Handle folder upload
                    if hasattr(file, 'content_type') and file.content_type == 'application/x-directory':
                        try:
                            folder_results = process_folder(business_id, file.temporary_file_path())
                            results.extend(folder_results)
                        except Exception as e:
                            errors.append({
                                'file': file.name,
                                'error': f"Folder processing failed: {str(e)}"
                            })
                            continue
                    else:
                        # Handle single file
                        try:
                            result = store_file_content(business_id, file, file.name)
                            results.append(result)
                        except ValueError as e:
                            errors.append({
                                'file': file.name,
                                'error': str(e)
                            })
                        except Exception as e:
                            errors.append({
                                'file': file.name,
                                'error': f"Unexpected error: {str(e)}"
                            })
                            continue

                except Exception as e:
                    errors.append({
                        'file': getattr(file, 'name', 'unknown'),
                        'error': f"File processing failed: {str(e)}"
                    })
                    continue

            # Return response with both results and errors
            response_data = {
                'status': 'success' if results else 'error',
                'message': f'Processed {len(results)} files' + (f' with {len(errors)} errors' if errors else ''),
                'files': results
            }
            
            if errors:
                response_data['errors'] = errors

            return JsonResponse(response_data)

        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'Server error: {str(e)}'
            }, status=500)

    return JsonResponse({
        'status': 'error',
        'message': 'Method not allowed'
    }, status=405)
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
