"""
Base LLM Provider Interface.

Defines the abstract contract that all LLM providers must implement,
along with shared data types and a consistent error hierarchy.
"""

from __future__ import annotations

import abc
from collections.abc import Generator
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Error hierarchy
# ---------------------------------------------------------------------------


class LLMError(Exception):
    """Base exception for all LLM-related errors."""


class ProviderError(LLMError):
    """Raised when the provider returns an error response."""


class LLMTimeoutError(LLMError):
    """Raised when an LLM request exceeds the configured timeout."""


class LLMConnectionError(LLMError):
    """Raised when a connection to the LLM provider cannot be established."""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class HealthResult:
    """Result of a provider health check.

    Attributes:
        ok:        Whether the provider is reachable and functioning.
        latency_ms: Response time of the health check in milliseconds.
        model:     The model identifier that was checked.
        error:     Error message if the check failed, otherwise None.
    """

    ok: bool
    latency_ms: float
    model: str
    error: str | None = None


@dataclass
class ProviderConfig:
    """Configuration for an LLM provider connection.

    Attributes:
        base_url:       Base URL of the provider API endpoint.
        model:          Model identifier to use for completions.
        provider_type:  Provider type identifier (default "ollama").
        api_key:        Optional API key for authentication.
        timeout:        Request timeout in seconds (default 30).
    """

    base_url: str
    model: str
    provider_type: str = "ollama"
    api_key: str | None = None
    timeout: int = 30

    def __repr__(self) -> str:
        """Return string representation with api_key redacted."""
        key = "****" if self.api_key is not None else None
        return (
            f"ProviderConfig(base_url={self.base_url!r}, "
            f"model={self.model!r}, "
            f"provider_type={self.provider_type!r}, "
            f"api_key={key!r}, "
            f"timeout={self.timeout})"
        )

    def to_dict(self, redact_api_key: bool = False) -> dict:
        """Convert to a dictionary, optionally redacting the API key."""
        api_key = self.api_key
        if redact_api_key and api_key is not None:
            api_key = "****"
        return {
            "base_url": self.base_url,
            "model": self.model,
            "provider_type": self.provider_type,
            "api_key": api_key,
            "timeout": self.timeout,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ProviderConfig:
        """Create a ProviderConfig from a dictionary.

        Raises
        ------
        ValueError
            If a required field (``base_url``, ``model``) is missing.
        """
        try:
            return cls(
                base_url=data["base_url"],
                model=data["model"],
                provider_type=data.get("provider_type", "ollama"),
                api_key=data.get("api_key"),
                timeout=data.get("timeout", 30),
            )
        except KeyError as e:
            raise ValueError(f"Missing required config field: {e}") from e


# ---------------------------------------------------------------------------
# Abstract provider interface
# ---------------------------------------------------------------------------


class LLMProvider(abc.ABC):
    """Abstract base class for all LLM providers.

    Every concrete provider must implement ``call()``, ``stream()``,
    and ``health()``.  Messages follow the OpenAI chat-completion
    format:

    .. code-block:: python

        [
            {"role": "system",    "content": "You are a helpful assistant."},
            {"role": "user",      "content": "Hello!"},
            {"role": "assistant", "content": "Hi there!"},
        ]

    Implementations should handle authentication, retry logic, and
    connection pooling internally.
    """

    @abc.abstractmethod
    def call(self, messages: list[dict]) -> dict:
        """Send a non-streaming chat completion request.

        Parameters
        ----------
        messages : list[dict]
            Conversation history in OpenAI format.  Each dict has
            ``role`` (``"system"`` | ``"user"`` | ``"assistant"``)
            and ``content`` (str) keys.

        Returns
        -------
        dict
            A dictionary with at least the following keys:

            - ``content``       (str)  – The model's response text.
            - ``finish_reason`` (str)  – Reason the generation stopped
              (e.g. ``"stop"``, ``"length"``).
            - ``usage``         (dict) – Token usage metadata with keys
              ``prompt_tokens``, ``completion_tokens``,
              ``total_tokens``.

        Raises
        ------
        ProviderError
            If the provider returns a non-success status.
        LLMTimeoutError
            If the request exceeds the configured timeout.
        LLMConnectionError
            If the provider is unreachable.
        """

    @abc.abstractmethod
    def stream(self, messages: list[dict]) -> Generator[str, None, None]:
        """Send a streaming chat completion request.

        Parameters
        ----------
        messages : list[dict]
            Same OpenAI-format message list as :meth:`call`.

        Yields
        ------
        str
            Content tokens as they are received from the provider.

        Raises
        ------
        ProviderError
            If the provider returns a non-success status.
        LLMTimeoutError
            If the request exceeds the configured timeout.
        LLMConnectionError
            If the provider is unreachable.
        """

    @abc.abstractmethod
    def health(self) -> HealthResult:
        """Check whether the provider is reachable and working.

        Implementations should perform a lightweight request (e.g. a
        model-list endpoint or a minimal completion) and measure
        latency.

        Returns
        -------
        HealthResult
            A dataclass with ``ok``, ``latency_ms``, ``model``,
            and optionally ``error``.
        """
