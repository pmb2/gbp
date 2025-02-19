from abc import ABC, abstractmethod
import time
from typing import List, Dict, Optional
import requests
import openai
import json
from django.conf import settings
from groq import Groq
import logging
import traceback

logger = logging.getLogger(__name__)


class LLMInterface(ABC):
    @abstractmethod
    def generate_response(self, query: str, context: str, chat_history: Optional[List[Dict[str, str]]] = None) -> str:
        pass

    @abstractmethod
    def generate_embedding(self, text: str) -> Optional[List[float]]:
        pass


class GroqModel(LLMInterface):
    def structured_reasoning(self, pre_prompt: str, prompt: str, max_tokens: int = 2000) -> dict:
        """Execute structured reasoning with pre-prompt and prompt, returning JSON-formatted actions."""
        print(f"\n[COMPLIANCE ENGINE] Initializing reasoning pipeline")
        print(
            f"[COMPLIANCE CONTEXT] Business ID: {prompt.split('business_id: ')[1].split('\n')[0] if 'business_id' in prompt else 'Unknown'}")
        print(f"[MODEL SETUP] Using deepseek-r1-distill-llama-70b-specdec")
        system_msg = {
            "role": "system",
            "content": f"{pre_prompt}\n\nOUTPUT MUST BE VALID JSON FOLLOWING THIS SCHEMA:\n"
                       "{{'reasoning': '...', 'actions': [{{'type': 'update|verify|quarantine|alert|log', "
                       "'target': '...', 'details': '...', 'risk_score': 1-10, 'confidence': 0.0-1.0, "
                       "'eta': 'ISO8601', 'dependencies': [...]}}]}}"
        }
        print(f"[REASONING SYSTEM PROMPT]\n{system_msg['content'][:500]}...")
        print(f"[REASONING USER PROMPT]\n{prompt[:500]}...")
        print(f"[API REQUEST] Initializing Groq API connection")

        user_msg = {
            "role": "user",
            "content": prompt
        }

        print(f"[API REQUEST] Sending payload to Groq API")
        try:
            response = self.client.chat.completions.create(
                model="deepseek-r1-distill-llama-70b-specdec",
                messages=[system_msg, user_msg],
                temperature=0.3,
                max_tokens=max_tokens,
                response_format={"type": "json_object"}
            )
            print(f"[API RESPONSE] Received status {response.status_code}")

            try:
                print(f"[DATA PROCESSING] Parsing JSON response")
                result = json.loads(response.choices[0].message.content)
                print(f"[COMPLIANCE ACTIONS] Generated {len(result.get('actions', []))} actions")
                print(
                    f"[RISK ASSESSMENT] Highest risk score: {max(a.get('risk_score', 0) for a in result.get('actions', []))}")
                return result
            except json.JSONDecodeError as e:
                print(f"[ERROR] JSON parsing failed: {str(e)}")
                print(f"[DEBUG] Raw response: {response.choices[0].message.content[:500]}")
                return {"error": "Failed to parse model response", "raw_response": response.choices[0].message.content}
        except Exception as e:
            print(f"[ERROR] Groq API request failed: {str(e)}")
            return {"error": "API request failed", "details": str(e)}

    def __init__(self):
        self.client = Groq(api_key=settings.GROQ_API_KEY)
        self.model_name = "llama-3.3-70b-versatile"
        self.embedding_model = "text-embedding-3-small"

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        try:
            if settings.OLLAMA_ENABLED:
                ollama_model = OllamaModel()
                emb = ollama_model.generate_embedding(text)
                if emb:
                    return emb
            if settings.OPENAI_API_KEY:
                openai_model = OpenAIModel()
                emb = openai_model.generate_embedding(text)
                if emb:
                    return emb
            logger.warning("No embedding provider configured - falling back to simple text encoding")
            return [float(ord(c)) for c in text[:1536]] + [0.0] * (1536 - len(text))
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            return None

    def _prepare_messages(self, query: str, context: str, chat_history: Optional[List[Dict[str, str]]] = None) -> List[
        Dict[str, str]]:
        messages = [{'role': 'system', 'content': context}]
        if chat_history:
            formatted_history = [{'role': m['role'], 'content': m['content']} for m in chat_history[-5:]]
            messages.extend(formatted_history)
        messages.append({'role': 'user', 'content': query})
        return messages

    def generate_response(self, query: str, context: str, chat_history: Optional[List[Dict[str, str]]] = None) -> str:
        try:
            messages = self._prepare_messages(query, context, chat_history)
            for msg in messages:
                print(f"Role: {msg['role']}, Content: {msg['content'][:500]}...")
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
            if settings.OLLAMA_ENABLED:
                try:
                    ollama_model = OllamaModel()
                    fallback_resp = ollama_model.generate_response(query, context, chat_history)
                    if fallback_resp:
                        return fallback_resp
                except Exception as ollama_ex:
                    logger.error(f"Ollama fallback failed: {str(ollama_ex)}")
            if settings.OPENAI_API_KEY:
                try:
                    openai_model = OpenAIModel()
                    fallback_resp = openai_model.generate_response(query, context, chat_history)
                    if fallback_resp:
                        return fallback_resp
                except Exception as openai_ex:
                    logger.error(f"OpenAI fallback failed: {str(openai_ex)}")
            return f"I'm having trouble generating a response right now. Please try again later. (Error: {str(e)})"


