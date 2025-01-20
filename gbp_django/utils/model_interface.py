from abc import ABC, abstractmethod
import time
from typing import List, Dict, Optional
import requests
from django.conf import settings
from groq import Groq

class LLMInterface(ABC):
    @abstractmethod
    def generate_response(self, query: str, context: str, chat_history: Optional[List[Dict[str, str]]] = None) -> str:
        pass
    
    @abstractmethod
    def generate_embedding(self, text: str) -> Optional[List[float]]:
        pass

class GroqModel(LLMInterface):
    def __init__(self):
        self.client = Groq(api_key=settings.GROQ_API_KEY)
        
    def generate_response(self, query: str, context: str, chat_history: Optional[List[Dict[str, str]]] = None) -> str:
        try:
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
                "When referencing information from documents, maintain the original meaning while presenting it naturally. "
                "If uncertain or if information seems outdated, acknowledge this in your response.\n\n"
                "Guidelines:\n"
                "- Synthesize information from multiple chunks when available\n"
                "- Maintain factual accuracy while being conversational\n"
                "- Cite specific sources when directly referencing information\n"
                "- Acknowledge if information seems incomplete or uncertain\n\n"
                f"Business Context: {context}\n\n"
                f"Memory Summaries:\n" + "\n".join(memory_summary) + "\n\n"
                "Instructions: Provide a helpful response based on the context and history."
            )

            # Prepare messages array
            messages = [{'role': 'system', 'content': system_prompt}]
            if formatted_history:
                messages.extend(formatted_history)
            messages.append({'role': 'user', 'content': query})
            
            chat_completion = self.client.chat.completions.create(
                messages=messages,
                model="llama-3.3-70b-versatile",
                temperature=0.7,
                max_tokens=1000,
                top_p=0.9,
                stream=False
            )
            
            return chat_completion.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error generating response with Groq: {str(e)}")
            return "I apologize, but I'm unable to generate a response at the moment."
            
    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embeddings with better error handling and retries"""
        try:
            # First try Groq's embedding endpoint if available
            response = requests.post(
                "https://api.groq.com/v1/embeddings",
                headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                json={"input": text, "model": "llama2-70b-4096"}
            )
            if response.ok:
                return response.json()['data'][0]['embedding']
        except Exception as e:
            print(f"Groq embedding failed, falling back to Ollama: {str(e)}")
            
        # Fallback to Ollama
        return OllamaModel().generate_embedding(text)

class OllamaModel(LLMInterface):
    def __init__(self):
        self.base_url = "http://localhost:11434/api"
        
    def generate_response(self, query: str, context: str, chat_history: Optional[List[Dict[str, str]]] = None) -> str:
        try:
            # Format context and history
            system_prompt = (
                "You are an AI assistant for a business automation platform. "
                "Use the provided context to give accurate, professional responses.\n\n"
                f"Context: {context}\n\n"
            )
            
            messages = [
                {"role": "system", "content": system_prompt}
            ]
            
            if chat_history:
                for msg in chat_history[-5:]:  # Last 5 messages
                    messages.append({"role": msg["role"], "content": msg["content"]})
                    
            messages.append({"role": "user", "content": query})
            
            response = requests.post(
                f"{self.base_url}/chat",
                json={
                    "model": "phi4",
                    "messages": messages,
                    "stream": False
                }
            )
            response.raise_for_status()
            
            return response.json()["message"]["content"].strip()
            
        except Exception as e:
            print(f"Error generating response with Ollama: {str(e)}")
            return "I apologize, but I'm unable to generate a response at the moment."
    
    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embeddings with better error handling and OpenAI fallback"""
        try:
            text = text.strip().replace('\n', ' ')
            
            # If text is too long, take first 8000 chars
            if len(text) > 8000:
                text = text[:8000]
            
            try:
                # Try to connect to Ollama with a short timeout
                response = requests.post(
                    f"{self.base_url}/api/generate",  # Fixed endpoint
                    json={
                        "model": "nomic-embed-text",
                        "prompt": text,
                        "stream": False,
                        "options": {
                            "temperature": 0,
                            "num_ctx": 8192
                        }
                    },
                    timeout=2  # Short timeout to fail fast if Ollama is down
                )
                response.raise_for_status()
                
                embedding = response.json().get('embedding')
                if not embedding:
                    raise ValueError("No embedding in response")
                
                # Handle different embedding dimensions
                if len(embedding) == 1536:
                    return embedding
                elif len(embedding) == 768:
                    return embedding * 2  # Repeat to get 1536 dims
                else:
                    print(f"[WARNING] Invalid embedding dimensions: {len(embedding)}")
                    raise ValueError("Invalid embedding dimensions")
                    
            except (requests.exceptions.ConnectionError, 
                    requests.exceptions.Timeout,
                    requests.exceptions.HTTPError) as e:
                print(f"Ollama service error, falling back to OpenAI: {str(e)}")
                raise  # Re-raise to trigger fallback
                
            except Exception as e:
                print(f"Error with Ollama embedding: {str(e)}")
                raise  # Re-raise to trigger fallback
                
        except Exception as e:
            # Fall back to OpenAI for embeddings
            try:
                import openai
                openai.api_key = settings.OPENAI_API_KEY
                
                response = openai.Embedding.create(
                    input=text,
                    model="text-embedding-ada-002"
                )
                
                if response and response.data and response.data[0].embedding:
                    return response.data[0].embedding
                    
            except Exception as openai_error:
                print(f"OpenAI fallback failed: {str(openai_error)}")
                # Final fallback to Groq
                return GroqModel().generate_embedding(text)

def get_llm_model() -> LLMInterface:
    """Factory function to get the configured LLM model"""
    model_name = getattr(settings, 'LLM_MODEL', 'groq')
    if model_name == 'ollama':
        return OllamaModel()
    return GroqModel()  # Default to Groq
