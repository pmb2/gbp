import time
import random
import requests
import json
from datetime import datetime, timedelta

# Log the module load and path to ensure the updated module is in use.
print(f"[INFO] business_management module loaded from: {__file__}")
print("[INFO] Using updated endpoints: Account details -> https://mybusinessaccountmanagement.googleapis.com/v1/accounts, Locations -> https://mybusinessbusinessinformation.googleapis.com/v1/{account_id}/locations")


# ======================
# ACCOUNT & LOCATION FETCHING
# ======================

def get_account_details(access_token):
    """
    Fetch the full account details using the My Business Account Management API.
    This endpoint is current and works with the 'mybusiness.account' scope.
    """
    print("\n[INFO] get_account_details: Using My Business Account Management API endpoint.")
    url = "https://mybusinessaccountmanagement.googleapis.com/v1/accounts"
    print(f"[DEBUG] get_account_details: GET URL: {url}")
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        print(f"[DEBUG] get_account_details: Response status code: {response.status_code}")
        print(f"[DEBUG] get_account_details: Response headers: {response.headers}")
        data = response.json()
        print("[DEBUG] get_account_details: Response data:")
        print(json.dumps(data, indent=2))
        return data
    except Exception as e:
        print(f"[ERROR] get_account_details: Exception while fetching account details: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"[ERROR] Response content: {e.response.text}")
        return {}


def get_business_account_id(access_token):
    """
    Obtain the first business account ID from the account details.
    """
    print("\n[INFO] get_business_account_id: Calling get_account_details()")
    data = get_account_details(access_token)
    accounts = data.get("accounts", [])
    if not accounts:
        print("[ERROR] get_business_account_id: No accounts found in account details.")
        return None
    account_id = accounts[0].get("name")
    print(f"[INFO] get_business_account_id: Retrieved account ID: {account_id}")
    return account_id


def get_user_locations(access_token):
    """
    Fetch the list of locations associated with the business account
    using the Business Information API.
    """
    print("\n[INFO] get_user_locations: Fetching locations using the Business Information API.")
    account_id = get_business_account_id(access_token)
    if not account_id:
        print("[ERROR] get_user_locations: No valid account ID; cannot fetch locations.")
        return {"locations": []}
    url = f"https://mybusinessbusinessinformation.googleapis.com/v1/{account_id}/locations"
    print(f"[DEBUG] get_user_locations: GET URL: {url}")
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        print(f"[DEBUG] get_user_locations: Response status code: {response.status_code}")
        data = response.json()
        print("[DEBUG] get_user_locations: Response data:")
        print(json.dumps(data, indent=2))
        if not data.get('locations'):
            print("[WARNING] get_user_locations: No locations found in the response.")
        else:
            print(f"[INFO] get_user_locations: Found {len(data.get('locations', []))} location(s).")
            for idx, location in enumerate(data.get('locations', []), 1):
                print(f"\n[INFO] Location {idx}:")
                print(f"  • Title: {location.get('title', 'Unknown')}")
                print(f"  • ID: {location.get('name', 'Unknown')}")
                addr = location.get('address', {}).get('formattedAddress', 'Unknown')
                print(f"  • Address: {addr}")
        return data
    except requests.exceptions.HTTPError as e:
        response_content = response.text if response else 'No response content'
        print(f"[ERROR] get_user_locations: HTTPError: {e}")
        print(f"[ERROR] get_user_locations: Response content: {response_content}")
        return {"locations": []}
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] get_user_locations: Request exception: {e}")
        return {"locations": []}


def get_location_details(access_token, location_id):
    """
    Fetch detailed information for a single location using the Business Information API.
    """
    print(f"\n[INFO] get_location_details: Fetching details for location: {location_id}")
    url = f"https://mybusinessbusinessinformation.googleapis.com/v1/{location_id}"
    print(f"[DEBUG] get_location_details: GET URL: {url}")
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        print(f"[DEBUG] get_location_details: Response status code: {response.status_code}")
        data = response.json()
        print("[DEBUG] get_location_details: Response data:")
        print(json.dumps(data, indent=2))
        return data
    except Exception as e:
        print(f"[ERROR] get_location_details: Exception: {e}")
        return {}