class OllamaModel(LLMInterface):
    def __init__(self):
        self.base_url = "http://localhost:11434/api"
        self.embedding_model = "nomic-embed-text"
        self.llm_model = "llama3.2:1b"

    def _prepare_messages(self, query: str, context: str, chat_history: Optional[List[Dict[str, str]]] = None) -> List[
        Dict[str, str]]:
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
            formatted_history = [{'role': m['role'], 'content': m['content']} for m in chat_history[-5:]]
        system_prompt = (
                "You are an AI assistant for a business automation platform. "
                "Use the provided context and memory summaries to generate accurate, professional responses.\n\n"
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
        try:
            messages = self._prepare_messages(query, context, chat_history)
            start_time = time.time()
            response = requests.post(
                f"{self.base_url}/chat",
                json={"model": self.llm_model, "messages": messages, "stream": False},
                timeout=30
            )
            if response.status_code == 404:
                response = requests.post(
                    f"{self.base_url}/generate",
                    json={"model": self.llm_model, "prompt": query, "context": context, "stream": False},
                    timeout=30
                )
            response.raise_for_status()
            latency = time.time() - start_time
            logger.info(f"Ollama response generated in {latency:.2f}s using {self.llm_model}")
            response_data = response.json()
            if "message" in response_data:
                return response_data["message"]["content"].strip()
            elif "response" in response_data:
                return response_data["response"].strip()
            else:
                return str(response_data).strip()
        except Exception as e:
            logger.error(f"Error generating response with Ollama: {str(e)}")
            return f"I'm having trouble generating a response right now. (Error: {str(e)})"

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        try:
            text = text.strip().replace('\n', ' ')
            if len(text) > 8000:
                text = text[:8000]
            start_time = time.time()
            response = requests.post(
                f"{self.base_url}/embeddings",
                json={"model": self.embedding_model, "prompt": text, "options": {"temperature": 0, "num_ctx": 8192}},
                timeout=30
            )
            response.raise_for_status()
            response_data = response.json()
            print(f"[DEBUG] Ollama embedding response: {response_data}")
            embedding = response_data.get('embedding')
            if embedding is None:
                raise ValueError("Embedding not found in Ollama response")
            print(f"[DEBUG] Received embedding of length {len(embedding)}")
            if len(embedding) != 1536:
                if len(embedding) == 768:
                    embedding = embedding * 2
                    print(f"[DEBUG] Adjusted embedding from 768 to 1536 dimensions")
                else:
                    raise ValueError(f"Unexpected embedding dimension: {len(embedding)}")
            return embedding
        except Exception as e:
            logger.error(f"Error generating embedding with Ollama: {str(e)}")
            logger.error(traceback.format_exc())
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
    try:
        return OllamaModel()
    except Exception as e:
        raise ValueError(f"Failed to initialize Ollama model: {str(e)}")


def get_embedding_model() -> LLMInterface:
    try:
        return OllamaModel()
    except Exception as e:
        raise ValueError("Failed to initialize Ollama model for embeddings: " + str(e))
