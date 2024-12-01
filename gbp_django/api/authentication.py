import os
import requests
from flask import session, current_app

def get_access_token(auth_code, client_id, client_secret, redirect_uri):
    url = "https://oauth2.googleapis.com/token"
    payload = {
        "code": auth_code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }
    response = requests.post(url, data=payload)
    response.raise_for_status()
    return response.json()

def refresh_access_token(refresh_token, client_id, client_secret):
    url = "https://oauth2.googleapis.com/token"
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }
    response = requests.post(url, data=payload)
    response.raise_for_status()
    return response.json()
def get_user_info(access_token):
    from gbp_dashboard.app.models.schema import Session
    from gbp_dashboard.app.models.schema import Session
    url = "https://openidconnect.googleapis.com/v1/userinfo"
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
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
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        else:
            raise e
