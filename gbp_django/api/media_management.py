import requests
from django.db import transaction
from ..models import BusinessAttribute

@transaction.atomic
def store_photos(photos_data, account_id):
    for photo in photos_data.get('mediaItems', []):
        existing_photo = BusinessAttribute.objects.filter(business_id=account_id, key='photo', value=photo['name']).first()
        if not existing_photo:
            BusinessAttribute.objects.create(
                business_id=account_id,
                key='photo',
                value=photo['name']
            )

def upload_photo(access_token, account_id, location_id, photo_data):
    logger.info(f"Starting media upload for location {location_id}")
    logger.debug(f"Request payload keys: {photo_data.keys()}")
    
    url = f"https://mybusiness.googleapis.com/v4/accounts/{account_id}/locations/{location_id}/media"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    try:
        response = requests.post(url, headers=headers, json=photo_data)
        response.raise_for_status()
        logger.info(f"Media upload successful - Status: {response.status_code}")
        logger.debug(f"API response: {response.json()}")
        return response.json()
    except requests.exceptions.HTTPError as e:
        logger.error(f"Media upload failed - Status: {e.response.status_code} - Response: {e.response.text}")
        raise

def delete_photo(access_token, account_id, location_id, media_id):
    url = f"https://mybusiness.googleapis.com/v4/accounts/{account_id}/locations/{location_id}/media/{media_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.delete(url, headers=headers)
    response.raise_for_status()
    return response.status_code == 204

def get_photos(access_token, account_id, location_id):
    url = f"https://mybusiness.googleapis.com/v4/accounts/{account_id}/locations/{location_id}/media"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()
