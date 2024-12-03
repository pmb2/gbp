import requests
from gbp_django.models import BusinessAttribute

def store_photos(photos_data, account_id):
    for photo in photos_data.get('mediaItems', []):
        existing_photo = BusinessAttribute.objects.filter(business_id=account_id, key='photo', value=photo['name']).first()
        if not existing_photo:
            new_photo = BusinessAttribute(
                business_id=account_id,
                key='photo',
                value=photo['name']
            )
            new_photo.save()

def upload_photo(access_token, account_id, location_id, photo_data):
    url = f"https://mybusiness.googleapis.com/v4/accounts/{account_id}/locations/{location_id}/media"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.post(url, headers=headers, json=photo_data)
    response.raise_for_status()
    return response.json()

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
