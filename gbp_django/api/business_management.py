import time
import random
import requests
import json
from datetime import datetime, timedelta


# ======================
# ACCOUNT & LOCATION FETCHING
# ======================

def get_account_details(access_token):
    """
    Fetch the full account details using the My Business Account Management API.
    This endpoint is current and works with the 'mybusiness.account' scope.
    """
    print("\n[INFO] Fetching account details using the Account Management API")
    url = "https://mybusinessaccountmanagement.googleapis.com/v1/accounts"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    print(f"[INFO] GET {url}")
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        print("[DEBUG] Account details response:")
        print(json.dumps(data, indent=2))
        return data
    except Exception as e:
        print(f"[ERROR] Failed to fetch account details: {e}")
        return {}


def get_business_account_id(access_token):
    """
    Obtain the first business account ID from the account details.
    """
    data = get_account_details(access_token)
    accounts = data.get("accounts", [])
    if not accounts:
        print("[ERROR] No business accounts found.")
        return None
    account_id = accounts[0].get("name")
    print(f"[INFO] Using business account ID: {account_id}")
    return account_id


def get_user_locations(access_token):
    """
    Fetch the list of locations associated with the business account
    using the Business Information API.
    """
    print("\n[INFO] Fetching locations for the business account.")
    account_id = get_business_account_id(access_token)
    if not account_id:
        print("[ERROR] No valid account ID; cannot fetch locations.")
        return {"locations": []}
    url = f"https://mybusinessbusinessinformation.googleapis.com/v1/{account_id}/locations"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    print(f"[INFO] GET {url}")
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        print("[DEBUG] Locations response:")
        print(json.dumps(data, indent=2))
        if not data.get('locations'):
            print("[WARNING] No locations found in the API response.")
        else:
            print(f"[INFO] Found {len(data.get('locations', []))} location(s).")
            for idx, location in enumerate(data['locations'], 1):
                print(f"\n[INFO] Location {idx}:")
                print(f"  • Title: {location.get('title', 'Unknown')}")
                print(f"  • ID: {location.get('name', 'Unknown')}")
                print(f"  • Address: {location.get('address', {}).get('formattedAddress', 'Unknown')}")
        return data
    except requests.exceptions.HTTPError as e:
        response_content = response.text if response else 'No response content'
        print(f"[ERROR] HTTPError during locations fetch: {e}")
        print(f"[ERROR] Response content: {response_content}")
        return {"locations": []}
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Request exception during locations fetch: {e}")
        return {"locations": []}


def get_location_details(access_token, location_id):
    """
    Fetch detailed information for a single location using the Business Information API.
    """
    print(f"\n[INFO] Fetching detailed information for location: {location_id}")
    url = f"https://mybusinessbusinessinformation.googleapis.com/v1/{location_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    print(f"[INFO] GET {url}")
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        print("[DEBUG] Detailed location response:")
        print(json.dumps(data, indent=2))
        return data
    except Exception as e:
        print(f"[ERROR] Failed to fetch detailed info for location {location_id}: {e}")
        return {}


def get_all_business_details(access_token):
    """
    Collect all available business details:
      - Full account details,
      - A list of locations (basic details),
      - Detailed info for each location.
    Returns a dictionary with keys: 'account_details', 'locations', and 'detailed_locations'.
    """
    print("\n[INFO] Collecting all business details.")
    account_details = get_account_details(access_token)
    locations_data = get_user_locations(access_token)
    detailed_locations = []
    for location in locations_data.get("locations", []):
        loc_id = location.get("name")
        if loc_id:
            details = get_location_details(access_token, loc_id)
            detailed_locations.append(details)
        else:
            print("[WARNING] Encountered a location without a 'name' field.")
    all_details = {
        "account_details": account_details,
        "locations": locations_data.get("locations", []),
        "detailed_locations": detailed_locations
    }
    print("\n[INFO] Completed collection of business details.")
    return all_details


# ======================
# UPDATING BUSINESS DETAILS
# ======================

