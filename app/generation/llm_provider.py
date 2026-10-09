import abc
import re
import json
import requests
from typing import List, Dict, Any, Optional
from app.config import Config


class LLMProvider(abc.ABC):
    """Abstract Base Class for LLM providers."""

    @abc.abstractmethod
    def generate(self, messages: List[Dict[str, str]], temperature: float = 0.1) -> str:
        """Generate response given a list of chat messages [{'role': ..., 'content': ...}]."""
        pass


class LocalMockLLMProvider(LLMProvider):
    """
    Local grounded extractive/synthesis engine for offline or CPU environments.
    Strictly answers from the delimited evidence context without external calls.
    """

    def generate(self, messages: List[Dict[str, str]], temperature: float = 0.1) -> str:
        user_msg = ""
        system_msg = ""
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            elif m["role"] == "user":
                user_msg = m["content"]

        # If user message contains delimited evidence, extract and synthesize answer
        if "--- RETRIEVED EVIDENCE (UNTRUSTED DATA) ---" in user_msg:
            parts = user_msg.split("--- RETRIEVED EVIDENCE (UNTRUSTED DATA) ---")
            header = parts[0]
            evidence_and_query = parts[1]
            
            # Extract question
            q_part = ""
            if "USER QUESTION:" in evidence_and_query:
                ev_part, q_part = evidence_and_query.split("USER QUESTION:")
            else:
                ev_part = evidence_and_query

            q_clean = q_part.strip().lower()
            
            # If no evidence chunks supplied
            if "No relevant evidence passages found" in ev_part:
                return "Based on the provided documents, sufficient information was not found to answer this question."

            # Extract Content: blocks from evidence passages
            content_blocks = re.findall(r'Content:\s*(.*?)(?=\n\[Source|\n---|\Z)', ev_part, re.DOTALL)
            if not content_blocks:
                # Fallback to line scanning if Content: tag is missing
                lines = [line.strip() for line in ev_part.split("\n") if line.strip()]
                relevant_text = " ".join(l for l in lines if not l.startswith(("[Source", "---", "Document:", "Page:")))
                content_blocks = [relevant_text]

            # Sentence-level relevance matching against user question
            question_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', q_clean)) - {
                "what", "when", "where", "which", "who", "whom", "whose", "why", "how",
                "explain", "describe", "tell", "about", "is", "are", "was", "were", "the"
            }

            scored_sentences = []
            seen_sents = set()

            for block in content_blocks:
                # Remove common private-use/bullet characters (e.g. \uf0b7, bullet points)
                cleaned = re.sub(r'[\uf000-\uf8ff\u2022\u2023\u25e6\u2043\u2219]', ' ', block)
                # Normalize line breaks within paragraphs into single spaces so full sentences are preserved
                cleaned = re.sub(r'\s*\n\s*', ' ', cleaned).strip()
                
                # Split into complete sentences
                sents = re.split(r'(?<=[.!?])\s+', cleaned)
                for s in sents:
                    s_clean = " ".join(s.split()).strip()
                    if len(s_clean) < 25 or s_clean in seen_sents:
                        continue
                    seen_sents.add(s_clean)
                    s_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', s_clean.lower()))
                    match_count = len(s_words.intersection(question_words))
                    scored_sentences.append((match_count, s_clean))

            if not scored_sentences:
                return "Based on the provided documents, sufficient information was not found to answer this question."

            # Prioritize sentences with highest keyword overlap
            scored_sentences.sort(key=lambda x: x[0], reverse=True)
            # Select up to 6 high-scoring sentences to give a rich, comprehensive answer
            top_sentences = [s[1] for s in scored_sentences if s[0] > 0][:6]

            if not top_sentences:
                top_sentences = [s[1] for s in scored_sentences[:4]]

            # Format into cohesive, multi-sentence paragraphs
            if len(top_sentences) > 3:
                paragraph_1 = " ".join(top_sentences[:3])
                paragraph_2 = " ".join(top_sentences[3:])
                synthesized = f"{paragraph_1}\n\n{paragraph_2}"
            else:
                synthesized = " ".join(top_sentences)

            return (
                f"{synthesized}\n\n"
                f"[SYSTEM NOTICE: Generated in DEGRADED MODE using local extractive heuristic. "
                f"Configure an active LLM provider (Ollama, OpenAI, Groq, or vLLM) in .env for generative synthesis.]"
            )
            
        return "I am an evidence-grounded assistant. Please query against the indexed documents."

    def health_check(self) -> bool:
        """Local mock provider is always available."""
        return True


class OpenAICompatibleLLMProvider(LLMProvider):
    """
    Provider for any OpenAI-compatible API endpoint (OpenAI, Ollama, Groq, vLLM, LocalAI).
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None
    ):
        self.base_url = (base_url or Config.LLM_BASE_URL).rstrip("/")
        self.api_key = api_key or Config.LLM_API_KEY
        self.model_name = model_name or Config.LLM_MODEL_NAME

    def health_check(self) -> bool:
        """Check reachability of the remote LLM endpoint with a short timeout."""
        try:
            headers = {"Content-Type": "application/json"}
            if self.api_key and self.api_key != "none":
                headers["Authorization"] = f"Bearer {self.api_key}"
            # Test endpoint reachability
            resp = requests.get(f"{self.base_url}/models", headers=headers, timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def generate(self, messages: List[Dict[str, str]], temperature: float = 0.1) -> str:
        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key and self.api_key != "none":
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature
        }

        try:
            endpoint = f"{self.base_url}/chat/completions"
            response = requests.post(endpoint, headers=headers, json=payload, timeout=45)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            # Fall back to local grounded generator if remote API is unavailable
            fallback = LocalMockLLMProvider()
            gen_res = fallback.generate(messages, temperature)
            return (
                f"{gen_res}\n\n"
                f"[SYSTEM NOTICE: Remote LLM provider '{self.base_url}' was unreachable. "
                f"Falling back to local extractive heuristic mode.]"
            )


def get_llm_provider() -> LLMProvider:
    """Factory to instantiate the configured LLM provider."""
    provider_type = Config.LLM_PROVIDER.lower()
    if provider_type in ("ollama", "openai", "openai_compatible"):
        return OpenAICompatibleLLMProvider()
    return LocalMockLLMProvider()
