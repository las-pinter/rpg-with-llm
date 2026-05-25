"""
llama.cpp LLM Provider.

Implements the :class:`LLMProvider` interface for llama.cpp's ``llama-server``
using its OpenAI-compatible chat completion endpoint with a two-tier
health check.

.. _llama.cpp: https://github.com/ggml-org/llama.cpp
"""

from __future__ import annotations

from app.llm._openai_compat import OpenAICompatibleProvider, ProviderSpec

_SPEC = ProviderSpec(
    provider_name="llama.cpp",
    models_endpoint="/v1/models",
    models_key="data",
    name_key="id",
    health_endpoint="/v1/models",
    health_fallback_endpoint="/health",
)


class LlamacppProvider(OpenAICompatibleProvider):
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
        timeout: int = 300,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> None:
        super().__init__(
            base_url=base_url,
            model=model,
            api_key=api_key,
            timeout=timeout,
            max_tokens=max_tokens,
            temperature=temperature,
            spec=_SPEC,
        )
