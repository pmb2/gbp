from typing import List, Dict, Any, Optional
import numpy as np
from django.db.models import Q
from pgvector.django import CosineDistance, L2Distance
from ..models import Business, FAQ
from .embeddings import generate_embedding, generate_response

def search_knowledge_base(query: str, business_id: str, top_k: int = 8, min_similarity: float = 0.4) -> List[Dict[str, Any]]:
    """Enhanced knowledge base search with comprehensive similarity scoring and metadata"""
    print(f"\n[DEBUG] Searching knowledge base for query: {query}")
    print(f"[DEBUG] Business ID: {business_id}, Top K: {top_k}")
    print(f"[DEBUG] Minimum similarity threshold: {min_similarity}")
    
    # Generate multiple query embeddings with different prompts
    query_embeddings = []
    prompts = [
        query,  # Original query
        f"Information about: {query}",  # Broader context
        f"Details regarding: {query}",  # Alternative phrasing
        f"Find content related to: {query}"  # Semantic search
    ]
    
    for prompt in prompts:
        embedding = generate_embedding(prompt)
        if embedding:
            query_embeddings.append(embedding)
            print(f"[DEBUG] Generated embedding for prompt: {prompt[:50]}...")
    
    if not query_embeddings:
        print("[ERROR] Failed to generate any query embeddings")
        return []
        
    try:
        # Get business and validate existence
        try:
            business = Business.objects.get(business_id=business_id)
            print(f"[DEBUG] Found business: {business.business_name}")
        except Business.DoesNotExist:
            print(f"[ERROR] Business not found with ID: {business_id}")
            return []
        
        # Get related FAQs using multiple similarity metrics and embeddings
        print("[DEBUG] Querying knowledge base with enhanced vector similarity search...")
        all_results = []
        
        for query_embedding in query_embeddings:
            faqs = FAQ.objects.filter(
                business=business,
                deleted_at__isnull=True,
                embedding__isnull=False
            ).annotate(
                cosine_similarity=CosineDistance('embedding', query_embedding),
                l2_distance=L2Distance('embedding', query_embedding)
            ).order_by('cosine_similarity')[:top_k * 2]
            
            all_results.extend(faqs)
        
        print(f"[DEBUG] Retrieved {len(all_results)} total candidate FAQs")
        
        # Deduplicate results while keeping highest scores
        seen_ids = set()
        unique_results = []
        for faq in all_results:
            if faq.id not in seen_ids:
                seen_ids.add(faq.id)
                unique_results.append(faq)
        
        results = []
        for faq in unique_results:
            # Calculate enhanced similarity scores
            cosine_sim = 1 - float(faq.cosine_similarity)
            l2_sim = 1 / (1 + float(faq.l2_distance))
            
            # Content-based scoring factors
            text_length = len(faq.question) + len(faq.answer)
            length_bonus = min(1.2, max(0.8, text_length / 1000))  # Favor longer, more detailed content
            
            # Term matching score
            query_terms = set(query.lower().split())
            content_terms = set((faq.question + " " + faq.answer).lower().split())
            term_overlap = len(query_terms & content_terms) / len(query_terms) if query_terms else 0
            
            # Semantic relevance weights
            semantic_weight = 0.5  # Cosine similarity
            structural_weight = 0.3  # L2 distance
            term_weight = 0.2  # Term matching
            
            # Calculate comprehensive score
            combined_score = (
                (cosine_sim * semantic_weight) +
                (l2_sim * structural_weight) +
                (term_overlap * term_weight)
            ) * length_bonus
            
            # Apply additional relevance boosting
            if any(term.lower() in faq.question.lower() for term in query.split()):
                combined_score *= 1.3  # Higher boost for question matches
            
            if any(term.lower() in faq.answer.lower() for term in query.split()):
                combined_score *= 1.2  # Boost for answer matches
            
            if combined_score >= min_similarity:
                print(f"\n[DEBUG] Found relevant FAQ:")
                print(f"Question: {faq.question[:100]}...")
                print(f"Answer length: {len(faq.answer)} chars")
                print(f"Semantic similarity: {cosine_sim:.3f}")
                print(f"Structural similarity: {l2_sim:.3f}")
                print(f"Length bonus: {length_bonus:.3f}")
                print(f"Final score: {combined_score:.3f}")
                
                results.append({
                    'question': faq.question,
                    'answer': faq.answer,
                    'similarity': combined_score,
                    'metadata': {
                        'cosine_similarity': f"{cosine_sim:.3f}",
                        'l2_similarity': f"{l2_sim:.3f}",
                        'file_type': faq.file_type,
                        'created_at': faq.created_at.isoformat(),
                        'source': faq.file_path.split('/')[-1] if faq.file_path else 'Direct Input',
                        'length': text_length,
                        'confidence': f"{combined_score:.1%}",
                        'relevance_boost': 'Yes' if combined_score > min_similarity * 1.2 else 'No'
                    }
                })
            else:
                print(f"[DEBUG] Skipping FAQ (score too low: {combined_score:.3f})")
        
        # Return top K results after reranking
        return sorted(results, key=lambda x: x['similarity'], reverse=True)[:top_k]
        
    except Exception as e:
        print(f"[ERROR] Failed to search knowledge base: {str(e)}")
        return []