def update_business_details(access_token, location_id, update_data):
    """
    Update business details for a given location using the Business Information API.
    (The account_id is not needed in the URL when using the location resource directly.)
    """
    print("\n[INFO] Updating business details for location:", location_id)
    url = f"https://mybusinessbusinessinformation.googleapis.com/v1/{location_id}?updateMask={','.join(update_data.keys())}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    print(f"[INFO] PATCH {url}")
    print(f"[INFO] Update payload: {json.dumps(update_data, indent=2)}")
    try:
        response = requests.patch(url, headers=headers, json=update_data)
        response.raise_for_status()
        result = response.json()
        print("[INFO] Business details updated successfully.")
        print("[DEBUG] Update response:")
        print(json.dumps(result, indent=2))
        return result
    except requests.exceptions.HTTPError as e:
        print(f"[ERROR] HTTP error during update: {e}")
        print(f"[ERROR] Response content: {response.text}")
        raise
    except Exception as e:
        print(f"[ERROR] Unexpected error during update: {e}")
        raise


# ======================
# STORING DATA & CALCULATIONS (AS BEFORE)
# ======================

from django.db import transaction
from django.contrib.auth import get_user_model
from ..models import Business
import traceback


@transaction.atomic
def store_business_data(locations_data, user_id, access_token):
    """
    Map each location from the API response to your Business model.
    """
    print("\n[INFO] Storing business data into the database.")
    print(f"[INFO] Target user_id: {user_id}")
    print(f"[INFO] Access token (prefix): {access_token[:8]}...")

    stored_businesses = []
    locations = locations_data.get('locations', [])
    print(f"[INFO] Received {len(locations)} location(s) for processing.")

    if not locations:
        print("[INFO] No location data available; exiting storage process.")
        return stored_businesses

    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
        print(f"[INFO] Retrieved user: {user} (ID: {user_id})")
    except Exception as e:
        print(f"[ERROR] Failed to retrieve user with ID {user_id}: {e}")
        return stored_businesses

    for location in locations:
        try:
            location_id = location.get('name')
            print(f"\n[INFO] Processing location with ID: {location_id}")
            business_defaults = {
                'user': user,
                'google_location_id': location_id,
                'business_name': location.get('title', 'Unnamed Business'),
                'address': location.get('address', {}).get('formattedAddress', ''),
                'phone_number': location.get('regularPhone', ''),
                'website_url': location.get('websiteUrl', ''),
                'category': location.get('primaryCategory', {}).get('displayName', ''),
                'description': location.get('profile', {}).get('description', ''),
                'verification_status': location.get('verification_state',
                                                    location.get('metadata', {}).get('verificationState',
                                                                                     'UNVERIFIED')),
                'verification_method': location.get('verification_method', 'NONE'),
                'is_verified': location.get('metadata', {}).get('verificationState', '') == 'VERIFIED',
                'profile_photo_url': location.get('profile', {}).get('profilePhotoUrl', ''),
                'is_connected': True,
            }
            print("[INFO] Mapped business details:")
            for key, value in business_defaults.items():
                print(f"  - {key}: {value}")

            business_id = location_id  # Using the location's unique name as business_id.
            business_obj, created = Business.objects.update_or_create(
                business_id=business_id,
                defaults=business_defaults
            )
            action = 'Created' if created else 'Updated'
            print(f"[INFO] {action} business: {business_obj.business_name} (DB ID: {business_obj.id})")
            stored_businesses.append(business_obj)
        except Exception as e:
            print(f"[ERROR] Error processing location {location.get('name')}: {e}")
            traceback.print_exc()
            continue

    print(f"[INFO] Completed storage; total businesses stored/updated: {len(stored_businesses)}")
    return stored_businesses


