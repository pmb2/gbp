import time
import random
import requests
import json

def get_business_account_id(access_token):
    print("\n[INFO] Fetching Google Business Account ID...")
    url = "https://mybusiness.googleapis.com/v4/accounts"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        print("[DEBUG] Full accounts API response:")
        print(json.dumps(data, indent=2))
        accounts = data.get("accounts", [])
        if not accounts:
            print("[ERROR] No business accounts found.")
            return None
        account_id = accounts[0].get("name")
        print(f"[INFO] Found account id: {account_id}")
        return account_id
    except Exception as e:
        print(f"[ERROR] Failed to fetch business account id: {e}")
        return None


def update_business_details(access_token, account_id, location_id, update_data):
    """
    Update business details on Google Business Profile.

    Parameters:
    - access_token: str, OAuth 2.0 access token.
    - account_id: str, in the format 'accounts/ACCOUNT_ID'.
    - location_id: str, in the format 'accounts/ACCOUNT_ID/locations/LOCATION_ID'.
    - update_data: dict, data to update in the business profile.

    Returns:
    - dict: Response data from the API call.

    Raises:
    - requests.exceptions.HTTPError: If the API call fails.
    """
    print("\n🔄 Starting business details update...")
    url = f"https://mybusinessbusinessinformation.googleapis.com/v1/{location_id}?updateMask={','.join(update_data.keys())}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    print(f"🌐 API Request details:")
    print(f"  • URL: {url}")
    print(f"  • Headers: {headers}")
    print(f"  • Update data: {update_data}")

    try:
        response = requests.patch(url, headers=headers, json=update_data)
        response.raise_for_status()
        print("✅ Business details updated successfully!")
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"[ERROR] Failed to update business details: {e}")
        print(f"Response content: {response.text}")
        raise

def get_user_locations(access_token):
    print("\n🔄 Starting locations fetch for business locations")
    account_id = get_business_account_id(access_token)
    if not account_id:
        print("[ERROR] Unable to fetch account ID. Aborting location fetch.")
        return {"locations": []}
    url = f"https://mybusiness.googleapis.com/v4/{account_id}/locations"
    print(f"\n[INFO] Fetching locations from URL: {url}")
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    max_retries = 3
    backoff_factor = 2
    initial_wait = 1
    total_wait = 0

    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            print("[DEBUG] Full locations API response:")
            print(json.dumps(data, indent=2))
            if not data or not data.get('locations'):
                print("\n⚠️ [WARNING] No locations found in API response")
                print("📝 Raw API response:")
                print(data)
                return {"locations": []}

            print("\n✅ Successfully retrieved locations!")
            print(f"📊 Found {len(data.get('locations', []))} locations:")
            for idx, location in enumerate(data['locations'], 1):
                print(f"\n📍 Location {idx}:")
                print(f"  • Name: {location.get('title', 'Unknown')}")
                print(f"  • ID: {location.get('name', 'Unknown')}")
                print(f"  • Address: {location.get('address', {}).get('formattedAddress', 'Unknown')}")
            return data

        except requests.exceptions.HTTPError as e:
            response_content = response.text if response else 'No response content'
            print(f"[ERROR] HTTPError: {e}, Response Content: {response_content}")
            if response.status_code == 429:
                if attempt < max_retries - 1:
                    wait_time = initial_wait * (backoff_factor ** attempt) + random.uniform(0, 1)
                    total_wait += wait_time
                    if total_wait > 20:
                        print("[ERROR] Total wait time exceeded due to rate limiting.")
                        break
                    print(f"[INFO] Rate limit exceeded. Retrying in {wait_time:.2f} seconds...")
                    time.sleep(wait_time)
                else:
                    print("[ERROR] Maximum retry attempts reached due to rate limiting.")
                    break
            else:
                break
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Request exception: {e}")
            break

    return {"locations": []}

from django.db import transaction
from django.contrib.auth import get_user_model
from ..models import Business
import traceback

@transaction.atomic
def store_business_data(locations_data, user_id, access_token):
    print(f"\n🔄 [OAUTH FLOW] Starting business data storage")
    print(f"👤 [OAUTH FLOW] Storing for user_id: {user_id}")
    print(f"🔑 [OAUTH FLOW] Access token (first 8): {access_token[:8]}...")
    
    stored_businesses = []
    locations = locations_data.get('locations', [])
    print(f"🏢 Found {len(locations)} locations to process")

    if not locations:
        print("[WARNING] No locations found in location data")
        return stored_businesses

    # Retrieve the User instance
    User = get_user_model()
    user = User.objects.get(pk=user_id)

    for location in locations:
        try:
            print(f"\n🗺️ Processing location: {location.get('name')}")
            business_defaults = {
                'user': user,
                'google_location_id': location['name'],
                'business_name': location.get('title', 'Unnamed Business'),
                'address': location.get('address', {}).get('formattedAddress', ''),
                'phone_number': location.get('regularPhone', ''),
                'website_url': location.get('websiteUrl', ''),
                'category': location.get('primaryCategory', {}).get('displayName', ''),
                'description': location.get('profile', {}).get('description', ''),
                'verification_status': location.get('verification_state', location.get('metadata', {}).get('verificationState', 'UNVERIFIED')),
                'verification_method': location.get('verification_method', 'NONE'),
                'is_verified': location.get('metadata', {}).get('verificationState', '') == 'VERIFIED',
                'profile_photo_url': location.get('profile', {}).get('profilePhotoUrl', ''),
                'is_connected': True,
            }
            print(f"[INFO] Mapped business defaults: {business_defaults}")
            
            # Use the location 'name' as 'business_id' to ensure uniqueness
            business_id = location.get('name')
            
            print(f"Business Defaults for {business_id}:")
            for key, value in business_defaults.items():
                print(f"  - {key}: {value}")
            
            business_obj, created = Business.objects.update_or_create(
                business_id=business_id,
                defaults=business_defaults
            )
            action = 'Created' if created else 'Updated'
            print(f"[INFO] {action} business: {business_obj.business_name} (DB id: {business_obj.id})")
            stored_businesses.append(business_obj)
        except Exception as e:
            print(f"[ERROR] Error processing location {location.get('name')}: {str(e)}")
            traceback.print_exc()
            continue

    if not stored_businesses:
        print("[ERROR] No businesses were stored. Possible causes:")
        print(" - Rate limiting prevented data retrieval.")
        print(" - API did not return any accounts or locations.")
        print(" - Data mapping issues in 'store_business_data' function.")

def get_locations(access_token, account_id):
    """Get detailed location information including verification status"""
    if not account_id.startswith("accounts/"):
         account_id = f"accounts/{account_id}"
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
