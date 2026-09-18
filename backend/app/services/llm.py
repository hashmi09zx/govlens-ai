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
        self.model_large = os.getenv("LLM_MODEL", "groq/compound")
        self.model_fast = os.getenv("LLM_MODEL_FAST", "groq/compound-mini")
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
        model = self.model_large if model_tier == "large" else self.model_fast

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

        attempt = 0
        backoff = 2.0

        while attempt < max_retries:
            try:
                kwargs = {
                    "model": model,
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
                attempt += 1
                logger.warning(f"Groq API error on attempt {attempt}/{max_retries}: {e}. Retrying in {backoff}s...")
                if attempt >= max_retries:
                    raise e
                time.sleep(backoff)
                backoff *= 2.0
            except (json.JSONDecodeError, ValueError) as e:
                attempt += 1
                logger.warning(f"JSON parsing or validation failed on attempt {attempt}/{max_retries}: {e}.")
                if attempt >= max_retries:
                    raise e
                time.sleep(1.0)


_llm_service_instance: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    global _llm_service_instance
    if _llm_service_instance is None:
        _llm_service_instance = LLMService()
    return _llm_service_instance