def get_all_business_details(access_token):
    """
    Collect all available business details:
      - Full account details,
      - A list of locations (basic details),
      - Detailed info for each location.
    Returns a dictionary with keys: 'account_details', 'locations', 'detailed_locations'.
    """
    print("\n[INFO] get_all_business_details: Starting collection of all business details.")
    account_details = get_account_details(access_token)
    locations_data = get_user_locations(access_token)
    detailed_locations = []
    for location in locations_data.get("locations", []):
        loc_id = location.get("name")
        if loc_id:
            print(f"[INFO] get_all_business_details: Fetching details for location {loc_id}")
            details = get_location_details(access_token, loc_id)
            detailed_locations.append(details)
        else:
            print("[WARNING] get_all_business_details: Encountered location without a 'name' field.")
    all_details = {
        "account_details": account_details,
        "locations": locations_data.get("locations", []),
        "detailed_locations": detailed_locations
    }
    print("[INFO] get_all_business_details: Completed collection of business details.")
    return all_details


# ======================
# UPDATING BUSINESS DETAILS
# ======================

def update_business_details(access_token, location_id, update_data):
    """
    Update business details for a given location using the Business Information API.
    """
    print(f"\n[INFO] update_business_details: Updating details for location: {location_id}")
    url = f"https://mybusinessbusinessinformation.googleapis.com/v1/{location_id}?updateMask={','.join(update_data.keys())}"
    print(f"[DEBUG] update_business_details: PATCH URL: {url}")
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    print("[DEBUG] update_business_details: Update payload:")
    print(json.dumps(update_data, indent=2))
    try:
        response = requests.patch(url, headers=headers, json=update_data)
        response.raise_for_status()
        result = response.json()
        print("[INFO] update_business_details: Update successful.")
        print("[DEBUG] update_business_details: Response data:")
        print(json.dumps(result, indent=2))
        return result
    except requests.exceptions.HTTPError as e:
        print(f"[ERROR] update_business_details: HTTPError: {e}")
        print(f"[ERROR] update_business_details: Response content: {response.text}")
        raise
    except Exception as e:
        print(f"[ERROR] update_business_details: Exception: {e}")
        raise


# ======================
# DETAILED LOCATION RETRIEVAL WITH VERIFICATION
# ======================

def get_locations_with_verification(access_token, account_id):
    """
    Retrieve detailed location information (including verification details)
    using the Business Information API.
    """
    print("\n[INFO] get_locations_with_verification: Fetching detailed locations with verification details.")
    if not account_id.startswith("accounts/"):
        account_id = f"accounts/{account_id}"
        print(f"[DEBUG] get_locations_with_verification: Adjusted account ID: {account_id}")
    url = f"https://mybusinessbusinessinformation.googleapis.com/v1/{account_id}/locations"
    print(f"[DEBUG] get_locations_with_verification: GET URL: {url}")
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        locations_data = response.json()
        print("[DEBUG] get_locations_with_verification: Locations response:")
        print(json.dumps(locations_data, indent=2))

        if 'locations' in locations_data:
            print(f"[INFO] get_locations_with_verification: Retrieved {len(locations_data['locations'])} location(s).")
            for location in locations_data['locations']:
                verification_url = f"https://mybusinessverifications.googleapis.com/v1/{location['name']}/verification"
                print(f"[DEBUG] get_locations_with_verification: GET Verification URL: {verification_url}")
                ver_response = requests.get(verification_url, headers=headers)
                if ver_response.ok:
                    ver_data = ver_response.json()
                    location['verification_state'] = ver_data.get('state', 'UNVERIFIED')
                    location['verification_method'] = ver_data.get('method', 'NONE')
                    print(
                        f"[INFO] Verification for {location['name']}: {location['verification_state']} via {location['verification_method']}")
                else:
                    print(
                        f"[WARNING] get_locations_with_verification: Could not retrieve verification for {location['name']}")
        else:
            print("[WARNING] get_locations_with_verification: No 'locations' key in response.")
        return locations_data
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] get_locations_with_verification: Request exception: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_details = e.response.json()
                print(
                    f"[ERROR] get_locations_with_verification: API error details: {json.dumps(error_details, indent=2)}")
            except Exception:
                print("[ERROR] get_locations_with_verification: Could not decode error details.")
        return {"locations": []}


