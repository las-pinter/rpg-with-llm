"""
OpenRouter LLM Provider.

Implements the :class:`LLMProvider` interface for OpenRouter_ using its
OpenAI-compatible chat completion endpoint.

.. _OpenRouter: https://openrouter.ai
"""

from __future__ import annotations

import time

import requests

from app.llm._openai_compat import (
    OpenAICompatibleProvider,
    ProviderSpec,
)
from app.llm.base import HealthResult, ModelInfo

_SPEC = ProviderSpec(
    provider_name="OpenRouter",
    models_endpoint="/v1/models",
    models_key="data",
    name_key="id",
    name_key_fallback="name",
    health_endpoint="/v1/models",
)


class OpenRouterProvider(OpenAICompatibleProvider):
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
        # Normalize empty-string api_key to None (preserves original behavior).
        if api_key == "":
            api_key = None
        self.site_url = site_url
        self.app_name = app_name
        super().__init__(
            base_url=base_url,
            model=model,
            api_key=api_key,
            timeout=timeout,
            max_tokens=max_tokens,
            temperature=temperature,
            spec=_SPEC,
        )

    def list_models(self) -> list[ModelInfo]:
        """Fetch available models from the OpenRouter API.

        Uses lowercase ``"openrouter"`` for the provider field
        (matching original behavior).
        """
        models = super().list_models()
        for m in models:
            m.provider = "openrouter"
        return models

    def _headers(self) -> dict[str, str]:
        """Build common HTTP headers for OpenRouter API requests."""
        headers = super()._headers()
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        if self.app_name:
            headers["X-Title"] = self.app_name
        return headers

    def health(self) -> HealthResult:
        """Check if the OpenRouter API is reachable.

        Uses the configured model name in the result (original behavior)
        rather than extracting from the API response.
        """
        url = f"{self.base_url}/v1/models"
        start = time.monotonic()
        try:
            response = requests.get(
                url,
                headers=self._headers(),
                timeout=self.timeout,
            )
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
