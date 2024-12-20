import os
import random
import requests
import time
import secrets
from django.conf import settings
from ..models import Business, Notification
from django.contrib.sessions.backends.db import SessionStore
from gbp_django.api.authentication import refresh_access_token
from gbp_django.utils.cache import cache_on_arguments
from gbp_django.models import (
    Business, Post, BusinessAttribute,
    QandA, Review
)

def create_business_location(access_token, account_id, location_data):
    """Create a new business location."""
    url = (f"https://mybusiness.googleapis.com/v4/accounts/"
           f"{account_id}/locations")
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.post(url, headers=headers, json=location_data)
    response.raise_for_status()
    return response.json()


def update_business_details(access_token, account_id, location_id, update_data):
    """Update details for a business location."""
    try:
        # Format the data according to Google's API requirements
        formatted_data = {
            "locationName": update_data.get('business_name', ''),
            "primaryPhone": update_data.get('phone', ''),
            "websiteUrl": update_data.get('website', ''),
            "primaryCategory": {"displayName": update_data.get('category', '')},
            "address": {
                "regionCode": "US",  # Default to US
                "addressLines": [update_data.get('address', '')]
            }
        }

        url = (f"https://mybusinessaccountmanagement.googleapis.com/v1/"
               f"{account_id}/locations/{location_id}")
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # Use PATCH with updateMask to specify which fields to update
        params = {
            "updateMask": "locationName,primaryPhone,websiteUrl,primaryCategory,address"
        }
        
        response = requests.patch(url, headers=headers, json=formatted_data, params=params)
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.RequestException as e:
        print(f"API Error: {str(e)}")
        if hasattr(e.response, 'json'):
            error_details = e.response.json()
            print(f"Error details: {error_details}")
        raise


def delete_location(access_token, account_id, location_id):
    """Delete a business location."""
    url = (f"https://mybusiness.googleapis.com/v4/accounts/"
           f"{account_id}/locations/{location_id}")
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.delete(url, headers=headers)
    response.raise_for_status()
    return response.status_code == 204



