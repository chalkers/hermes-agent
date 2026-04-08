from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import aiohttp


class HermesApiError(Exception):
    """Raised when the Hermes API returns an error."""


@dataclass(slots=True)
class HermesApiResult:
    session_id: str | None
    text: str
    raw: dict[str, Any]


class HermesApiClient:
    """Tiny async client for the Hermes OpenAI-compatible API server."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        api_key: str,
        model: str,
        timeout: int,
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    @property
    def auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def async_validate(self) -> None:
        """Validate connectivity and auth against the Hermes API server."""
        timeout = aiohttp.ClientTimeout(total=min(self._timeout, 15))
        async with self._session.get(
            f"{self._base_url}/models",
            headers=self.auth_headers,
            timeout=timeout,
        ) as resp:
            if resp.status >= 400:
                detail = await resp.text()
                raise HermesApiError(
                    f"Hermes API validation failed ({resp.status}): {detail[:300]}"
                )
            await resp.json()

    async def async_send(
        self,
        *,
        text: str,
        instructions: str,
        session_id: str | None,
    ) -> HermesApiResult:
        messages: list[dict[str, str]] = []
        if instructions:
            messages.append({"role": "system", "content": instructions})
        messages.append({"role": "user", "content": text})

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
        }

        headers = dict(self.auth_headers)
        if session_id:
            headers["X-Hermes-Session-Id"] = session_id

        timeout = aiohttp.ClientTimeout(total=self._timeout)
        async with self._session.post(
            f"{self._base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=timeout,
        ) as resp:
            raw_text = await resp.text()
            if resp.status >= 400:
                raise HermesApiError(
                    f"Hermes API request failed ({resp.status}): {raw_text[:500]}"
                )
            data = await resp.json()
            response_session_id = resp.headers.get("X-Hermes-Session-Id") or session_id

        return HermesApiResult(
            session_id=response_session_id,
            text=self._extract_text(data),
            raw=data,
        )

    def _extract_text(self, data: dict[str, Any]) -> str:
        choices = data.get("choices") or []
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message") or {}
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()

            if isinstance(content, list):
                texts: list[str] = []
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    text = block.get("text")
                    if isinstance(text, str) and text.strip():
                        texts.append(text.strip())
                if texts:
                    return "\n".join(texts)

        if isinstance(data.get("output_text"), str) and data["output_text"].strip():
            return data["output_text"].strip()

        return "I completed that, but Hermes returned no spoken text."
