from abc import ABC, abstractmethod
import time
from typing import List, Dict, Optional
import requests
import openai
from django.conf import settings
from groq import Groq
import logging

logger = logging.getLogger(__name__)

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
        self.model_name = "llama-3.3-70b-versatile"
        self.embedding_model = "text-embedding-3-small"  # Default embedding model
        
    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embeddings using Groq's API with OpenAI fallback"""
        try:
            # First try OpenAI if configured
            if settings.OPENAI_API_KEY:
                openai_model = OpenAIModel()
                return openai_model.generate_embedding(text)
            
            # If OpenAI not available, try Ollama
            if settings.OLLAMA_ENABLED:
                ollama_model = OllamaModel()
                return ollama_model.generate_embedding(text)
                
            logger.warning("No embedding provider configured - falling back to simple text encoding")
            # Fallback to simple text encoding if no providers available
            return [float(ord(c)) for c in text[:1536]] + [0.0] * (1536 - len(text))
            
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            return None
        
    def _prepare_messages(self, query: str, context: str, chat_history: Optional[List[Dict[str, str]]] = None) -> List[Dict[str, str]]:
        """Prepare messages array for LLM input"""
        # Format chat history and summarize memories
        memory_summary = []
        formatted_history = []
        
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

        # Create system prompt with context and memory summaries
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
        
        return messages

    def generate_response(self, query: str, context: str, chat_history: Optional[List[Dict[str, str]]] = None) -> str:
        try:
            # First try Groq
            messages = self._prepare_messages(query, context, chat_history)
            
            start_time = time.time()
            chat_completion = self.client.chat.completions.create(
                messages=messages,
                model=self.model_name,
                temperature=0.7,
                max_tokens=1000,
                top_p=0.9,
                stream=False
            )
            latency = time.time() - start_time
            
            logger.info(f"Groq response generated in {latency:.2f}s using {self.model_name}")
            return chat_completion.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error generating response with Groq: {str(e)}")
            
            # Fallback to OpenAI if configured
            if settings.OPENAI_API_KEY:
                try:
                    openai_model = OpenAIModel()
                    return openai_model.generate_response(query, context, chat_history)
                except Exception as e:
                    logger.error(f"OpenAI fallback failed: {str(e)}")
            
            # Final fallback to Ollama if enabled
            if settings.OLLAMA_ENABLED:
                try:
                    ollama_model = OllamaModel()
                    return ollama_model.generate_response(query, context, chat_history)
                except Exception as e:
                    logger.error(f"Ollama fallback failed: {str(e)}")
            
            # If all else fails, return a simple response
            return f"I'm having trouble generating a response right now. Please try again later. (Error: {str(e)})"

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
            
            start_time = time.time()
            chat_completion = self.client.chat.completions.create(
                messages=messages,
                model=self.model_name,
                temperature=0.7,
                max_tokens=1000,
                top_p=0.9,
                stream=False
            )
            latency = time.time() - start_time
            
            logger.info(f"Groq response generated in {latency:.2f}s using {self.model_name}")
            return chat_completion.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error generating response with Groq: {str(e)}")
            return None  # Return None to trigger fallback

