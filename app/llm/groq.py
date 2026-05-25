"""
Groq LLM Provider.

Implements the :class:`LLMProvider` interface for Groq_ using its
OpenAI-compatible chat completion endpoint.

.. _Groq: https://groq.com
"""

from __future__ import annotations

from app.llm._openai_compat import (
    OpenAICompatibleProvider,
    ProviderSpec,
)

_SPEC = ProviderSpec(
    provider_name="Groq",
    models_endpoint="/v1/models",
    models_key="data",
    name_key="id",
    health_endpoint="/v1/models",
)


class GroqProvider(OpenAICompatibleProvider):
    """LLM provider backed by the Groq cloud API.

    Communicates with Groq through its OpenAI-compatible
    ``/v1/chat/completions`` endpoint.

    Parameters
    ----------
    base_url:
        Base URL of the Groq API (e.g. ``https://api.groq.com/openai``).
    model:
        Model name to use for completions (e.g. ``"llama3-70b-8192"``).
    api_key:
        API key for Groq authentication (required for API access).
    timeout:
        Request timeout in seconds (default 30).
    max_tokens:
        Maximum number of tokens to generate.
    temperature:
        Sampling temperature for generation.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout: int = 300,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> None:
        if api_key == "":
            api_key = None
        super().__init__(
            base_url=base_url,
            model=model,
            api_key=api_key,
            timeout=timeout,
            max_tokens=max_tokens,
            temperature=temperature,
            spec=_SPEC,
        )