def get_locations_with_verification(access_token, account_id):
    """
    Retrieve detailed location information (including verification details)
    using the Business Information API.
    """
    print("\n[INFO] Fetching detailed location information with verification details.")
    # Ensure account_id is properly prefixed
    if not account_id.startswith("accounts/"):
        account_id = f"accounts/{account_id}"
        print(f"[INFO] Adjusted account ID: {account_id}")
    url = f"https://mybusinessbusinessinformation.googleapis.com/v1/{account_id}/locations"
    print(f"[INFO] GET {url}")
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        locations_data = response.json()
        print("[DEBUG] Detailed locations response:")
        print(json.dumps(locations_data, indent=2))

        if 'locations' in locations_data:
            print(f"[INFO] Retrieved {len(locations_data['locations'])} location(s). Fetching verification details...")
            for location in locations_data['locations']:
                verification_url = f"https://mybusinessverifications.googleapis.com/v1/{location['name']}/verification"
                print(f"[INFO] GET verification details for location: {location['name']}")
                verification_response = requests.get(verification_url, headers=headers)
                if verification_response.ok:
                    verification_data = verification_response.json()
                    location['verification_state'] = verification_data.get('state', 'UNVERIFIED')
                    location['verification_method'] = verification_data.get('method', 'NONE')
                    print(
                        f"[INFO] Verification for {location['name']}: State={location['verification_state']}, Method={location['verification_method']}")
                else:
                    print(f"[WARNING] Could not retrieve verification details for {location['name']}")
        print("[INFO] Completed detailed location retrieval.")
        return locations_data
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Exception during detailed location retrieval: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_details = e.response.json()
                print(f"[ERROR] API error details: {json.dumps(error_details, indent=2)}")
            except Exception:
                print("[ERROR] Could not decode error details from response.")
        return {"locations": []}


# ======================
# COMPLIANCE & UPDATE CALCULATIONS
# ======================

def calculate_compliance_score(location_data):
    """
    Calculate a compliance score (0–100) based on the completeness of the location’s profile.
    """
    print("\n[INFO] Calculating compliance score for location data.")
    score = 0
    total_checks = 7

    if location_data.get('locationName'):
        score += 1
        print("[INFO] locationName present: +1")
    else:
        print("[INFO] locationName missing: +0")
    if location_data.get('primaryPhone'):
        score += 1
        print("[INFO] primaryPhone present: +1")
    else:
        print("[INFO] primaryPhone missing: +0")
    if location_data.get('websiteUrl'):
        score += 1
        print("[INFO] websiteUrl present: +1")
    else:
        print("[INFO] websiteUrl missing: +0")
    if location_data.get('regularHours'):
        score += 1
        print("[INFO] regularHours present: +1")
    else:
        print("[INFO] regularHours missing: +0")

    address = location_data.get('address', {})
    if address and all(address.get(f) for f in ['addressLines', 'locality', 'regionCode']):
        score += 1
        print("[INFO] Complete address details found: +1")
    else:
        print("[INFO] Incomplete address details: +0")

    if location_data.get('primaryCategory'):
        score += 1
        print("[INFO] primaryCategory present: +1")
    else:
        print("[INFO] primaryCategory missing: +0")

    profile = location_data.get('profile', {})
    if profile and profile.get('description') and profile.get('primaryPhoto'):
        score += 1
        print("[INFO] Complete profile details found: +1")
    else:
        print("[INFO] Incomplete profile details: +0")

    compliance_score = int((score / total_checks) * 100)
    print(f"[INFO] Final compliance score: {compliance_score}%")
    return compliance_score


def calculate_next_update(location_data):
    """
    Determine the next update schedule based on the location's last post date.
    """
    print("\n[INFO] Calculating next update schedule for the location.")
    last_post = location_data.get('profile', {}).get('lastPostDate')
    if last_post:
        try:
            last_post_date = datetime.fromisoformat(last_post.replace('Z', '+00:00'))
            next_update = last_post_date + timedelta(days=7)
            print(f"[INFO] Last post date: {last_post}. Next update scheduled for: {next_update.isoformat()}")
            return next_update
        except Exception as e:
            print(f"[ERROR] Error parsing last post date: {e}")
    next_update = datetime.now() + timedelta(days=1)
    print(f"[INFO] No valid last post date found. Defaulting next update to: {next_update.isoformat()}")
    return next_update
