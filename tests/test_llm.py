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
        h = HealthResult(ok=False, latency_ms=0.0, model="gpt-4", error="Connection refused")
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

        with patch("app.llm.ollama.requests.post", return_value=mock_response) as mock_post:
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
            b'data: {"choices":[{"index":0,"delta":{"content":"Hello "},"finish_reason":null}]}',
            b'data: {"choices":[{"index":0,"delta":{"content":"world"},"finish_reason":null}]}',
            b'data: {"choices":[{"index":0,"delta":{"content":"!"},"finish_reason":null}]}',
            b'data: {"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}',
            b'data: [DONE]',
        ]

        with patch("app.llm.ollama.requests.post", return_value=mock_response) as mock_post:
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
            b'data: [DONE]',
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

    def test_stream_invalid_json_chunk_raises_provider_error(self):
        """stream() should raise ProviderError on malformed SSE data."""
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
            b'data: {invalid json here}',
        ]

        with patch("app.llm.ollama.requests.post", return_value=mock_response):
            with pytest.raises(ProviderError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert "Invalid JSON" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

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
        mock_response.iter_lines.side_effect = (
            requests.exceptions.ChunkedEncodingError("Connection broken")
        )

        with patch(
            "app.llm.ollama.requests.post", return_value=mock_response
        ):
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
        mock_response.iter_lines.side_effect = (
            requests.exceptions.RequestException("Something went wrong")
        )

        with patch(
            "app.llm.ollama.requests.post", return_value=mock_response
        ):
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
