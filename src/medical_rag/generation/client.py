from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from medical_rag.generation.models import LLMRawResponse, LLMUsage
from medical_rag.rag.prompt import RAGPrompt


class LLMGenerationError(RuntimeError):
    pass


@dataclass(frozen=True)
class OpenAICompatibleConfig:
    base_url: str
    model: str
    api_key: str | None = None
    temperature: float = 0.0
    max_output_tokens: int = 512
    timeout_seconds: float = 60.0

    def __post_init__(self) -> None:
        if not self.base_url.strip():
            raise ValueError("base_url must not be empty")
        if not self.model.strip():
            raise ValueError("model must not be empty")
        if self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.temperature < 0:
            raise ValueError("temperature must be non-negative")

    @property
    def chat_completions_url(self) -> str:
        return self.base_url.rstrip("/") + "/chat/completions"


class OpenAICompatibleChatClient:
    """Small OpenAI-compatible chat client built on httpx.

    It deliberately depends on the HTTP protocol rather than a vendor SDK so the
    same RAG generation layer can later point at a hosted API or a local vLLM
    OpenAI-compatible endpoint. API keys are accepted at runtime and are never
    serialized into generation artifacts.
    """

    provider_name = "openai_compatible"

    def __init__(self, config: OpenAICompatibleConfig, *, transport: httpx.BaseTransport | None = None) -> None:
        self.config = config
        self._transport = transport

    def generate(self, prompt: RAGPrompt) -> LLMRawResponse:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": prompt.system_prompt},
                {"role": "user", "content": prompt.user_prompt},
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_output_tokens,
        }

        try:
            with httpx.Client(
                timeout=self.config.timeout_seconds,
                transport=self._transport,
            ) as client:
                response = client.post(
                    self.config.chat_completions_url,
                    headers=headers,
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise LLMGenerationError(f"LLM request failed: {exc}") from exc

        if response.status_code >= 400:
            body = response.text[:2000]
            raise LLMGenerationError(
                f"LLM returned HTTP {response.status_code}: {body}"
            )

        try:
            data: dict[str, Any] = response.json()
            choices = data.get("choices") or []
            if not choices:
                raise KeyError("choices")
            first = choices[0]
            message = first.get("message") or {}
            answer = message.get("content")
            if not isinstance(answer, str) or not answer.strip():
                raise KeyError("choices[0].message.content")
        except (ValueError, TypeError, KeyError) as exc:
            raise LLMGenerationError(
                "LLM response does not match the expected OpenAI-compatible chat format"
            ) from exc

        usage_data = data.get("usage") or {}
        usage = LLMUsage(
            prompt_tokens=_optional_int(usage_data.get("prompt_tokens")),
            completion_tokens=_optional_int(usage_data.get("completion_tokens")),
            total_tokens=_optional_int(usage_data.get("total_tokens")),
        )
        return LLMRawResponse(
            provider=self.provider_name,
            model=str(data.get("model") or self.config.model),
            answer=answer.strip(),
            finish_reason=(first.get("finish_reason") if isinstance(first, dict) else None),
            usage=usage,
            response_id=(str(data["id"]) if data.get("id") is not None else None),
        )


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
