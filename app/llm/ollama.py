"""
Ollama LLM Provider.

Implements the :class:`LLMProvider` interface for Ollama_ using its
OpenAI-compatible chat completion endpoint.

.. _Ollama: https://ollama.com
"""

from __future__ import annotations

import json
import time
from typing import Any, Generator

import requests

from app.llm.base import (
    HealthResult,
    LLMConnectionError,
    LLMProvider,
    LLMTimeoutError,
    ProviderError,
)


class OllamaProvider(LLMProvider):
    """LLM provider backed by an Ollama instance.

    Communicates with Ollama through its OpenAI-compatible
    ``/v1/chat/completions`` endpoint.

    Parameters
    ----------
    base_url:
        Base URL of the Ollama server (e.g. ``http://localhost:11434``).
    model:
        Model name to use for completions (e.g. ``"llama3.2"``).
    api_key:
        Optional API key.  Some Ollama proxy setups require
        authentication.
    timeout:
        Request timeout in seconds (default 30).
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout: int = 30,
    ) -> None:
        self.base_url = base_url.strip().rstrip("/")
        self.model = model
        self.api_key = api_key if api_key else None
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        """Build common HTTP headers for Ollama API requests."""
        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    # ------------------------------------------------------------------
    # Public API --- LLMProvider interface
    # ------------------------------------------------------------------

    def call(self, messages: list[dict]) -> dict:
        """Send a non-streaming chat completion request to Ollama.

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

        try:
            response = requests.post(
                url,
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
        except requests.exceptions.Timeout as e:
            raise LLMTimeoutError(
                f"Ollama request timed out after {self.timeout}s: {e}"
            ) from e
        except requests.exceptions.ConnectionError as e:
            raise LLMConnectionError(
                f"Cannot connect to Ollama at {self.base_url}: {e}"
            ) from e

        if not response.ok:
            raise ProviderError(
                f"Ollama returned HTTP {response.status_code}: "
                f"{response.text}"
            )

        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError) as e:
            raise ProviderError(
                f"Invalid JSON in Ollama response: {e}"
            ) from e

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
        """Send a streaming chat completion request to Ollama.

        POSTs with ``stream=True`` and yields content tokens as they
        arrive via Server-Sent Events.
        """
        url = f"{self.base_url}/v1/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }

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
                f"Ollama stream request timed out after {self.timeout}s: "
                f"{e}"
            ) from e
        except requests.exceptions.ConnectionError as e:
            raise LLMConnectionError(
                f"Cannot connect to Ollama at {self.base_url}: {e}"
            ) from e

        if not response.ok:
            raise ProviderError(
                f"Ollama returned HTTP {response.status_code}: "
                f"{response.text}"
            )

        try:
            for line in response.iter_lines():
                if not line:
                    continue
                line_str = line.decode("utf-8").strip()
                if not line_str.startswith("data: "):
                    continue
                payload_str = line_str[len("data: "):]
                if payload_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload_str)
                except (json.JSONDecodeError, ValueError) as e:
                    raise ProviderError(
                        f"Invalid JSON in Ollama stream chunk: {e}"
                    ) from e
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content")
                if content:
                    yield content
        except requests.exceptions.Timeout as e:
            raise LLMTimeoutError(
                f"Stream timed out: {e}"
            ) from e
        except requests.exceptions.ChunkedEncodingError as e:
            raise LLMConnectionError(
                f"Stream connection lost: {e}"
            ) from e
        except requests.exceptions.ConnectionError as e:
            raise LLMConnectionError(
                f"Stream connection lost: {e}"
            ) from e
        except requests.exceptions.RequestException as e:
            raise ProviderError(
                f"Stream error: {e}"
            ) from e

    def health(self) -> HealthResult:
        """Check if the Ollama server is reachable.

        Hits the ``/api/tags`` endpoint and measures response latency.
        Always returns a :class:`HealthResult` --- never raises.
        """
        url = f"{self.base_url}/api/tags"
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
                    f"Ollama returned HTTP {response.status_code}: "
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
