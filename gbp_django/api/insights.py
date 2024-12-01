import requests

def request_insights(access_token, account_id, location_id, insights_request=None):
    url = f"https://mybusiness.googleapis.com/v4/accounts/{account_id}/locations/{location_id}/insights"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers, json=insights_request)
    response.raise_for_status()
    return response.json()

def get_insights(access_token, account_id, location_id):
    url = f"https://mybusiness.googleapis.com/v4/accounts/{account_id}/locations/{location_id}/insights"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()
