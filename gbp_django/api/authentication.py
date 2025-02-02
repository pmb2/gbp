import os
import json
import requests
import logging
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.sessions.backends.db import SessionStore
from django.utils import timezone

logger = logging.getLogger(__name__)

def get_business_account_id(access_token):
    """Fetch the Google Business Account ID for the authenticated user"""
    url = "https://mybusinessbusinessinformation.googleapis.com/v1/accounts"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        logger.info("🏢 Fetching business account ID...")
        logger.debug(f"Making request to: {url}")
        logger.debug(f"Using token (first 10 chars): {access_token[:10]}...")
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        accounts_data = response.json()
        logger.debug(f"Accounts response: {json.dumps(accounts_data, indent=2)}")
        
        if not accounts_data.get('accounts'):
            logger.warning("No business accounts found for this user")
            return None
            
        account_id = accounts_data['accounts'][0]['name']
        logger.info(f"✅ Found business account ID: {account_id}")
        return account_id
        
    except requests.exceptions.HTTPError as e:
        logger.error(f"❌ Failed to fetch business account: {str(e)}")
        logger.error(f"Response: {e.response.text}")
        return None
    except Exception as e:
        logger.error(f"❌ Unexpected error fetching business account: {str(e)}")
        return None

def get_business_locations(access_token, account_id):
    """Fetch all business locations for the given account"""
    if not account_id:
        logger.error("❌ No account ID provided")
        return None
        
    url = f"https://mybusinessbusinessinformation.googleapis.com/v1/{account_id}/locations"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        logger.info(f"🏪 Fetching business locations for account: {account_id}")
        logger.debug(f"Making request to: {url}")
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        locations_data = response.json()
        logger.debug(f"Locations response: {json.dumps(locations_data, indent=2)}")
        
        if not locations_data.get('locations'):
            logger.warning("No locations found for this account")
            return None
            
        logger.info(f"✅ Found {len(locations_data['locations'])} location(s)")
        return locations_data['locations']
        
    except requests.exceptions.HTTPError as e:
        logger.error(f"❌ Failed to fetch locations: {str(e)}")
        logger.error(f"Response: {e.response.text}")
        return None
    except Exception as e:
        logger.error(f"❌ Unexpected error fetching locations: {str(e)}")
        return None

def get_access_token(auth_code, client_id, client_secret, redirect_uri):
    logger.info("\n🔑 Starting OAuth token exchange...")
    url = "https://oauth2.googleapis.com/token"
    payload = {
        "code": auth_code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }
    print(f"📡 Making token request to: {url}")
    print(f"🔐 Using client_id: {client_id[:8]}...")
    print(f"🔄 Redirect URI: {redirect_uri}")
    
    response = requests.post(url, data=payload)
    response.raise_for_status()
    token_data = response.json()
    
    print("✅ Token exchange successful!")
    print(f"📦 Received tokens:")
    print(f"  • Access token length: {len(token_data.get('access_token', ''))}")
    print(f"  • Refresh token present: {'refresh_token' in token_data}")
    print(f"  • Token type: {token_data.get('token_type')}")
    print(f"  • Expires in: {token_data.get('expires_in')} seconds")
    
    return token_data

def refresh_access_token(refresh_token, client_id, client_secret, redirect_uri=None):
    """
    Refresh OAuth token with proper error handling and expiration tracking
    Returns dict with new token info including calculated expiry timestamp
    """
    logger.info("\n🔄 Refreshing access token...")
    url = "https://oauth2.googleapis.com/token"
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
        "redirect_uri": redirect_uri  # Match original redirect URI
    }
    
    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()
        token_data = response.json()
        # Add absolute expiration timestamp
        token_data['expiry_timestamp'] = (timezone.now() + 
            timedelta(seconds=token_data.get('expires_in', 3600))).isoformat()
        
        logger.info("✅ Token refresh successful")
        logger.debug(f"New token expires at: {token_data['expiry_timestamp']}")
        return token_data
    except requests.exceptions.HTTPError as e:
        print(f"❌ Token refresh failed: {e.response.status_code} {e.response.text}")
        raise
def get_user_info(access_token):
    logger.info("\n👤 Fetching Google user info...")
    url = "https://openidconnect.googleapis.com/v1/userinfo"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        logger.info(f"📡 Making userinfo request to: {url}")
        logger.debug(f"Using token (first 10 chars): {access_token[:10]}...")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        user_data = response.json()
        # Add fallback for email if not in response
        if 'email' not in user_data:
            user_data['email'] = f"{user_data.get('sub', 'unknown')}@googleauth.com"
        
        print("✅ User info retrieved successfully!")
        print(f"📦 User details:")
        print(f"  • Email: {user_data.get('email')}")
        print(f"  • Name: {user_data.get('name')}")
        print(f"  • Google ID: {user_data.get('sub')}")
        print(f"  • Picture URL: {user_data.get('picture', 'None')}")
        
        return user_data
    except requests.exceptions.HTTPError as e:
        if response.status_code == 401:
            # Token expired, refresh token
            print("[INFO] Access token expired, attempting to refresh.")
            session = SessionStore()
            new_token = refresh_access_token(
                session.get('refresh_token'),
                os.getenv('CLIENT_ID'),
                os.getenv('CLIENT_SECRET')
            )
            session['google_token'] = new_token['access_token']
            session.save()
            headers["Authorization"] = f"Bearer {new_token['access_token']}"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        else:
            raise e
