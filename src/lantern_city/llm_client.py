from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx


class LLMClientError(RuntimeError):
    pass


class LLMClientResponseError(LLMClientError):
    pass


@dataclass(frozen=True, slots=True)
class OpenAICompatibleConfig:
    base_url: str
    model: str
    api_key: str | None = None
    timeout: float = 30.0

    @property
    def normalized_base_url(self) -> str:
        base_url = self.base_url.rstrip("/")
        if base_url.endswith("/v1"):
            return base_url
        return f"{base_url}/v1"


@dataclass(frozen=True, slots=True)
class ChatCompletionResult:
    raw_response: dict[str, Any]
    content: str


class OpenAICompatibleLLMClient:
    def __init__(
        self,
        config: OpenAICompatibleConfig,
        *,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.config = config
        self._http_client = http_client or httpx.Client(timeout=config.timeout)
        self._owns_http_client = http_client is None

    def close(self) -> None:
        if self._owns_http_client:
            self._http_client.close()

    def create_chat_completion(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 2400,
        response_format: dict[str, Any] | None = None,
    ) -> ChatCompletionResult:
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": response_format or {"type": "text"},
        }

        try:
            response = self._http_client.post(
                f"{self.config.normalized_base_url}/chat/completions",
                headers=self._build_headers(),
                json=payload,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            raise LLMClientError(
                f"LLM request failed with status {status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMClientError(f"LLM request failed: {exc}") from exc

        try:
            raw_response = response.json()
        except ValueError as exc:
            raise LLMClientResponseError("LLM response body was not valid JSON") from exc
        return ChatCompletionResult(
            raw_response=raw_response,
            content=self.extract_content(raw_response),
        )

    def generate_json(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 2400,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = self.create_chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=self._build_response_format(schema=schema),
        )
        return self.parse_json_content(response.raw_response)

    def _build_response_format(self, *, schema: dict[str, Any] | None) -> dict[str, Any]:
        if schema is None:
            return {"type": "text"}
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "structured_output",
                "schema": schema,
            },
        }

    def parse_json_content(self, response_payload: dict[str, Any]) -> dict[str, Any]:
        content = self.extract_content(response_payload)
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMClientResponseError("Model response contained invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise LLMClientResponseError("Model response JSON must be an object")
        return parsed

    def extract_content(self, response_payload: dict[str, Any]) -> str:
        try:
            message = response_payload["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientResponseError(
                "Model response is missing choices[0].message content"
            ) from exc

        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = [part.get("text", "") for part in content if isinstance(part, dict)]
            combined = "".join(text_parts).strip()
            if combined:
                return combined

        raise LLMClientResponseError("Model response did not include textual message content")

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers


__all__ = [
    "ChatCompletionResult",
    "LLMClientError",
    "LLMClientResponseError",
    "OpenAICompatibleConfig",
    "OpenAICompatibleLLMClient",
]