def get_relevant_context(query: str, business_id: str, min_similarity: float = 0.6) -> str:
    """Get relevant context from knowledge base with enhanced formatting and metadata"""
    print(f"\n[DEBUG] Getting relevant context for query: {query}")
    results = search_knowledge_base(query, business_id, min_similarity=min_similarity)
    
    if not results:
        print("[DEBUG] No relevant context found in knowledge base")
        return ""
    
    print(f"[DEBUG] Building context from {len(results)} relevant results")
    
    # Build comprehensive context with detailed metadata
    context_parts = []
    for i, result in enumerate(results, 1):
        metadata = result['metadata']
        
        # Format context with rich metadata
        context_parts.append(
            f"[Context Block {i}]\n"
            f"Source: {metadata['source']}\n"
            f"Confidence: {metadata['confidence']}\n"
            f"Semantic Similarity: {metadata['cosine_similarity']}\n"
            f"Structural Match: {metadata['l2_similarity']}\n"
            f"Relevance Boost: {metadata['relevance_boost']}\n"
            f"Created: {metadata['created_at']}\n"
            f"Length: {metadata['length']} chars\n"
            f"\nQuestion: {result['question']}\n"
            f"Answer: {result['answer']}\n"
            f"{'='*50}\n"
        )
    
    if not context_parts:
        return ""
        
    context = "\n".join(context_parts)
    print(f"[DEBUG] Generated context length: {len(context)}")
    return context

def answer_question(query: str, business_id: str, chat_history: List[Dict[str, str]] = None) -> str:
    """Generate answer using enhanced RAG with chat history and memory"""
    try:
        print("\n[DEBUG] answer_question called with:")
        print(f"[DEBUG] Query: {query}")
        print(f"[DEBUG] Business ID: {business_id}")
        print(f"[DEBUG] Chat history length: {len(chat_history) if chat_history else 0}")

        # Get business info
        try:
            business = Business.objects.get(business_id=business_id)
            print(f"[DEBUG] Found business:")
            print(f"[DEBUG] - ID: {business.id}")
            print(f"[DEBUG] - Business ID: {business.business_id}")
            print(f"[DEBUG] - Name: {business.business_name}")
            print(f"[DEBUG] - User ID: {business.user_id}")
        except Business.DoesNotExist:
            print(f"[ERROR] No business found with ID: {business_id}")
            return "Business not found"

        # Store chat history as embeddings
        if chat_history:
            print("[DEBUG] Processing chat history for embeddings...")
            for msg in chat_history:
                try:
                    # Create FAQ entry for each message pair
                    if msg['role'] == 'user':
                        question = msg['content']
                        # Find corresponding assistant response
                        idx = chat_history.index(msg)
                        if idx + 1 < len(chat_history) and chat_history[idx + 1]['role'] == 'assistant':
                            answer = chat_history[idx + 1]['content']
                            add_to_knowledge_base(business_id, question, answer)
                            print(f"[DEBUG] Added Q&A to knowledge base: Q: {question[:50]}...")
                except Exception as e:
                    print(f"[WARNING] Failed to add chat history to knowledge base: {str(e)}")
        
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

        # Get relevant knowledge base entries
        print("[DEBUG] Searching knowledge base for relevant context...")
        faq_results = search_knowledge_base(query, business_id, top_k=5)
        
        knowledge_context = []
        if faq_results:
            print(f"[DEBUG] Found {len(faq_results)} relevant knowledge base entries")
            for result in faq_results:
                confidence = float(result['metadata']['confidence'].strip('%')) / 100
                source = result['metadata']['source']
                
                if confidence >= 0.8:
                    prefix = "🟢 [High Confidence]"
                elif confidence >= 0.6:
                    prefix = "🟡 [Moderate Confidence]"
                else:
                    prefix = "🔴 [Low Confidence]"
                    
                entry = (
                    f"{prefix} Source: {source}\n"
                    f"Q: {result['question']}\n"
                    f"A: {result['answer']}\n"
                    f"---"
                )
                knowledge_context.append(entry)
                print(f"[DEBUG] Added context from {source} with confidence {confidence:.2%}")
        else:
            print("[DEBUG] No relevant knowledge base entries found")
        
        # Combine all contexts with clear sections
        full_context = (
            f"{business_context}\n\n"
            f"📚 Knowledge Base Context:\n"
            f"{'-' * 40}\n"
            f"{''.join(knowledge_context) if knowledge_context else 'No specific documentation found for this query.'}\n\n"
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
        print("[DEBUG] Context sections:", full_context.count('---'))
        
        # Generate response using chat history
        response = generate_response(query, full_context, chat_history)
        
        # Store the interaction in chat history
        if chat_history is not None:
            chat_history.append({'role': 'user', 'content': query})
            chat_history.append({'role': 'assistant', 'content': response})
        
        # Add source attribution if relevant documents were found
        if knowledge_context:
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
