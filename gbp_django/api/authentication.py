import os
import requests
from django.conf import settings
from django.contrib.sessions.backends.db import SessionStore

def get_access_token(auth_code, client_id, client_secret, redirect_uri):
    print("\n🔑 Starting OAuth token exchange...")
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
    """Refresh OAuth token with proper error handling"""
    print("\n🔄 Refreshing access token...")
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
        print("✅ Token refresh successful")
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"❌ Token refresh failed: {e.response.status_code} {e.response.text}")
        raise
def get_user_info(access_token):
    print("\n👤 Fetching Google user info...")
    url = "https://openidconnect.googleapis.com/v1/userinfo"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    try:
        print(f"📡 Making userinfo request to: {url}")
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
