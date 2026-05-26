"""
Base LLM Provider Interface.

Defines the abstract contract that all LLM providers must implement,
along with shared data types and a consistent error hierarchy.
"""

from __future__ import annotations

import abc
import time
from collections.abc import Generator
from dataclasses import dataclass

# Default timeout in seconds for HTTP requests.
DEFAULT_TIMEOUT: int = 300

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
class ModelInfo:
    """Information about a model available from a provider.

    Attributes:
        id:       The model identifier (e.g. ``"llama3.2"``).
        name:     Human-readable name (defaults to ``id``).
        provider: The provider type (e.g. ``"ollama"``, ``"groq"``).
    """

    id: str
    name: str = ""
    provider: str = ""

    def __post_init__(self) -> None:
        """Default ``name`` to ``id`` if not provided."""
        if not self.name:
            self.name = self.id

    def to_dict(self) -> dict:
        """Return a dict with ``id``, ``name``, and optional ``provider`` for JSON."""
        d: dict = {"id": self.id, "name": self.name}
        if self.provider:
            d["provider"] = self.provider
        return d


@dataclass
class ProviderConfig:
    """Configuration for an LLM provider connection.

    Attributes:
        base_url:       Base URL of the provider API endpoint.
        model:          Model identifier to use for completions.
        provider_type:  Provider type identifier (default "ollama").
        api_key:        Optional API key for authentication.
        timeout:        Request timeout in seconds (default 300).
        max_tokens:     Maximum tokens in the response (default None).
        temperature:    Sampling temperature (default None).
    """

    base_url: str
    model: str
    provider_type: str = "ollama"
    api_key: str | None = None
    timeout: int = DEFAULT_TIMEOUT
    max_tokens: int | None = None
    temperature: float | None = None

    def __repr__(self) -> str:
        """Return string representation with api_key redacted."""
        key = "****" if self.api_key is not None else None
        return (
            f"ProviderConfig(base_url={self.base_url!r}, "
            f"model={self.model!r}, "
            f"provider_type={self.provider_type!r}, "
            f"api_key={key!r}, "
            f"timeout={self.timeout}, "
            f"max_tokens={self.max_tokens!r}, "
            f"temperature={self.temperature!r})"
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
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
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
                timeout=data.get("timeout", DEFAULT_TIMEOUT),
                max_tokens=data.get("max_tokens"),
                temperature=data.get("temperature"),
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

    _last_stream_usage: dict | None = None
    """Token usage from the most recent streaming response, if available.

    Populated by ``stream()`` when the provider includes usage data
    in the final chunk before ``[DONE]``.
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
    def list_models(self) -> list[ModelInfo]:
        """Fetch available models from the provider.

        Makes an HTTP GET to the provider's model-list endpoint and
        returns the parsed results.  If the request fails for any
        reason (connection error, non-OK status, invalid JSON), an
        empty list is returned — this method **never raises**.

        Returns
        -------
        list[ModelInfo]
            A list of available models.  Always returns a list,
            empty on failure.
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
        ...


# ---------------------------------------------------------------------------
# Model-list caching
# ---------------------------------------------------------------------------

_model_cache: dict[str, tuple[list[ModelInfo], float]] = {}
"""Simple in-memory cache for provider model lists.

Maps ``"{provider_type}:{base_url}"`` to a ``(models, timestamp)``
tuple.  The cache lives for the lifetime of the process.
"""


def get_cached_models(
    provider_type: str,
    base_url: str,
    ttl: int = 300,
) -> list[ModelInfo] | None:
    """Return cached models for *provider_type* / *base_url* if still fresh.

    Parameters
    ----------
    provider_type:
        Provider type identifier (e.g. ``"ollama"``).
    base_url:
        Base URL of the provider.
    ttl:
        Time-to-live in seconds (default 300 = 5 minutes).

    Returns
    -------
    list[ModelInfo] | None
        The cached model list if available and within TTL, or ``None``
        if no valid cache entry exists.
    """
    key = f"{provider_type}:{base_url}"
    entry = _model_cache.get(key)
    if entry is None:
        return None
    models, timestamp = entry
    if time.monotonic() - timestamp > ttl:
        del _model_cache[key]
        return None
    return models


def set_cached_models(
    provider_type: str,
    base_url: str,
    models: list[ModelInfo],
) -> None:
    """Store *models* in the cache for *provider_type* / *base_url*.

    Parameters
    ----------
    provider_type:
        Provider type identifier (e.g. ``"ollama"``).
    base_url:
        Base URL of the provider.
    models:
        The model list to cache.
    """
    key = f"{provider_type}:{base_url}"
    _model_cache[key] = (models, time.monotonic())
