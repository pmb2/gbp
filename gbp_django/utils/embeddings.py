import requests
from django.conf import settings
from django.db.models import F
from pgvector.django import L2Distance, CosineDistance
from typing import List, Dict, Any, Optional, Tuple

def generate_embedding(text: str) -> Optional[List[float]]:
    """Generate embeddings using Ollama's local API"""
    try:
        # Ensure text is properly formatted and chunked if needed
        text = text.strip().replace('\n', ' ')
        
        # If text is too long, take first 8000 chars to avoid token limits
        if len(text) > 8000:
            text = text[:8000]
        
        # Try nomic-embed-text first
        response = requests.post(
            'http://localhost:11434/api/embeddings',
            json={
                'model': 'nomic-embed-text',
                'prompt': text,
                'options': {
                    'temperature': 0,
                    'num_ctx': 8192
                }
            },
            timeout=30
        )
        response.raise_for_status()
        
        embedding = response.json()['embedding']
        dim = len(embedding)
        
        if dim == 1536:
            return embedding
            
        # If we got 768 dims, pad to 1536 by repeating
        if dim == 768:
            print("[INFO] Got 768 dims, padding to 1536...")
            return embedding * 2  # Repeat the embedding to get 1536 dims
            
        print(f"[WARNING] Invalid embedding dimensions: got {dim}, expected 1536")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Network error generating embedding: {str(e)}")
        return None
    except Exception as e:
        print(f"Error generating embedding: {str(e)}")
        return None

def generate_response(query: str, context: str, chat_history: List[Dict[str, str]] = None) -> str:
    """Generate response using Groq's LLaMA API with chat history and memory summaries"""
    try:
        from groq import Groq
        
        # Format chat history and summarize memories
        formatted_history = []
        memory_summary = []
        
        if chat_history:
            # Group messages by topic and summarize
            current_topic = []
            for msg in chat_history[-10:]:  # Look at last 10 messages
                current_topic.append(msg['content'])
                if len(current_topic) >= 3:  # Summarize every 3 messages
                    summary = f"• Previous discussion about: {' '.join(current_topic)[:100]}..."
                    memory_summary.append(summary)
                    current_topic = []
            
            # Add remaining messages
            if current_topic:
                summary = f"• Recent exchange about: {' '.join(current_topic)[:100]}..."
                memory_summary.append(summary)
            
            # Format recent messages
            formatted_history = [
                {'role': m['role'], 'content': m['content']} 
                for m in chat_history[-5:]  # Keep last 5 messages verbatim
            ]

        system_prompt = (
            "You are an AI assistant for a business automation platform. "
            "You have access to the business's profile information, documents, and chat history. "
            "Use the provided context to give accurate, professional responses. "
            "If uncertain, acknowledge the limitations of your knowledge.\n\n"
            f"Business Context: {context}\n\n"
            f"Memory Summaries:\n" + "\n".join(memory_summary) + "\n\n"
            "Instructions: Provide a helpful response based on the context and history."
        )

        # Prepare messages array
        messages = [{'role': 'system', 'content': system_prompt}]
        if formatted_history:
            messages.extend(formatted_history)
        messages.append({'role': 'user', 'content': query})
        
        # Initialize Groq client
        client = Groq(api_key=settings.GROQ_API_KEY)
        
        # Make API call using official client
        chat_completion = client.chat.completions.create(
            messages=messages,
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            max_tokens=1000,
            top_p=0.9,
            stream=False
        )
        
        return chat_completion.choices[0].message.content.strip()
    except requests.exceptions.RequestException as e:
        print(f"Network error generating response: {str(e)}")
        return "I apologize, but I'm experiencing connectivity issues. Please try again in a moment."
    except Exception as e:
        print(f"Error generating response: {str(e)}")
        return "I apologize, but I'm unable to generate a response at the moment."

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
