from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib import error, request


@dataclass(slots=True)
class QwenClientConfig:
    base_url: str
    api_key: str
    model: str
    timeout_seconds: float = 60.0
    temperature: float = 0.1

    @classmethod
    def from_env(cls) -> "QwenClientConfig":
        base_url = os.getenv("QWEN_BASE_URL", "").strip()
        api_key = os.getenv("QWEN_API_KEY", "").strip()
        model = os.getenv("QWEN_MODEL", "").strip()
        if not base_url:
            raise ValueError("QWEN_BASE_URL is required")
        if not api_key:
            raise ValueError("QWEN_API_KEY is required")
        if not model:
            raise ValueError("QWEN_MODEL is required")
        timeout_seconds = float(os.getenv("QWEN_TIMEOUT_SECONDS", "60"))
        temperature = float(os.getenv("QWEN_TEMPERATURE", "0.1"))
        return cls(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds,
            temperature=temperature,
        )


class QwenClientError(RuntimeError):
    """Raised when the Qwen client cannot produce a valid response."""


class QwenChatClient:
    """Minimal OpenAI-compatible chat client for Qwen-style backends."""

    def __init__(self, config: QwenClientConfig) -> None:
        self.config = config

    @classmethod
    def from_env(cls) -> "QwenChatClient":
        return cls(config=QwenClientConfig.from_env())

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.config.temperature if temperature is None else temperature,
            "response_format": {"type": "json_object"},
        }
        raw_response = self._post_json(payload)
        content = self._extract_message_content(raw_response)
        return self._extract_json_object(content)

    def chat(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        extra_body: dict[str, Any] | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature if temperature is None else temperature,
        }
        if extra_body:
            payload.update(extra_body)
        raw_response = self._post_json(payload)
        return self._extract_message_content(raw_response)

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=self._chat_completions_url(),
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
            },
        )
        try:
            with request.urlopen(req, timeout=self.config.timeout_seconds) as response:
                response_text = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise QwenClientError(f"Qwen HTTP error {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise QwenClientError(f"Qwen request failed: {exc.reason}") from exc

        try:
            parsed = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise QwenClientError("Qwen response was not valid JSON") from exc

        if isinstance(parsed, dict) and parsed.get("error"):
            raise QwenClientError(f"Qwen API returned an error: {parsed['error']}")
        return parsed

    def _chat_completions_url(self) -> str:
        base_url = self.config.base_url.rstrip("/")
        if base_url.endswith("/chat/completions"):
            return base_url
        if base_url.endswith("/v1"):
            return f"{base_url}/chat/completions"
        return f"{base_url}/v1/chat/completions"

    @staticmethod
    def _extract_message_content(response_payload: dict[str, Any]) -> str:
        try:
            choices = response_payload["choices"]
            message = choices[0]["message"]
            content = message["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise QwenClientError("Qwen response did not include a usable assistant message") from exc
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text = item.get("text")
                    if isinstance(text, str):
                        text_parts.append(text)
            if text_parts:
                return "".join(text_parts)
        raise QwenClientError("Qwen assistant message content was not text")

    @staticmethod
    def _extract_json_object(content: str) -> dict[str, Any]:
        stripped = content.strip()
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            start = stripped.find("{")
            end = stripped.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise QwenClientError("Qwen output did not contain a JSON object")
            try:
                parsed = json.loads(stripped[start : end + 1])
            except json.JSONDecodeError as exc:
                raise QwenClientError("Qwen output JSON could not be parsed") from exc
        if not isinstance(parsed, dict):
            raise QwenClientError("Qwen output JSON was not an object")
        return parsed
