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
        # Groq doesn't support embeddings yet, fallback to Ollama
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
                    "model": "phi",
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
        try:
            text = text.strip().replace('\n', ' ')
            
            # If text is too long, take first 8000 chars
            if len(text) > 8000:
                text = text[:8000]
            
            response = requests.post(
                f"{self.base_url}/embeddings",
                json={
                    "model": "nomic-embed-text",
                    "prompt": text,
                    "options": {
                        "temperature": 0,
                        "num_ctx": 8192
                    }
                }
            )
            response.raise_for_status()
            
            embedding = response.json()['embedding']
            
            # Handle different embedding dimensions
            if len(embedding) == 1536:
                return embedding
            elif len(embedding) == 768:
                return embedding * 2  # Repeat to get 1536 dims
            else:
                print(f"[WARNING] Invalid embedding dimensions: {len(embedding)}")
                return None
                
        except Exception as e:
            print(f"Error generating embedding with Ollama: {str(e)}")
            return None

def get_llm_model() -> LLMInterface:
    """Factory function to get the configured LLM model"""
    model_name = getattr(settings, 'LLM_MODEL', 'groq')
    if model_name == 'ollama':
        return OllamaModel()
    return GroqModel()  # Default to Groq
