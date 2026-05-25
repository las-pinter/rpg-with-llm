"""
Ollama LLM Provider.

Implements the :class:`LLMProvider` interface for Ollama_ using its
OpenAI-compatible chat completion endpoint.

.. _Ollama: https://ollama.com
"""

from __future__ import annotations

from app.llm._openai_compat import OpenAICompatibleProvider, ProviderSpec

_SPEC: ProviderSpec = ProviderSpec(
    provider_name="Ollama",
    models_endpoint="/api/tags",
    models_key="models",
    name_key="name",
    health_endpoint="/api/tags",
)


class OllamaProvider(OpenAICompatibleProvider):
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
        # Normalize empty string api_key to None (preserves old behavior).
        if self.api_key == "":
            self.api_key = None
