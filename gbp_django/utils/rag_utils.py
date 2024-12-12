from typing import List, Dict, Any, Optional
import numpy as np
from django.db.models import Q
from pgvector.django import CosineDistance
from ..models import Business, FAQ
from .embeddings import generate_embedding, generate_response

def search_knowledge_base(query: str, business_id: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """Search knowledge base using vector similarity"""
    print(f"\n[DEBUG] Searching knowledge base for query: {query}")
    print(f"[DEBUG] Business ID: {business_id}, Top K: {top_k}")
    
    # Generate embedding for query
    query_embedding = generate_embedding(query)
    if not query_embedding:
        print("[ERROR] Failed to generate query embedding")
        return []
        
    try:
        # Get business and related FAQs using vector similarity
        faqs = FAQ.objects.filter(
            business_id=business_id
        ).annotate(
            similarity=CosineDistance('embedding', query_embedding)
        ).filter(
            embedding__isnull=False
        ).order_by('similarity')[:top_k]
        
        print(f"[DEBUG] Found {faqs.count()} relevant FAQs")
        
        results = []
        for faq in faqs:
            similarity = float(faq.similarity)
            print(f"[DEBUG] FAQ: {faq.question[:50]}... Similarity: {1 - similarity:.3f}")
            
            results.append({
                'question': faq.question,
                'answer': faq.answer,
                'similarity': 1 - similarity  # Convert distance to similarity
            })
        
        return results
        
    except Exception as e:
        print(f"[ERROR] Failed to search knowledge base: {str(e)}")
        return []

def get_relevant_context(query: str, business_id: str, min_similarity: float = 0.7) -> str:
    """Get relevant context from knowledge base"""
    results = search_knowledge_base(query, business_id)
    if not results:
        return ""
    
    # Filter and combine relevant QA pairs
    relevant_pairs = [
        f"Q: {result['question']}\nA: {result['answer']}"
        for result in results
        if result['similarity'] >= min_similarity
    ]
    
    if not relevant_pairs:
        return ""
        
    context = "\n\n".join(relevant_pairs)
    print(f"[DEBUG] Generated context length: {len(context)}")
    return context

def answer_question(query: str, business_id: str) -> str:
    """Generate answer using RAG"""
    try:
        # Get business info for additional context
        business = Business.objects.get(business_id=business_id)
        business_context = (
            f"Business Name: {business.business_name}\n"
            f"Category: {business.category}\n"
            f"Location: {business.address}\n"
        )
        
        # Get relevant FAQ context
        faq_context = get_relevant_context(query, business_id)
        
        # Combine contexts
        full_context = f"{business_context}\n\nRelevant Information:\n{faq_context}"
        
        if not faq_context:
            return (
                "I don't have enough specific information to answer that question. "
                "However, I can help you with general inquiries about the business."
            )
        
        # Generate response using combined context
        response = generate_response(query, full_context)
        return response
        
    except Business.DoesNotExist:
        return "I couldn't find information for this business."
    except Exception as e:
        print(f"[ERROR] Failed to answer question: {str(e)}")
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
