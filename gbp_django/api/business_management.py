import os
import random
import requests
import time
from django.conf import settings
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
    url = (f"https://mybusiness.googleapis.com/v4/accounts/"
           f"{account_id}/locations/{location_id}")
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.patch(url, headers=headers, json=update_data)
    response.raise_for_status()
    return response.json()


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
    url = "https://mybusinessaccountmanagement.googleapis.com/v1/accounts"
    headers = {"Authorization": f"Bearer {access_token}"}
    retries = 3
    backoff_factor = 2

    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            if not data.get('accounts'):
                print("[ERROR] No business accounts found.")
                # Log the warning as a notification
                from gbp_django.models import Notification
                from django.contrib.sessions.backends.db import SessionStore
                session = SessionStore()
                user_id = session.get('user_id')
                if user_id:
                    notification = Notification(user_id=user_id, message="No business accounts found. Using placeholder data.", priority="high")
                    notification.save()
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
    for account in business_data.get('accounts', []):
        # Get locations for this account
        locations = get_locations(access_token, account['name'])
        if locations.get('locations'):
            location = locations['locations'][0]  # Use first location
            
            # Get or create the business record with full details
            business, created = Business.objects.get_or_create(
                business_id=account['name'],
                defaults={
                    'user_id': user_id,
                    'business_name': account.get('accountName', 'Unnamed Business'),
                    'address': location.get('address', {}).get('formattedAddress', ''),
                    'phone_number': location.get('primaryPhone', ''),
                    'website_url': location.get('websiteUrl', ''),
                    'category': location.get('primaryCategory', {}).get('displayName', ''),
                    'is_verified': location.get('locationState', {}).get('isVerified', False)
                }
            )
            
            # Update existing business with latest data
            if not created:
                business.business_name = account.get('accountName', 'Unnamed Business')
                business.address = location.get('address', {}).get('formattedAddress', '')
                business.phone_number = location.get('primaryPhone', '')
                business.website_url = location.get('websiteUrl', '')
                business.category = location.get('primaryCategory', {}).get('displayName', '')
                business.is_verified = location.get('locationState', {}).get('isVerified', False)
                business.save()
        
        # Fetch locations for this account
        locations = get_locations(access_token, account['name'])
        if locations.get('locations'):
            location = locations['locations'][0]  # Use first location
            
            # Update business details
            business.address = location.get('address', {}).get('formattedAddress')
            business.phone_number = location.get('primaryPhone')
            business.website_url = location.get('websiteUrl')
            business.category = location.get('primaryCategory', {}).get('displayName')
            business.is_verified = location.get('locationState', {}).get('isVerified', False)
            
            # Count related data
            business.posts_count = Post.objects.filter(business=business).count()
            business.photos_count = BusinessAttribute.objects.filter(business=business, key='photo').count()
            business.qanda_count = QandA.objects.filter(business=business).count()
            business.reviews_count = Review.objects.filter(business=business).count()
            
            # Set default values for settings
            business.email_settings = 'Enabled'
            business.automation_status = 'Active'
            
            business.save()

def get_locations(access_token, account_id):
    url = f"https://mybusiness.googleapis.com/v4/accounts/{account_id}/locations"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()