class OllamaModel(LLMInterface):
    def __init__(self):
        self.base_url = "http://localhost:11434/api"
        self.embedding_model = "nomic-embed-text"
        self.llm_model = "phi4"
        
    def generate_response(self, query: str, context: str, chat_history: Optional[List[Dict[str, str]]] = None) -> str:
        try:
            # First try the chat endpoint
            messages = self._prepare_messages(query, context, chat_history)
            
            start_time = time.time()
            response = requests.post(
                f"{self.base_url}/chat",
                json={
                    "model": self.llm_model,
                    "messages": messages,
                    "stream": False
                },
                timeout=30
            )
            
            # If chat endpoint fails, try the generate endpoint
            if response.status_code == 404:
                response = requests.post(
                    f"{self.base_url}/generate",
                    json={
                        "model": self.llm_model,
                        "prompt": query,
                        "context": context,
                        "stream": False
                    },
                    timeout=30
                )
                
            response.raise_for_status()
            latency = time.time() - start_time
            
            logger.info(f"Ollama response generated in {latency:.2f}s using {self.llm_model}")
            
            # Handle different response formats
            response_data = response.json()
            if "message" in response_data:
                return response_data["message"]["content"].strip()
            elif "response" in response_data:
                return response_data["response"].strip()
            else:
                return str(response_data).strip()
            
        except Exception as e:
            logger.error(f"Error generating response with Ollama: {str(e)}")
            # Fallback to simple response if all else fails
            return f"I'm having trouble generating a response right now. Please try again later. (Error: {str(e)})"
    
    def generate_embedding(self, text: str) -> Optional[List[float]]:
        try:
            text = text.strip().replace('\n', ' ')
            
            # If text is too long, take first 8000 chars
            if len(text) > 8000:
                text = text[:8000]
            
            start_time = time.time()
            response = requests.post(
                f"{self.base_url}/embeddings",
                json={
                    "model": self.embedding_model,
                    "prompt": text,
                    "options": {
                        "temperature": 0,
                        "num_ctx": 8192
                    }
                },
                timeout=30
            )
            response.raise_for_status()
            
            embedding = response.json()['embedding']
            latency = time.time() - start_time
            
            logger.info(f"Ollama embedding generated in {latency:.2f}s using {self.embedding_model}")
            
            # Handle different embedding dimensions
            if len(embedding) == 1536:
                return embedding
            elif len(embedding) == 768:
                return embedding * 2  # Repeat to get 1536 dims
            else:
                logger.warning(f"Invalid embedding dimensions: {len(embedding)}")
                return None
                
        except Exception as e:
            logger.error(f"Error generating embedding with Ollama: {str(e)}")
            return None

class OpenAIModel(LLMInterface):
    def __init__(self):
        self.embedding_model = "text-embedding-3-small"
        self.llm_model = "gpt-3.5-turbo"
        openai.api_key = settings.OPENAI_API_KEY
        
    def generate_response(self, query: str, context: str, chat_history: Optional[List[Dict[str, str]]] = None) -> str:
        try:
            messages = [{"role": "system", "content": context}]
            
            if chat_history:
                for msg in chat_history[-5:]:  # Last 5 messages
                    messages.append({"role": msg["role"], "content": msg["content"]})
                    
            messages.append({"role": "user", "content": query})
            
            start_time = time.time()
            response = openai.ChatCompletion.create(
                model=self.llm_model,
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
            latency = time.time() - start_time
            
            logger.info(f"OpenAI response generated in {latency:.2f}s using {self.llm_model}")
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error generating response with OpenAI: {str(e)}")
            return None
    
    def generate_embedding(self, text: str) -> Optional[List[float]]:
        try:
            text = text.strip().replace('\n', ' ')
            
            # If text is too long, take first 8000 chars
            if len(text) > 8000:
                text = text[:8000]
            
            start_time = time.time()
            response = openai.Embedding.create(
                input=text,
                model=self.embedding_model
            )
            latency = time.time() - start_time
            
            logger.info(f"OpenAI embedding generated in {latency:.2f}s using {self.embedding_model}")
            return response['data'][0]['embedding']
                
        except Exception as e:
            logger.error(f"Error generating embedding with OpenAI: {str(e)}")
            return None

def get_llm_model() -> LLMInterface:
    """Factory function to get the configured LLM model with fallback"""
    try:
        # Try Groq first
        if settings.GROQ_API_KEY:
            return GroqModel()
    except Exception as e:
        logger.warning(f"Failed to initialize Groq: {str(e)}")
    
    # Fallback to Ollama
    try:
        if settings.OLLAMA_ENABLED:
            return OllamaModel()
    except Exception as e:
        logger.warning(f"Failed to initialize Ollama: {str(e)}")
    
    # Final fallback to OpenAI
    if settings.OPENAI_API_KEY:
        return OpenAIModel()
    
    raise ValueError("No valid LLM configuration found")

def get_embedding_model() -> LLMInterface:
    """Factory function to get the configured embedding model with fallback"""
    try:
        # Try Ollama first
        if settings.OLLAMA_ENABLED:
            return OllamaModel()
    except Exception as e:
        logger.warning(f"Failed to initialize Ollama for embeddings: {str(e)}")
    
    # Fallback to OpenAI
    if settings.OPENAI_API_KEY:
        return OpenAIModel()
    
    raise ValueError("No valid embedding configuration found")
