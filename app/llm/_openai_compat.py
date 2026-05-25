"""
OpenAI-compatible provider base class.

Provides a shared implementation of ``call()``, ``stream()``,
``list_models()``, ``health()``, and ``_headers()`` for all
providers that speak the OpenAI chat-completions protocol
(Ollama, Groq, OpenRouter, Unsloth, llama.cpp).

Only provider-specific metadata (endpoints, JSON keys, error
messages) varies — everything else is identical.
"""

from __future__ import annotations

import json
import time
from collections.abc import Generator
from dataclasses import dataclass
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

# Sentinel value to distinguish "not provided" from "explicitly None".
_UNSET: object = object()


# ---------------------------------------------------------------------------
# Provider specification dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProviderSpec:
    """Immutable configuration for an OpenAI-compatible provider.

    Attributes
    ----------
    provider_name:
        Human-readable provider name used in error messages.
    models_endpoint:
        Path to the model-list endpoint (e.g. ``"/v1/models"``).
    models_key:
        JSON key that holds the model list in the response body
        (e.g. ``"data"``).
    name_key:
        JSON key for the model identifier within each model object
        (e.g. ``"id"``).
    name_key_fallback:
        Optional JSON key for a human-readable model name.
    health_endpoint:
        Optional path for the health-check endpoint.  Defaults to
        ``models_endpoint`` when ``None``.
    health_fallback_endpoint:
        Optional second health-check path tried when the primary
        endpoint fails (e.g. ``"/health"``).
    """

    provider_name: str
    models_endpoint: str
    models_key: str
    name_key: str
    name_key_fallback: str | None = None
    health_endpoint: str | None = None
    health_fallback_endpoint: str | None = None


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class OpenAICompatibleProvider(LLMProvider):
    """Base class for providers that speak the OpenAI chat-completions API.

    Subclasses must only supply a ``ProviderSpec`` via the ``spec``
    constructor argument.  All HTTP interaction, JSON parsing, and
    error handling is shared here.
    """

    _last_stream_usage: dict[str, Any] | None = None
    """Token usage from the most recent streaming response."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout: int = 300,
        max_tokens: int | None = None,
        temperature: float | None = None,
        spec: ProviderSpec | object = _UNSET,
    ) -> None:
        base_url = base_url.strip().rstrip("/")
        self.base_url: str = base_url
        self.model: str = model
        self.api_key: str | None = api_key
        self.timeout: int = timeout
        self.max_tokens: int | None = max_tokens
        self.temperature: float | None = temperature
        self._spec: ProviderSpec = (
            spec
            if isinstance(spec, ProviderSpec)
            else ProviderSpec(
                provider_name="OpenAI-Compatible",
                models_endpoint="/v1/models",
                models_key="data",
                name_key="id",
            )
        )
        # Instance attribute shadows the class-level one — fixes the
        # shared-mutable-class-attribute bug in LLMProvider.
        self._last_stream_usage: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        """Return default request headers with optional Bearer auth."""
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    # ------------------------------------------------------------------
    # call() — non-streaming chat completion
    # ------------------------------------------------------------------

    def call(self, messages: list[dict]) -> dict:
        """Send a non-streaming chat completion request.

        Parameters
        ----------
        messages:
            Conversation history in OpenAI format.

        Returns
        -------
        dict
            Dict with ``content``, ``finish_reason``, and ``usage``.

        Raises
        ------
        LLMTimeoutError
            If the request exceeds the configured timeout.
        LLMConnectionError
            If the provider is unreachable.
        ProviderError
            If the provider returns a non-success status or invalid JSON.
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
                f"{self._spec.provider_name} request timed out "
                f"after {self.timeout}s: {e}"
            ) from e
        except requests.exceptions.ConnectionError as e:
            raise LLMConnectionError(
                f"Cannot connect to {self._spec.provider_name} at {self.base_url}: {e}"
            ) from e

        if not response.ok:
            raise ProviderError(
                f"{self._spec.provider_name} returned "
                f"HTTP {response.status_code}: {response.text}"
            )

        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError) as e:
            raise ProviderError(
                f"Invalid JSON in {self._spec.provider_name} response: {e}"
            ) from e

        try:
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
        except (KeyError, IndexError) as e:
            raise ProviderError(
                f"Invalid response structure from {self._spec.provider_name}: {e}"
            ) from e

    # ------------------------------------------------------------------
    # stream() — streaming chat completion
    # ------------------------------------------------------------------

    def stream(self, messages: list[dict]) -> Generator[str, None, None]:
        """Send a streaming chat completion request.

        Parameters
        ----------
        messages:
            Conversation history in OpenAI format.

        Yields
        ------
        str
            Content tokens as they are received.

        Raises
        ------
        LLMTimeoutError
            If the request exceeds the configured timeout.
        LLMConnectionError
            If the provider is unreachable.
        ProviderError
            If the provider returns a non-success status or invalid JSON.
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
                f"{self._spec.provider_name} stream request timed out "
                f"after {self.timeout}s: {e}"
            ) from e
        except requests.exceptions.ConnectionError as e:
            raise LLMConnectionError(
                f"Cannot connect to {self._spec.provider_name} at {self.base_url}: {e}"
            ) from e

        if not response.ok:
            raise ProviderError(
                f"{self._spec.provider_name} returned "
                f"HTTP {response.status_code}: {response.text}"
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
                        f"Invalid JSON in {self._spec.provider_name} stream chunk: {e}"
                    ) from e
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

    # ------------------------------------------------------------------
    # list_models()
    # ------------------------------------------------------------------

    def list_models(self) -> list[ModelInfo]:
        """Fetch available models from the provider.

        Returns an empty list on any failure — this method never raises.

        Returns
        -------
        list[ModelInfo]
            Available models, or ``[]`` on error.
        """
        endpoint = self._spec.health_endpoint or self._spec.models_endpoint
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.get(
                url,
                headers=self._headers(),
                timeout=self.timeout,
            )
            if not response.ok:
                return []
            data = response.json()
        except Exception:
            return []

        models: list[ModelInfo] = []
        for m in data.get(self._spec.models_key, []):
            mid = m.get(self._spec.name_key, "")
            if mid:
                if self._spec.name_key_fallback:
                    name = m.get(self._spec.name_key_fallback, mid)
                else:
                    name = mid
                models.append(
                    ModelInfo(
                        id=mid,
                        name=name,
                        provider=self._spec.provider_name,
                    )
                )
        return models

    # ------------------------------------------------------------------
    # health()
    # ------------------------------------------------------------------

    def health(self) -> HealthResult:
        """Check whether the provider is reachable and working.

        Uses a two-tier fallback strategy when
        ``spec.health_fallback_endpoint`` is set.

        Returns
        -------
        HealthResult
            Health status with latency and model info.
        """
        start = time.monotonic()
        endpoint = self._spec.health_endpoint or self._spec.models_endpoint
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.get(
                url,
                headers=self._headers(),
                timeout=self.timeout,
            )
            if not response.ok:
                return HealthResult(
                    ok=False,
                    latency_ms=(time.monotonic() - start) * 1000,
                    model="",
                    error=(
                        f"{self._spec.provider_name} returned "
                        f"HTTP {response.status_code}"
                    ),
                )
            data = response.json()
            model_list = data.get(self._spec.models_key, [])
            model_name = (
                model_list[0].get(self._spec.name_key, "") if model_list else ""
            )
            return HealthResult(
                ok=True,
                latency_ms=(time.monotonic() - start) * 1000,
                model=model_name,
            )
        except requests.exceptions.Timeout:
            return HealthResult(
                ok=False,
                latency_ms=(time.monotonic() - start) * 1000,
                model="",
                error=f"{self._spec.provider_name} health check: Timeout",
            )
        except requests.exceptions.ConnectionError:
            if self._spec.health_fallback_endpoint:
                fallback_url = f"{self.base_url}{self._spec.health_fallback_endpoint}"
                try:
                    response = requests.get(
                        fallback_url,
                        headers=self._headers(),
                        timeout=self.timeout,
                    )
                    if not response.ok:
                        return HealthResult(
                            ok=False,
                            latency_ms=(time.monotonic() - start) * 1000,
                            model="",
                            error=(
                                f"{self._spec.provider_name} returned "
                                f"HTTP {response.status_code}"
                            ),
                        )
                    data = response.json()
                    model_list = data.get(self._spec.models_key, [])
                    model_name = (
                        model_list[0].get(self._spec.name_key, "") if model_list else ""
                    )
                    return HealthResult(
                        ok=True,
                        latency_ms=(time.monotonic() - start) * 1000,
                        model=model_name,
                    )
                except requests.exceptions.Timeout:
                    return HealthResult(
                        ok=False,
                        latency_ms=(time.monotonic() - start) * 1000,
                        model="",
                        error=(f"{self._spec.provider_name} health check: Timeout"),
                    )
                except requests.exceptions.ConnectionError:
                    return HealthResult(
                        ok=False,
                        latency_ms=(time.monotonic() - start) * 1000,
                        model="",
                        error=(f"{self._spec.provider_name} health check failed"),
                    )
            return HealthResult(
                ok=False,
                latency_ms=(time.monotonic() - start) * 1000,
                model="",
                error=(f"{self._spec.provider_name} health check: Connection error"),
            )
        except Exception:
            return HealthResult(
                ok=False,
                latency_ms=(time.monotonic() - start) * 1000,
                model="",
                error=f"{self._spec.provider_name} health check failed",
            )