# For backward compatibility, alias get_locations to get_locations_with_verification.
get_locations = get_locations_with_verification

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
    print("\n[INFO] store_business_data: Storing business data into the database.")
    print(f"[INFO] store_business_data: Target user_id: {user_id}")
    print(f"[INFO] store_business_data: Access token prefix: {access_token[:8]}...")

    stored_businesses = []
    locations = locations_data.get('locations', [])
    print(f"[INFO] store_business_data: Received {len(locations)} location(s) for processing.")

    if not locations:
        print("[INFO] store_business_data: No location data available; exiting storage process.")
        return stored_businesses

    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
        print(f"[INFO] store_business_data: Retrieved user: {user} (ID: {user_id})")
    except Exception as e:
        print(f"[ERROR] store_business_data: Failed to retrieve user with ID {user_id}: {e}")
        return stored_businesses

    for location in locations:
        try:
            location_id = location.get('name')
            print(f"\n[INFO] store_business_data: Processing location with ID: {location_id}")
            business_defaults = {
                'user': user,
                'google_location_id': location_id,
                'business_name': location.get('locationName', 'Unnamed Business'),
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
            print("[INFO] store_business_data: Mapped business details:")
            for key, value in business_defaults.items():
                print(f"  - {key}: {value}")

            # Use the location 'name' as the unique business identifier.
            business_id = location_id
            business_obj, created = Business.objects.update_or_create(
                business_id=business_id,
                defaults=business_defaults
            )
            action = 'Created' if created else 'Updated'
            print(
                f"[INFO] store_business_data: {action} business: {business_obj.business_name} (DB ID: {business_obj.id})")
            stored_businesses.append(business_obj)
        except Exception as e:
            print(f"[ERROR] store_business_data: Error processing location {location.get('name')}: {e}")
            traceback.print_exc()
            continue

    print(f"[INFO] store_business_data: Completed storage; total businesses stored/updated: {len(stored_businesses)}")
    return stored_businesses


def calculate_compliance_score(location_data):
    """
    Calculate a compliance score (0–100) based on the completeness of the location’s profile.
    """
    print("\n[INFO] calculate_compliance_score: Calculating compliance score for location data.")
    score = 0
    total_checks = 7

    if location_data.get('locationName'):
        score += 1
        print("[INFO] calculate_compliance_score: locationName present: +1")
    else:
        print("[INFO] calculate_compliance_score: locationName missing: +0")
    if location_data.get('primaryPhone'):
        score += 1
        print("[INFO] calculate_compliance_score: primaryPhone present: +1")
    else:
        print("[INFO] calculate_compliance_score: primaryPhone missing: +0")
    if location_data.get('websiteUrl'):
        score += 1
        print("[INFO] calculate_compliance_score: websiteUrl present: +1")
    else:
        print("[INFO] calculate_compliance_score: websiteUrl missing: +0")
    if location_data.get('regularHours'):
        score += 1
        print("[INFO] calculate_compliance_score: regularHours present: +1")
    else:
        print("[INFO] calculate_compliance_score: regularHours missing: +0")

    address = location_data.get('address', {})
    if address and all(address.get(f) for f in ['addressLines', 'locality', 'regionCode']):
        score += 1
        print("[INFO] calculate_compliance_score: Complete address details found: +1")
    else:
        print("[INFO] calculate_compliance_score: Incomplete address details: +0")

    if location_data.get('primaryCategory'):
        score += 1
        print("[INFO] calculate_compliance_score: primaryCategory present: +1")
    else:
        print("[INFO] calculate_compliance_score: primaryCategory missing: +0")

    profile = location_data.get('profile', {})
    if profile and profile.get('description') and profile.get('primaryPhoto'):
        score += 1
        print("[INFO] calculate_compliance_score: Complete profile details found: +1")
    else:
        print("[INFO] calculate_compliance_score: Incomplete profile details: +0")

    compliance_score = int((score / total_checks) * 100)
    print(f"[INFO] calculate_compliance_score: Final compliance score: {compliance_score}%")
    return compliance_score


def calculate_next_update(location_data):
    """
    Determine the next update schedule based on the location's last post date.
    """
    print("\n[INFO] calculate_next_update: Calculating next update schedule for the location.")
    last_post = location_data.get('profile', {}).get('lastPostDate')
    if last_post:
        try:
            last_post_date = datetime.fromisoformat(last_post.replace('Z', '+00:00'))
            next_update = last_post_date + timedelta(days=7)
            print(
                f"[INFO] calculate_next_update: Last post date: {last_post}. Next update scheduled for: {next_update.isoformat()}")
            return next_update
        except Exception as e:
            print(f"[ERROR] calculate_next_update: Error parsing last post date: {e}")
    next_update = datetime.now() + timedelta(days=1)
    print(
        f"[INFO] calculate_next_update: No valid last post date found. Defaulting next update to: {next_update.isoformat()}")
    return next_update
