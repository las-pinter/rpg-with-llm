"""
Unsloth LLM Provider.

Implements the :class:`LLMProvider` interface for Unsloth_ using its
OpenAI-compatible chat completion endpoint with a two-tier health check.

.. _Unsloth: https://unsloth.ai
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


class UnslothProvider(LLMProvider):
    """LLM provider backed by an Unsloth instance.

    Communicates with Unsloth through its OpenAI-compatible
    ``/v1/chat/completions`` endpoint.  The health check uses a
    two-tier strategy: first try ``/v1/models`` (Unsloth Studio),
    then fall back to ``/health`` (raw llama-server).

    Parameters
    ----------
    base_url:
        Base URL of the Unsloth server (e.g. ``http://localhost:8888``).
    model:
        Model name to use for completions
        (e.g. ``"unsloth/Llama-3.2-1B-Instruct"``).
    api_key:
        Optional API key.  Unsloth instances typically use
        ``sk-unsloth-...`` prefixed keys.
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
        """Build common HTTP headers for Unsloth API requests."""
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
        """Send a non-streaming chat completion request to Unsloth.

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
                f"Unsloth request timed out after {self.timeout}s: {e}"
            ) from e
        except requests.exceptions.ConnectionError as e:
            raise LLMConnectionError(
                f"Cannot connect to Unsloth at {self.base_url}: {e}"
            ) from e

        if not response.ok:
            raise ProviderError(
                f"Unsloth returned HTTP {response.status_code}: {response.text}"
            )

        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError) as e:
            raise ProviderError(f"Invalid JSON in Unsloth response: {e}") from e

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
        """Send a streaming chat completion request to Unsloth.

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
                f"Unsloth stream request timed out after {self.timeout}s: {e}"
            ) from e
        except requests.exceptions.ConnectionError as e:
            raise LLMConnectionError(
                f"Cannot connect to Unsloth at {self.base_url}: {e}"
            ) from e

        if not response.ok:
            raise ProviderError(
                f"Unsloth returned HTTP {response.status_code}: {response.text}"
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
                        f"Invalid JSON in Unsloth stream chunk: {e}"
                    ) from e
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
        """Fetch available models from the Unsloth server.

        GETs ``{base_url}/v1/models`` and parses the ``data`` array.
        Always returns a list — never raises.

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
                models.append(ModelInfo(id=mid, name=mid, provider="unsloth"))
        return models

    def health(self) -> HealthResult:
        """Check if the Unsloth server is reachable.

        Two-tier strategy:
        1. Try ``GET {base_url}/v1/models`` (Unsloth Studio).
        2. On connection error, fallback to ``GET {base_url}/health``
           (raw llama-server).

        When the ``/v1/models`` endpoint responds, the active model
        name is extracted from its response if available.

        Always returns a :class:`HealthResult` --- never raises.
        """
        url_v1 = f"{self.base_url}/v1/models"
        start = time.monotonic()
        try:
            response = requests.get(url_v1, timeout=self.timeout)
            latency_ms = (time.monotonic() - start) * 1000

            if response.ok:
                model_name = self.model
                try:
                    data = response.json()
                    model_name = data["data"][0]["id"]
                except (KeyError, IndexError, TypeError, json.JSONDecodeError):
                    pass
                return HealthResult(
                    ok=True,
                    latency_ms=latency_ms,
                    model=model_name,
                )
            return HealthResult(
                ok=False,
                latency_ms=latency_ms,
                model=self.model,
                error=(
                    f"Unsloth returned HTTP {response.status_code}: "
                    f"{response.text[:200]}"
                ),
            )
        except requests.exceptions.ConnectionError:
            # Fallback to /health endpoint (raw llama-server)
            url_health = f"{self.base_url}/health"
            try:
                response = requests.get(url_health, timeout=self.timeout)
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
                        f"Unsloth returned HTTP {response.status_code}: "
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
                    error=f"Unsloth health check: Timeout after {self.timeout}s: {e}",
                )
            except Exception as e:
                latency_ms = (time.monotonic() - start) * 1000
                return HealthResult(
                    ok=False,
                    latency_ms=latency_ms,
                    model=self.model,
                    error=f"Health check failed: {e}",
                )
        except requests.exceptions.Timeout as e:
            latency_ms = (time.monotonic() - start) * 1000
            return HealthResult(
                ok=False,
                latency_ms=latency_ms,
                model=self.model,
                error=f"Unsloth health check: Timeout after {self.timeout}s: {e}",
            )
        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            return HealthResult(
                ok=False,
                latency_ms=latency_ms,
                model=self.model,
                error=f"Health check failed: {e}",
            )
