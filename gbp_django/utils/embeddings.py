from django.db.models import F
from pgvector.django import L2Distance, CosineDistance
from typing import List, Dict, Any, Optional, Tuple
from .model_interface import get_llm_model

def generate_embedding(text: str) -> Optional[List[float]]:
    """Generate embeddings using configured model"""
    return get_llm_model().generate_embedding(text)

def generate_response(query: str, context: str, chat_history: List[Dict[str, str]] = None) -> str:
    """Generate response using configured model"""
    return get_llm_model().generate_response(query, context, chat_history)

def update_business_embedding(business) -> bool:
    """Update embedding for a business profile"""
    try:
        # Combine relevant business information
        text_parts = [
            business.business_name,
            business.description or '',
            f"Category: {business.category}",
            f"Address: {business.address}",
            f"Website: {business.website_url}",
            f"Phone: {business.phone_number}"
        ]
        text = '\n'.join(filter(None, text_parts))
        
        # Generate embedding
        embedding = generate_embedding(text)
        if embedding:
            business.embedding = embedding
            business.save(update_fields=['embedding'])
            return True
            
        return False
    except Exception as e:
        print(f"Error updating business embedding: {str(e)}")
        return False

def find_similar_businesses(query_embedding: List[float], limit: int = 5) -> List[Tuple[Any, float]]:
    """Find similar businesses using vector similarity search"""
    from ..models import Business  # Import here to avoid circular imports
    
    try:
        businesses = Business.objects.annotate(
            similarity=CosineDistance('embedding', query_embedding)
        ).filter(
            embedding__isnull=False
        ).order_by('similarity')[:limit]
        
        return [(business, float(business.similarity)) for business in businesses]
    except Exception as e:
        print(f"Error finding similar businesses: {str(e)}")
        return []
