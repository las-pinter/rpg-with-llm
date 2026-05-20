"""
llama.cpp LLM Provider.

Implements the :class:`LLMProvider` interface for llama.cpp's ``llama-server``
using its OpenAI-compatible chat completion endpoint with a two-tier
health check.

.. _llama.cpp: https://github.com/ggml-org/llama.cpp
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


class LlamacppProvider(LLMProvider):
    """LLM provider backed by a llama.cpp server instance.

    Communicates with llama.cpp's ``llama-server`` through its
    OpenAI-compatible ``/v1/chat/completions`` endpoint.  The health
    check uses a two-tier strategy: first try ``/v1/models`` (OpenAI-
    compatible endpoint), then fall back to ``/health`` (legacy).

    Parameters
    ----------
    base_url:
        Base URL of the llama.cpp server (e.g. ``http://localhost:8080``).
    model:
        Model name to use for completions.  llama.cpp uses the filename
        or ``--alias`` (default ``"default"``).
    api_key:
        Optional API key.  Required when ``llama-server`` is started
        with ``--api-key``.
    timeout:
        Request timeout in seconds (default 30).
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        model: str = "default",
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
        """Build common HTTP headers for llama.cpp API requests."""
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
        """Send a non-streaming chat completion request to llama.cpp.

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
                f"llama.cpp request timed out after {self.timeout}s: {e}"
            ) from e
        except requests.exceptions.ConnectionError as e:
            raise LLMConnectionError(
                f"Cannot connect to llama.cpp at {self.base_url}: {e}"
            ) from e

        if not response.ok:
            raise ProviderError(
                f"llama.cpp returned HTTP {response.status_code}: {response.text}"
            )

        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError) as e:
            raise ProviderError(f"Invalid JSON in llama.cpp response: {e}") from e

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
        """Send a streaming chat completion request to llama.cpp.

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
                f"llama.cpp stream request timed out after {self.timeout}s: {e}"
            ) from e
        except requests.exceptions.ConnectionError as e:
            raise LLMConnectionError(
                f"Cannot connect to llama.cpp at {self.base_url}: {e}"
            ) from e

        if not response.ok:
            raise ProviderError(
                f"llama.cpp returned HTTP {response.status_code}: {response.text}"
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
                        f"Invalid JSON in llama.cpp stream chunk: {e}"
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
        """Fetch available models from the llama.cpp server.

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
                models.append(ModelInfo(id=mid, name=mid, provider="llamacpp"))
        return models

    def health(self) -> HealthResult:
        """Check if the llama.cpp server is reachable.

        Two-tier strategy:
        1. Try ``GET {base_url}/v1/models`` (OpenAI-compatible endpoint
           on newer llama.cpp builds).
        2. On connection error, fall back to ``GET {base_url}/health``
           (legacy endpoint on older builds).

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
                    f"llama.cpp returned HTTP {response.status_code}: "
                    f"{response.text[:200]}"
                ),
            )
        except requests.exceptions.ConnectionError:
            # Fallback to /health endpoint (legacy llama.cpp)
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
                        f"llama.cpp returned HTTP {response.status_code}: "
                        f"{response.text[:200]}"
                    ),
                )
            except requests.exceptions.ConnectionError as e:
                latency_ms = (time.monotonic() - start) * 1000
                return HealthResult(
                    ok=False,
                    latency_ms=latency_ms,
                    model=self.model,
                    error=f"llama.cpp health check: Connection error: {e}",
                )
            except requests.exceptions.Timeout as e:
                latency_ms = (time.monotonic() - start) * 1000
                return HealthResult(
                    ok=False,
                    latency_ms=latency_ms,
                    model=self.model,
                    error=(
                        f"llama.cpp health check: Timeout after {self.timeout}s: {e}"
                    ),
                )
            except Exception as e:
                latency_ms = (time.monotonic() - start) * 1000
                return HealthResult(
                    ok=False,
                    latency_ms=latency_ms,
                    model=self.model,
                    error=f"llama.cpp health check failed: {e}",
                )
        except requests.exceptions.Timeout as e:
            latency_ms = (time.monotonic() - start) * 1000
            return HealthResult(
                ok=False,
                latency_ms=latency_ms,
                model=self.model,
                error=(f"llama.cpp health check: Timeout after {self.timeout}s: {e}"),
            )
        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            return HealthResult(
                ok=False,
                latency_ms=latency_ms,
                model=self.model,
                error=f"llama.cpp health check failed: {e}",
            )
