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
        # Example model names—adjust for your Groq account
        self.model_name = "llama-3.3-70b-versatile"
        self.embedding_model = "text-embedding-3-small"  # Not currently used here, we do embedding fallback

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embeddings, *primarily* with Ollama,
        *secondarily* with OpenAI, and finally a simple fallback.
        """
        try:
            # 1) If Ollama is enabled, use it for embeddings
            if settings.OLLAMA_ENABLED:
                ollama_model = OllamaModel()
                emb = ollama_model.generate_embedding(text)
                if emb:
                    return emb

            # 2) Otherwise, if OpenAI is available, use it
            if settings.OPENAI_API_KEY:
                openai_model = OpenAIModel()
                emb = openai_model.generate_embedding(text)
                if emb:
                    return emb

            # 3) Final fallback: simple numeric encoding of characters
            logger.warning("No embedding provider configured - falling back to simple text encoding")
            return [float(ord(c)) for c in text[:1536]] + [0.0] * (1536 - len(text))

        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            return None

    def _prepare_messages(self, query: str, context: str, chat_history: Optional[List[Dict[str, str]]] = None) -> List[
        Dict[str, str]]:
        """Prepare messages array for LLM input with memory summaries."""
        memory_summary = []
        formatted_history = []

        if chat_history:
            # Summarize recent messages
            current_topic = []
            for msg in chat_history[-10:]:  # Summarize up to last 10 messages
                current_topic.append(msg['content'])
                if len(current_topic) >= 3:  # Summarize every 3 messages
                    summary = f"• Previous discussion about: {' '.join(current_topic)[:100]}..."
                    memory_summary.append(summary)
                    current_topic = []
            if current_topic:
                summary = f"• Recent exchange about: {' '.join(current_topic)[:100]}..."
                memory_summary.append(summary)

            # Keep last 5 messages verbatim
            formatted_history = [
                {'role': m['role'], 'content': m['content']}
                for m in chat_history[-5:]
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

        messages = [{'role': 'system', 'content': system_prompt}]
        if formatted_history:
            messages.extend(formatted_history)
        messages.append({'role': 'user', 'content': query})

        return messages

    def generate_response(self, query: str, context: str, chat_history: Optional[List[Dict[str, str]]] = None) -> str:
        """
        Generate a response primarily with Groq,
        then fall back to Ollama, then to OpenAI if needed.
        """
        try:
            # Attempt Groq
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

            # 1) Fall back to Ollama if enabled
            if settings.OLLAMA_ENABLED:
                try:
                    ollama_model = OllamaModel()
                    fallback_resp = ollama_model.generate_response(query, context, chat_history)
                    if fallback_resp:
                        return fallback_resp
                except Exception as ollama_ex:
                    logger.error(f"Ollama fallback failed: {str(ollama_ex)}")

            # 2) If Ollama not available or fails, try OpenAI
            if settings.OPENAI_API_KEY:
                try:
                    openai_model = OpenAIModel()
                    fallback_resp = openai_model.generate_response(query, context, chat_history)
                    if fallback_resp:
                        return fallback_resp
                except Exception as openai_ex:
                    logger.error(f"OpenAI fallback failed: {str(openai_ex)}")

            # 3) Final fallback: simple error message
            return f"I'm having trouble generating a response right now. Please try again later. (Error: {str(e)})"


class OllamaModel(LLMInterface):
    """
    Uses a local Ollama server for both LLM responses (via `phi4`) and embeddings (via `nomic-embed-text`).
    """

    def __init__(self):
        self.base_url = "http://localhost:11434/api"
        self.embedding_model = "nomic-embed-text"
        self.llm_model = "phi4"

    def _prepare_messages(self, query: str, context: str, chat_history: Optional[List[Dict[str, str]]] = None) -> List[
        Dict[str, str]]:
        """Replicate the memory-summary logic for consistency with GroqModel."""
        memory_summary = []
        formatted_history = []

        if chat_history:
            current_topic = []
            for msg in chat_history[-10:]:
                current_topic.append(msg['content'])
                if len(current_topic) >= 3:
                    summary = f"• Previous discussion about: {' '.join(current_topic)[:100]}..."
                    memory_summary.append(summary)
                    current_topic = []
            if current_topic:
                summary = f"• Recent exchange about: {' '.join(current_topic)[:100]}..."
                memory_summary.append(summary)

            formatted_history = [
                {'role': m['role'], 'content': m['content']}
                for m in chat_history[-5:]
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

        messages = [{'role': 'system', 'content': system_prompt}]
        if formatted_history:
            messages.extend(formatted_history)
        messages.append({'role': 'user', 'content': query})

        return messages

    def generate_response(self, query: str, context: str, chat_history: Optional[List[Dict[str, str]]] = None) -> str:
        """Use Ollama's local LLM (`phi4`) for chat responses."""
        try:
            messages = self._prepare_messages(query, context, chat_history)
            start_time = time.time()

            # Attempt the /chat endpoint first
            response = requests.post(
                f"{self.base_url}/chat",
                json={
                    "model": self.llm_model,
                    "messages": messages,
                    "stream": False
                },
                timeout=30
            )

            # If /chat endpoint is not found, try /generate
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

            # Ollama can return "message" or "response" fields, depending on version
            response_data = response.json()
            if "message" in response_data:
                return response_data["message"]["content"].strip()
            elif "response" in response_data:
                return response_data["response"].strip()
            else:
                return str(response_data).strip()

        except Exception as e:
            logger.error(f"Error generating response with Ollama: {str(e)}")
            return f"I'm having trouble generating a response right now. Please try again later. (Error: {str(e)})"

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Use Ollama's `nomic-embed-text` model to generate a 1536-dim embedding (if possible)."""
        try:
            text = text.strip().replace('\n', ' ')
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

            # Attempt to unify to 1536 dims if needed
            if len(embedding) == 1536:
                return embedding
            elif len(embedding) == 768:
                return embedding * 2  # Double to reach 1536
            else:
                logger.warning(f"Unexpected embedding dimension: {len(embedding)}")
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
        """
        Use OpenAI's ChatCompletion to generate a response.
        Note that this is the *last* fallback for LLM usage.
        """
        try:
            messages = [{"role": "system", "content": context}]

            if chat_history:
                for msg in chat_history[-5:]:
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
        """Use OpenAI to generate a 1536-dim text embedding."""
        try:
            text = text.strip().replace('\n', ' ')
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
    """
    Factory function to get the configured LLM model:
      1) Groq if GROQ_API_KEY is set,
      2) otherwise Ollama if OLLAMA_ENABLED,
      3) else OpenAI if OPENAI_API_KEY,
      4) else raise error.
    """
    # 1) Try Groq
    if getattr(settings, 'GROQ_API_KEY', None):
        try:
            return GroqModel()
        except Exception as e:
            logger.warning(f"Failed to initialize Groq: {str(e)}")

    # 2) If Groq not available, try Ollama
    if getattr(settings, 'OLLAMA_ENABLED', False):
        try:
            return OllamaModel()
        except Exception as e:
            logger.warning(f"Failed to initialize Ollama: {str(e)}")

    # 3) If Ollama not available, try OpenAI
    if getattr(settings, 'OPENAI_API_KEY', None):
        return OpenAIModel()

    raise ValueError("No valid LLM configuration found. Check your settings.")


def get_embedding_model() -> LLMInterface:
    """
    Factory function to get the configured embedding model:
      1) Ollama if OLLAMA_ENABLED,
      2) otherwise OpenAI if OPENAI_API_KEY,
      3) else raise error.
    """
    # 1) Try Ollama for embeddings
    if getattr(settings, 'OLLAMA_ENABLED', False):
        try:
            return OllamaModel()
        except Exception as e:
            logger.warning(f"Failed to initialize Ollama for embeddings: {str(e)}")

    # 2) Otherwise, try OpenAI
    if getattr(settings, 'OPENAI_API_KEY', None):
        return OpenAIModel()

    raise ValueError("No valid embedding configuration found. Check your settings.")
