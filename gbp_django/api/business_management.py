import os
from datetime import datetime, timedelta
import requests
import time
import secrets
import json
from django.conf import settings
from django.utils import timezone
from django.contrib.sessions.backends.db import SessionStore
from django.core.exceptions import ObjectDoesNotExist
from allauth.socialaccount.models import SocialAccount
from gbp_django.api.authentication import refresh_access_token
from gbp_django.utils.cache import cache_on_arguments
from gbp_django.models import (
    Business, Post, BusinessAttribute,
    QandA, Review, Notification
)
from gbp_django.utils.logging_utils import log_api_request

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
            # Very minimal delay between attempts
            if attempt > 0:
                time.sleep(0.1)  # Reduced to 0.1s delay
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
                    wait_time = 0.1 * (attempt + 1)  # Reduced linear backoff: 0.1s, 0.2s
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
                wait_time = 0.5 * (attempt + 1)  # Linear backoff: 0.5s, 1s
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

    # Get Google account info
    try:
        social_account = SocialAccount.objects.get(user_id=user_id, provider='google')
        google_email = social_account.extra_data.get('email')
        google_account_id = social_account.uid
    except SocialAccount.DoesNotExist:
        google_email = None
        google_account_id = None

    # Process each account from Google API
    for account in accounts:
        try:
            # Get locations for this account
            locations = get_locations(access_token, account['name'])
            location = locations.get('locations', [{}])[0]  # Get first location or empty dict

            # Build business details
            business_details = {
                'user_id': user_id,
                'business_id': account['name'],
                'google_account_id': account['name'],
                'google_email': google_email,
                'business_name': account.get('accountName', 'Unnamed Business'),
                'business_email': account.get('primaryOwner', {}).get('email', ''),
                'is_connected': True,
                'is_verified': location.get('locationState', {}).get('isVerified', False),
                'google_location_id': location.get('name'),
                'address': location.get('address', {}).get('formattedAddress', 'Pending verification'),
                'phone_number': location.get('primaryPhone', 'Pending verification'),
                'website_url': location.get('websiteUrl', 'Pending verification'),
                'category': location.get('primaryCategory', {}).get('displayName', 'Pending verification'),
                'description': location.get('profile', {}).get('description', ''),
                'email_verification_pending': True,
                'email_verification_token': secrets.token_urlsafe(32),
                'email_settings': {
                    'enabled': True,
                    'compliance_alerts': True,
                    'content_approval': True,
                    'weekly_summary': True,
                    'verification_reminders': True
                },
                'automation_status': 'Active',
                'compliance_score': calculate_compliance_score(location),
                'last_post_date': location.get('profile', {}).get('lastPostDate'),
                'next_update_date': calculate_next_update(location)
            }

            # Find or create business
            business, created = Business.objects.update_or_create(
                business_id=account['name'],
                defaults=business_details
            )

            # Store additional attributes
            if location:
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
                    if value is not None:
                        BusinessAttribute.objects.update_or_create(
                            business=business,
                            key=key,
                            defaults={'value': json.dumps(value) if isinstance(value, (dict, list)) else str(value)}
                        )

            stored_businesses.append(business)
            print(f"[INFO] {'Created' if created else 'Updated'} business: {business.business_name}")

        except Exception as e:
            print(f"[ERROR] Failed to store business data for account {account.get('name')}: {str(e)}")
            continue

    # Create unverified business if no businesses found
    if not stored_businesses:
        print("\n[DEBUG] No businesses found - creating unverified business record")
        timestamp = int(time.time())
        business_id = f"unverified-{user_id}-{timestamp}"

        try:
            social_account = SocialAccount.objects.get(user_id=user_id, provider='google')
            user_info = social_account.extra_data
            business_name = user_info.get('name', '').strip() or 'New Business'
            business_email = user_info.get('email', '').strip() or 'pending@verification.com'
        except SocialAccount.DoesNotExist:
            business_name = 'New Business'
            business_email = 'pending@verification.com'

        business = Business.objects.create(
            user_id=user_id,
            business_id=business_id,
            google_email=google_email,
            google_account_id=google_account_id,
            business_name=business_name,
            business_email=business_email,
            is_verified=False,
            is_connected=True,
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

        # Create notification
        Notification.objects.create(
            user_id=user_id,
            message="Please complete your business profile to get started."
        )

        stored_businesses = [business]

    return stored_businesses

def get_locations(access_token, account_id):
    """Get detailed location information including verification status"""
    url = f"https://mybusinessbusinessinformation.googleapis.com/v1/{account_id}/locations"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    try:
        log_api_request(None, account_id, 'get_locations', 'Fetching location data')
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        # Get additional verification details for each location
        locations_data = response.json()
        if 'locations' in locations_data:
            for location in locations_data['locations']:
                try:
                    verification_url = f"https://mybusinessverifications.googleapis.com/v1/{location['name']}/verification"
                    verification_response = requests.get(verification_url, headers=headers)
                    if verification_response.ok:
                        verification_data = verification_response.json()
                        location['verification_state'] = verification_data.get('state', 'UNVERIFIED')
                        location['verification_method'] = verification_data.get('method', 'NONE')
                    else:
                        log_api_request(None, account_id, 'get_locations', 
                                      f"Verification check failed: {verification_response.status_code}", 
                                      status='warning')
                except Exception as ve:
                    log_api_request(None, account_id, 'get_locations',
                                  f"Verification check error: {str(ve)}", 
                                  status='error')
                    location['verification_state'] = 'UNVERIFIED'
                    location['verification_method'] = 'NONE'

        log_api_request(None, account_id, 'get_locations', 
                       f"Successfully fetched {len(locations_data.get('locations', []))} locations")
        return locations_data

    except requests.exceptions.RequestException as e:
        error_details = None
        if hasattr(e.response, 'json'):
            try:
                error_details = e.response.json()
            except:
                error_details = str(e)
                
        log_api_request(None, account_id, 'get_locations',
                       f"Error fetching location data: {error_details}",
                       status='error')
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
