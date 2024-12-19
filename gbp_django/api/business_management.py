import os
import random
import requests
import time
from django.conf import settings
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
    retries = 3
    backoff_factor = 2
    print(f"[DEBUG] Request URL: {url}")
    print(f"[DEBUG] Authorization header present: {'Authorization' in headers}")

    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            if not data:
                print("[WARNING] Empty response from Google API")
                return {"accounts": []}
            if not data.get('accounts'):
                print("[WARNING] No business accounts found")
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
                    wait_time = backoff_factor ** attempt + random.uniform(0, 1)
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
    print("\n[DEBUG] Starting business data storage...")
    print(f"[DEBUG] Raw business data received: {business_data}")
    
    stored_businesses = []
    accounts = business_data.get('accounts', []) if business_data else []
    print(f"[DEBUG] Found {len(accounts)} accounts to process")

    # Delete any existing businesses for this user
    Business.objects.filter(user_id=user_id).delete()
    
    if not accounts:
        print("[WARNING] No accounts found in business data")
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
                        'address': location.get('address', {}).get('formattedAddress', 'No info'),
                        'phone_number': location.get('primaryPhone', 'No info'),
                        'website_url': location.get('websiteUrl', 'No info'),
                        'category': location.get('primaryCategory', {}).get('displayName', 'No info'),
                        'is_verified': location.get('locationState', {}).get('isVerified', False),
                        'email_settings': 'Enabled',
                        'automation_status': 'Active'
                    }

                    # Store additional attributes
                    attributes = {
                        'opening_hours': location.get('regularHours', {}),
                        'special_hours': location.get('specialHours', {}),
                        'service_area': location.get('serviceArea', {}),
                        'labels': location.get('labels', []),
                        'profile_state': location.get('profile', {}).get('state', 'COMPLETE'),
                    }
                
                # Get or create the business record
                business, created = Business.objects.update_or_create(
                    business_id=account['name'],
                    defaults=business_details
                )
                
                stored_businesses.append(business)
                print(f"[INFO] Successfully stored/updated business: {business.business_name}")
                
        except Exception as e:
            print(f"[ERROR] Failed to store business data for account {account.get('name')}: {str(e)}")
            continue
    
    return stored_businesses

def get_locations(access_token, account_id):
    url = f"https://mybusiness.googleapis.com/v4/accounts/{account_id}/locations"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()
