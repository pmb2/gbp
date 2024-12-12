import requests
from django.conf import settings
from typing import List, Dict, Any

def generate_embedding(text: str) -> List[float]:
    """Generate embeddings using Ollama's local API"""
    try:
        response = requests.post(
            'http://localhost:11434/api/embeddings',
            json={'model': 'mxbai-embed-large', 'prompt': text}
        )
        return response.json()['embedding']
    except Exception as e:
        print(f"Error generating embedding: {str(e)}")
        return None

def generate_response(query: str, context: str) -> str:
    """Generate response using Groq's API"""
    try:
        system_prompt = f"Context: {context}\n\nInstructions: Answer the user's question based on the above context."
        response = requests.post(
            'https://api.groq.com/v1/completions',
            json={
                'model': 'llama3',
                'prompt': query,
                'system_prompt': system_prompt,
                'temperature': 0.7,
                'max_tokens': 500
            },
            headers={'Authorization': f'Bearer {settings.GROQ_API_KEY}'}
        )
        return response.json()['choices'][0]['text']
    except Exception as e:
        print(f"Error generating response: {str(e)}")
        return "I apologize, but I'm unable to generate a response at the moment."

def update_business_embedding(business) -> None:
    """Update embedding for a business profile"""
    try:
        # Combine relevant business information
        text = f"{business.business_name}\n{business.description or ''}\n"
        text += f"Category: {business.category}\n"
        text += f"Address: {business.address}\n"
        text += f"Website: {business.website_url}\n"
        
        # Generate embedding
        embedding = generate_embedding(text)
        if embedding:
            business.embedding = embedding
            business.save(update_fields=['embedding'])
    except Exception as e:
        print(f"Error updating business embedding: {str(e)}")
