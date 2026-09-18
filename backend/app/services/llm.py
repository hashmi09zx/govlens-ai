import os
import json
import time
import logging
from typing import Optional, Type, TypeVar, Any
from pydantic import BaseModel
from groq import Groq, RateLimitError, APIError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMService:
    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "groq")
        self.api_key = os.getenv("GROQ_API_KEY", "")
        self.model_large = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
        self.model_fast = os.getenv("LLM_MODEL_FAST", "qwen/qwen3.8-27b")
        self._client: Optional[Groq] = None

    @property
    def client(self) -> Groq:
        if not self._client:
            if not self.api_key:
                raise ValueError(
                    "GROQ_API_KEY environment variable is missing or empty. "
                    "Please set GROQ_API_KEY in backend/.env before starting the application."
                )
            self._client = Groq(api_key=self.api_key)
        return self._client

    def invoke(
        self,
        prompt: str,
        system_prompt: str = "You are an expert AI assistant specializing in Indian Government Recruitment analysis.",
        model_tier: str = "fast",  # "fast" or "large"
        response_schema: Optional[Type[T]] = None,
        max_retries: int = 4,
        temperature: float = 0.1,
    ) -> Any:
        primary_model = self.model_large if model_tier == "large" else self.model_fast
        candidate_models = [primary_model, "openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b", "groq/compound-mini", "groq/compound"]
        # Remove duplicates preserving order
        candidate_models = list(dict.fromkeys(candidate_models))

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # If a Pydantic schema is requested, append JSON instruction if not present
        if response_schema:
            schema_json = json.dumps(response_schema.model_json_schema(), indent=2)
            json_instruction = (
                f"\n\nReturn ONLY a valid JSON object matching this JSON Schema:\n{schema_json}\nDo not include code markdown block ticks or commentary."
            )
            messages[-1]["content"] += json_instruction

        last_exception = None

        for current_model in candidate_models:
            attempt = 0
            backoff = 1.0

            while attempt < max_retries:
                try:
                    kwargs = {
                        "model": current_model,
                        "messages": messages,
                        "temperature": temperature,
                    }
                    if response_schema:
                        kwargs["response_format"] = {"type": "json_object"}

                    response = self.client.chat.completions.create(**kwargs)
                    content = response.choices[0].message.content or ""

                    if response_schema:
                        # Clean any accidental markdown code fence wrapping
                        cleaned = content.strip()
                        if cleaned.startswith("```json"):
                            cleaned = cleaned[7:]
                        if cleaned.startswith("```"):
                            cleaned = cleaned[3:]
                        if cleaned.endswith("```"):
                            cleaned = cleaned[:-3]
                        cleaned = cleaned.strip()

                        parsed_json = json.loads(cleaned)
                        return response_schema.model_validate(parsed_json)

                    return content

                except (RateLimitError, APIError) as e:
                    last_exception = e
                    # If 404 (model_not_found), do not retry on the same model, switch to next candidate immediately
                    if getattr(e, "status_code", None) == 404 or "model_not_found" in str(e):
                        logger.warning(f"Model '{current_model}' returned 404 Not Found. Skipping to next candidate model...")
                        break

                    attempt += 1
                    logger.warning(
                        f"Groq API error for model '{current_model}' on attempt {attempt}/{max_retries}: {e}. Retrying/falling back..."
                    )
                    if attempt >= max_retries:
                        break  # Fall back to next model candidate
                    time.sleep(backoff)
                    backoff *= 1.5
                except (json.JSONDecodeError, ValueError) as e:
                    attempt += 1
                    last_exception = e
                    logger.warning(f"JSON parsing or validation failed on attempt {attempt}/{max_retries}: {e}.")
                    if attempt >= max_retries:
                        break
                    time.sleep(0.5)

        if last_exception:
            raise last_exception
        raise RuntimeError("LLM invocation failed across all model candidates.")


_llm_service_instance: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    global _llm_service_instance
    if _llm_service_instance is None:
        _llm_service_instance = LLMService()
    return _llm_service_instance
