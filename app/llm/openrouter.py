"""
OpenRouter LLM Provider.

Implements the :class:`LLMProvider` interface for OpenRouter_ using its
OpenAI-compatible chat completion endpoint.

.. _OpenRouter: https://openrouter.ai
"""

from __future__ import annotations

import json
import time
from collections.abc import Generator
from typing import Any

import requests

from app.llm.base import (
    HealthResult,
    LLMConnectionError,
    LLMProvider,
    LLMTimeoutError,
    ModelInfo,
    ProviderError,
)


class OpenRouterProvider(LLMProvider):
    """LLM provider backed by the OpenRouter cloud API.

    Communicates with OpenRouter through its OpenAI-compatible
    ``/v1/chat/completions`` endpoint.

    Parameters
    ----------
    base_url:
        Base URL of the OpenRouter API
        (e.g. ``https://openrouter.ai/api``).
    model:
        Model name to use for completions
        (e.g. ``"mistralai/mistral-7b-instruct:free"``).
    api_key:
        API key for OpenRouter authentication (required for API access).
    timeout:
        Request timeout in seconds (default 30).
    site_url:
        Site URL sent as the ``HTTP-Referer`` header (optional).
    app_name:
        App name sent as the ``X-Title`` header (optional).
    """

    def __init__(
        self,
        base_url: str = "https://openrouter.ai/api",
        model: str = "mistralai/mistral-7b-instruct:free",
        api_key: str | None = None,
        timeout: int = 300,
        site_url: str | None = None,
        app_name: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> None:
        self.base_url = base_url.strip().rstrip("/")
        self.model = model
        self.api_key = api_key if api_key else None
        self.timeout = timeout
        self.site_url = site_url
        self.app_name = app_name
        self.max_tokens = max_tokens
        self.temperature = temperature

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        """Build common HTTP headers for OpenRouter API requests."""
        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        if self.app_name:
            headers["X-Title"] = self.app_name
        return headers

    # ------------------------------------------------------------------
    # Public API --- LLMProvider interface
    # ------------------------------------------------------------------

    def call(self, messages: list[dict]) -> dict:
        """Send a non-streaming chat completion request to OpenRouter.

        POSTs to ``{base_url}/v1/chat/completions`` with an
        OpenAI-compatible payload.

        Returns
        -------
        dict
            With keys ``content``, ``finish_reason``, and ``usage``.
        """
        url = f"{self.base_url}/v1/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        if self.temperature is not None:
            payload["temperature"] = self.temperature

        try:
            response = requests.post(
                url,
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
        except requests.exceptions.Timeout as e:
            raise LLMTimeoutError(
                f"OpenRouter request timed out after {self.timeout}s: {e}"
            ) from e
        except requests.exceptions.ConnectionError as e:
            raise LLMConnectionError(
                f"Cannot connect to OpenRouter at {self.base_url}: {e}"
            ) from e

        if not response.ok:
            raise ProviderError(
                f"OpenRouter returned HTTP {response.status_code}: {response.text}"
            )

        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError) as e:
            raise ProviderError(f"Invalid JSON in OpenRouter response: {e}") from e

        choice = data["choices"][0]
        return {
            "content": choice["message"]["content"],
            "finish_reason": choice["finish_reason"],
            "usage": {
                "prompt_tokens": data["usage"]["prompt_tokens"],
                "completion_tokens": data["usage"]["completion_tokens"],
                "total_tokens": data["usage"]["total_tokens"],
            },
        }

    def stream(self, messages: list[dict]) -> Generator[str, None, None]:
        """Send a streaming chat completion request to OpenRouter.

        POSTs with ``stream=True`` and yields content tokens as they
        arrive via Server-Sent Events.
        """
        url = f"{self.base_url}/v1/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        if self.temperature is not None:
            payload["temperature"] = self.temperature

        try:
            response = requests.post(
                url,
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
                stream=True,
            )
        except requests.exceptions.Timeout as e:
            raise LLMTimeoutError(
                f"OpenRouter stream request timed out after {self.timeout}s: {e}"
            ) from e
        except requests.exceptions.ConnectionError as e:
            raise LLMConnectionError(
                f"Cannot connect to OpenRouter at {self.base_url}: {e}"
            ) from e

        if not response.ok:
            raise ProviderError(
                f"OpenRouter returned HTTP {response.status_code}: {response.text}"
            )

        try:
            for line in response.iter_lines():
                if not line:
                    continue
                line_str = line.decode("utf-8").strip()
                if not line_str.startswith("data: "):
                    continue
                payload_str = line_str[len("data: ") :]
                if payload_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload_str)
                except (json.JSONDecodeError, ValueError) as e:
                    raise ProviderError(
                        f"Invalid JSON in OpenRouter stream chunk: {e}"
                    ) from e
                # Capture usage data from the final streaming chunk
                if "usage" in chunk:
                    self._last_stream_usage = chunk["usage"]
                choices = chunk.get("choices")
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                content = delta.get("content")
                if content:
                    yield content
        except requests.exceptions.Timeout as e:
            raise LLMTimeoutError(f"Stream timed out: {e}") from e
        except requests.exceptions.ChunkedEncodingError as e:
            raise LLMConnectionError(f"Stream connection lost: {e}") from e
        except requests.exceptions.ConnectionError as e:
            raise LLMConnectionError(f"Stream connection lost: {e}") from e
        except requests.exceptions.RequestException as e:
            raise ProviderError(f"Stream error: {e}") from e

    def list_models(self) -> list[ModelInfo]:
        """Fetch available models from the OpenRouter API.

        GETs ``{base_url}/v1/models`` with auth headers and parses
        the ``data`` array.  Always returns a list — never raises.

        Returns
        -------
        list[ModelInfo]
            Available models, or empty list on failure.
        """
        url = f"{self.base_url}/v1/models"
        try:
            response = requests.get(url, headers=self._headers(), timeout=self.timeout)
            if not response.ok:
                return []
            data = response.json()
        except Exception:
            return []

        models: list[ModelInfo] = []
        for m in data.get("data", []):
            mid = m.get("id", "")
            if mid:
                models.append(
                    ModelInfo(
                        id=mid,
                        name=m.get("name", mid),
                        provider="openrouter",
                    )
                )
        return models

    def health(self) -> HealthResult:
        """Check if the OpenRouter API is reachable.

        Hits the ``/v1/models`` endpoint and measures response latency.
        Always returns a :class:`HealthResult` --- never raises.
        """
        url = f"{self.base_url}/v1/models"
        start = time.monotonic()
        try:
            response = requests.get(url, timeout=self.timeout)
            latency_ms = (time.monotonic() - start) * 1000

            if response.ok:
                return HealthResult(
                    ok=True,
                    latency_ms=latency_ms,
                    model=self.model,
                )
            return HealthResult(
                ok=False,
                latency_ms=latency_ms,
                model=self.model,
                error=(
                    f"OpenRouter returned HTTP {response.status_code}: "
                    f"{response.text[:200]}"
                ),
            )
        except requests.exceptions.ConnectionError as e:
            latency_ms = (time.monotonic() - start) * 1000
            return HealthResult(
                ok=False,
                latency_ms=latency_ms,
                model=self.model,
                error=f"Connection error: {e}",
            )
        except requests.exceptions.Timeout as e:
            latency_ms = (time.monotonic() - start) * 1000
            return HealthResult(
                ok=False,
                latency_ms=latency_ms,
                model=self.model,
                error=f"Timeout after {self.timeout}s: {e}",
            )
        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            return HealthResult(
                ok=False,
                latency_ms=latency_ms,
                model=self.model,
                error=f"Health check failed: {e}",
            )
