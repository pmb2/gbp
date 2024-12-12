from typing import List, Dict, Any
import numpy as np
from django.db.models import Q
from ..models import Business, FAQ
from .embeddings import generate_embedding, generate_response

def search_knowledge_base(query: str, business_id: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """Search knowledge base using vector similarity"""
    print(f"\n[DEBUG] Searching knowledge base for query: {query}")
    print(f"[DEBUG] Business ID: {business_id}")
    
    # Generate embedding for query
    query_embedding = generate_embedding(query)
    if not query_embedding:
        print("[ERROR] Failed to generate query embedding")
        return []
        
    try:
        # Get business and related FAQs
        business = Business.objects.get(business_id=business_id)
        faqs = FAQ.objects.filter(business=business)
        print(f"[DEBUG] Found {faqs.count()} FAQs for business")
    
        # Calculate similarities
        similarities = []
        for faq in faqs:
            if faq.embedding:
                try:
                    similarity = np.dot(query_embedding, faq.embedding) / (
                        np.linalg.norm(query_embedding) * np.linalg.norm(faq.embedding)
                    )
                    similarities.append((similarity, faq))
                    print(f"[DEBUG] FAQ: {faq.question[:50]}... Similarity: {similarity:.3f}")
                except Exception as e:
                    print(f"[ERROR] Failed to calculate similarity: {str(e)}")
                    continue
    
    # Sort by similarity and get top_k
    similarities.sort(key=lambda x: x[0], reverse=True)
    return [
        {
            'question': faq.question,
            'answer': faq.answer,
            'similarity': float(sim)
        }
        for sim, faq in similarities[:top_k]
    ]

def get_relevant_context(query: str, business_id: str) -> str:
    """Get relevant context from knowledge base"""
    results = search_knowledge_base(query, business_id)
    if not results:
        return ""
        
    # Combine relevant QA pairs into context
    context = "\n\n".join([
        f"Q: {result['question']}\nA: {result['answer']}"
        for result in results
    ])
    return context

def answer_question(query: str, business_id: str) -> str:
    """Generate answer using RAG"""
    # Get relevant context
    context = get_relevant_context(query, business_id)
    if not context:
        return "I don't have enough information to answer that question."
        
    # Generate response using context
    response = generate_response(query, context)
    return response

def add_to_knowledge_base(business_id: str, question: str, answer: str) -> FAQ:
    """Add new QA pair to knowledge base"""
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
    return faq
