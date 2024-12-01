import os
from flask_caching import Cache

# Initialize cache
cache = Cache(config={'CACHE_TYPE': 'simple'})
import requests
import time
import random
from flask import session
from gbp_django.api.authentication import refresh_access_token

def create_business_location(access_token, account_id, location_data):
    url = f"https://mybusiness.googleapis.com/v4/accounts/{account_id}/locations"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.post(url, headers=headers, json=location_data)
    response.raise_for_status()
    return response.json()

def update_business_details(access_token, account_id, location_id, update_data):
    url = f"https://mybusiness.googleapis.com/v4/accounts/{account_id}/locations/{location_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.patch(url, headers=headers, json=update_data)
    response.raise_for_status()
    return response.json()

def delete_location(access_token, account_id, location_id):
    url = f"https://mybusiness.googleapis.com/v4/accounts/{account_id}/locations/{location_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.delete(url, headers=headers)
    response.raise_for_status()
    return response.status_code == 204

import time

@cache.cached(timeout=300, key_prefix='business_accounts')
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
                from flask import session
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
                new_token = refresh_access_token(
                    session['refresh_token'],
                    os.getenv('CLIENT_ID'),
                    os.getenv('CLIENT_SECRET')
                )
                session['google_token'] = new_token['access_token']
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
                    if 'refresh_token' in session:
                        new_token = refresh_access_token(
                            session['refresh_token'],
                            os.getenv('CLIENT_ID'),
                            os.getenv('CLIENT_SECRET')
                        )
                        session['google_token'] = new_token['access_token']
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

from gbp_django.models import Business
from django.db import transaction

def store_business_data(business_data, user_id):
    for account in business_data.get('accounts', []):
        business = Business.query.filter_by(business_id=account['name']).first()
        if not business:
            business = Business(
                user_id=user_id,
                business_name=account.get('accountName'),
                business_id=account['name']
            )
            business.save()
        else:
            business.business_name = account.get('accountName')
            business.save()

def get_locations(access_token, account_id):
    url = f"https://mybusiness.googleapis.com/v4/accounts/{account_id}/locations"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()
