from typing import List, Dict, Any, Optional
import numpy as np
from django.db.models import Q
from pgvector.django import CosineDistance, L2Distance
from ..models import Business, FAQ, KnowledgeChunk
from .embeddings import generate_embedding, generate_response

def search_knowledge_base(query: str, business_id: str, top_k: int = 20, min_similarity: float = 0.4) -> List[Dict[str, Any]]:
    print(f"\n[DEBUG] Searching knowledge base for query: {query}")
    print(f"[DEBUG] Business ID: {business_id}, Top K: {top_k}")
    print(f"[DEBUG] Minimum similarity threshold: {min_similarity}")
    
    query_embeddings = []
    prompts = [
        query,
        f"Information about: {query}",
        f"Details regarding: {query}",
        f"Find content related to: {query}"
    ]
    
    for prompt in prompts:
        embedding = generate_embedding(prompt)
        if embedding:
            query_embeddings.append(embedding)
            print(f"[DEBUG] Generated embedding for prompt: {prompt[:50]}...")
        else:
            print(f"[WARNING] Failed to generate embedding for prompt: {prompt[:50]}")

    if not query_embeddings:
        print("[ERROR] Failed to generate any query embeddings")
        return []
        
    try:
        business = Business.objects.get(business_id=business_id)
        print(f"[DEBUG] Found business: {business.business_name}")
        
        results = []
        
        for query_embedding in query_embeddings:
            chunks = KnowledgeChunk.objects.filter(
                knowledge_file__business__business_id=business_id,
                knowledge_file__deleted_at__isnull=True
            ).annotate(
                similarity=CosineDistance('embedding', query_embedding)
            ).order_by('similarity')[:top_k]

            for chunk in chunks:
                cosine_sim = 1 - float(chunk.similarity)
                if cosine_sim >= min_similarity:
                    print(f"[DEBUG] Chunk ID: {chunk.id}, Similarity: {cosine_sim}")
                    results.append({
                        'content': chunk.content,
                        'similarity': cosine_sim,
                        'metadata': {
                            'file_name': chunk.knowledge_file.file_name,
                            'position': chunk.position,
                            'created_at': chunk.created_at.isoformat(),
                            'confidence': f"{cosine_sim:.1%}"
                        }
                    })
                else:
                    print(f"[DEBUG] Chunk ID: {chunk.id} below similarity threshold: {cosine_sim}")

        print(f"[DEBUG] Total relevant chunks found: {len(results)}")
        return results
        
    except Exception as e:
        print(f"[ERROR] Failed to search knowledge base: {str(e)}")
        traceback.print_exc()
        return []

def get_relevant_context(query: str, business_id: str, min_similarity: float = 0.6) -> str:
    print(f"\n[DEBUG] Getting relevant context for query: {query}")
    try:
        results = search_knowledge_base(query, business_id, min_similarity=min_similarity)
        print(f"[DEBUG] search_knowledge_base returned {len(results)} results")
        if not results:
            print("[DEBUG] No relevant context found in knowledge base")
            return ""

        context_parts = []
        for i, result in enumerate(results, 1):
            metadata = result['metadata']
            content = result['content']
            print(f"[DEBUG] Result {i} metadata: {metadata}")
            # Use available metadata keys
            context_parts.append(
                f"[Context Block {i}]\n"
                f"Source: {metadata.get('file_name', 'Unknown')}\n"
                f"Position: {metadata.get('position', 'N/A')}\n"
                f"Confidence: {metadata.get('confidence', 'N/A')}\n"
                f"Created At: {metadata.get('created_at', 'N/A')}\n"
                f"Content:\n{content}\n"
                f"{'='*50}\n"
            )

        context = "\n".join(context_parts)
        print(f"[DEBUG] Generated context length: {len(context)}")
        return context

    except Exception as e:
        print(f"[ERROR] Exception in get_relevant_context: {str(e)}")
        traceback.print_exc()
        return ""

TASK_TEMPLATES = {
    "POST": {
        "DEFAULT": "Create a social media post about {topic} that aligns with our brand voice and incorporates key information from our knowledge base.",
        "ENGAGING": "Generate an engaging social media post about {topic} that encourages user interaction. Use emojis and include relevant FAQs: {faqs}",
        "PROMOTIONAL": "Create promotional content about {topic} that highlights special offers. Use these key points: {faqs}",
        "INFORMATIVE": "Write an informative post explaining {topic}. Use this structured information: {faqs}"
    },
    "REVIEW": {
        "DEFAULT": "Generate a professional response to this review: {review_text}. Consider these business details: {faqs}",
        "APPRECIATIVE": "Create a grateful response to this positive review: {review_text}. Mention: {faqs}",
        "EMPATHETIC": "Draft an empathetic response to this negative review: {review_text}. Reference our policies: {faqs}"
    }
}

