import requests
from django.db import transaction
from ..models import Post

@transaction.atomic
def store_posts(posts_data, account_id):
    print(f"\n[DEBUG] Starting post storage for account: {account_id}")
    print(f"[DEBUG] Raw posts data: {posts_data}")
    stored_posts = []
    try:
        local_posts = posts_data.get('localPosts', [])
        print(f"[DEBUG] Found {len(local_posts)} posts to process")
        for post in local_posts:
            post_data = {
                'business_id': account_id,
                'post_id': post['name'],
                'post_type': post.get('topicType', 'STANDARD'),
                'content': post.get('summary', ''),
                'media_url': post.get('media', [{}])[0].get('sourceUrl', '') if post.get('media') else '',
                'scheduled_at': post.get('scheduledTime', None),
                'status': post.get('state', 'PUBLISHED')
            }
            
            post_obj, created = Post.objects.update_or_create(
                post_id=post['name'],
                defaults=post_data
            )
            stored_posts.append(post_obj)
            print(f"[INFO] Successfully stored/updated post: {post['name']}")
    except Exception as e:
        print(f"[ERROR] Failed to store post data: {str(e)}")
    return stored_posts

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
