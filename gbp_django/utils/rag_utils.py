from typing import List, Dict, Any, Optional
import numpy as np
from django.db.models import Q
from pgvector.django import CosineDistance
from ..models import Business, FAQ
from .embeddings import generate_embedding, generate_response

def search_knowledge_base(query: str, business_id: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """Enhanced knowledge base search with metadata and multiple similarity metrics"""
    print(f"\n[DEBUG] Searching knowledge base for query: {query}")
    print(f"[DEBUG] Business ID: {business_id}, Top K: {top_k}")
    
    # Generate embedding for query
    query_embedding = generate_embedding(query)
    if not query_embedding:
        print("[ERROR] Failed to generate query embedding")
        return []
        
    try:
        # Get business and related FAQs using both cosine and L2 distance
        faqs = FAQ.objects.filter(
            business_id=business_id,
            deleted_at__isnull=True  # Exclude deleted documents
        ).annotate(
            cosine_similarity=CosineDistance('embedding', query_embedding),
            l2_distance=L2Distance('embedding', query_embedding)
        ).filter(
            embedding__isnull=False
        ).order_by('cosine_similarity')[:top_k]
        
        print(f"[DEBUG] Found {faqs.count()} relevant FAQs")
        
        results = []
        for faq in faqs:
            cosine_sim = 1 - float(faq.cosine_similarity)  # Convert distance to similarity
            l2_sim = 1 / (1 + float(faq.l2_distance))  # Normalize L2 distance to 0-1
            
            # Calculate combined similarity score
            combined_score = (cosine_sim * 0.7) + (l2_sim * 0.3)
            
            print(f"[DEBUG] FAQ: {faq.question[:50]}...")
            print(f"[DEBUG] Cosine Similarity: {cosine_sim:.3f}")
            print(f"[DEBUG] L2 Similarity: {l2_sim:.3f}")
            print(f"[DEBUG] Combined Score: {combined_score:.3f}")
            
            results.append({
                'question': faq.question,
                'answer': faq.answer,
                'similarity': combined_score,
                'metadata': {
                    'cosine_similarity': cosine_sim,
                    'l2_similarity': l2_sim,
                    'file_type': faq.file_type,
                    'created_at': faq.created_at.isoformat(),
                    'source': faq.file_path.split('/')[-1] if faq.file_path else 'Direct Input'
                }
            })
        
        return sorted(results, key=lambda x: x['similarity'], reverse=True)
        
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
    """Generate answer using enhanced RAG with multiple knowledge sources"""
    try:
        # Get business info
        business = Business.objects.get(business_id=business_id)
        
        # Build comprehensive business context
        business_context = (
            f"Business Profile:\n"
            f"Name: {business.business_name}\n"
            f"Category: {business.category}\n"
            f"Location: {business.address}\n"
            f"Website: {business.website_url}\n"
            f"Phone: {business.phone_number}\n"
            f"Verification Status: {'Verified' if business.is_verified else 'Not Verified'}\n"
            f"Profile Completion: {business.calculate_profile_completion()}%\n"
            f"\nAutomation Settings:\n"
            f"Posts: {business.posts_automation}\n"
            f"Reviews: {business.reviews_automation}\n"
            f"Q&A: {business.qa_automation}\n"
        )
        
        # Get relevant contexts with similarity scores
        faq_results = search_knowledge_base(query, business_id, top_k=5)
        
        if not faq_results:
            # No relevant documents found - use general business context
            system_prompt = (
                "You are an AI assistant for a business. "
                "While I don't have specific documentation about this topic, "
                "I can help with general business information and questions.\n\n"
                f"Business Context:\n{business_context}"
            )
            return generate_response(query, system_prompt)
            
        # Build context from relevant documents
        doc_contexts = []
        for result in faq_results:
            similarity = result['similarity']
            if similarity >= 0.7:  # High relevance
                doc_contexts.append(f"[High Relevance] {result['question']}\n{result['answer']}")
            elif similarity >= 0.5:  # Moderate relevance
                doc_contexts.append(f"[Related] {result['question']}\n{result['answer']}")
                
        # Combine all contexts
        full_context = (
            f"{business_context}\n\n"
            f"Relevant Information:\n"
            f"{'-' * 40}\n"
            f"{'\n'.join(doc_contexts)}"
        )
        
        # Generate response with enhanced context
        system_prompt = (
            "You are an AI assistant for a business. Use the following context to provide "
            "accurate and helpful responses. If you're not completely sure about something, "
            "acknowledge the uncertainty while providing the best available information.\n\n"
            f"Context:\n{full_context}"
        )
        
        response = generate_response(query, system_prompt)
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
