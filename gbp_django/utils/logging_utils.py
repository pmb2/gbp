import logging
from datetime import datetime
from ..models import AutomationLog

logger = logging.getLogger(__name__)

def log_api_request(user_id, business_id, action_type, details=None, status='success', error=None):
    """
    Log API requests and their outcomes
    """
    try:
        AutomationLog.objects.create(
            user_id=user_id,
            business_id=business_id,
            action_type=action_type,
            details=details,
            status=status,
            error_message=str(error) if error else None,
            executed_at=datetime.now()
        )
    except Exception as e:
        logger.error(f"Failed to create log entry: {str(e)}")

def log_data_sync(user_id, business_id, sync_type, changes=None):
    """
    Log data synchronization activities
    """
    details = f"Sync type: {sync_type}, Changes: {changes}"
    log_api_request(user_id, business_id, 'data_sync', details)
