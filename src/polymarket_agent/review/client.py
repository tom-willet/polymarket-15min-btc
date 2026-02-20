from __future__ import annotations

import asyncio
import os
import random
from dataclasses import dataclass

import httpx

from .models import ProviderResult


@dataclass(frozen=True)
class ReviewClientConfig:
    provider: str
    model: str
    timeout_seconds: int
    max_retries: int


class ReviewClient:
    def __init__(self, config: ReviewClientConfig) -> None:
        self._config = config

    def _use_responses_api(self) -> bool:
        model = self._config.model.strip().lower()
        return model.startswith("gpt-5")

    def _effective_timeout_seconds(self) -> float:
        # GPT-5 response generation on larger payloads can exceed short chat-era defaults.
        if self._use_responses_api():
            return float(max(self._config.timeout_seconds, 60))
        return float(self._config.timeout_seconds)

    @staticmethod
    def _extract_text_from_chat_body(body: dict) -> str:
        choices = body.get("choices", [])
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("provider response missing choices")

        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
            if parts:
                return "\n".join(parts)

        raise RuntimeError("provider response missing content")

    @staticmethod
    def _extract_text_from_responses_body(body: dict) -> str:
        output = body.get("output", [])
        if not isinstance(output, list) or not output:
            raise RuntimeError("provider response missing output")

        parts: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content", [])
            if not isinstance(content, list):
                continue
            for piece in content:
                if not isinstance(piece, dict):
                    continue
                text = piece.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())

        if parts:
            return "\n".join(parts)

        raise RuntimeError("provider response missing output text")

    async def _call_once(self, *, system_prompt: str, user_prompt: str) -> ProviderResult:
        provider = self._config.provider.strip().lower()
        if provider != "openai":
            raise RuntimeError(f"unsupported provider: {self._config.provider}")

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for LLM reviews")

        use_responses_api = self._use_responses_api()
        if use_responses_api:
            payload = {
                "model": self._config.model,
                "input": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.1,
            }
            endpoint = "https://api.openai.com/v1/responses"
        else:
            payload = {
                "model": self._config.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.1,
            }
            endpoint = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        effective_timeout = self._effective_timeout_seconds()

        async with httpx.AsyncClient(timeout=effective_timeout) as client:
            response = await client.post(endpoint, json=payload, headers=headers)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                snippet = response.text[:800] if response.text else ""
                raise RuntimeError(
                    f"openai http {response.status_code} at {endpoint}: {snippet}"
                ) from exc
            body = response.json()

        text = (
            self._extract_text_from_responses_body(body)
            if use_responses_api
            else self._extract_text_from_chat_body(body)
        )

        usage = body.get("usage", {})
        if isinstance(usage, dict):
            token_in = usage.get("prompt_tokens")
            if token_in is None:
                token_in = usage.get("input_tokens")

            token_out = usage.get("completion_tokens")
            if token_out is None:
                token_out = usage.get("output_tokens")
        else:
            token_in = None
            token_out = None
        return ProviderResult(
            raw_text=text,
            token_in=int(token_in) if isinstance(token_in, int) else None,
            token_out=int(token_out) if isinstance(token_out, int) else None,
            cost_usd_estimate=None,
        )

    async def run(self, *, system_prompt: str, user_prompt: str) -> ProviderResult:
        attempts = max(0, self._config.max_retries) + 1
        last_error: Exception | None = None

        for attempt in range(attempts):
            try:
                return await asyncio.wait_for(
                    self._call_once(system_prompt=system_prompt, user_prompt=user_prompt),
                    timeout=self._effective_timeout_seconds(),
                )
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt >= attempts - 1:
                    break
                await asyncio.sleep(min(2.0, (0.35 * (2**attempt)) + random.uniform(0.05, 0.25)))

        raise RuntimeError(f"review provider failed after retries: {last_error}")
