import requests
from gbp_django.models import Review
from django.db import transaction
from ..models import Review

@transaction.atomic
def store_reviews(reviews_data, account_id):
    reviews = reviews_data.get('reviews', [])
    for review in reviews:
        existing_review = Review.objects.filter(review_id=review['name']).first()
        if not existing_review:
            Review.objects.create(
                business_id=account_id,
                review_id=review['name'],
                reviewer_name=review.get('reviewer', {}).get('displayName', 'Anonymous'),
                reviewer_profile_url=review.get('reviewer', {}).get('profilePhotoUrl', ''),
                rating=review.get('starRating', 0),
                content=review.get('comment', ''),
                responded=review.get('responded', False),
                response=review.get('response', {}).get('comment', '')
            )
        else:
            existing_review.rating = review.get('starRating', 0)
            existing_review.content = review.get('comment', '')
            existing_review.responded = review.get('responded', False)
            existing_review.response = review.get('response', {}).get('comment', '')
            existing_review.save()

def respond_to_review(access_token, account_id, location_id, review_id, response_data):
    url = f"https://mybusiness.googleapis.com/v4/accounts/{account_id}/locations/{location_id}/reviews/{review_id}/reply"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.put(url, headers=headers, json=response_data)
    response.raise_for_status()
    return response.json()

def delete_review_reply(access_token, account_id, location_id, review_id):
    url = f"https://mybusiness.googleapis.com/v4/accounts/{account_id}/locations/{location_id}/reviews/{review_id}/reply"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.delete(url, headers=headers)
    response.raise_for_status()
    return response.status_code == 204

def get_reviews(access_token, account_id, location_id):
    url = f"https://mybusiness.googleapis.com/v4/accounts/{account_id}/locations/{location_id}/reviews"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()
