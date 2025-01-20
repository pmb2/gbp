from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
import requests
import json
import logging

logger = logging.getLogger(__name__)

def refresh_oauth_token(user):
    """
    Refresh OAuth token if expired or about to expire
    Returns True if token was refreshed, False if not needed
    """
    try:
        # Check if token needs refresh (within 5 minutes of expiry)
        if not user.google_token_expiry or \
           user.google_token_expiry - timezone.now() < timedelta(minutes=5):
            
            logger.info(f"Refreshing OAuth token for user {user.email}")
            
            response = requests.post(
                'https://oauth2.googleapis.com/token',
                data={
                    'client_id': settings.GOOGLE_OAUTH2_CLIENT_ID,
                    'client_secret': settings.GOOGLE_OAUTH2_CLIENT_SECRET,
                    'refresh_token': user.google_refresh_token,
                    'grant_type': 'refresh_token'
                }
            )
            
            if response.status_code != 200:
                logger.error(f"Token refresh failed: {response.text}")
                return False
                
            data = response.json()
            user.google_access_token = data['access_token']
            user.google_token_expiry = timezone.now() + \
                                     timedelta(seconds=data['expires_in'])
            user.save(update_fields=['google_access_token', 
                                   'google_token_expiry'])
            
            logger.info(f"Successfully refreshed token for {user.email}")
            return True
            
        return False
        
    except Exception as e:
        logger.error(f"Error refreshing token: {str(e)}")
        return False
