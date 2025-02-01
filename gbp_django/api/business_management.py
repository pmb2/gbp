import time
import random

def get_business_accounts(access_token):
    print("\n🔄 Starting Google Business Profile accounts fetch...")
    url = "https://mybusinessaccountmanagement.googleapis.com/v1/accounts"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    max_retries = 5  # Increase the number of retries
    backoff_factor = 2  # Exponential backoff factor
    initial_wait = 1  # Start with 1 second wait

    print(f"🌐 API Request details:")
    print(f"  • URL: {url}")
    print(f"  • Headers: ['Authorization', 'Content-Type']")
    print(f"  • Max retries: {max_retries}")
    print(f"  • Access token (first 10 chars): {access_token[:10]}...")

    for attempt in range(max_retries):
        try:
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
            if response.status_code == 429:
                if attempt < max_retries - 1:
                    wait_time = initial_wait * (backoff_factor ** attempt) + random.uniform(0, 1)
                    print(f"[INFO] Rate limit exceeded. Retrying in {wait_time:.2f} seconds...")
                    time.sleep(wait_time)
                else:
                    print("[ERROR] Maximum retry attempts reached due to rate limiting.")
                    print("Please try again later.")
                    return {"accounts": []}
            else:
                print(f"[ERROR] Failed to fetch business accounts: {e}")
                return {"accounts": []}
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait_time = initial_wait * (backoff_factor ** attempt) + random.uniform(0, 1)
                print(f"[INFO] Request failed. Retrying in {wait_time:.2f} seconds...")
                time.sleep(wait_time)
            else:
                print("[ERROR] Maximum retry attempts reached due to request failure.")
                print(f"Error details: {str(e)}")
                return {"accounts": []}

from django.db import transaction
from django.contrib.auth import get_user_model
from ..models import Business
import traceback

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

    # Retrieve the User instance
    User = get_user_model()
    user = User.objects.get(pk=user_id)

    for account in accounts:
        try:
            print(f"\n🔍 [OAUTH FLOW] Processing Google Business account: {account.get('name')}")
            print(f"[DEBUG] Account data: {json.dumps(account, indent=2)}")
            print(f"   - Account Type: {account.get('type', 'unknown')}")
            print(f"   - Account Role: {account.get('role', 'unknown')}")
                
            # Process each location within the account
            locations = account.get('locations', [])
            if locations:
                for location in locations:
                    print(f"🗺️ Processing location: {location.get('name')}")
                    # Map API data to Business model fields
                    business_defaults = {
                        'user': user,
                        'google_account_id': account['name'],
                        'google_location_id': location['name'],
                        'business_name': location.get('title', 'Unnamed Business'),
                        'address': location.get('address', {}).get('formattedAddress', ''),
                        'phone_number': location.get('primaryPhone', ''),
                        'website_url': location.get('websiteUrl', ''),
                        'category': location.get('primaryCategory', {}).get('displayName', ''),
                        'description': location.get('profile', {}).get('description', ''),
                        'is_verified': location.get('metadata', {}).get('verified', False),
                        'profile_photo_url': location.get('profile', {}).get('profilePhotoUrl', ''),
                        'is_connected': True,
                    }
                    
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
                    print(f"✅ {action} business: {business_obj.business_name} (ID: {business_obj.id})")
                    stored_businesses.append(business_obj)
            else:
                print("⚠️ No locations found for this account")
        except Exception as e:
            print(f"[ERROR] Error processing account {account.get('name')}: {str(e)}")
            traceback.print_exc()
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
