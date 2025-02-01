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
    Business, Post, QandA, Review
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
    print("\n🔄 Starting Google Business Profile accounts fetch...")
    url = "https://mybusinessaccountmanagement.googleapis.com/v1/accounts"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    retries = 3
    print(f"🌐 API Request details:")
    print(f"  • URL: {url}")
    print(f"  • Headers: {list(headers.keys())}")
    print(f"  • Max retries: {retries}")
    print(f"  • Access token (first 10 chars): {access_token[:10]}...")

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
                print("\n⚠️ [WARNING] No business accounts found in API response")
                print("📝 Raw API response:")
                print(data)
                return {"accounts": []}
            
            print("\n✅ Successfully retrieved business accounts!")
            print(f"📊 Found {len(data.get('accounts', []))} business accounts:")
            for idx, account in enumerate(data['accounts'], 1):
                print(f"\n📍 Account {idx}:")
                print(f"  • Name: {account.get('accountName', 'Unknown')}")
                print(f"  • ID: {account.get('name', 'Unknown')}")
                print(f"  • Type: {account.get('type', 'Unknown')}")
                print(f"  • Role: {account.get('role', 'Unknown')}")
            
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
    print(f"\n🔄 [OAUTH FLOW] Starting business data storage")
    print(f"📦 [OAUTH FLOW] Raw business data keys: {list(business_data.keys())}")
    print(f"👤 [OAUTH FLOW] Storing for user_id: {user_id}")
    print(f"🔑 [OAUTH FLOW] Access token (first 8): {access_token[:8]}...") 
    
    stored_businesses = []
    accounts = business_data.get('accounts', []) if business_data else []
    print(f"🏢 Found {len(accounts)} business accounts to process")

    # Check for empty accounts
    if not accounts:
        print("[WARNING] No accounts found in business data")
        return stored_businesses

    # Get user's Google email from social account
    from allauth.socialaccount.models import SocialAccount
    try:
        social_account = SocialAccount.objects.get(user_id=user_id, provider='google')
        google_email = social_account.extra_data.get('email')
        print(f"👤 Found Google account: {google_email}")
    except SocialAccount.DoesNotExist:
        google_email = None
        print("⚠️ No Google social account found")

    for account in accounts:
        try:
            print(f"\n🔍 [OAUTH FLOW] Processing Google Business account: {account.get('name')}")
            print(f"[DEBUG] Account data: {json.dumps(account, indent=2)}")
            print(f"   - Account Type: {account.get('type', 'unknown')}")
            print(f"   - Account Role: {account.get('role', 'unknown')}")
                
            # Basic business details from account
            # Generate unique business ID if not exists
            business_id = f"biz_{user_id}_{int(time.time())}"
            print(f"🏷️ [OAUTH FLOW] Generated business ID: {business_id}")
                
            business_details = {
                'user_id': user_id,
                'business_id': business_id,
                'google_account_id': account['name'],  # Store Google account ID separately
                'business_name': account.get('accountName', 'Unnamed Business'),
                'business_email': account.get('primaryOwner', {}).get('email', ''),
                'is_connected': True  # Mark as connected via OAuth
            }

            # Get locations from the account data
            locations = account.get('locations', [])
            if locations:
                # Use first location's details
                location = locations[0]
                print(f"[DEBUG] Location data: {json.dumps(location, indent=2)}")
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
        except Exception as e:
            print(f"Error processing account {account.get('name')}: {str(e)}")
            continue

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
