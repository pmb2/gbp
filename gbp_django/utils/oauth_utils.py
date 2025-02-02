from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
import requests
import json
import logging

logger = logging.getLogger(__name__)

def is_token_expired(expiry_time, buffer_minutes=5):
    """Check if token is expired or will expire soon"""
    if not expiry_time:
        return True
    
    try:
        if isinstance(expiry_time, str):
            expiry_time = datetime.fromisoformat(expiry_time)
        buffer_time = timezone.now() + timedelta(minutes=buffer_minutes)
        return expiry_time <= buffer_time
    except Exception as e:
        logger.error(f"Error checking token expiration: {str(e)}")
        return True

def validate_business_data(locations_data):
    """Validate the structure and content of business location data"""
    if not locations_data or not isinstance(locations_data, list):
        logger.error("Invalid locations data structure")
        return False
        
    required_fields = ['name', 'locationName', 'address', 'phoneNumbers']
    for location in locations_data:
        missing_fields = [field for field in required_fields if field not in location]
        if missing_fields:
            logger.error(f"Missing required fields: {missing_fields}")
            return False
    
    return True

def refresh_oauth_token(user):
    """
    Refresh OAuth token if expired or about to expire
    Returns True if token was refreshed, False if not needed
    
    Includes enhanced validation, debugging, and business data fetching
    """
    try:
        # Enhanced token validation
        if is_token_expired(user.google_token_expiry):
            logger.debug(f"Token expired or near expiry for user {user.email}")
            logger.debug(f"Current token expiry: {user.google_token_expiry}")
            
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
            logger.debug(f"New token expiry: {user.google_token_expiry}")
            logger.debug(f"Token length: {len(user.google_access_token)}")
            return True
            
        return False
        
    except Exception as e:
        logger.error(f"Error refreshing token: {str(e)}")
        return False