@cache_on_arguments(timeout=300)
def get_business_accounts(access_token):
    print("\n[DEBUG] Starting business accounts fetch...")
    url = "https://mybusinessaccountmanagement.googleapis.com/v1/accounts"
    headers = {"Authorization": f"Bearer {access_token}"}
    retries = 2  # Reduced retries
    print(f"[DEBUG] Request URL: {url}")
    print(f"[DEBUG] Authorization header present: {'Authorization' in headers}")

    for attempt in range(retries):
        try:
            # Minimal delay between attempts
            if attempt > 0:
                time.sleep(0.5)  # Fixed 0.5s delay between retries
                print(f"[DEBUG] API retry attempt {attempt + 1}")
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            if not data or not data.get('accounts'):
                print("[WARNING] No business accounts found")
                # Return empty accounts list but don't fail
                return {"accounts": []}
            return data
        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                # Token expired, refresh token
                print("[INFO] Access token expired, attempting to refresh.")
                session = SessionStore()
                new_token = refresh_access_token(
                    session.get('refresh_token'),
                    settings.GOOGLE_OAUTH2_CLIENT_ID,
                    settings.GOOGLE_OAUTH2_CLIENT_SECRET
                )
                session['google_token'] = new_token['access_token']
                session.save()
                headers["Authorization"] = f"Bearer {new_token['access_token']}"
            elif response.status_code == 429:
                # Too many requests, apply exponential backoff
                if attempt < retries - 1:
                    wait_time = 0.5 * (attempt + 1)  # Linear backoff: 0.5s, 1s, 1.5s
                    print(f"[INFO] Rate limit exceeded. Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                elif response.status_code == 401:
                    # Token expired, refresh token
                    print("[INFO] Access token expired, attempting to refresh.")
                    from django.contrib.sessions.backends.db import SessionStore
                    session = SessionStore()
                    if session.get('refresh_token'):
                        new_token = refresh_access_token(
                            session.get('refresh_token'),
                            settings.GOOGLE_OAUTH2_CLIENT_ID,
                            settings.GOOGLE_OAUTH2_CLIENT_SECRET
                        )
                        session['google_token'] = new_token['access_token']
                        session.save()
                        headers["Authorization"] = f"Bearer {new_token['access_token']}"
                    else:
                        raise Exception("No refresh token available. User needs to re-authenticate.")
                else:
                    print(f"[ERROR] Failed to fetch business accounts: {e}")
                    return {"accounts": []}  # Return an empty structure to continue the flow
        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                wait_time = backoff_factor ** attempt + random.uniform(0, 1)
                print(f"[INFO] Request failed. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print("[ERROR] Maximum retry attempts reached. Please try again later.")
                raise e

from django.db import transaction
from ..models import Business

@transaction.atomic
def store_business_data(business_data, user_id, access_token):
    """Store business data from Google API response"""
    print("\n[DEBUG] Starting business data storage...")
    print(f"[DEBUG] Raw business data received: {business_data}")
    
    stored_businesses = []
    accounts = business_data.get('accounts', []) if business_data else []
    print(f"[DEBUG] Found {len(accounts)} accounts to process")

    # Process each account from Google API
    for account in accounts:
        try:
            # Basic business details from account
            # Generate unique business ID if not exists
            business_id = f"biz_{user_id}_{int(time.time())}"
            
            business_details = {
                'user_id': user_id,
                'business_id': business_id,
                'google_account_id': account['name'],  # Store Google account ID separately
                'business_name': account.get('accountName', 'Unnamed Business'),
                'business_email': account.get('primaryOwner', {}).get('email', ''),
                'is_connected': True  # Mark as connected via OAuth
            }

            # Get locations for this account
            locations = get_locations(access_token, account['name'])
            
            if locations.get('locations'):
                # Use first location's details
                location = locations['locations'][0]
                business_details.update({
                    'google_location_id': location['name'],
                    'address': location.get('address', {}).get('formattedAddress', 'Pending'),
                    'phone_number': location.get('primaryPhone', 'Pending'),
                    'website_url': location.get('websiteUrl', 'Pending'),
                    'category': location.get('primaryCategory', {}).get('displayName', 'Pending'),
                    'is_verified': location.get('locationState', {}).get('isVerified', False),
                    'description': location.get('profile', {}).get('description', '')
                })
            else:
                # No locations found - store with pending values
                business_details.update({
                    'is_verified': False,
                    'address': 'Pending',
                    'phone_number': 'Pending',
                    'website_url': 'Pending',
                    'category': 'Pending'
                })

            # Create or update business record
            # Try to find existing business by Google account ID first
            existing_business = Business.objects.filter(
                google_account_id=business_details['google_account_id']
            ).first()
            
            if existing_business:
                # Update existing business
                for key, value in business_details.items():
                    setattr(existing_business, key, value)
                existing_business.save()
                business = existing_business
                created = False
            else:
                # Create new business
                business = Business.objects.create(**business_details)
                created = True
            
            stored_businesses.append(business)
            print(f"[INFO] {'Created' if created else 'Updated'} business: {business.business_name}")

        except Exception as e:
            print(f"[ERROR] Failed to store business data for account {account.get('name')}: {str(e)}")
            continue

    # If no businesses were stored, create an unverified business entry from OAuth data
    if not stored_businesses:
        print("\n[DEBUG] No businesses found - creating unverified business record")
        business_id = f"biz_{user_id}_{int(time.time())}"
        
        # Get user info from social account
        from allauth.socialaccount.models import SocialAccount
        try:
            social_account = SocialAccount.objects.get(user_id=user_id, provider='google')
            user_info = social_account.extra_data
            business_name = user_info.get('name', '').strip() or 'My Business'
            business_email = user_info.get('email', '').strip() or 'pending@verification.com'
        except SocialAccount.DoesNotExist:
            business_name = 'My Business'
            business_email = 'pending@verification.com'
            
        # Create or get existing unverified business
        business, created = Business.objects.get_or_create(
            user_id=user_id,
            is_verified=False,
            defaults={
                'business_id': business_id,
                'business_name': business_name,
                'business_email': business_email,
                'is_connected': True,  # Connected via OAuth
                'email_verification_pending': True,
                'email_verification_token': secrets.token_urlsafe(32),
                'address': 'Pending verification',
                'phone_number': 'Pending verification',
                'website_url': 'Pending verification',
                'category': 'Pending verification',
                'email_settings': {
                    'enabled': True,
                    'compliance_alerts': True,
                    'content_approval': True,
                    'weekly_summary': True,
                    'verification_reminders': True
                },
                'automation_status': 'Active'
            }
        )
        
        # Create notification
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.get(id=user_id)
            Notification.objects.create(
                user=user,
                message="Please complete your business profile to get started.",
                notification_type="PROFILE_COMPLETION"
            )
        except Exception as e:
            print(f"[WARNING] Failed to create notification: {str(e)}")
        
        stored_businesses = [business]
        return stored_businesses

    # Process each account's business data
    
    if not accounts:
        print("[WARNING] No accounts found in business data")
        # Create unvalidated business entry
        timestamp = int(time.time())
        business_id = f"unvalidated-{user_id}-{timestamp}"
        
        business = Business.objects.create(
            user_id=user_id,
            business_id=business_id,
            business_name="Unvalidated Business",
            business_email="pending@verification.com",
            is_verified=False,
            email_verification_pending=True,
            email_verification_token=secrets.token_urlsafe(32),
            address='Pending verification',
            phone_number='Pending verification',
            website_url='Pending verification',
            category='Pending verification',
            email_settings='{"enabled":true,"compliance_alerts":true,"content_approval":true,"weekly_summary":true,"verification_reminders":true}',
            automation_status='Active'
        )
        
        # Create notification only if user exists
        from django.contrib.auth import get_user_model
        User = get_user_model()
            
        try:
            user = User.objects.get(id=user_id)
            Notification.objects.create(
                user=user,
                message="Please complete your business profile to get started."
            )
        except User.DoesNotExist:
            print(f"[WARNING] User {user_id} not found - skipping notification creation")
        
        stored_businesses = [business]
        return stored_businesses
        
    for account in accounts:
        try:
            # Get locations for this account
            locations = get_locations(access_token, account['name'])
            
            if locations.get('locations'):
                for location in locations['locations']:
                    # Extract business details with enhanced data
                    business_details = {
                        'user_id': user_id,
                        'business_name': account.get('accountName', 'Unnamed Business'),
                        'business_id': account['name'],
                        'business_email': account.get('primaryOwner', {}).get('email', 'pending@verification.com'),
                        'address': location.get('address', {}).get('formattedAddress', 'No info'),
                        'phone_number': location.get('primaryPhone', 'No info'),
                        'website_url': location.get('websiteUrl', 'No info'),
                        'category': location.get('primaryCategory', {}).get('displayName', 'No info'),
                        'is_verified': location.get('locationState', {}).get('isVerified', False),
                        'email_verification_pending': True,
                        'email_verification_token': secrets.token_urlsafe(32),
                        'email_settings': '{"enabled":true,"compliance_alerts":true,"content_approval":true,"weekly_summary":true,"verification_reminders":true}',
                        'automation_status': 'Active',
                        'description': location.get('profile', {}).get('description', '')
                    }

                    # Store additional attributes
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
                
                # Get or create the business record with enhanced details
                business, created = Business.objects.update_or_create(
                    business_id=account['name'],
                    defaults={
                        **business_details,
                        'is_verified': location.get('verification_state') == 'VERIFIED',
                        'is_connected': True,
                        'google_location_id': location.get('name', ''),
                        'compliance_score': calculate_compliance_score(location),
                        'automation_status': 'Active',
                        'last_post_date': location.get('profile', {}).get('lastPostDate'),
                        'next_update_date': calculate_next_update(location)
                    }
                )
                
                stored_businesses.append(business)
                print(f"[INFO] Successfully stored/updated business: {business.business_name}")
                
        except Exception as e:
            print(f"[ERROR] Failed to store business data for account {account.get('name')}: {str(e)}")
            continue
    
    # If no businesses were stored, create an unverified business entry
    if not stored_businesses:
        print("\n[DEBUG] No businesses found - creating unverified business record")
        timestamp = int(time.time())
        business_id = f"unverified-{user_id}-{timestamp}"
        
        # Get user info from social account if available
        from allauth.socialaccount.models import SocialAccount
        try:
            social_account = SocialAccount.objects.get(user_id=user_id, provider='google')
            user_info = social_account.extra_data
            business_name = user_info.get('name', 'My Business')
            business_email = user_info.get('email', 'pending@verification.com')
        except SocialAccount.DoesNotExist:
            business_name = 'My Business'
            business_email = 'pending@verification.com'
            
        unverified_business = Business.objects.create(
            user_id=user_id,
            business_id=business_id,
            business_name=business_name,
            business_email=business_email,
            is_verified=False,
            is_connected=True,  # Connected via OAuth but not verified
            email_verification_pending=True,
            email_verification_token=secrets.token_urlsafe(32),
            address='Pending verification',
            phone_number='Pending verification',
            website_url='Pending verification',
            category='Pending verification',
            email_settings={
                'enabled': True,
                'compliance_alerts': True,
                'content_approval': True,
                'weekly_summary': True,
                'verification_reminders': True
            },
            automation_status='Active'
        )
        
        # Create notification for new business
        Notification.objects.create(
            user_id=user_id,
            message="Please verify your business profile to unlock all features."
        )
        
        stored_businesses = [unverified_business]
        
    return stored_businesses

def get_locations(access_token, account_id):
    """Get detailed location information including verification status"""
    url = f"https://mybusinessbusinessinformation.googleapis.com/v1/{account_id}/locations"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # Get additional verification details for each location
        locations_data = response.json()
        if 'locations' in locations_data:
            for location in locations_data['locations']:
                verification_url = f"https://mybusinessverifications.googleapis.com/v1/{location['name']}/verification"
                verification_response = requests.get(verification_url, headers=headers)
                if verification_response.ok:
                    verification_data = verification_response.json()
                    location['verification_state'] = verification_data.get('state', 'UNVERIFIED')
                    location['verification_method'] = verification_data.get('method', 'NONE')
                
        return locations_data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching location data: {str(e)}")
        if hasattr(e.response, 'json'):
            print(f"API Error details: {e.response.json()}")
        return {"locations": []}
def calculate_compliance_score(location_data):
    """Calculate compliance score based on profile completeness"""
    score = 0
    total_checks = 7
    
    # Check basic info
    if location_data.get('locationName'): score += 1
    if location_data.get('primaryPhone'): score += 1
    if location_data.get('websiteUrl'): score += 1
    if location_data.get('regularHours'): score += 1
    
    # Check address
    address = location_data.get('address', {})
    if address and all(address.get(f) for f in ['addressLines', 'locality', 'regionCode']):
        score += 1
        
    # Check categories
    if location_data.get('primaryCategory'): score += 1
    
    # Check profile completeness
    profile = location_data.get('profile', {})
    if profile and profile.get('description') and profile.get('primaryPhoto'):
        score += 1
        
    return int((score / total_checks) * 100)

def calculate_next_update(location_data):
    """Calculate next update date based on last activity"""
    from datetime import datetime, timedelta
    
    last_post = location_data.get('profile', {}).get('lastPostDate')
    if last_post:
        last_post_date = datetime.fromisoformat(last_post.replace('Z', '+00:00'))
        return last_post_date + timedelta(days=7)
    return datetime.now() + timedelta(days=1)
