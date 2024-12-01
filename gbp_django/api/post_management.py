import requests
from gbp_django.models import Post
from gbp_django import db

def store_posts(posts_data, account_id):
    for post in posts_data.get('localPosts', []):
        existing_post = Post.query.filter_by(post_id=post['name']).first()
        if not existing_post:
            new_post = Post(
                business_id=account_id,
                post_type=post.get('topicType', 'STANDARD'),
                content=post.get('summary', ''),
                media_url=post.get('media', [{}])[0].get('sourceUrl', '') if post.get('media') else '',
                scheduled_at=post.get('scheduledTime', None),
                status=post.get('state', 'PUBLISHED')
            )
            db.session.add(new_post)
        else:
            existing_post.content = post.get('summary', '')
            existing_post.media_url = post.get('media', [{}])[0].get('sourceUrl', '') if post.get('media') else ''
            existing_post.scheduled_at = post.get('scheduledTime', None)
            existing_post.status = post.get('state', 'PUBLISHED')
    db.session.commit()

def create_post(access_token, account_id, location_id, post_data):
    url = f"https://mybusiness.googleapis.com/v4/accounts/{account_id}/locations/{location_id}/localPosts"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.post(url, headers=headers, json=post_data)
    response.raise_for_status()
    return response.json()

def update_post(access_token, account_id, location_id, post_id, update_data):
    url = f"https://mybusiness.googleapis.com/v4/accounts/{account_id}/locations/{location_id}/localPosts/{post_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.patch(url, headers=headers, json=update_data)
    response.raise_for_status()
    return response.json()

def delete_post(access_token, account_id, location_id, post_id):
    url = f"https://mybusiness.googleapis.com/v4/accounts/{account_id}/locations/{location_id}/localPosts/{post_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.delete(url, headers=headers)
    response.raise_for_status()
    return response.status_code == 204

def get_posts(access_token, account_id, location_id):
    url = f"https://mybusiness.googleapis.com/v4/accounts/{account_id}/locations/{location_id}/localPosts"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()
