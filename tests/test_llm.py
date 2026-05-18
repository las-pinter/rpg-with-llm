"""Tests for the base LLM provider interface."""

from __future__ import annotations

from collections.abc import Generator

import pytest

from app.llm.base import (
    HealthResult,
    LLMConnectionError,
    LLMError,
    LLMProvider,
    LLMTimeoutError,
    ProviderConfig,
    ProviderError,
)

# ---------------------------------------------------------------------------
# Concrete mock provider used across several tests
# ---------------------------------------------------------------------------


class MockProvider(LLMProvider):
    """A minimal concrete provider for testing the abstract interface."""

    def call(self, messages: list[dict]) -> dict:
        return {
            "content": "Mock response",
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

    def stream(self, messages: list[dict]) -> Generator[str, None, None]:
        yield "Mock "
        yield "streaming "
        yield "response"

    def health(self) -> HealthResult:
        return HealthResult(ok=True, latency_ms=42.0, model="mock-model")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLLMProvider:
    """Tests for the LLMProvider abstract base class."""

    def test_cannot_instantiate_directly(self):
        """LLMProvider should raise TypeError when instantiated directly."""
        with pytest.raises(TypeError):
            LLMProvider()  # type: ignore[abstract]

    def test_mock_subclass_implements_all_methods(self):
        """A concrete subclass should be instantiable and implement all methods."""
        provider = MockProvider()

        # call()
        result = provider.call([{"role": "user", "content": "Hi"}])
        assert isinstance(result, dict)
        assert "content" in result
        assert "finish_reason" in result
        assert "usage" in result

        # stream()
        tokens = list(provider.stream([{"role": "user", "content": "Hi"}]))
        assert tokens == ["Mock ", "streaming ", "response"]

        # health()
        h = provider.health()
        assert isinstance(h, HealthResult)
        assert h.ok is True
        assert h.latency_ms == 42.0

    def test_mock_provider_returns_expected_content(self):
        """Verify the mock's non-streaming response shape."""
        provider = MockProvider()
        result = provider.call([{"role": "user", "content": "hello"}])

        assert result["content"] == "Mock response"
        assert result["finish_reason"] == "stop"
        assert result["usage"]["total_tokens"] == 15


class TestHealthResult:
    """Tests for the HealthResult dataclass."""

    def test_fields(self):
        """HealthResult should have the expected fields."""
        h = HealthResult(ok=True, latency_ms=12.5, model="gpt-4")
        assert h.ok is True
        assert h.latency_ms == 12.5
        assert h.model == "gpt-4"
        assert h.error is None

    def test_error_field_defaults_to_none(self):
        """The error field should be None when not provided."""
        h = HealthResult(ok=False, latency_ms=0.0, model="gpt-4")
        assert h.error is None

    def test_error_field_with_message(self):
        """The error field should store the provided message."""
        h = HealthResult(
            ok=False,
            latency_ms=0.0,
            model="gpt-4",
            error="Connection refused",
        )
        assert h.error == "Connection refused"


class TestProviderConfig:
    """Tests for the ProviderConfig dataclass."""

    def test_fields(self):
        """ProviderConfig should have the expected fields."""
        cfg = ProviderConfig(base_url="https://api.example.com", model="gpt-4")
        assert cfg.base_url == "https://api.example.com"
        assert cfg.model == "gpt-4"

    def test_api_key_defaults_to_none(self):
        """api_key should default to None."""
        cfg = ProviderConfig(base_url="https://api.example.com", model="gpt-4")
        assert cfg.api_key is None

    def test_timeout_defaults_to_30(self):
        """timeout should default to 30."""
        cfg = ProviderConfig(base_url="https://api.example.com", model="gpt-4")
        assert cfg.timeout == 30

    def test_custom_api_key(self):
        """api_key should accept a provided value."""
        cfg = ProviderConfig(
            base_url="https://api.example.com",
            model="gpt-4",
            api_key="sk-test",
        )
        assert cfg.api_key == "sk-test"

    def test_custom_timeout(self):
        """timeout should accept a custom value."""
        cfg = ProviderConfig(
            base_url="https://api.example.com",
            model="gpt-4",
            timeout=60,
        )
        assert cfg.timeout == 60


class TestErrorHierarchy:
    """Tests for the LLM error hierarchy."""

    def test_llm_error_is_exception(self):
        """LLMError should inherit from Exception."""
        assert issubclass(LLMError, Exception)

    def test_provider_error_is_llm_error(self):
        """ProviderError should inherit from LLMError."""
        assert issubclass(ProviderError, LLMError)

    def test_timeout_error_is_llm_error(self):
        """LLMTimeoutError should inherit from LLMError."""
        assert issubclass(LLMTimeoutError, LLMError)

    def test_connection_error_is_llm_error(self):
        """LLMConnectionError should inherit from LLMError."""
        assert issubclass(LLMConnectionError, LLMError)

    def test_all_custom_exceptions_are_llm_errors(self):
        """All custom exceptions should be instances of LLMError."""
        for exc in (ProviderError, LLMTimeoutError, LLMConnectionError):
            assert issubclass(exc, LLMError)

    def test_llm_error_can_be_raised_and_caught(self):
        """LLMError should be raiseable and catchable."""
        with pytest.raises(LLMError):
            raise ProviderError("provider broke")

        with pytest.raises(LLMError):
            raise LLMTimeoutError("timed out")

        with pytest.raises(LLMError):
            raise LLMConnectionError("connection lost")

    def test_provider_error_message(self):
        """ProviderError should carry its message."""
        err = ProviderError("bad request")
        assert str(err) == "bad request"

    def test_timeout_error_message(self):
        """LLMTimeoutError should carry its message."""
        err = LLMTimeoutError("request timed out")
        assert str(err) == "request timed out"

    def test_connection_error_message(self):
        """LLMConnectionError should carry its message."""
        err = LLMConnectionError("connection refused")
        assert str(err) == "connection refused"


class TestMessageFormat:
    """Tests related to the OpenAI message format convention."""

    def test_valid_openai_message_structure(self):
        """Verify the expected OpenAI message format is documented and usable."""
        valid_messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        provider = MockProvider()
        result = provider.call(valid_messages)
        assert result["content"] == "Mock response"

        stream_tokens = list(provider.stream(valid_messages))
        assert "".join(stream_tokens) == "Mock streaming response"


# ---------------------------------------------------------------------------
# Ollama provider tests
# ---------------------------------------------------------------------------


class TestOllamaProvider:
    """Tests for the OllamaProvider implementation."""

    def test_is_instance_of_llm_provider(self):
        """OllamaProvider should be a concrete LLMProvider subclass."""
        from app.llm.ollama import OllamaProvider

        provider = OllamaProvider(base_url="http://localhost:11434", model="llama3.2")
        assert isinstance(provider, LLMProvider)

    def test_initialization_defaults(self):
        """Default values for api_key and timeout should be set correctly."""
        from app.llm.ollama import OllamaProvider

        provider = OllamaProvider(
            base_url="http://localhost:11434",
            model="llama3.2",
        )
        assert provider.base_url == "http://localhost:11434"
        assert provider.model == "llama3.2"
        assert provider.api_key is None
        assert provider.timeout == 30

    def test_initialization_custom_values(self):
        """Custom constructor arguments should be stored."""
        from app.llm.ollama import OllamaProvider

        provider = OllamaProvider(
            base_url="http://my-ollama:11434/",
            model="mistral",
            api_key="sk-test",
            timeout=60,
        )
        # Trailing slash should be stripped
        assert provider.base_url == "http://my-ollama:11434"
        assert provider.model == "mistral"
        assert provider.api_key == "sk-test"
        assert provider.timeout == 60

    def test_initialization_strips_trailing_slash(self):
        """Trailing slashes on base_url should be removed."""
        from app.llm.ollama import OllamaProvider

        provider = OllamaProvider(
            base_url="http://localhost:11434///",
            model="llama3.2",
        )
        assert provider.base_url == "http://localhost:11434"

    def test_call_sends_correct_payload(self):
        """call() should POST to /v1/chat/completions with correct body."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.ollama import OllamaProvider

        provider = OllamaProvider(
            base_url="http://localhost:11434",
            model="llama3.2",
            api_key="sk-test",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "llama3.2",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Hello! How can I help?",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }

        messages = [{"role": "user", "content": "Hi"}]

        with patch(
            "app.llm.ollama.requests.post",
            return_value=mock_response,
        ) as mock_post:
            result = provider.call(messages)

        # Verify the request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "http://localhost:11434/v1/chat/completions"
        assert call_args[1]["json"] == {
            "model": "llama3.2",
            "messages": messages,
            "stream": False,
        }
        assert call_args[1]["headers"] == {
            "Content-Type": "application/json",
            "Authorization": "Bearer sk-test",
        }
        assert call_args[1]["timeout"] == 30

        # Verify the returned dict shape
        assert result == {
            "content": "Hello! How can I help?",
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

    def test_call_returns_formatted_response(self):
        """call() should parse the response into the expected dict format."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.ollama import OllamaProvider

        provider = OllamaProvider(
            base_url="http://localhost:11434",
            model="llama3.2",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-456",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "llama3.2",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Sure, here is a poem...",
                    },
                    "finish_reason": "length",
                }
            ],
            "usage": {
                "prompt_tokens": 25,
                "completion_tokens": 100,
                "total_tokens": 125,
            },
        }

        with patch("app.llm.ollama.requests.post", return_value=mock_response):
            result = provider.call([{"role": "user", "content": "Write a poem"}])

        assert result["content"] == "Sure, here is a poem..."
        assert result["finish_reason"] == "length"
        assert result["usage"]["total_tokens"] == 125

    def test_stream_yields_tokens(self):
        """stream() should yield content tokens from SSE lines."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.ollama import OllamaProvider

        provider = OllamaProvider(
            base_url="http://localhost:11434",
            model="llama3.2",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            (
                b'data: {"choices":[{"index":0,"delta":{"content":"Hello "},'
                b'"finish_reason":null}]}'
            ),
            (
                b'data: {"choices":[{"index":0,"delta":{"content":"world"},'
                b'"finish_reason":null}]}'
            ),
            (
                b'data: {"choices":[{"index":0,"delta":{"content":"!"},'
                b'"finish_reason":null}]}'
            ),
            (b'data: {"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}'),
            b"data: [DONE]",
        ]

        with patch(
            "app.llm.ollama.requests.post",
            return_value=mock_response,
        ) as mock_post:
            tokens = list(provider.stream([{"role": "user", "content": "Hi"}]))

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]["json"]["stream"] is True

        assert tokens == ["Hello ", "world", "!"]

    def test_stream_skips_empty_lines_and_irrelevant_data(self):
        """stream() should gracefully handle blank lines and non-data SSE."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.ollama import OllamaProvider

        provider = OllamaProvider(
            base_url="http://localhost:11434",
            model="llama3.2",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b"",
            b'data: {"choices":[{"index":0,"delta":{"content":"Hi"}}]}',
            b":comment",
            b'data: {"choices":[{"index":0,"delta":{"content":" there"}}]}',
            b"data: [DONE]",
        ]

        with patch("app.llm.ollama.requests.post", return_value=mock_response):
            tokens = list(provider.stream([{"role": "user", "content": "Hi"}]))

        assert tokens == ["Hi", " there"]

    def test_health_returns_success(self):
        """health() should return a HealthResult with ok=True on success."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.ollama import OllamaProvider

        provider = OllamaProvider(
            base_url="http://localhost:11434",
            model="llama3.2",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200

        with patch("app.llm.ollama.requests.get", return_value=mock_response):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is True
        assert result.model == "llama3.2"
        assert result.error is None
        assert result.latency_ms >= 0

    def test_health_returns_failure_on_http_error(self):
        """health() should return a HealthResult with ok=False on HTTP error."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.ollama import OllamaProvider

        provider = OllamaProvider(
            base_url="http://localhost:11434",
            model="llama3.2",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = False
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("app.llm.ollama.requests.get", return_value=mock_response):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is False
        assert result.model == "llama3.2"
        assert result.error is not None
        assert "500" in result.error
        assert result.latency_ms >= 0

    def test_health_handles_connection_error(self):
        """health() should return ok=False when connection is refused."""
        from unittest.mock import patch

        import requests

        from app.llm.ollama import OllamaProvider

        provider = OllamaProvider(
            base_url="http://localhost:11434",
            model="llama3.2",
        )

        with patch(
            "app.llm.ollama.requests.get",
            side_effect=requests.exceptions.ConnectionError("Connection refused"),
        ):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is False
        assert result.error is not None
        assert "Connection error" in result.error

    def test_http_error_raises_provider_error(self):
        """call() should raise ProviderError on HTTP 4xx/5xx."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.ollama import OllamaProvider

        provider = OllamaProvider(
            base_url="http://localhost:11434",
            model="llama3.2",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = False
        mock_response.status_code = 400
        mock_response.text = '{"error": "bad request"}'
        mock_response.__bool__ = lambda self: False

        with patch("app.llm.ollama.requests.post", return_value=mock_response):
            with pytest.raises(ProviderError) as excinfo:
                provider.call([{"role": "user", "content": "Hi"}])

        assert "400" in str(excinfo.value)
        assert "bad request" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_http_error_in_stream_raises_provider_error(self):
        """stream() should raise ProviderError on HTTP 4xx/5xx."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.ollama import OllamaProvider

        provider = OllamaProvider(
            base_url="http://localhost:11434",
            model="llama3.2",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = False
        mock_response.status_code = 401
        mock_response.text = "unauthorized"

        with patch("app.llm.ollama.requests.post", return_value=mock_response):
            with pytest.raises(ProviderError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert "401" in str(excinfo.value)

    def test_timeout_raises_timeout_error(self):
        """call() should raise LLMTimeoutError on request timeout."""
        from unittest.mock import patch

        import requests

        from app.llm.ollama import OllamaProvider

        provider = OllamaProvider(
            base_url="http://localhost:11434",
            model="llama3.2",
            timeout=5,
        )

        with patch(
            "app.llm.ollama.requests.post",
            side_effect=requests.exceptions.Timeout("Connection timed out"),
        ):
            with pytest.raises(LLMTimeoutError) as excinfo:
                provider.call([{"role": "user", "content": "Hi"}])

        assert "timed out" in str(excinfo.value).lower()
        assert isinstance(excinfo.value, LLMError)

    def test_connection_error_raises_connection_error(self):
        """call() should raise LLMConnectionError when provider is unreachable."""
        from unittest.mock import patch

        import requests

        from app.llm.ollama import OllamaProvider

        provider = OllamaProvider(
            base_url="http://localhost:11434",
            model="llama3.2",
        )

        with patch(
            "app.llm.ollama.requests.post",
            side_effect=requests.exceptions.ConnectionError("Connection refused"),
        ):
            with pytest.raises(LLMConnectionError) as excinfo:
                provider.call([{"role": "user", "content": "Hi"}])

        assert "Cannot connect" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_invalid_json_raises_provider_error(self):
        """call() should raise ProviderError when response is not valid JSON."""
        import json
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.ollama import OllamaProvider

        provider = OllamaProvider(
            base_url="http://localhost:11434",
            model="llama3.2",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)

        with patch("app.llm.ollama.requests.post", return_value=mock_response):
            with pytest.raises(ProviderError) as excinfo:
                provider.call([{"role": "user", "content": "Hi"}])

        assert "Invalid JSON" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_stream_empty_choices_array_does_not_crash(self):
        """stream() should not crash when a chunk has an empty choices array."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.ollama import OllamaProvider

        provider = OllamaProvider(base_url="http://localhost:11434", model="llama3.2")
        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b'data: {"choices":[],"finish_reason":null}',
            b"data: [DONE]",
        ]
        with patch("app.llm.ollama.requests.post", return_value=mock_response):
            tokens = list(provider.stream([{"role": "user", "content": "Hi"}]))
        assert tokens == []

    def test_stream_timeout_raises_timeout_error(self):
        """stream() should raise LLMTimeoutError on request timeout."""
        from unittest.mock import patch

        import requests

        from app.llm.ollama import OllamaProvider

        provider = OllamaProvider(
            base_url="http://localhost:11434",
            model="llama3.2",
        )

        with patch(
            "app.llm.ollama.requests.post",
            side_effect=requests.exceptions.Timeout("Stream timed out"),
        ):
            with pytest.raises(LLMTimeoutError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert isinstance(excinfo.value, LLMError)

    def test_stream_connection_error_raises_connection_error(self):
        """stream() should raise LLMConnectionError when provider is unreachable."""
        from unittest.mock import patch

        import requests

        from app.llm.ollama import OllamaProvider

        provider = OllamaProvider(
            base_url="http://localhost:11434",
            model="llama3.2",
        )

        with patch(
            "app.llm.ollama.requests.post",
            side_effect=requests.exceptions.ConnectionError("Connection refused"),
        ):
            with pytest.raises(LLMConnectionError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert isinstance(excinfo.value, LLMError)

    def test_stream_chunked_encoding_error_raises_connection_error(self):
        """stream() should raise LLMConnectionError when connection drops mid-stream."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.ollama import OllamaProvider

        provider = OllamaProvider(
            base_url="http://localhost:11434",
            model="llama3.2",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        # Simulate connection dropping mid-stream
        mock_response.iter_lines.side_effect = requests.exceptions.ChunkedEncodingError(
            "Connection broken"
        )

        with patch("app.llm.ollama.requests.post", return_value=mock_response):
            with pytest.raises(LLMConnectionError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert "Stream connection lost" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_stream_generic_request_exception_raises_provider_error(self):
        """stream() should raise ProviderError on generic request error mid-stream."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.ollama import OllamaProvider

        provider = OllamaProvider(
            base_url="http://localhost:11434",
            model="llama3.2",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.side_effect = requests.exceptions.RequestException(
            "Something went wrong"
        )

        with patch("app.llm.ollama.requests.post", return_value=mock_response):
            with pytest.raises(ProviderError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert "Stream error" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_api_key_empty_string_normalized_to_none(self):
        """Empty string api_key should be normalized to None."""
        from app.llm.ollama import OllamaProvider

        provider = OllamaProvider(
            base_url="http://localhost:11434",
            model="llama3.2",
            api_key="",
        )
        assert provider.api_key is None

    def test_base_url_whitespace_stripped(self):
        """base_url should have leading/trailing whitespace stripped."""
        from app.llm.ollama import OllamaProvider

        provider = OllamaProvider(
            base_url="  http://localhost:11434  ",
            model="llama3.2",
        )
        assert provider.base_url == "http://localhost:11434"


# ---------------------------------------------------------------------------
# Groq provider tests
# ---------------------------------------------------------------------------


class TestGroqProvider:
    """Tests for the GroqProvider implementation."""

    def test_is_instance_of_llm_provider(self):
        """GroqProvider should be a concrete LLMProvider subclass."""
        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
        )
        assert isinstance(provider, LLMProvider)

    def test_initialization_defaults(self):
        """Default values for api_key and timeout should be set correctly."""
        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
        )
        assert provider.base_url == "https://api.groq.com/openai"
        assert provider.model == "llama3-70b-8192"
        assert provider.api_key is None
        assert provider.timeout == 30

    def test_initialization_custom_values(self):
        """Custom constructor arguments should be stored."""
        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://custom.groq.com/openai/v1/",
            model="mixtral-8x7b-32768",
            api_key="gsk-test",
            timeout=120,
        )
        # Trailing slash should be stripped
        assert provider.base_url == "https://custom.groq.com/openai/v1"
        assert provider.model == "mixtral-8x7b-32768"
        assert provider.api_key == "gsk-test"
        assert provider.timeout == 120

    def test_initialization_strips_trailing_slash(self):
        """Trailing slashes on base_url should be removed."""
        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai///",
            model="llama3-70b-8192",
        )
        assert provider.base_url == "https://api.groq.com/openai"

    def test_call_sends_correct_payload(self):
        """call() should POST to /v1/chat/completions with correct body."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
            api_key="gsk-test",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "llama3-70b-8192",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Hello! How can I help?",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }

        messages = [{"role": "user", "content": "Hi"}]

        with patch(
            "app.llm.groq.requests.post",
            return_value=mock_response,
        ) as mock_post:
            result = provider.call(messages)

        # Verify the request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://api.groq.com/openai/v1/chat/completions"
        assert call_args[1]["json"] == {
            "model": "llama3-70b-8192",
            "messages": messages,
            "stream": False,
        }
        assert call_args[1]["headers"] == {
            "Content-Type": "application/json",
            "Authorization": "Bearer gsk-test",
        }
        assert call_args[1]["timeout"] == 30

        # Verify the returned dict shape
        assert result == {
            "content": "Hello! How can I help?",
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

    def test_call_returns_formatted_response(self):
        """call() should parse the response into the expected dict format."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-456",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "llama3-70b-8192",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Sure, here is a poem...",
                    },
                    "finish_reason": "length",
                }
            ],
            "usage": {
                "prompt_tokens": 25,
                "completion_tokens": 100,
                "total_tokens": 125,
            },
        }

        with patch("app.llm.groq.requests.post", return_value=mock_response):
            result = provider.call([{"role": "user", "content": "Write a poem"}])

        assert result["content"] == "Sure, here is a poem..."
        assert result["finish_reason"] == "length"
        assert result["usage"]["total_tokens"] == 125

    def test_stream_yields_tokens(self):
        """stream() should yield content tokens from SSE lines."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            (
                b'data: {"choices":[{"index":0,"delta":{"content":"Hello "},'
                b'"finish_reason":null}]}'
            ),
            (
                b'data: {"choices":[{"index":0,"delta":{"content":"world"},'
                b'"finish_reason":null}]}'
            ),
            (
                b'data: {"choices":[{"index":0,"delta":{"content":"!"},'
                b'"finish_reason":null}]}'
            ),
            (b'data: {"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}'),
            b"data: [DONE]",
        ]

        with patch(
            "app.llm.groq.requests.post",
            return_value=mock_response,
        ) as mock_post:
            tokens = list(provider.stream([{"role": "user", "content": "Hi"}]))

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]["json"]["stream"] is True

        assert tokens == ["Hello ", "world", "!"]

    def test_stream_skips_empty_lines_and_irrelevant_data(self):
        """stream() should gracefully handle blank lines and non-data SSE."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b"",
            b'data: {"choices":[{"index":0,"delta":{"content":"Hi"}}]}',
            b":comment",
            b'data: {"choices":[{"index":0,"delta":{"content":" there"}}]}',
            b"data: [DONE]",
        ]

        with patch("app.llm.groq.requests.post", return_value=mock_response):
            tokens = list(provider.stream([{"role": "user", "content": "Hi"}]))

        assert tokens == ["Hi", " there"]

    def test_health_returns_success(self):
        """health() should return a HealthResult with ok=True on success."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200

        with patch("app.llm.groq.requests.get", return_value=mock_response):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is True
        assert result.model == "llama3-70b-8192"
        assert result.error is None
        assert result.latency_ms >= 0

    def test_health_returns_failure_on_http_error(self):
        """health() should return a HealthResult with ok=False on HTTP error."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = False
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("app.llm.groq.requests.get", return_value=mock_response):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is False
        assert result.model == "llama3-70b-8192"
        assert result.error is not None
        assert "500" in result.error
        assert result.latency_ms >= 0

    def test_health_handles_connection_error(self):
        """health() should return ok=False when connection is refused."""
        from unittest.mock import patch

        import requests

        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
        )

        with patch(
            "app.llm.groq.requests.get",
            side_effect=requests.exceptions.ConnectionError("Connection refused"),
        ):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is False
        assert result.error is not None
        assert "Connection error" in result.error

    def test_http_error_raises_provider_error(self):
        """call() should raise ProviderError on HTTP 4xx/5xx."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = False
        mock_response.status_code = 400
        mock_response.text = '{"error": "bad request"}'
        mock_response.__bool__ = lambda self: False

        with patch("app.llm.groq.requests.post", return_value=mock_response):
            with pytest.raises(ProviderError) as excinfo:
                provider.call([{"role": "user", "content": "Hi"}])

        assert "400" in str(excinfo.value)
        assert "bad request" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_http_error_in_stream_raises_provider_error(self):
        """stream() should raise ProviderError on HTTP 4xx/5xx."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = False
        mock_response.status_code = 401
        mock_response.text = "unauthorized"

        with patch("app.llm.groq.requests.post", return_value=mock_response):
            with pytest.raises(ProviderError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert "401" in str(excinfo.value)

    def test_timeout_raises_timeout_error(self):
        """call() should raise LLMTimeoutError on request timeout."""
        from unittest.mock import patch

        import requests

        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
            timeout=5,
        )

        with patch(
            "app.llm.groq.requests.post",
            side_effect=requests.exceptions.Timeout("Connection timed out"),
        ):
            with pytest.raises(LLMTimeoutError) as excinfo:
                provider.call([{"role": "user", "content": "Hi"}])

        assert "timed out" in str(excinfo.value).lower()
        assert isinstance(excinfo.value, LLMError)

    def test_connection_error_raises_connection_error(self):
        """call() should raise LLMConnectionError when provider is unreachable."""
        from unittest.mock import patch

        import requests

        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
        )

        with patch(
            "app.llm.groq.requests.post",
            side_effect=requests.exceptions.ConnectionError("Connection refused"),
        ):
            with pytest.raises(LLMConnectionError) as excinfo:
                provider.call([{"role": "user", "content": "Hi"}])

        assert "Cannot connect" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_invalid_json_raises_provider_error(self):
        """call() should raise ProviderError when response is not valid JSON."""
        import json
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)

        with patch("app.llm.groq.requests.post", return_value=mock_response):
            with pytest.raises(ProviderError) as excinfo:
                provider.call([{"role": "user", "content": "Hi"}])

        assert "Invalid JSON" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_stream_invalid_json_chunk_raises_provider_error(self):
        """stream() should raise ProviderError on malformed SSE data."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b"data: {invalid json here}",
        ]

        with patch("app.llm.groq.requests.post", return_value=mock_response):
            with pytest.raises(ProviderError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert "Invalid JSON" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_stream_timeout_raises_timeout_error(self):
        """stream() should raise LLMTimeoutError on request timeout."""
        from unittest.mock import patch

        import requests

        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
        )

        with patch(
            "app.llm.groq.requests.post",
            side_effect=requests.exceptions.Timeout("Stream timed out"),
        ):
            with pytest.raises(LLMTimeoutError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert isinstance(excinfo.value, LLMError)

    def test_stream_connection_error_raises_connection_error(self):
        """stream() should raise LLMConnectionError when provider is unreachable."""
        from unittest.mock import patch

        import requests

        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
        )

        with patch(
            "app.llm.groq.requests.post",
            side_effect=requests.exceptions.ConnectionError("Connection refused"),
        ):
            with pytest.raises(LLMConnectionError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert isinstance(excinfo.value, LLMError)

    def test_stream_chunked_encoding_error_raises_connection_error(self):
        """stream() should raise LLMConnectionError when connection drops mid-stream."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        # Simulate connection dropping mid-stream
        mock_response.iter_lines.side_effect = requests.exceptions.ChunkedEncodingError(
            "Connection broken"
        )

        with patch("app.llm.groq.requests.post", return_value=mock_response):
            with pytest.raises(LLMConnectionError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert "Stream connection lost" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_stream_generic_request_exception_raises_provider_error(self):
        """stream() should raise ProviderError on generic request error mid-stream."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.side_effect = requests.exceptions.RequestException(
            "Something went wrong"
        )

        with patch("app.llm.groq.requests.post", return_value=mock_response):
            with pytest.raises(ProviderError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert "Stream error" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_api_key_empty_string_normalized_to_none(self):
        """Empty string api_key should be normalized to None."""
        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
            api_key="",
        )
        assert provider.api_key is None

    def test_base_url_whitespace_stripped(self):
        """base_url should have leading/trailing whitespace stripped."""
        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="  https://api.groq.com/openai  ",
            model="llama3-70b-8192",
        )
        assert provider.base_url == "https://api.groq.com/openai"

    # ------------------------------------------------------------------
    # Stream edge cases (beyond happy path)
    # ------------------------------------------------------------------

    def test_stream_empty_only_done(self):
        """stream() should yield nothing when only [DONE] is received."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [b"data: [DONE]"]

        with patch("app.llm.groq.requests.post", return_value=mock_response):
            tokens = list(provider.stream([{"role": "user", "content": "Hi"}]))

        assert tokens == []

    def test_stream_non_content_delta_only(self):
        """stream() should skip deltas without a 'content' key."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b'data: {"choices":[{"index":0,"delta":{},"finish_reason":null}]}',
            b'data: {"choices":[{"index":0,"delta":{"role":"assistant"},'
            b'"finish_reason":null}]}',
            b'data: {"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}',
            b"data: [DONE]",
        ]

        with patch("app.llm.groq.requests.post", return_value=mock_response):
            tokens = list(provider.stream([{"role": "user", "content": "Hi"}]))

        assert tokens == []

    def test_stream_empty_choices_array_does_not_crash(self):
        """stream() should handle an empty choices array gracefully."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b'data: {"choices":[],"finish_reason":null}',
            b"data: [DONE]",
        ]

        with patch("app.llm.groq.requests.post", return_value=mock_response):
            tokens = list(provider.stream([{"role": "user", "content": "Hi"}]))

        assert tokens == []

    # ------------------------------------------------------------------
    # Health-check edge cases
    # ------------------------------------------------------------------

    def test_health_returns_failure_on_403(self):
        """health() should return ok=False on HTTP 403 (unauthorized)."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = False
        mock_response.status_code = 403
        mock_response.text = "Forbidden"

        with patch("app.llm.groq.requests.get", return_value=mock_response):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is False
        assert result.model == "llama3-70b-8192"
        assert "403" in result.error
        assert result.latency_ms >= 0

    def test_health_handles_timeout(self):
        """health() should return ok=False when the request times out."""
        from unittest.mock import patch

        import requests

        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
        )

        with patch(
            "app.llm.groq.requests.get",
            side_effect=requests.exceptions.Timeout("Timed out"),
        ):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is False
        assert "Timeout" in result.error
        assert result.latency_ms >= 0

    # ------------------------------------------------------------------
    # call() response-parsing edge cases
    # ------------------------------------------------------------------

    def test_call_missing_choices_key(self):
        """call() should raise KeyError when response has no 'choices'."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "model": "llama3-70b-8192",
        }

        with patch("app.llm.groq.requests.post", return_value=mock_response):
            with pytest.raises(KeyError):
                provider.call([{"role": "user", "content": "Hi"}])

    def test_call_empty_choices_array(self):
        """call() should raise IndexError when choices array is empty."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "model": "llama3-70b-8192",
            "choices": [],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

        with patch("app.llm.groq.requests.post", return_value=mock_response):
            with pytest.raises(IndexError):
                provider.call([{"role": "user", "content": "Hi"}])

    def test_call_missing_message_in_choice(self):
        """call() should raise KeyError when a choice has no 'message'."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "model": "llama3-70b-8192",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

        with patch("app.llm.groq.requests.post", return_value=mock_response):
            with pytest.raises(KeyError):
                provider.call([{"role": "user", "content": "Hi"}])

    def test_call_missing_usage(self):
        """call() should raise KeyError when response has no 'usage'."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "model": "llama3-70b-8192",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Hello!",
                    },
                    "finish_reason": "stop",
                }
            ],
        }

        with patch("app.llm.groq.requests.post", return_value=mock_response):
            with pytest.raises(KeyError):
                provider.call([{"role": "user", "content": "Hi"}])

    def test_call_extra_fields_in_response(self):
        """call() should ignore unexpected fields in the response."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-789",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "llama3-70b-8192",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Hello!",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
            "system_fingerprint": "fp_abc123",
            "x_groq": {"hint": "extra metadata"},
        }

        with patch("app.llm.groq.requests.post", return_value=mock_response):
            result = provider.call([{"role": "user", "content": "Hi"}])

        assert result["content"] == "Hello!"
        assert result["finish_reason"] == "stop"
        assert result["usage"]["total_tokens"] == 15

    # ------------------------------------------------------------------
    # Constructor edge cases
    # ------------------------------------------------------------------

    def test_constructor_api_key_explicit_none(self):
        """api_key=None should be stored as None."""
        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
            api_key=None,
        )
        assert provider.api_key is None

    def test_constructor_timeout_zero(self):
        """timeout=0 should be stored without validation."""
        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
            timeout=0,
        )
        assert provider.timeout == 0

    def test_constructor_very_long_model_name(self):
        """A very long model name should be accepted."""
        from app.llm.groq import GroqProvider

        long_name = "meta-llama/" + "x" * 500 + ":v1"
        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model=long_name,
        )
        assert provider.model == long_name

    # ------------------------------------------------------------------
    # _headers() edge cases
    # ------------------------------------------------------------------

    def test_headers_no_api_key(self):
        """_headers() should not include Authorization when api_key is None."""
        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
        )
        headers = provider._headers()
        assert headers == {"Content-Type": "application/json"}
        assert "Authorization" not in headers

    def test_headers_with_api_key(self):
        """_headers() should include Bearer Authorization when api_key is set."""
        from app.llm.groq import GroqProvider

        provider = GroqProvider(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
            api_key="gsk-test-key",
        )
        headers = provider._headers()
        assert headers == {
            "Content-Type": "application/json",
            "Authorization": "Bearer gsk-test-key",
        }


# ---------------------------------------------------------------------------
# OpenRouter provider tests
# ---------------------------------------------------------------------------


class TestOpenRouterProvider:
    """Tests for the OpenRouterProvider implementation."""

    def test_is_instance_of_llm_provider(self):
        """OpenRouterProvider should be a concrete LLMProvider subclass."""
        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
        )
        assert isinstance(provider, LLMProvider)

    def test_initialization_defaults(self):
        """Default values for api_key and timeout should be set correctly."""
        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
        )
        assert provider.base_url == "https://openrouter.ai/api/v1"
        assert provider.model == "mistralai/mistral-7b-instruct:free"
        assert provider.api_key is None
        assert provider.timeout == 30

    def test_initialization_custom_values(self):
        """Custom constructor arguments should be stored."""
        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://custom.openrouter.ai/api/v1/",
            model="anthropic/claude-3-opus",
            api_key="sk-or-v1-test",
            timeout=120,
        )
        # Trailing slash should be stripped
        assert provider.base_url == "https://custom.openrouter.ai/api/v1"
        assert provider.model == "anthropic/claude-3-opus"
        assert provider.api_key == "sk-or-v1-test"
        assert provider.timeout == 120

    def test_initialization_strips_trailing_slash(self):
        """Trailing slashes on base_url should be removed."""
        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1///",
            model="mistralai/mistral-7b-instruct:free",
        )
        assert provider.base_url == "https://openrouter.ai/api/v1"

    def test_initialization_with_optional_headers(self):
        """site_url and app_name should be stored when provided."""
        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
            site_url="https://mygame.example.com",
            app_name="MyRPG",
        )
        assert provider.site_url == "https://mygame.example.com"
        assert provider.app_name == "MyRPG"

    def test_call_sends_correct_payload(self):
        """call() should POST to /v1/chat/completions with correct body."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api",
            model="mistralai/mistral-7b-instruct:free",
            api_key="sk-or-v1-test",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "mistralai/mistral-7b-instruct:free",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Hello! How can I help?",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }

        messages = [{"role": "user", "content": "Hi"}]

        with patch(
            "app.llm.openrouter.requests.post",
            return_value=mock_response,
        ) as mock_post:
            result = provider.call(messages)

        # Verify the request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://openrouter.ai/api/v1/chat/completions"
        assert call_args[1]["json"] == {
            "model": "mistralai/mistral-7b-instruct:free",
            "messages": messages,
            "stream": False,
        }
        assert call_args[1]["headers"] == {
            "Content-Type": "application/json",
            "Authorization": "Bearer sk-or-v1-test",
        }
        assert call_args[1]["timeout"] == 30

        # Verify the returned dict shape
        assert result == {
            "content": "Hello! How can I help?",
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

    def test_call_returns_formatted_response(self):
        """call() should parse the response into the expected dict format."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-456",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "mistralai/mistral-7b-instruct:free",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Sure, here is a poem...",
                    },
                    "finish_reason": "length",
                }
            ],
            "usage": {
                "prompt_tokens": 25,
                "completion_tokens": 100,
                "total_tokens": 125,
            },
        }

        with patch("app.llm.openrouter.requests.post", return_value=mock_response):
            result = provider.call([{"role": "user", "content": "Write a poem"}])

        assert result["content"] == "Sure, here is a poem..."
        assert result["finish_reason"] == "length"
        assert result["usage"]["total_tokens"] == 125

    def test_stream_yields_tokens(self):
        """stream() should yield content tokens from SSE lines."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            (
                b'data: {"choices":[{"index":0,"delta":{"content":"Hello "},'
                b'"finish_reason":null}]}'
            ),
            (
                b'data: {"choices":[{"index":0,"delta":{"content":"world"},'
                b'"finish_reason":null}]}'
            ),
            (
                b'data: {"choices":[{"index":0,"delta":{"content":"!"},'
                b'"finish_reason":null}]}'
            ),
            (b'data: {"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}'),
            b"data: [DONE]",
        ]

        with patch(
            "app.llm.openrouter.requests.post",
            return_value=mock_response,
        ) as mock_post:
            tokens = list(provider.stream([{"role": "user", "content": "Hi"}]))

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]["json"]["stream"] is True

        assert tokens == ["Hello ", "world", "!"]

    def test_stream_skips_empty_lines_and_irrelevant_data(self):
        """stream() should gracefully handle blank lines and non-data SSE."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b"",
            b'data: {"choices":[{"index":0,"delta":{"content":"Hi"}}]}',
            b":comment",
            b'data: {"choices":[{"index":0,"delta":{"content":" there"}}]}',
            b"data: [DONE]",
        ]

        with patch("app.llm.openrouter.requests.post", return_value=mock_response):
            tokens = list(provider.stream([{"role": "user", "content": "Hi"}]))

        assert tokens == ["Hi", " there"]

    def test_health_returns_success(self):
        """health() should return a HealthResult with ok=True on success."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200

        with patch("app.llm.openrouter.requests.get", return_value=mock_response):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is True
        assert result.model == "mistralai/mistral-7b-instruct:free"
        assert result.error is None
        assert result.latency_ms >= 0

    def test_health_returns_failure_on_http_error(self):
        """health() should return a HealthResult with ok=False on HTTP error."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = False
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("app.llm.openrouter.requests.get", return_value=mock_response):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is False
        assert result.model == "mistralai/mistral-7b-instruct:free"
        assert result.error is not None
        assert "500" in result.error
        assert result.latency_ms >= 0

    def test_health_handles_connection_error(self):
        """health() should return ok=False when connection is refused."""
        from unittest.mock import patch

        import requests

        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
        )

        with patch(
            "app.llm.openrouter.requests.get",
            side_effect=requests.exceptions.ConnectionError("Connection refused"),
        ):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is False
        assert result.error is not None
        assert "Connection error" in result.error

    def test_http_error_raises_provider_error(self):
        """call() should raise ProviderError on HTTP 4xx/5xx."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = False
        mock_response.status_code = 400
        mock_response.text = '{"error": "bad request"}'
        mock_response.__bool__ = lambda self: False

        with patch("app.llm.openrouter.requests.post", return_value=mock_response):
            with pytest.raises(ProviderError) as excinfo:
                provider.call([{"role": "user", "content": "Hi"}])

        assert "400" in str(excinfo.value)
        assert "bad request" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_http_error_in_stream_raises_provider_error(self):
        """stream() should raise ProviderError on HTTP 4xx/5xx."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = False
        mock_response.status_code = 401
        mock_response.text = "unauthorized"

        with patch("app.llm.openrouter.requests.post", return_value=mock_response):
            with pytest.raises(ProviderError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert "401" in str(excinfo.value)

    def test_timeout_raises_timeout_error(self):
        """call() should raise LLMTimeoutError on request timeout."""
        from unittest.mock import patch

        import requests

        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
            timeout=5,
        )

        with patch(
            "app.llm.openrouter.requests.post",
            side_effect=requests.exceptions.Timeout("Connection timed out"),
        ):
            with pytest.raises(LLMTimeoutError) as excinfo:
                provider.call([{"role": "user", "content": "Hi"}])

        assert "timed out" in str(excinfo.value).lower()
        assert isinstance(excinfo.value, LLMError)

    def test_connection_error_raises_connection_error(self):
        """call() should raise LLMConnectionError when provider is unreachable."""
        from unittest.mock import patch

        import requests

        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
        )

        with patch(
            "app.llm.openrouter.requests.post",
            side_effect=requests.exceptions.ConnectionError("Connection refused"),
        ):
            with pytest.raises(LLMConnectionError) as excinfo:
                provider.call([{"role": "user", "content": "Hi"}])

        assert "Cannot connect" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_invalid_json_raises_provider_error(self):
        """call() should raise ProviderError when response is not valid JSON."""
        import json
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)

        with patch("app.llm.openrouter.requests.post", return_value=mock_response):
            with pytest.raises(ProviderError) as excinfo:
                provider.call([{"role": "user", "content": "Hi"}])

        assert "Invalid JSON" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_stream_invalid_json_chunk_raises_provider_error(self):
        """stream() should raise ProviderError on malformed SSE data."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b"data: {invalid json here}",
        ]

        with patch("app.llm.openrouter.requests.post", return_value=mock_response):
            with pytest.raises(ProviderError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert "Invalid JSON" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_stream_timeout_raises_timeout_error(self):
        """stream() should raise LLMTimeoutError on request timeout."""
        from unittest.mock import patch

        import requests

        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
        )

        with patch(
            "app.llm.openrouter.requests.post",
            side_effect=requests.exceptions.Timeout("Stream timed out"),
        ):
            with pytest.raises(LLMTimeoutError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert isinstance(excinfo.value, LLMError)

    def test_stream_connection_error_raises_connection_error(self):
        """stream() should raise LLMConnectionError when provider is unreachable."""
        from unittest.mock import patch

        import requests

        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
        )

        with patch(
            "app.llm.openrouter.requests.post",
            side_effect=requests.exceptions.ConnectionError("Connection refused"),
        ):
            with pytest.raises(LLMConnectionError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert isinstance(excinfo.value, LLMError)

    def test_stream_chunked_encoding_error_raises_connection_error(self):
        """stream() should raise LLMConnectionError when connection drops mid-stream."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        # Simulate connection dropping mid-stream
        mock_response.iter_lines.side_effect = requests.exceptions.ChunkedEncodingError(
            "Connection broken"
        )

        with patch("app.llm.openrouter.requests.post", return_value=mock_response):
            with pytest.raises(LLMConnectionError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert "Stream connection lost" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_stream_generic_request_exception_raises_provider_error(self):
        """stream() should raise ProviderError on generic request error mid-stream."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.side_effect = requests.exceptions.RequestException(
            "Something went wrong"
        )

        with patch("app.llm.openrouter.requests.post", return_value=mock_response):
            with pytest.raises(ProviderError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert "Stream error" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_api_key_empty_string_normalized_to_none(self):
        """Empty string api_key should be normalized to None."""
        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
            api_key="",
        )
        assert provider.api_key is None

    def test_base_url_whitespace_stripped(self):
        """base_url should have leading/trailing whitespace stripped."""
        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="  https://openrouter.ai/api/v1  ",
            model="mistralai/mistral-7b-instruct:free",
        )
        assert provider.base_url == "https://openrouter.ai/api/v1"

    # ------------------------------------------------------------------
    # Stream edge cases (beyond happy path)
    # ------------------------------------------------------------------

    def test_stream_empty_only_done(self):
        """stream() should yield nothing when only [DONE] is received."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [b"data: [DONE]"]

        with patch("app.llm.openrouter.requests.post", return_value=mock_response):
            tokens = list(provider.stream([{"role": "user", "content": "Hi"}]))

        assert tokens == []

    def test_stream_non_content_delta_only(self):
        """stream() should skip deltas without a 'content' key."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b'data: {"choices":[{"index":0,"delta":{},"finish_reason":null}]}',
            b'data: {"choices":[{"index":0,"delta":{"role":"assistant"},'
            b'"finish_reason":null}]}',
            b'data: {"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}',
            b"data: [DONE]",
        ]

        with patch("app.llm.openrouter.requests.post", return_value=mock_response):
            tokens = list(provider.stream([{"role": "user", "content": "Hi"}]))

        assert tokens == []

    def test_stream_empty_choices_array_does_not_crash(self):
        """stream() should handle an empty choices array gracefully."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b'data: {"choices":[],"finish_reason":null}',
            b"data: [DONE]",
        ]

        with patch("app.llm.openrouter.requests.post", return_value=mock_response):
            tokens = list(provider.stream([{"role": "user", "content": "Hi"}]))

        assert tokens == []

    # ------------------------------------------------------------------
    # Health-check edge cases
    # ------------------------------------------------------------------

    def test_health_returns_failure_on_403(self):
        """health() should return ok=False on HTTP 403 (unauthorized)."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = False
        mock_response.status_code = 403
        mock_response.text = "Forbidden"

        with patch("app.llm.openrouter.requests.get", return_value=mock_response):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is False
        assert result.model == "mistralai/mistral-7b-instruct:free"
        assert "403" in result.error
        assert result.latency_ms >= 0

    def test_health_handles_timeout(self):
        """health() should return ok=False when the request times out."""
        from unittest.mock import patch

        import requests

        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
        )

        with patch(
            "app.llm.openrouter.requests.get",
            side_effect=requests.exceptions.Timeout("Timed out"),
        ):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is False
        assert "Timeout" in result.error
        assert result.latency_ms >= 0

    # ------------------------------------------------------------------
    # call() response-parsing edge cases
    # ------------------------------------------------------------------

    def test_call_missing_choices_key(self):
        """call() should raise KeyError when response has no 'choices'."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "model": "mistralai/mistral-7b-instruct:free",
        }

        with patch("app.llm.openrouter.requests.post", return_value=mock_response):
            with pytest.raises(KeyError):
                provider.call([{"role": "user", "content": "Hi"}])

    def test_call_empty_choices_array(self):
        """call() should raise IndexError when choices array is empty."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "model": "mistralai/mistral-7b-instruct:free",
            "choices": [],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

        with patch("app.llm.openrouter.requests.post", return_value=mock_response):
            with pytest.raises(IndexError):
                provider.call([{"role": "user", "content": "Hi"}])

    def test_call_missing_message_in_choice(self):
        """call() should raise KeyError when a choice has no 'message'."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "model": "mistralai/mistral-7b-instruct:free",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

        with patch("app.llm.openrouter.requests.post", return_value=mock_response):
            with pytest.raises(KeyError):
                provider.call([{"role": "user", "content": "Hi"}])

    def test_call_missing_usage(self):
        """call() should raise KeyError when response has no 'usage'."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "model": "mistralai/mistral-7b-instruct:free",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Hello!",
                    },
                    "finish_reason": "stop",
                }
            ],
        }

        with patch("app.llm.openrouter.requests.post", return_value=mock_response):
            with pytest.raises(KeyError):
                provider.call([{"role": "user", "content": "Hi"}])

    def test_call_extra_fields_in_response(self):
        """call() should ignore unexpected fields in the response."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-789",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "mistralai/mistral-7b-instruct:free",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Hello!",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
            "system_fingerprint": "fp_abc123",
            "x_openrouter": {"hint": "extra metadata"},
        }

        with patch("app.llm.openrouter.requests.post", return_value=mock_response):
            result = provider.call([{"role": "user", "content": "Hi"}])

        assert result["content"] == "Hello!"
        assert result["finish_reason"] == "stop"
        assert result["usage"]["total_tokens"] == 15

    # ------------------------------------------------------------------
    # Constructor edge cases
    # ------------------------------------------------------------------

    def test_constructor_api_key_explicit_none(self):
        """api_key=None should be stored as None."""
        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
            api_key=None,
        )
        assert provider.api_key is None

    def test_constructor_timeout_zero(self):
        """timeout=0 should be stored without validation."""
        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
            timeout=0,
        )
        assert provider.timeout == 0

    def test_constructor_very_long_model_name(self):
        """A very long model name should be accepted."""
        from app.llm.openrouter import OpenRouterProvider

        long_name = "openrouter/" + "x" * 500 + ":v1"
        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model=long_name,
        )
        assert provider.model == long_name

    # ------------------------------------------------------------------
    # _headers() edge cases
    # ------------------------------------------------------------------

    def test_headers_no_api_key(self):
        """_headers() should not include Authorization when api_key is None."""
        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
        )
        headers = provider._headers()
        assert headers == {"Content-Type": "application/json"}
        assert "Authorization" not in headers

    def test_headers_with_api_key(self):
        """_headers() should include Bearer Authorization when api_key is set."""
        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
            api_key="sk-or-v1-test-key",
        )
        headers = provider._headers()
        assert headers == {
            "Content-Type": "application/json",
            "Authorization": "Bearer sk-or-v1-test-key",
        }

    # ------------------------------------------------------------------
    # OpenRouter-specific header tests
    # ------------------------------------------------------------------

    def test_headers_include_openrouter_extra_headers(self):
        """call() should send HTTP-Referer and X-Title headers
        when site_url and app_name are set."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
            api_key="sk-or-v1-test",
            site_url="https://mygame.example.com",
            app_name="MyRPG",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "mistralai/mistral-7b-instruct:free",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Hello!",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }

        with patch(
            "app.llm.openrouter.requests.post",
            return_value=mock_response,
        ) as mock_post:
            provider.call([{"role": "user", "content": "Hi"}])

        call_args = mock_post.call_args
        headers = call_args[1]["headers"]
        assert headers["Content-Type"] == "application/json"
        assert headers["Authorization"] == "Bearer sk-or-v1-test"
        assert headers["HTTP-Referer"] == "https://mygame.example.com"
        assert headers["X-Title"] == "MyRPG"

    def test_headers_omit_openrouter_headers_when_not_set(self):
        """call() should not send HTTP-Referer or X-Title when not configured."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
            api_key="sk-or-v1-test",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "mistralai/mistral-7b-instruct:free",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Hello!",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }

        with patch(
            "app.llm.openrouter.requests.post",
            return_value=mock_response,
        ) as mock_post:
            provider.call([{"role": "user", "content": "Hi"}])

        call_args = mock_post.call_args
        headers = call_args[1]["headers"]
        assert "HTTP-Referer" not in headers
        assert "X-Title" not in headers
        assert headers["Content-Type"] == "application/json"
        assert headers["Authorization"] == "Bearer sk-or-v1-test"

    def test_stream_timeout_error_messages_prefix(self):
        """stream() timeout error messages should include 'OpenRouter' prefix."""
        from unittest.mock import patch

        import requests

        from app.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-7b-instruct:free",
        )

        with patch(
            "app.llm.openrouter.requests.post",
            side_effect=requests.exceptions.Timeout("Stream timed out"),
        ):
            with pytest.raises(LLMTimeoutError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert "OpenRouter" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Llamacpp provider tests
# ---------------------------------------------------------------------------
# Two-tier health check: /v1/models primary, /health fallback.
# Default base_url: http://localhost:8080, default model: "default"
# ---------------------------------------------------------------------------


class TestLlamacppProvider:
    """Tests for the LlamacppProvider implementation."""

    def test_is_instance_of_llm_provider(self):
        """LlamacppProvider should be a concrete LLMProvider subclass."""
        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider()
        assert isinstance(provider, LLMProvider)

    def test_initialization_defaults(self):
        """Default values for api_key and timeout should be set correctly."""
        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider()
        assert provider.base_url == "http://localhost:8080"
        assert provider.model == "default"
        assert provider.api_key is None
        assert provider.timeout == 30

    def test_initialization_custom_values(self):
        """Custom constructor arguments should be stored."""
        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://my-llamacpp:8080/",
            model="llama-3.2-3b",
            api_key="sk-llama-test",
            timeout=120,
        )
        # Trailing slash should be stripped
        assert provider.base_url == "http://my-llamacpp:8080"
        assert provider.model == "llama-3.2-3b"
        assert provider.api_key == "sk-llama-test"
        assert provider.timeout == 120

    def test_initialization_strips_trailing_slash(self):
        """Trailing slashes on base_url should be removed."""
        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080///",
            model="default",
        )
        assert provider.base_url == "http://localhost:8080"

    def test_call_sends_correct_payload(self):
        """call() should POST to /v1/chat/completions with correct body."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="llama-3.2-3b",
            api_key="sk-llama-test",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "llama-3.2-3b",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Hello! How can I help?",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }

        messages = [{"role": "user", "content": "Hi"}]

        with patch(
            "app.llm.llamacpp.requests.post",
            return_value=mock_response,
        ) as mock_post:
            result = provider.call(messages)

        # Verify the request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "http://localhost:8080/v1/chat/completions"
        assert call_args[1]["json"] == {
            "model": "llama-3.2-3b",
            "messages": messages,
            "stream": False,
        }
        assert call_args[1]["headers"] == {
            "Content-Type": "application/json",
            "Authorization": "Bearer sk-llama-test",
        }
        assert call_args[1]["timeout"] == 30

        # Verify the returned dict shape
        assert result == {
            "content": "Hello! How can I help?",
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

    def test_call_returns_formatted_response(self):
        """call() should parse the response into the expected dict format."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="llama-3.2-3b",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-456",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "llama-3.2-3b",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Sure, here is a poem...",
                    },
                    "finish_reason": "length",
                }
            ],
            "usage": {
                "prompt_tokens": 25,
                "completion_tokens": 100,
                "total_tokens": 125,
            },
        }

        with patch("app.llm.llamacpp.requests.post", return_value=mock_response):
            result = provider.call([{"role": "user", "content": "Write a poem"}])

        assert result["content"] == "Sure, here is a poem..."
        assert result["finish_reason"] == "length"
        assert result["usage"]["total_tokens"] == 125

    def test_stream_yields_tokens(self):
        """stream() should yield content tokens from SSE lines."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="llama-3.2-3b",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            (
                b'data: {"choices":[{"index":0,"delta":{"content":"Hello "},'
                b'"finish_reason":null}]}'
            ),
            (
                b'data: {"choices":[{"index":0,"delta":{"content":"world"},'
                b'"finish_reason":null}]}'
            ),
            (
                b'data: {"choices":[{"index":0,"delta":{"content":"!"},'
                b'"finish_reason":null}]}'
            ),
            (b'data: {"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}'),
            b"data: [DONE]",
        ]

        with patch(
            "app.llm.llamacpp.requests.post",
            return_value=mock_response,
        ) as mock_post:
            tokens = list(provider.stream([{"role": "user", "content": "Hi"}]))

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]["json"]["stream"] is True

        assert tokens == ["Hello ", "world", "!"]

    def test_stream_skips_empty_lines_and_irrelevant_data(self):
        """stream() should gracefully handle blank lines and non-data SSE."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="llama-3.2-3b",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b"",
            b'data: {"choices":[{"index":0,"delta":{"content":"Hi"}}]}',
            b":comment",
            b'data: {"choices":[{"index":0,"delta":{"content":" there"}}]}',
            b"data: [DONE]",
        ]

        with patch("app.llm.llamacpp.requests.post", return_value=mock_response):
            tokens = list(provider.stream([{"role": "user", "content": "Hi"}]))

        assert tokens == ["Hi", " there"]

    # ------------------------------------------------------------------
    # Health-check — two-tier: /v1/models primary, /health fallback
    # ------------------------------------------------------------------

    def test_health_returns_success(self):
        """health() should return a HealthResult with ok=True on success
        via /v1/models."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="default",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "object": "list",
            "data": [{"id": "llama-3.2-3b"}],
        }

        with patch("app.llm.llamacpp.requests.get", return_value=mock_response):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is True
        assert result.model == "llama-3.2-3b"
        assert result.error is None
        assert result.latency_ms >= 0

    def test_health_fallback_to_health_endpoint(self):
        """health() should fall back to /health when /v1/models
        raises a ConnectionError."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="default",
        )

        mock_health_response = MagicMock(spec=requests.Response)
        mock_health_response.ok = True
        mock_health_response.status_code = 200

        with patch(
            "app.llm.llamacpp.requests.get",
            side_effect=[
                requests.exceptions.ConnectionError("Connection refused"),
                mock_health_response,
            ],
        ):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is True
        assert result.model == "default"
        assert result.error is None
        assert result.latency_ms >= 0

    def test_health_both_endpoints_fail(self):
        """health() should return ok=False when both /v1/models
        and /health fail with ConnectionError."""
        from unittest.mock import patch

        import requests

        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="default",
        )

        with patch(
            "app.llm.llamacpp.requests.get",
            side_effect=[
                requests.exceptions.ConnectionError("Connection refused"),
                requests.exceptions.ConnectionError("Also refused"),
            ],
        ):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is False
        assert result.model == "default"
        assert "Connection error" in result.error
        assert result.latency_ms >= 0

    def test_health_returns_failure_on_http_error(self):
        """health() should return a HealthResult with ok=False on HTTP error
        from /v1/models (no fallback triggered)."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="default",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = False
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("app.llm.llamacpp.requests.get", return_value=mock_response):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is False
        assert result.model == "default"
        assert result.error is not None
        assert "500" in result.error
        assert result.latency_ms >= 0

    def test_health_handles_connection_error(self):
        """health() should return ok=False when both endpoints are unreachable."""
        from unittest.mock import patch

        import requests

        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="default",
        )

        with patch(
            "app.llm.llamacpp.requests.get",
            side_effect=requests.exceptions.ConnectionError("Connection refused"),
        ):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is False
        assert result.error is not None
        assert "Connection error" in result.error
        assert result.latency_ms >= 0

    def test_health_model_name_extraction(self):
        """health() should extract model name from /v1/models
        data[0]['id'] when available."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="default",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "object": "list",
            "data": [{"id": "llama-3.2-3b"}],
        }

        with patch("app.llm.llamacpp.requests.get", return_value=mock_response):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is True
        assert result.model == "llama-3.2-3b"
        assert result.error is None

    def test_health_model_name_extraction_failure(self):
        """health() should fall back to constructor model when
        /v1/models response is malformed."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="default",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "object": "list",
            # "data" key missing entirely
        }

        with patch("app.llm.llamacpp.requests.get", return_value=mock_response):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is True
        assert result.model == "default"  # falls back to constructor-provided model
        assert result.error is None

    def test_health_fallback_timeout(self):
        """health() should return ok=False when /v1/models fails with
        ConnectionError and /health times out."""
        from unittest.mock import patch

        import requests

        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="default",
        )

        with patch(
            "app.llm.llamacpp.requests.get",
            side_effect=[
                requests.exceptions.ConnectionError("Connection refused"),
                requests.exceptions.Timeout("Timed out"),
            ],
        ):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is False
        assert "Timeout" in result.error
        assert result.latency_ms >= 0

    def test_health_handles_unexpected_exception(self):
        """health() should return ok=False on unexpected exceptions."""
        from unittest.mock import patch

        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="default",
        )

        with patch(
            "app.llm.llamacpp.requests.get",
            side_effect=RuntimeError("Something unexpected happened"),
        ):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is False
        assert "health check failed" in result.error
        assert result.latency_ms >= 0

    def test_http_error_raises_provider_error(self):
        """call() should raise ProviderError on HTTP 4xx/5xx."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="default",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = False
        mock_response.status_code = 400
        mock_response.text = '{"error": "bad request"}'
        mock_response.__bool__ = lambda self: False

        with patch("app.llm.llamacpp.requests.post", return_value=mock_response):
            with pytest.raises(ProviderError) as excinfo:
                provider.call([{"role": "user", "content": "Hi"}])

        assert "400" in str(excinfo.value)
        assert "bad request" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_http_error_in_stream_raises_provider_error(self):
        """stream() should raise ProviderError on HTTP 4xx/5xx."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="default",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = False
        mock_response.status_code = 401
        mock_response.text = "unauthorized"

        with patch("app.llm.llamacpp.requests.post", return_value=mock_response):
            with pytest.raises(ProviderError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert "401" in str(excinfo.value)

    def test_timeout_raises_timeout_error(self):
        """call() should raise LLMTimeoutError on request timeout."""
        from unittest.mock import patch

        import requests

        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="default",
            timeout=5,
        )

        with patch(
            "app.llm.llamacpp.requests.post",
            side_effect=requests.exceptions.Timeout("Connection timed out"),
        ):
            with pytest.raises(LLMTimeoutError) as excinfo:
                provider.call([{"role": "user", "content": "Hi"}])

        assert "timed out" in str(excinfo.value).lower()
        assert isinstance(excinfo.value, LLMError)

    def test_connection_error_raises_connection_error(self):
        """call() should raise LLMConnectionError when provider is unreachable."""
        from unittest.mock import patch

        import requests

        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="default",
        )

        with patch(
            "app.llm.llamacpp.requests.post",
            side_effect=requests.exceptions.ConnectionError("Connection refused"),
        ):
            with pytest.raises(LLMConnectionError) as excinfo:
                provider.call([{"role": "user", "content": "Hi"}])

        assert "Cannot connect" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_invalid_json_raises_provider_error(self):
        """call() should raise ProviderError when response is not valid JSON."""
        import json
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="default",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)

        with patch("app.llm.llamacpp.requests.post", return_value=mock_response):
            with pytest.raises(ProviderError) as excinfo:
                provider.call([{"role": "user", "content": "Hi"}])

        assert "Invalid JSON" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_stream_invalid_json_chunk_raises_provider_error(self):
        """stream() should raise ProviderError on malformed SSE data."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="default",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b"data: {invalid json here}",
        ]

        with patch("app.llm.llamacpp.requests.post", return_value=mock_response):
            with pytest.raises(ProviderError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert "Invalid JSON" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_stream_timeout_raises_timeout_error(self):
        """stream() should raise LLMTimeoutError on request timeout."""
        from unittest.mock import patch

        import requests

        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="default",
        )

        with patch(
            "app.llm.llamacpp.requests.post",
            side_effect=requests.exceptions.Timeout("Stream timed out"),
        ):
            with pytest.raises(LLMTimeoutError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert isinstance(excinfo.value, LLMError)

    def test_stream_connection_error_raises_connection_error(self):
        """stream() should raise LLMConnectionError when provider is unreachable."""
        from unittest.mock import patch

        import requests

        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="default",
        )

        with patch(
            "app.llm.llamacpp.requests.post",
            side_effect=requests.exceptions.ConnectionError("Connection refused"),
        ):
            with pytest.raises(LLMConnectionError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert isinstance(excinfo.value, LLMError)

    def test_stream_chunked_encoding_error_raises_connection_error(self):
        """stream() should raise LLMConnectionError when connection drops mid-stream."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="default",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        # Simulate connection dropping mid-stream
        mock_response.iter_lines.side_effect = requests.exceptions.ChunkedEncodingError(
            "Connection broken"
        )

        with patch("app.llm.llamacpp.requests.post", return_value=mock_response):
            with pytest.raises(LLMConnectionError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert "Stream connection lost" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_stream_generic_request_exception_raises_provider_error(self):
        """stream() should raise ProviderError on generic request error mid-stream."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="default",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.side_effect = requests.exceptions.RequestException(
            "Something went wrong"
        )

        with patch("app.llm.llamacpp.requests.post", return_value=mock_response):
            with pytest.raises(ProviderError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert "Stream error" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_api_key_empty_string_normalized_to_none(self):
        """Empty string api_key should be normalized to None."""
        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="default",
            api_key="",
        )
        assert provider.api_key is None

    def test_base_url_whitespace_stripped(self):
        """base_url should have leading/trailing whitespace stripped."""
        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="  http://localhost:8080  ",
            model="default",
        )
        assert provider.base_url == "http://localhost:8080"

    # ------------------------------------------------------------------
    # Stream edge cases (beyond happy path)
    # ------------------------------------------------------------------

    def test_stream_empty_only_done(self):
        """stream() should yield nothing when only [DONE] is received."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="default",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [b"data: [DONE]"]

        with patch("app.llm.llamacpp.requests.post", return_value=mock_response):
            tokens = list(provider.stream([{"role": "user", "content": "Hi"}]))

        assert tokens == []

    def test_stream_non_content_delta_only(self):
        """stream() should skip deltas without a 'content' key."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="default",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b'data: {"choices":[{"index":0,"delta":{},"finish_reason":null}]}',
            (
                b'data: {"choices":[{"index":0,"delta":{"role":"assistant"},'
                b'"finish_reason":null}]}'
            ),
            b'data: {"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}',
            b"data: [DONE]",
        ]

        with patch("app.llm.llamacpp.requests.post", return_value=mock_response):
            tokens = list(provider.stream([{"role": "user", "content": "Hi"}]))

        assert tokens == []

    def test_stream_empty_choices_array_does_not_crash(self):
        """stream() should handle an empty choices array gracefully."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="default",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b'data: {"choices":[],"finish_reason":null}',
            b"data: [DONE]",
        ]

        with patch("app.llm.llamacpp.requests.post", return_value=mock_response):
            tokens = list(provider.stream([{"role": "user", "content": "Hi"}]))

        assert tokens == []

    # ------------------------------------------------------------------
    # call() response-parsing edge cases
    # ------------------------------------------------------------------

    def test_call_missing_choices_key(self):
        """call() should raise KeyError when response has no 'choices'."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="default",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "model": "default",
        }

        with patch("app.llm.llamacpp.requests.post", return_value=mock_response):
            with pytest.raises(KeyError):
                provider.call([{"role": "user", "content": "Hi"}])

    def test_call_empty_choices_array(self):
        """call() should raise IndexError when choices array is empty."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="default",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "model": "default",
            "choices": [],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

        with patch("app.llm.llamacpp.requests.post", return_value=mock_response):
            with pytest.raises(IndexError):
                provider.call([{"role": "user", "content": "Hi"}])

    def test_call_missing_message_in_choice(self):
        """call() should raise KeyError when a choice has no 'message'."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="default",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "model": "default",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

        with patch("app.llm.llamacpp.requests.post", return_value=mock_response):
            with pytest.raises(KeyError):
                provider.call([{"role": "user", "content": "Hi"}])

    def test_call_missing_usage(self):
        """call() should raise KeyError when response has no 'usage'."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="default",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "model": "default",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Hello!",
                    },
                    "finish_reason": "stop",
                }
            ],
        }

        with patch("app.llm.llamacpp.requests.post", return_value=mock_response):
            with pytest.raises(KeyError):
                provider.call([{"role": "user", "content": "Hi"}])

    def test_call_extra_fields_in_response(self):
        """call() should ignore unexpected fields in the response."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="default",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-789",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "default",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Hello!",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
            "system_fingerprint": "fp_abc123",
            "x_llamacpp": {"hint": "extra metadata"},
        }

        with patch("app.llm.llamacpp.requests.post", return_value=mock_response):
            result = provider.call([{"role": "user", "content": "Hi"}])

        assert result["content"] == "Hello!"
        assert result["finish_reason"] == "stop"
        assert result["usage"]["total_tokens"] == 15

    # ------------------------------------------------------------------
    # Constructor edge cases
    # ------------------------------------------------------------------

    def test_constructor_api_key_explicit_none(self):
        """api_key=None should be stored as None."""
        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="default",
            api_key=None,
        )
        assert provider.api_key is None

    def test_constructor_timeout_zero(self):
        """timeout=0 should be stored without validation."""
        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="default",
            timeout=0,
        )
        assert provider.timeout == 0

    def test_constructor_very_long_model_name(self):
        """A very long model name should be accepted."""
        from app.llm.llamacpp import LlamacppProvider

        long_name = "meta-llama/" + "x" * 500 + ":v1"
        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model=long_name,
        )
        assert provider.model == long_name

    # ------------------------------------------------------------------
    # _headers() edge cases
    # ------------------------------------------------------------------

    def test_headers_no_api_key(self):
        """_headers() should not include Authorization when api_key is None."""
        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="default",
        )
        headers = provider._headers()
        assert headers == {"Content-Type": "application/json"}
        assert "Authorization" not in headers

    def test_headers_with_api_key(self):
        """_headers() should include Bearer Authorization when api_key is set."""
        from app.llm.llamacpp import LlamacppProvider

        provider = LlamacppProvider(
            base_url="http://localhost:8080",
            model="default",
            api_key="sk-llama-test-key",
        )
        headers = provider._headers()
        assert headers == {
            "Content-Type": "application/json",
            "Authorization": "Bearer sk-llama-test-key",
        }


# ---------------------------------------------------------------------------
# Unsloth provider tests
# ---------------------------------------------------------------------------


class TestUnslothProvider:
    """Tests for the UnslothProvider implementation."""

    def test_is_instance_of_llm_provider(self):
        """UnslothProvider should be a concrete LLMProvider subclass."""
        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )
        assert isinstance(provider, LLMProvider)

    def test_initialization_defaults(self):
        """Default values for api_key and timeout should be set correctly."""
        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )
        assert provider.base_url == "http://localhost:8888"
        assert provider.model == "unsloth/Devstral-Small-2-24B-Instruct-2512"
        assert provider.api_key is None
        assert provider.timeout == 30

    def test_initialization_custom_values(self):
        """Custom constructor arguments should be stored."""
        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://my-unsloth:8888/",
            model="unsloth/gemma-3-27b-it-GGUF",
            api_key="sk-unsloth-test",
            timeout=60,
        )
        # Trailing slash should be stripped
        assert provider.base_url == "http://my-unsloth:8888"
        assert provider.model == "unsloth/gemma-3-27b-it-GGUF"
        assert provider.api_key == "sk-unsloth-test"
        assert provider.timeout == 60

    def test_initialization_strips_trailing_slash(self):
        """Trailing slashes on base_url should be removed."""
        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888///",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )
        assert provider.base_url == "http://localhost:8888"

    def test_call_sends_correct_payload(self):
        """call() should POST to /v1/chat/completions with correct body."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
            api_key="sk-unsloth-test",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "unsloth/Devstral-Small-2-24B-Instruct-2512",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Hello! How can I help?",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }

        messages = [{"role": "user", "content": "Hi"}]

        with patch(
            "app.llm.unsloth.requests.post",
            return_value=mock_response,
        ) as mock_post:
            result = provider.call(messages)

        # Verify the request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "http://localhost:8888/v1/chat/completions"
        assert call_args[1]["json"] == {
            "model": "unsloth/Devstral-Small-2-24B-Instruct-2512",
            "messages": messages,
            "stream": False,
        }
        assert call_args[1]["headers"] == {
            "Content-Type": "application/json",
            "Authorization": "Bearer sk-unsloth-test",
        }
        assert call_args[1]["timeout"] == 30

        # Verify the returned dict shape
        assert result == {
            "content": "Hello! How can I help?",
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

    def test_call_returns_formatted_response(self):
        """call() should parse the response into the expected dict format."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-456",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "unsloth/Devstral-Small-2-24B-Instruct-2512",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Sure, here is a poem...",
                    },
                    "finish_reason": "length",
                }
            ],
            "usage": {
                "prompt_tokens": 25,
                "completion_tokens": 100,
                "total_tokens": 125,
            },
        }

        with patch("app.llm.unsloth.requests.post", return_value=mock_response):
            result = provider.call([{"role": "user", "content": "Write a poem"}])

        assert result["content"] == "Sure, here is a poem..."
        assert result["finish_reason"] == "length"
        assert result["usage"]["total_tokens"] == 125

    def test_stream_yields_tokens(self):
        """stream() should yield content tokens from SSE lines."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            (
                b'data: {"choices":[{"index":0,"delta":{"content":"Hello "},'
                b'"finish_reason":null}]}'
            ),
            (
                b'data: {"choices":[{"index":0,"delta":{"content":"world"},'
                b'"finish_reason":null}]}'
            ),
            (
                b'data: {"choices":[{"index":0,"delta":{"content":"!"},'
                b'"finish_reason":null}]}'
            ),
            (b'data: {"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}'),
            b"data: [DONE]",
        ]

        with patch(
            "app.llm.unsloth.requests.post",
            return_value=mock_response,
        ) as mock_post:
            tokens = list(provider.stream([{"role": "user", "content": "Hi"}]))

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]["json"]["stream"] is True

        assert tokens == ["Hello ", "world", "!"]

    def test_stream_skips_empty_lines_and_irrelevant_data(self):
        """stream() should gracefully handle blank lines and non-data SSE."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b"",
            b'data: {"choices":[{"index":0,"delta":{"content":"Hi"}}]}',
            b":comment",
            b'data: {"choices":[{"index":0,"delta":{"content":" there"}}]}',
            b"data: [DONE]",
        ]

        with patch("app.llm.unsloth.requests.post", return_value=mock_response):
            tokens = list(provider.stream([{"role": "user", "content": "Hi"}]))

        assert tokens == ["Hi", " there"]

    def test_health_returns_success_via_v1_models(self):
        """health() should extract model from /v1/models response when available."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "object": "list",
            "data": [{"id": "unsloth/gemma-3-27b-it-GGUF"}],
        }

        with patch("app.llm.unsloth.requests.get", return_value=mock_response):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is True
        assert result.model == "unsloth/gemma-3-27b-it-GGUF"
        assert result.error is None
        assert result.latency_ms >= 0

    def test_health_falls_back_to_health_endpoint(self):
        """health() should fall back to /health when /v1/models has connection error."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        mock_health_response = MagicMock(spec=requests.Response)
        mock_health_response.ok = True
        mock_health_response.status_code = 200

        with patch(
            "app.llm.unsloth.requests.get",
            side_effect=[
                requests.exceptions.ConnectionError("Connection refused"),
                mock_health_response,
            ],
        ):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is True
        assert result.model == "unsloth/Devstral-Small-2-24B-Instruct-2512"
        assert result.error is None
        assert result.latency_ms >= 0

    def test_health_returns_failure_on_http_error(self):
        """health() should return a HealthResult with ok=False on HTTP error."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = False
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("app.llm.unsloth.requests.get", return_value=mock_response):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is False
        assert result.model == "unsloth/Devstral-Small-2-24B-Instruct-2512"
        assert result.error is not None
        assert "500" in result.error
        assert result.latency_ms >= 0

    def test_health_handles_connection_error(self):
        """health() should return ok=False when both endpoints are unreachable."""
        from unittest.mock import patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        with patch(
            "app.llm.unsloth.requests.get",
            side_effect=requests.exceptions.ConnectionError("Connection refused"),
        ):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is False
        assert result.error is not None
        assert "Connection error" in result.error

    def test_http_error_raises_provider_error(self):
        """call() should raise ProviderError on HTTP 4xx/5xx."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = False
        mock_response.status_code = 400
        mock_response.text = '{"error": "bad request"}'
        mock_response.__bool__ = lambda self: False

        with patch("app.llm.unsloth.requests.post", return_value=mock_response):
            with pytest.raises(ProviderError) as excinfo:
                provider.call([{"role": "user", "content": "Hi"}])

        assert "400" in str(excinfo.value)
        assert "bad request" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_http_error_in_stream_raises_provider_error(self):
        """stream() should raise ProviderError on HTTP 4xx/5xx."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = False
        mock_response.status_code = 401
        mock_response.text = "unauthorized"

        with patch("app.llm.unsloth.requests.post", return_value=mock_response):
            with pytest.raises(ProviderError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert "401" in str(excinfo.value)

    def test_timeout_raises_timeout_error(self):
        """call() should raise LLMTimeoutError on request timeout."""
        from unittest.mock import patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
            timeout=5,
        )

        with patch(
            "app.llm.unsloth.requests.post",
            side_effect=requests.exceptions.Timeout("Connection timed out"),
        ):
            with pytest.raises(LLMTimeoutError) as excinfo:
                provider.call([{"role": "user", "content": "Hi"}])

        assert "timed out" in str(excinfo.value).lower()
        assert isinstance(excinfo.value, LLMError)

    def test_connection_error_raises_connection_error(self):
        """call() should raise LLMConnectionError when provider is unreachable."""
        from unittest.mock import patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        with patch(
            "app.llm.unsloth.requests.post",
            side_effect=requests.exceptions.ConnectionError("Connection refused"),
        ):
            with pytest.raises(LLMConnectionError) as excinfo:
                provider.call([{"role": "user", "content": "Hi"}])

        assert "Cannot connect" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_invalid_json_raises_provider_error(self):
        """call() should raise ProviderError when response is not valid JSON."""
        import json
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)

        with patch("app.llm.unsloth.requests.post", return_value=mock_response):
            with pytest.raises(ProviderError) as excinfo:
                provider.call([{"role": "user", "content": "Hi"}])

        assert "Invalid JSON" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_stream_empty_choices_array_does_not_crash(self):
        """stream() should not crash when a chunk has an empty choices array."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )
        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b'data: {"choices":[],"finish_reason":null}',
            b"data: [DONE]",
        ]
        with patch("app.llm.unsloth.requests.post", return_value=mock_response):
            tokens = list(provider.stream([{"role": "user", "content": "Hi"}]))
        assert tokens == []

    def test_stream_timeout_raises_timeout_error(self):
        """stream() should raise LLMTimeoutError on request timeout."""
        from unittest.mock import patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        with patch(
            "app.llm.unsloth.requests.post",
            side_effect=requests.exceptions.Timeout("Stream timed out"),
        ):
            with pytest.raises(LLMTimeoutError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert isinstance(excinfo.value, LLMError)

    def test_stream_connection_error_raises_connection_error(self):
        """stream() should raise LLMConnectionError when provider is unreachable."""
        from unittest.mock import patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        with patch(
            "app.llm.unsloth.requests.post",
            side_effect=requests.exceptions.ConnectionError("Connection refused"),
        ):
            with pytest.raises(LLMConnectionError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert isinstance(excinfo.value, LLMError)

    def test_stream_chunked_encoding_error_raises_connection_error(self):
        """stream() should raise LLMConnectionError when connection drops mid-stream."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        # Simulate connection dropping mid-stream
        mock_response.iter_lines.side_effect = requests.exceptions.ChunkedEncodingError(
            "Connection broken"
        )

        with patch("app.llm.unsloth.requests.post", return_value=mock_response):
            with pytest.raises(LLMConnectionError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert "Stream connection lost" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_stream_generic_request_exception_raises_provider_error(self):
        """stream() should raise ProviderError on generic request error mid-stream."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.side_effect = requests.exceptions.RequestException(
            "Something went wrong"
        )

        with patch("app.llm.unsloth.requests.post", return_value=mock_response):
            with pytest.raises(ProviderError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert "Stream error" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_api_key_empty_string_normalized_to_none(self):
        """Empty string api_key should be normalized to None."""
        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
            api_key="",
        )
        assert provider.api_key is None

    def test_base_url_whitespace_stripped(self):
        """base_url should have leading/trailing whitespace stripped."""
        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="  http://localhost:8888  ",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )
        assert provider.base_url == "http://localhost:8888"

    def test_stream_empty_only_done(self):
        """stream() should yield nothing when only [DONE] is received."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [b"data: [DONE]"]

        with patch("app.llm.unsloth.requests.post", return_value=mock_response):
            tokens = list(provider.stream([{"role": "user", "content": "Hi"}]))

        assert tokens == []

    def test_stream_non_content_delta_only(self):
        """stream() should skip deltas without a 'content' key."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b'data: {"choices":[{"index":0,"delta":{},"finish_reason":null}]}',
            b'data: {"choices":[{"index":0,"delta":{"role":"assistant"},'
            b'"finish_reason":null}]}',
            b'data: {"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}',
            b"data: [DONE]",
        ]

        with patch("app.llm.unsloth.requests.post", return_value=mock_response):
            tokens = list(provider.stream([{"role": "user", "content": "Hi"}]))

        assert tokens == []

    def test_stream_invalid_json_chunk_raises_provider_error(self):
        """stream() should raise ProviderError on malformed SSE data."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b"data: {invalid json here}",
        ]

        with patch("app.llm.unsloth.requests.post", return_value=mock_response):
            with pytest.raises(ProviderError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert "Invalid JSON" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_health_returns_failure_on_403(self):
        """health() should return ok=False on HTTP 403 (unauthorized)."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = False
        mock_response.status_code = 403
        mock_response.text = "Forbidden"

        with patch("app.llm.unsloth.requests.get", return_value=mock_response):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is False
        assert result.model == "unsloth/Devstral-Small-2-24B-Instruct-2512"
        assert "403" in result.error
        assert result.latency_ms >= 0

    def test_health_handles_timeout(self):
        """health() should return ok=False when the request times out."""
        from unittest.mock import patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        with patch(
            "app.llm.unsloth.requests.get",
            side_effect=requests.exceptions.Timeout("Timed out"),
        ):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is False
        assert "Timeout" in result.error
        assert result.latency_ms >= 0

    # ------------------------------------------------------------------
    # call() response-parsing edge cases
    # ------------------------------------------------------------------

    def test_call_missing_choices_key(self):
        """call() should raise KeyError when response has no 'choices'."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "model": "unsloth/Devstral-Small-2-24B-Instruct-2512",
        }

        with patch("app.llm.unsloth.requests.post", return_value=mock_response):
            with pytest.raises(KeyError):
                provider.call([{"role": "user", "content": "Hi"}])

    def test_call_empty_choices_array(self):
        """call() should raise IndexError when choices array is empty."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "model": "unsloth/Devstral-Small-2-24B-Instruct-2512",
            "choices": [],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

        with patch("app.llm.unsloth.requests.post", return_value=mock_response):
            with pytest.raises(IndexError):
                provider.call([{"role": "user", "content": "Hi"}])

    def test_call_missing_message_in_choice(self):
        """call() should raise KeyError when a choice has no 'message'."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "model": "unsloth/Devstral-Small-2-24B-Instruct-2512",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

        with patch("app.llm.unsloth.requests.post", return_value=mock_response):
            with pytest.raises(KeyError):
                provider.call([{"role": "user", "content": "Hi"}])

    def test_call_missing_usage(self):
        """call() should raise KeyError when response has no 'usage'."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "model": "unsloth/Devstral-Small-2-24B-Instruct-2512",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Hello!",
                    },
                    "finish_reason": "stop",
                }
            ],
        }

        with patch("app.llm.unsloth.requests.post", return_value=mock_response):
            with pytest.raises(KeyError):
                provider.call([{"role": "user", "content": "Hi"}])

    def test_call_extra_fields_in_response(self):
        """call() should ignore unexpected fields in the response."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-789",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "unsloth/Devstral-Small-2-24B-Instruct-2512",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Hello!",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
            "system_fingerprint": "fp_abc123",
            "x_unsloth": {"hint": "extra metadata"},
        }

        with patch("app.llm.unsloth.requests.post", return_value=mock_response):
            result = provider.call([{"role": "user", "content": "Hi"}])

        assert result["content"] == "Hello!"
        assert result["finish_reason"] == "stop"
        assert result["usage"]["total_tokens"] == 15

    # ------------------------------------------------------------------
    # Constructor edge cases
    # ------------------------------------------------------------------

    def test_constructor_api_key_explicit_none(self):
        """api_key=None should be stored as None."""
        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
            api_key=None,
        )
        assert provider.api_key is None

    def test_constructor_timeout_zero(self):
        """timeout=0 should be stored without validation."""
        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
            timeout=0,
        )
        assert provider.timeout == 0

    def test_constructor_very_long_model_name(self):
        """A very long model name should be accepted."""
        from app.llm.unsloth import UnslothProvider

        long_name = "unsloth/" + "x" * 500 + ":v1"
        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model=long_name,
        )
        assert provider.model == long_name

    # ------------------------------------------------------------------
    # _headers() edge cases
    # ------------------------------------------------------------------

    def test_headers_no_api_key(self):
        """_headers() should not include Authorization when api_key is None."""
        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )
        headers = provider._headers()
        assert headers == {"Content-Type": "application/json"}
        assert "Authorization" not in headers

    def test_headers_with_api_key(self):
        """_headers() should include Bearer Authorization when api_key is set."""
        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
            api_key="sk-unsloth-test-key",
        )
        headers = provider._headers()
        assert headers == {
            "Content-Type": "application/json",
            "Authorization": "Bearer sk-unsloth-test-key",
        }

    # ------------------------------------------------------------------
    # Health-check: /v1/models HTTP errors (NOT connection) — should
    # NOT trigger fallback to /health
    # ------------------------------------------------------------------

    def test_health_v1_models_http_500_does_not_fallback(self):
        """health() should NOT fallback to /health when /v1/models returns
        HTTP 500 — only ConnectionError triggers the fallback."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        mock_v1 = MagicMock(spec=requests.Response)
        mock_v1.ok = False
        mock_v1.status_code = 500
        mock_v1.text = "Internal Server Error"

        # If /v1/models 500 also fell through to /health, the second
        # call would need another mock.  We only supply one, so
        # expecting a single GET call.
        with patch(
            "app.llm.unsloth.requests.get",
            return_value=mock_v1,
        ) as mock_get:
            result = provider.health()

        mock_get.assert_called_once()
        url_used = mock_get.call_args[0][0]
        assert "/v1/models" in url_used
        assert "/health" not in url_used
        assert isinstance(result, HealthResult)
        assert result.ok is False
        assert "500" in result.error
        assert result.latency_ms >= 0

    def test_health_v1_models_http_403_uses_self_model(
        self,
    ):
        """health() with /v1/models HTTP 403 should use self.model
        (not extracted from response)."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        mock_v1 = MagicMock(spec=requests.Response)
        mock_v1.ok = False
        mock_v1.status_code = 403
        mock_v1.text = "Forbidden"

        with patch("app.llm.unsloth.requests.get", return_value=mock_v1):
            result = provider.health()

        assert result.ok is False
        assert result.model == "unsloth/Devstral-Small-2-24B-Instruct-2512"
        assert "403" in result.error

    # ------------------------------------------------------------------
    # Health-check: /v1/models responses with missing / malformed data
    # ------------------------------------------------------------------

    def test_health_v1_models_empty_data_array(self):
        """health() should use self.model when /v1/models data is an empty list."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "object": "list",
            "data": [],
        }

        with patch("app.llm.unsloth.requests.get", return_value=mock_response):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is True
        # Falls back to constructor-provided model name
        assert result.model == "unsloth/Devstral-Small-2-24B-Instruct-2512"
        assert result.error is None

    def test_health_v1_models_data_entry_without_id(self):
        """health() should use self.model when /v1/models data entry has no 'id'."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "object": "list",
            "data": [{"object": "model"}],  # no "id" key
        }

        with patch("app.llm.unsloth.requests.get", return_value=mock_response):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is True
        assert result.model == "unsloth/Devstral-Small-2-24B-Instruct-2512"
        assert result.error is None

    def test_health_v1_models_missing_data_key(self):
        """health() should use self.model when /v1/models response has no 'data' key."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "object": "list",
            # "data" key is missing entirely
        }

        with patch("app.llm.unsloth.requests.get", return_value=mock_response):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is True
        assert result.model == "unsloth/Devstral-Small-2-24B-Instruct-2512"
        assert result.error is None

    def test_health_v1_models_data_not_a_list(self):
        """health() should use self.model when /v1/models data is not a list."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "object": "list",
            "data": "not_a_list",  # TypeError on [0]
        }

        with patch("app.llm.unsloth.requests.get", return_value=mock_response):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is True
        assert result.model == "unsloth/Devstral-Small-2-24B-Instruct-2512"
        assert result.error is None

    def test_health_v1_models_invalid_json_graceful(self):
        """health() should use self.model when /v1/models returns invalid JSON."""
        import json
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Bad JSON", "", 0)

        with patch("app.llm.unsloth.requests.get", return_value=mock_response):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is True
        assert result.model == "unsloth/Devstral-Small-2-24B-Instruct-2512"
        assert result.error is None

    def test_health_v1_models_multiple_models_uses_first(self):
        """health() should extract the first model from /v1/models data array."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "object": "list",
            "data": [
                {"id": "unsloth/gemma-3-27b-it-GGUF"},
                {"id": "unsloth/llama-3-8b-instruct"},
                {"id": "unsloth/mistral-7b-v3"},
            ],
        }

        with patch("app.llm.unsloth.requests.get", return_value=mock_response):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is True
        assert result.model == "unsloth/gemma-3-27b-it-GGUF"
        assert result.error is None

    # ------------------------------------------------------------------
    # Fallback: /health endpoint error scenarios
    # ------------------------------------------------------------------

    def test_health_both_endpoints_fail_different_errors(self):
        """health() should report /health HTTP error when /v1/models gets
        ConnectionError and /health returns HTTP 500."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        mock_health = MagicMock(spec=requests.Response)
        mock_health.ok = False
        mock_health.status_code = 500
        mock_health.text = "Internal Server Error"

        with patch(
            "app.llm.unsloth.requests.get",
            side_effect=[
                requests.exceptions.ConnectionError("Connection refused"),
                mock_health,
            ],
        ):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is False
        assert result.model == "unsloth/Devstral-Small-2-24B-Instruct-2512"
        assert "500" in result.error
        assert result.latency_ms >= 0

    def test_health_fallback_health_endpoint_timeout(self):
        """health() should report timeout when /v1/models gets ConnectionError
        and /health times out."""
        from unittest.mock import patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        with patch(
            "app.llm.unsloth.requests.get",
            side_effect=[
                requests.exceptions.ConnectionError("Connection refused"),
                requests.exceptions.Timeout("Timed out"),
            ],
        ):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is False
        assert "Timeout" in result.error
        assert result.latency_ms >= 0

    # ------------------------------------------------------------------
    # call() / stream() with "default" model name
    # ------------------------------------------------------------------

    def test_model_default_accepted_in_call_payload(self):
        """call() should send 'default' as model when user passes 'default'."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="default",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-default",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "default",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "I am the default model!",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 5,
                "completion_tokens": 6,
                "total_tokens": 11,
            },
        }

        with patch(
            "app.llm.unsloth.requests.post",
            return_value=mock_response,
        ) as mock_post:
            result = provider.call([{"role": "user", "content": "Hi"}])

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]["json"]["model"] == "default"
        assert result["content"] == "I am the default model!"

    def test_model_default_accepted_in_stream_payload(self):
        """stream() should send 'default' as model when user passes 'default'."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="default",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            (
                b'data: {"choices":[{"index":0,"delta":{"content":"Hello "},'
                b'"finish_reason":null}]}'
            ),
            b"data: [DONE]",
        ]

        with patch(
            "app.llm.unsloth.requests.post",
            return_value=mock_response,
        ) as mock_post:
            tokens = list(provider.stream([{"role": "user", "content": "Hi"}]))

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]["json"]["model"] == "default"
        assert tokens == ["Hello "]

    # ------------------------------------------------------------------
    # call() / stream() with empty messages
    # ------------------------------------------------------------------

    def test_call_empty_messages(self):
        """call() should send an empty messages list to the API."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-empty",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "unsloth/Devstral-Small-2-24B-Instruct-2512",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Empty messages response",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 3,
                "total_tokens": 3,
            },
        }

        with patch("app.llm.unsloth.requests.post", return_value=mock_response):
            result = provider.call([])

        assert result["content"] == "Empty messages response"
        assert result["finish_reason"] == "stop"

    def test_stream_empty_messages(self):
        """stream() should send an empty messages list to the API."""
        from unittest.mock import MagicMock, patch

        import requests

        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
        )

        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            (
                b'data: {"choices":[{"index":0,"delta":{"content":"No "},'
                b'"finish_reason":null}]}'
            ),
            (
                b'data: {"choices":[{"index":0,"delta":{"content":"messages"},'
                b'"finish_reason":null}]}'
            ),
            b"data: [DONE]",
        ]

        with patch("app.llm.unsloth.requests.post", return_value=mock_response):
            tokens = list(provider.stream([]))

        assert tokens == ["No ", "messages"]

    # ------------------------------------------------------------------
    # Constructor edge cases
    # ------------------------------------------------------------------

    def test_constructor_timeout_negative(self):
        """A negative timeout should be stored without validation
        (server will reject at request time)."""
        from app.llm.unsloth import UnslothProvider

        provider = UnslothProvider(
            base_url="http://localhost:8888",
            model="unsloth/Devstral-Small-2-24B-Instruct-2512",
            timeout=-5,
        )
        assert provider.timeout == -5