import traceback  # Add this import at the top

def answer_question(query: str, business_id: str, chat_history: List[Dict[str, str]] = None) -> str:
    print(f"\n[INFO] Starting RAG process for query: '{query}'")
    try:
        print("\n[DEBUG] answer_question called with:")
        print(f"[DEBUG] Query: {query}")
        print(f"[DEBUG] Business ID: {business_id}")
        print(f"[DEBUG] Chat history: {chat_history}")

        # Get business info
        try:
            business = Business.objects.get(business_id=business_id)
            print(f"[DEBUG] Found business: {business.business_name}")
        except Business.DoesNotExist:
            print(f"[ERROR] No business found with ID: {business_id}")
            return "Business not found"

        # Get relevant context
        context = get_relevant_context(query, business_id)
        print(f"[DEBUG] Retrieved context: {context}")

        # Build full context for LLM
        print("[INFO] Building context for LLM response...")
        business_context = {
            "profile": {
                "name": business.business_name,
                "category": business.category,
                "location": business.address,
                "website": business.website_url,
                "phone": business.phone_number,
                "verification_status": 'Verified' if business.is_verified else 'Not Verified',
                "profile_completion": f"{business.calculate_profile_completion()}%",
            },
            "automation_settings": {
                "posts": business.posts_automation,
                "reviews": business.reviews_automation,
                "qa": business.qa_automation,
            },
            # Assuming you have a way to get summaries
            "content_sources": [
                {"type": "file", "name": doc.file_name, "summary": getattr(doc, 'summary', 'No summary available')}
                for doc in business.knowledge_files.all()
            ]
        }

        full_context = (
            f"{business_context}\n\n"
            f"📚 Knowledge Base Context:\n"
            f"{'-' * 40}\n"
            f"{context if context else 'No relevant context found in the knowledge base.'}\n\n"
            f"💬 Recent Chat Context:\n"
            f"{'-' * 40}\n"
        )

        # Add recent chat context
        if chat_history:
            recent_chats = chat_history[-5:]  # Get last 5 exchanges
            chat_context = []
            for msg in recent_chats:
                prefix = "👤 User:" if msg['role'] == 'user' else "🤖 Assistant:"
                chat_context.append(f"{prefix} {msg['content']}")
            full_context += '\n'.join(chat_context)
        else:
            full_context += "No previous chat history.\n"

        print("[DEBUG] Final context length:", len(full_context))
        print("[DEBUG] Full context:\n", full_context)

        # Generate response using chat history
        response = generate_response(query, full_context, chat_history)
        print("[DEBUG] Generated response:", response)

        # Store the interaction in chat history
        if chat_history is not None:
            chat_history.append({'role': 'user', 'content': query})
            chat_history.append({'role': 'assistant', 'content': response})

        # Add source attribution if relevant context was found
        if context:
            response += "\n\n[Response based on business documentation and profile information]"

        return response

    except Exception as e:
        print(f"[ERROR] Exception in answer_question: {str(e)}")
        traceback.print_exc()  # This will print the stack trace
        return "I apologize, but I encountered an error while trying to answer your question."

def add_to_knowledge_base(business_id: str, question: str, answer: str) -> Optional[FAQ]:
    """Add new QA pair to knowledge base"""
    try:
        # Clean and validate input
        question = question.strip()
        answer = answer.strip()
        
        if not question or not answer:
            raise ValueError("Question and answer cannot be empty")
            
        # Generate embedding for question
        embedding = generate_embedding(question)
        if not embedding:
            raise ValueError("Failed to generate embedding")
            
        # Create FAQ entry
        faq = FAQ.objects.create(
            business_id=business_id,
            question=question,
            answer=answer,
            embedding=embedding
        )
        
        print(f"[INFO] Added new FAQ to knowledge base for business {business_id}")
        return faq
        
    except Exception as e:
        print(f"[ERROR] Failed to add to knowledge base: {str(e)}")
        return None
