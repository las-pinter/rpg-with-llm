"""
Unsloth LLM Provider.

Implements the :class:`LLMProvider` interface for Unsloth_ using its
OpenAI-compatible chat completion endpoint with a two-tier health check.

.. _Unsloth: https://unsloth.ai
"""

from __future__ import annotations

from app.llm._openai_compat import (
    OpenAICompatibleProvider,
    ProviderSpec,
)

_SPEC = ProviderSpec(
    provider_name="unsloth",
    models_endpoint="/v1/models",
    models_key="data",
    name_key="id",
    health_endpoint="/v1/models",
    health_fallback_endpoint="/health",
)


class UnslothProvider(OpenAICompatibleProvider):
    """LLM provider backed by an Unsloth instance.

    Communicates with Unsloth through its OpenAI-compatible
    ``/v1/chat/completions`` endpoint.  The health check uses a
    two-tier strategy: first try ``/v1/models`` (Unsloth Studio),
    then fall back to ``/health`` (raw llama-server).

    Parameters
    ----------
    base_url:
        Base URL of the Unsloth server (e.g. ``http://localhost:8000``).
    model:
        Model name to use for completions
        (e.g. ``"unsloth/Qwen3-4B-128K-GGUF:UD-Q4_K_XL"``).
    api_key:
        Optional API key.  Unsloth instances typically use
        ``sk-unsloth-...`` prefixed keys.
    timeout:
        Request timeout in seconds (default 30).
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        model: str = "unsloth/Qwen3-4B-128K-GGUF:UD-Q4_K_XL",
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
