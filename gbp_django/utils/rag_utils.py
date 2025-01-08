from typing import List, Dict, Any, Optional
import numpy as np
from django.db.models import Q
from pgvector.django import CosineDistance, L2Distance
from ..models import Business, FAQ
from .embeddings import generate_embedding, generate_response

def search_knowledge_base(query: str, business_id: str, top_k: int = 3, min_similarity: float = 0.7) -> List[Dict[str, Any]]:
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
            deleted_at__isnull=True,  # Exclude deleted documents
            embedding__isnull=False  # Ensure embedding exists
        ).annotate(
            cosine_similarity=CosineDistance('embedding', query_embedding),
            l2_distance=L2Distance('embedding', query_embedding)
        ).order_by('cosine_similarity')[:top_k * 2]  # Get more candidates for reranking
        
        print(f"[DEBUG] Found {faqs.count()} candidate FAQs")
        
        results = []
        for faq in faqs:
            # Calculate multiple similarity scores
            cosine_sim = 1 - float(faq.cosine_similarity)  # Convert distance to similarity
            l2_sim = 1 / (1 + float(faq.l2_distance))  # Normalize L2 distance to 0-1
            
            # Enhanced scoring with weighted combination
            combined_score = (cosine_sim * 0.6) + (l2_sim * 0.4)
            
            # Apply length normalization
            text_length = len(faq.question) + len(faq.answer)
            length_penalty = min(1.0, 1000 / max(500, text_length))
            final_score = combined_score * length_penalty
            
            if final_score >= min_similarity:
                print(f"[DEBUG] FAQ: {faq.question[:50]}...")
                print(f"[DEBUG] Cosine Similarity: {cosine_sim:.3f}")
                print(f"[DEBUG] L2 Similarity: {l2_sim:.3f}")
                print(f"[DEBUG] Final Score: {final_score:.3f}")
                
                results.append({
                    'question': faq.question,
                    'answer': faq.answer,
                    'similarity': final_score,
                    'metadata': {
                        'cosine_similarity': cosine_sim,
                        'l2_similarity': l2_sim,
                        'file_type': faq.file_type,
                        'created_at': faq.created_at.isoformat(),
                        'source': faq.file_path.split('/')[-1] if faq.file_path else 'Direct Input',
                        'length': text_length,
                        'confidence': f"{final_score:.1%}"
                    }
                })
        
        # Return top K results after reranking
        return sorted(results, key=lambda x: x['similarity'], reverse=True)[:top_k]
        
    except Exception as e:
        print(f"[ERROR] Failed to search knowledge base: {str(e)}")
        return []

def get_relevant_context(query: str, business_id: str, min_similarity: float = 0.7) -> str:
    """Get relevant context from knowledge base with enhanced formatting"""
    results = search_knowledge_base(query, business_id, min_similarity=min_similarity)
    if not results:
        return ""
    
    # Build context with metadata and confidence scores
    context_parts = []
    for result in results:
        metadata = result['metadata']
        confidence = metadata['confidence']
        source = metadata['source']
        
        context_parts.append(
            f"[Source: {source} | Confidence: {confidence}]\n"
            f"Q: {result['question']}\n"
            f"A: {result['answer']}\n"
            f"---"
        )
    
    if not context_parts:
        return ""
        
    context = "\n".join(context_parts)
    print(f"[DEBUG] Generated context length: {len(context)}")
    return context

def answer_question(query: str, business_id: str, chat_history: List[Dict[str, str]] = None) -> str:
    """Generate answer using enhanced RAG with chat history and memory"""
    try:
        # Get business info
        business = Business.objects.get(business_id=business_id)
        
        # Build comprehensive business context
        business_context = (
            f"🏢 Business Profile:\n"
            f"• Name: {business.business_name}\n"
            f"• Category: {business.category}\n"
            f"• Location: {business.address}\n"
            f"• Website: {business.website_url}\n"
            f"• Phone: {business.phone_number}\n"
            f"• Status: {'✅ Verified' if business.is_verified else '⚠️ Not Verified'}\n"
            f"• Profile Completion: {business.calculate_profile_completion()}%\n"
            f"\n⚙️ Automation Settings:\n"
            f"• Posts: {business.posts_automation}\n"
            f"• Reviews: {business.reviews_automation}\n"
            f"• Q&A: {business.qa_automation}\n"
        )
        
        # Get relevant contexts with enhanced metadata
        faq_results = search_knowledge_base(query, business_id, top_k=5)
        
        # Build context from relevant documents with confidence levels
        doc_contexts = []
        if faq_results:
            for result in faq_results:
                metadata = result['metadata']
                confidence = float(metadata['confidence'].strip('%')) / 100
                source = metadata['source']
                
                if confidence >= 0.8:
                    prefix = "🟢 [High Confidence]"
                elif confidence >= 0.6:
                    prefix = "🟡 [Moderate Confidence]"
                else:
                    prefix = "🔴 [Low Confidence]"
                    
                doc_contexts.append(
                    f"{prefix} Source: {source}\n"
                    f"Q: {result['question']}\n"
                    f"A: {result['answer']}\n"
                    f"---"
                )
        
        # Combine all contexts
        full_context = (
            f"{business_context}\n\n"
            f"📚 Relevant Information:\n"
            f"{'-' * 40}\n"
            f"{'\n'.join(doc_contexts) if doc_contexts else 'No specific documentation found for this query.'}"
        )
        
        # Generate response using chat history
        response = generate_response(query, full_context, chat_history)
        
        # Store the interaction in chat history
        if chat_history is not None:
            chat_history.append({'role': 'user', 'content': query})
            chat_history.append({'role': 'assistant', 'content': response})
        
        # Add source attribution if relevant documents were found
        if doc_contexts:
            response += "\n\n[Response based on business documentation and profile information]"
        
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
