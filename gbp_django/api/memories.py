from django.http import JsonResponse
from ..models import FAQ

def get_memories(business_id):
    """Get memories/chat history for a business"""
    memories = FAQ.objects.filter(
        business_id=business_id,
        deleted_at__isnull=True
    ).order_by('-created_at')
    
    return {
        'memories': [
            {
                'id': memory.id,
                'content': memory.answer,
                'created_at': memory.created_at.isoformat()
            }
            for memory in memories
        ]
    }
