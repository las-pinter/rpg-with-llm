"""Tests for the OpenAICompatibleProvider base class.

Covers ProviderSpec, call(), stream(), list_models(), health(),
_headers(), base_url normalization, and _last_stream_usage isolation.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from app.llm._openai_compat import OpenAICompatibleProvider, ProviderSpec
from app.llm.base import (
    HealthResult,
    LLMConnectionError,
    LLMError,
    LLMTimeoutError,
    ModelInfo,
    ProviderError,
)

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

_TEST_SPEC = ProviderSpec(
    provider_name="TestProvider",
    models_endpoint="/v1/models",
    models_key="data",
    name_key="id",
)

_TEST_SPEC_WITH_FALLBACKS = ProviderSpec(
    provider_name="FallbackProvider",
    models_endpoint="/v1/models",
    models_key="data",
    name_key="id",
    name_key_fallback="display_name",
    health_endpoint="/health",
    health_fallback_endpoint="/status",
)

_TEST_SPEC_OPENROUTER = ProviderSpec(
    provider_name="OpenRouter",
    models_endpoint="/v1/models",
    models_key="data",
    name_key="id",
    name_key_fallback="name",
)


def _make_provider(
    spec: ProviderSpec | None = None,
    api_key: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    timeout: int = 300,
    base_url: str = "http://localhost:11434",
    model: str = "test-model",
) -> OpenAICompatibleProvider:
    """Build a provider with a real ProviderSpec for testing."""
    return OpenAICompatibleProvider(
        base_url=base_url,
        model=model,
        api_key=api_key,
        timeout=timeout,
        max_tokens=max_tokens,
        temperature=temperature,
        spec=spec or _TEST_SPEC,
    )


def _make_mock_response(
    ok: bool = True,
    status_code: int = 200,
    json_data: dict | None = None,
    text: str = "",
    json_side_effect: Exception | None = None,
) -> MagicMock:
    """Build a MagicMock that mimics requests.Response."""
    mock = MagicMock(spec=requests.Response)
    mock.ok = ok
    mock.status_code = status_code
    mock.text = text
    if json_side_effect:
        mock.json.side_effect = json_side_effect
    elif json_data is not None:
        mock.json.return_value = json_data
    else:
        mock.json.return_value = {}
    return mock


# ===========================================================================
# ProviderSpec tests
# ===========================================================================


class TestProviderSpec:
    """Tests for the immutable ProviderSpec dataclass."""

    def test_provider_spec_is_frozen(self):
        """ProviderSpec should be immutable (frozen)."""
        spec = ProviderSpec(
            provider_name="Test",
            models_endpoint="/v1/models",
            models_key="data",
            name_key="id",
        )
        with pytest.raises(AttributeError):
            spec.provider_name = "Changed"  # type: ignore[assignment]

        with pytest.raises(AttributeError):
            spec.models_endpoint = "/changed"  # type: ignore[assignment]

    def test_provider_spec_defaults(self):
        """Optional fields default to None."""
        spec = ProviderSpec(
            provider_name="Test",
            models_endpoint="/v1/models",
            models_key="data",
            name_key="id",
        )
        assert spec.name_key_fallback is None
        assert spec.health_endpoint is None
        assert spec.health_fallback_endpoint is None

    def test_provider_spec_accepts_all_fields(self):
        """ProviderSpec should accept all optional fields."""
        spec = ProviderSpec(
            provider_name="FullSpec",
            models_endpoint="/v1/models",
            models_key="results",
            name_key="uid",
            name_key_fallback="display",
            health_endpoint="/healthz",
            health_fallback_endpoint="/ping",
        )
        assert spec.provider_name == "FullSpec"
        assert spec.models_endpoint == "/v1/models"
        assert spec.models_key == "results"
        assert spec.name_key == "uid"
        assert spec.name_key_fallback == "display"
        assert spec.health_endpoint == "/healthz"
        assert spec.health_fallback_endpoint == "/ping"


# ===========================================================================
# call() method tests
# ===========================================================================


class TestCallMethod:
    """Tests for the call() non-streaming method."""

    def test_call_success(self):
        """call() should return parsed content, finish_reason, and usage."""
        provider = _make_provider()
        mock_response = _make_mock_response(
            json_data={
                "choices": [
                    {
                        "message": {"content": "Hello"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                },
            }
        )

        with patch("app.llm._openai_compat.requests.post", return_value=mock_response):
            result = provider.call([{"role": "user", "content": "Hi"}])

        assert result["content"] == "Hello"
        assert result["finish_reason"] == "stop"
        assert result["usage"]["total_tokens"] == 15

    def test_call_with_max_tokens_and_temperature(self):
        """call() payload should include max_tokens and temperature when set."""
        provider = _make_provider(
            max_tokens=512,
            temperature=0.7,
        )
        mock_response = _make_mock_response(
            json_data={
                "choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                },
            }
        )

        with patch(
            "app.llm._openai_compat.requests.post", return_value=mock_response
        ) as m:
            provider.call([{"role": "user", "content": "Hi"}])

        payload = m.call_args[1]["json"]
        assert payload["max_tokens"] == 512
        assert payload["temperature"] == 0.7

    def test_call_without_max_tokens_and_temperature(self):
        """call() payload should omit max_tokens and temperature when None."""
        provider = _make_provider(max_tokens=None, temperature=None)
        mock_response = _make_mock_response(
            json_data={
                "choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                },
            }
        )

        with patch(
            "app.llm._openai_compat.requests.post", return_value=mock_response
        ) as m:
            provider.call([{"role": "user", "content": "Hi"}])

        payload = m.call_args[1]["json"]
        assert "max_tokens" not in payload
        assert "temperature" not in payload

    def test_call_timeout_raises_llm_timeout_error(self):
        """call() should raise LLMTimeoutError on request timeout."""
        provider = _make_provider()

        with patch(
            "app.llm._openai_compat.requests.post",
            side_effect=requests.exceptions.Timeout("Connection timed out"),
        ):
            with pytest.raises(LLMTimeoutError) as excinfo:
                provider.call([{"role": "user", "content": "Hi"}])

        assert "TestProvider" in str(excinfo.value)
        assert "timed out" in str(excinfo.value).lower()
        assert isinstance(excinfo.value, LLMError)

    def test_call_connection_error_raises_llm_connection_error(self):
        """call() should raise LLMConnectionError when provider is unreachable."""
        provider = _make_provider()

        with patch(
            "app.llm._openai_compat.requests.post",
            side_effect=requests.exceptions.ConnectionError("Connection refused"),
        ):
            with pytest.raises(LLMConnectionError) as excinfo:
                provider.call([{"role": "user", "content": "Hi"}])

        assert "TestProvider" in str(excinfo.value)
        assert "Cannot connect" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_call_http_error_raises_provider_error(self):
        """call() should raise ProviderError on non-OK HTTP status."""
        provider = _make_provider()
        mock_response = _make_mock_response(
            ok=False,
            status_code=400,
            text='{"error": "bad request"}',
        )

        with patch("app.llm._openai_compat.requests.post", return_value=mock_response):
            with pytest.raises(ProviderError) as excinfo:
                provider.call([{"role": "user", "content": "Hi"}])

        assert "TestProvider" in str(excinfo.value)
        assert "400" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_call_invalid_json_raises_provider_error(self):
        """call() should raise ProviderError on invalid JSON response body."""
        provider = _make_provider()
        mock_response = _make_mock_response(
            ok=True,
            json_side_effect=json.JSONDecodeError("Expecting value", "", 0),
        )

        with patch("app.llm._openai_compat.requests.post", return_value=mock_response):
            with pytest.raises(ProviderError) as excinfo:
                provider.call([{"role": "user", "content": "Hi"}])

        assert "TestProvider" in str(excinfo.value)
        assert "Invalid JSON" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_call_empty_choices_raises_provider_error(self):
        """call() should raise ProviderError when choices array is empty."""
        provider = _make_provider()
        mock_response = _make_mock_response(
            json_data={
                "choices": [],
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
            }
        )

        with patch("app.llm._openai_compat.requests.post", return_value=mock_response):
            with pytest.raises(ProviderError) as excinfo:
                provider.call([{"role": "user", "content": "Hi"}])

        assert "TestProvider" in str(excinfo.value)
        assert "Invalid response structure" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_call_missing_usage_raises_provider_error(self):
        """call() should raise ProviderError when response lacks 'usage' key."""
        provider = _make_provider()
        mock_response = _make_mock_response(
            json_data={
                "choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}],
            }
        )

        with patch("app.llm._openai_compat.requests.post", return_value=mock_response):
            with pytest.raises(ProviderError) as excinfo:
                provider.call([{"role": "user", "content": "Hi"}])

        assert "TestProvider" in str(excinfo.value)
        assert "Invalid response structure" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_call_error_messages_include_provider_name(self):
        """All call() error messages should include the provider_name from spec."""
        provider = _make_provider(
            spec=ProviderSpec(
                provider_name="SneakyProvider",
                models_endpoint="/v1/models",
                models_key="data",
                name_key="id",
            )
        )

        # HTTP error
        mock_resp = _make_mock_response(ok=False, status_code=500, text="fail")
        with patch("app.llm._openai_compat.requests.post", return_value=mock_resp):
            with pytest.raises(ProviderError) as excinfo:
                provider.call([{"role": "user", "content": "Hi"}])
        assert "SneakyProvider" in str(excinfo.value)

        # Timeout
        with patch(
            "app.llm._openai_compat.requests.post",
            side_effect=requests.exceptions.Timeout("timeout"),
        ):
            with pytest.raises(LLMTimeoutError) as excinfo:
                provider.call([{"role": "user", "content": "Hi"}])
        assert "SneakyProvider" in str(excinfo.value)

        # Connection error
        with patch(
            "app.llm._openai_compat.requests.post",
            side_effect=requests.exceptions.ConnectionError("refused"),
        ):
            with pytest.raises(LLMConnectionError) as excinfo:
                provider.call([{"role": "user", "content": "Hi"}])
        assert "SneakyProvider" in str(excinfo.value)

        # Invalid JSON
        mock_resp2 = _make_mock_response(
            ok=True,
            json_side_effect=json.JSONDecodeError("bad", "", 0),
        )
        with patch("app.llm._openai_compat.requests.post", return_value=mock_resp2):
            with pytest.raises(ProviderError) as excinfo:
                provider.call([{"role": "user", "content": "Hi"}])
        assert "SneakyProvider" in str(excinfo.value)

        # Empty choices
        mock_resp3 = _make_mock_response(
            json_data={"choices": []},
        )
        with patch("app.llm._openai_compat.requests.post", return_value=mock_resp3):
            with pytest.raises(ProviderError) as excinfo:
                provider.call([{"role": "user", "content": "Hi"}])
        assert "SneakyProvider" in str(excinfo.value)

    def test_call_posts_to_correct_url(self):
        """call() should POST to {base_url}/v1/chat/completions."""
        provider = _make_provider(base_url="http://my-host:9000")
        mock_response = _make_mock_response(
            json_data={
                "choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                },
            }
        )

        with patch(
            "app.llm._openai_compat.requests.post", return_value=mock_response
        ) as m:
            provider.call([{"role": "user", "content": "Hi"}])

        assert m.call_args[0][0] == "http://my-host:9000/v1/chat/completions"

    def test_call_includes_correct_headers(self):
        """call() should send Content-Type and optional Authorization headers."""
        provider = _make_provider(api_key="sk-mykey")
        mock_response = _make_mock_response(
            json_data={
                "choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                },
            }
        )

        with patch(
            "app.llm._openai_compat.requests.post", return_value=mock_response
        ) as m:
            provider.call([{"role": "user", "content": "Hi"}])

        headers = m.call_args[1]["headers"]
        assert headers["Content-Type"] == "application/json"
        assert headers["Authorization"] == "Bearer sk-mykey"

    def test_call_uses_configured_timeout(self):
        """call() should pass the configured timeout to requests.post."""
        provider = _make_provider(timeout=60)
        mock_response = _make_mock_response(
            json_data={
                "choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                },
            }
        )

        with patch(
            "app.llm._openai_compat.requests.post", return_value=mock_response
        ) as m:
            provider.call([{"role": "user", "content": "Hi"}])

        assert m.call_args[1]["timeout"] == 60

    def test_call_with_finish_reason_length(self):
        """call() should pass through any finish_reason value."""
        provider = _make_provider()
        mock_response = _make_mock_response(
            json_data={
                "choices": [
                    {
                        "message": {"content": "A very long response..."},
                        "finish_reason": "length",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 100,
                    "total_tokens": 110,
                },
            }
        )

        with patch("app.llm._openai_compat.requests.post", return_value=mock_response):
            result = provider.call([{"role": "user", "content": "Write an essay"}])

        assert result["finish_reason"] == "length"
        assert result["usage"]["completion_tokens"] == 100


# ===========================================================================
# stream() method tests
# ===========================================================================


class TestStreamMethod:
    """Tests for the stream() streaming method."""

    def _make_sse_lines(self, chunks: list[dict], done: bool = True) -> list[bytes]:
        """Convert SSE chunk dicts to raw bytes for iter_lines."""
        lines: list[bytes] = []
        for chunk in chunks:
            lines.append(f"data: {json.dumps(chunk)}".encode())
        if done:
            lines.append(b"data: [DONE]")
        return lines

    def test_stream_yields_tokens(self):
        """stream() should yield content tokens from multiple SSE chunks."""
        provider = _make_provider()
        chunks = [
            {"choices": [{"index": 0, "delta": {"content": "Hello "}}]},
            {"choices": [{"index": 0, "delta": {"content": "world"}}]},
            {"choices": [{"index": 0, "delta": {"content": "!"}}]},
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
        ]
        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = self._make_sse_lines(chunks)

        with patch("app.llm._openai_compat.requests.post", return_value=mock_response):
            tokens = list(provider.stream([{"role": "user", "content": "Hi"}]))

        assert tokens == ["Hello ", "world", "!"]

    def test_stream_skips_non_data_lines(self):
        """stream() should skip lines that do not start with 'data: '."""
        provider = _make_provider()
        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b"",
            b":comment",
            b"  ",
            b'data: {"choices":[{"index":0,"delta":{"content":"Hi"}}]}',
            b"data: [DONE]",
        ]

        with patch("app.llm._openai_compat.requests.post", return_value=mock_response):
            tokens = list(provider.stream([{"role": "user", "content": "Hi"}]))

        assert tokens == ["Hi"]

    def test_stream_stops_at_done(self):
        """stream() should terminate iteration when it sees '[DONE]'."""
        provider = _make_provider()
        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b'data: {"choices":[{"index":0,"delta":{"content":"First"}}]}',
            b"data: [DONE]",
            b'data: {"choices":[{"index":0,"delta":{"content":"ShouldNotAppear"}}]}',
        ]

        with patch("app.llm._openai_compat.requests.post", return_value=mock_response):
            tokens = list(provider.stream([{"role": "user", "content": "Hi"}]))

        assert tokens == ["First"]

    def test_stream_captures_usage(self):
        """stream() should set _last_stream_usage when a 'usage' chunk appears."""
        provider = _make_provider()
        chunks = [
            {"choices": [{"index": 0, "delta": {"content": "Hi"}}]},
            {
                "usage": {
                    "prompt_tokens": 5,
                    "completion_tokens": 3,
                    "total_tokens": 8,
                }
            },
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
        ]
        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = self._make_sse_lines(chunks)

        with patch("app.llm._openai_compat.requests.post", return_value=mock_response):
            list(provider.stream([{"role": "user", "content": "Hi"}]))

        assert provider._last_stream_usage is not None
        assert provider._last_stream_usage["total_tokens"] == 8

    def test_stream_timeout_raises_llm_timeout_error(self):
        """stream() should raise LLMTimeoutError on request timeout."""
        provider = _make_provider()

        with patch(
            "app.llm._openai_compat.requests.post",
            side_effect=requests.exceptions.Timeout("Stream timed out"),
        ):
            with pytest.raises(LLMTimeoutError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert isinstance(excinfo.value, LLMError)

    def test_stream_connection_error_raises_llm_connection_error(self):
        """stream() should raise LLMConnectionError when provider is unreachable."""
        provider = _make_provider()

        with patch(
            "app.llm._openai_compat.requests.post",
            side_effect=requests.exceptions.ConnectionError("Connection refused"),
        ):
            with pytest.raises(LLMConnectionError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert isinstance(excinfo.value, LLMError)

    def test_stream_http_error_raises_provider_error(self):
        """stream() should raise ProviderError on non-OK HTTP status."""
        provider = _make_provider()
        mock_response = _make_mock_response(
            ok=False,
            status_code=401,
            text="unauthorized",
        )

        with patch("app.llm._openai_compat.requests.post", return_value=mock_response):
            with pytest.raises(ProviderError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert "401" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_stream_invalid_json_raises_provider_error(self):
        """stream() should raise ProviderError on invalid JSON in a stream chunk."""
        provider = _make_provider()
        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b"data: {not valid json}",
            b"data: [DONE]",
        ]

        with patch("app.llm._openai_compat.requests.post", return_value=mock_response):
            with pytest.raises(ProviderError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert "Invalid JSON" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_stream_posts_with_stream_true(self):
        """stream() should POST with stream=True and stream=True in payload."""
        provider = _make_provider()
        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [b"data: [DONE]"]

        with patch(
            "app.llm._openai_compat.requests.post", return_value=mock_response
        ) as m:
            list(provider.stream([{"role": "user", "content": "Hi"}]))

        payload = m.call_args[1]["json"]
        assert payload["stream"] is True
        assert m.call_args[1]["stream"] is True

    def test_stream_with_max_tokens_and_temperature(self):
        """stream() payload should include max_tokens and temperature when set."""
        provider = _make_provider(max_tokens=256, temperature=0.5)
        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [b"data: [DONE]"]

        with patch(
            "app.llm._openai_compat.requests.post", return_value=mock_response
        ) as m:
            list(provider.stream([{"role": "user", "content": "Hi"}]))

        payload = m.call_args[1]["json"]
        assert payload["max_tokens"] == 256
        assert payload["temperature"] == 0.5

    def test_stream_chunked_encoding_error_raises_connection_error(self):
        """stream() should raise LLMConnectionError on ChunkedEncodingError."""
        provider = _make_provider()
        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.side_effect = requests.exceptions.ChunkedEncodingError(
            "Connection broken"
        )

        with patch("app.llm._openai_compat.requests.post", return_value=mock_response):
            with pytest.raises(LLMConnectionError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert "Stream connection lost" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)

    def test_stream_generic_request_exception_raises_provider_error(self):
        """ProviderError raised on generic RequestException mid-stream."""
        provider = _make_provider()
        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.iter_lines.side_effect = requests.exceptions.RequestException(
            "Unknown stream error"
        )

        with patch("app.llm._openai_compat.requests.post", return_value=mock_response):
            with pytest.raises(ProviderError) as excinfo:
                for _ in provider.stream([{"role": "user", "content": "Hi"}]):
                    pass

        assert "Stream error" in str(excinfo.value)
        assert isinstance(excinfo.value, LLMError)


# ===========================================================================
# list_models() method tests
# ===========================================================================


class TestListModelsMethod:
    """Tests for the list_models() method."""

    def test_list_models_success(self):
        """list_models() should return parsed ModelInfo objects on success."""
        provider = _make_provider()
        mock_response = _make_mock_response(
            json_data={
                "data": [
                    {"id": "model-a", "display_name": "Model A"},
                    {"id": "model-b", "display_name": "Model B"},
                ]
            }
        )

        with patch("app.llm._openai_compat.requests.get", return_value=mock_response):
            models = provider.list_models()

        assert len(models) == 2
        assert isinstance(models[0], ModelInfo)
        assert models[0].id == "model-a"
        assert models[0].name == "model-a"
        assert models[0].provider == "TestProvider"
        assert models[1].id == "model-b"
        assert models[1].provider == "TestProvider"

    def test_list_models_empty_response(self):
        """list_models() should return [] when models array is empty."""
        provider = _make_provider()
        mock_response = _make_mock_response(json_data={"data": []})

        with patch("app.llm._openai_compat.requests.get", return_value=mock_response):
            models = provider.list_models()

        assert models == []

    def test_list_models_http_error_returns_empty(self):
        """list_models() should return [] on HTTP error."""
        provider = _make_provider()
        mock_response = _make_mock_response(ok=False, status_code=500)

        with patch("app.llm._openai_compat.requests.get", return_value=mock_response):
            models = provider.list_models()

        assert models == []

    def test_list_models_json_parse_error_returns_empty(self):
        """list_models() should return [] on invalid JSON."""
        provider = _make_provider()
        mock_response = _make_mock_response(
            ok=True,
            json_side_effect=json.JSONDecodeError("bad", "", 0),
        )

        with patch("app.llm._openai_compat.requests.get", return_value=mock_response):
            models = provider.list_models()

        assert models == []

    def test_list_models_uses_spec_endpoints(self):
        """list_models() should use health_endpoint over models_endpoint when set."""
        provider = _make_provider(spec=_TEST_SPEC_WITH_FALLBACKS)
        mock_response = _make_mock_response(json_data={"data": []})

        with patch(
            "app.llm._openai_compat.requests.get", return_value=mock_response
        ) as m:
            provider.list_models()

        # health_endpoint takes precedence
        assert m.call_args[0][0] == "http://localhost:11434/health"

    def test_list_models_name_key_fallback(self):
        """list_models() should use name_key_fallback when set (OpenRouter case)."""
        provider = _make_provider(spec=_TEST_SPEC_OPENROUTER)
        mock_response = _make_mock_response(
            json_data={
                "data": [
                    {"id": "meta/llama-3.1-8b", "name": "Llama 3.1 8B"},
                ]
            }
        )

        with patch("app.llm._openai_compat.requests.get", return_value=mock_response):
            models = provider.list_models()

        assert len(models) == 1
        assert models[0].id == "meta/llama-3.1-8b"
        assert models[0].name == "Llama 3.1 8B"

    def test_list_models_uses_models_endpoint_when_no_health_endpoint(self):
        """Uses models_endpoint when health_endpoint is None."""
        provider = _make_provider(spec=_TEST_SPEC)
        mock_response = _make_mock_response(json_data={"data": []})

        with patch(
            "app.llm._openai_compat.requests.get", return_value=mock_response
        ) as m:
            provider.list_models()

        assert m.call_args[0][0] == "http://localhost:11434/v1/models"

    def test_list_models_skips_empty_id(self):
        """list_models() should skip entries with empty id."""
        provider = _make_provider()
        mock_response = _make_mock_response(
            json_data={
                "data": [
                    {"id": "valid-model"},
                    {"id": ""},
                    {"id": "another-valid"},
                ]
            }
        )

        with patch("app.llm._openai_compat.requests.get", return_value=mock_response):
            models = provider.list_models()

        assert len(models) == 2
        assert models[0].id == "valid-model"
        assert models[1].id == "another-valid"

    def test_list_models_connection_error_returns_empty(self):
        """list_models() should return [] on connection error."""
        provider = _make_provider()

        with patch(
            "app.llm._openai_compat.requests.get",
            side_effect=requests.exceptions.ConnectionError("refused"),
        ):
            models = provider.list_models()

        assert models == []

    def test_list_models_timeout_returns_empty(self):
        """list_models() should return [] on timeout."""
        provider = _make_provider()

        with patch(
            "app.llm._openai_compat.requests.get",
            side_effect=requests.exceptions.Timeout("timeout"),
        ):
            models = provider.list_models()

        assert models == []


# ===========================================================================
# health() method tests
# ===========================================================================


class TestHealthMethod:
    """Tests for the health() method."""

    def test_health_success(self):
        """health() should return HealthResult(ok=True) on success."""
        provider = _make_provider()
        mock_response = _make_mock_response(
            json_data={
                "data": [{"id": "test-model"}],
            }
        )

        with patch("app.llm._openai_compat.requests.get", return_value=mock_response):
            result = provider.health()

        assert isinstance(result, HealthResult)
        assert result.ok is True
        assert result.model == "test-model"
        assert result.error is None
        assert result.latency_ms >= 0

    def test_health_http_error_returns_unhealthy(self):
        """health() should return ok=False on HTTP error."""
        provider = _make_provider()
        mock_response = _make_mock_response(ok=False, status_code=500)

        with patch("app.llm._openai_compat.requests.get", return_value=mock_response):
            result = provider.health()

        assert result.ok is False
        assert result.error is not None
        assert "TestProvider" in result.error
        assert "500" in result.error
        assert result.latency_ms >= 0

    def test_health_timeout_returns_unhealthy(self):
        """health() should return ok=False on timeout."""
        provider = _make_provider()

        with patch(
            "app.llm._openai_compat.requests.get",
            side_effect=requests.exceptions.Timeout("timeout"),
        ):
            result = provider.health()

        assert result.ok is False
        assert result.error is not None
        assert "TestProvider" in result.error
        assert "Timeout" in result.error
        assert result.latency_ms >= 0

    def test_health_connection_error_without_fallback_returns_unhealthy(
        self,
    ):
        """Unhealthy when no fallback endpoint is configured."""
        provider = _make_provider(spec=_TEST_SPEC)

        with patch(
            "app.llm._openai_compat.requests.get",
            side_effect=requests.exceptions.ConnectionError("refused"),
        ):
            result = provider.health()

        assert result.ok is False
        assert result.error is not None
        assert "TestProvider" in result.error
        assert "Connection error" in result.error

    def test_health_connection_error_with_fallback_succeeds(self):
        """health() should try fallback endpoint when primary connection fails."""
        provider = _make_provider(spec=_TEST_SPEC_WITH_FALLBACKS)
        primary_resp = MagicMock(spec=requests.Response)
        primary_resp.ok = False
        primary_resp.status_code = 0

        fallback_resp = _make_mock_response(
            json_data={"data": [{"id": "fallback-model"}]},
        )

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise requests.exceptions.ConnectionError("primary refused")
            return fallback_resp

        with patch("app.llm._openai_compat.requests.get", side_effect=side_effect):
            result = provider.health()

        assert result.ok is True
        assert result.model == "fallback-model"
        assert call_count == 2

    def test_health_both_tiers_fail(self):
        """health() should return unhealthy when both primary and fallback fail."""
        provider = _make_provider(spec=_TEST_SPEC_WITH_FALLBACKS)

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise requests.exceptions.ConnectionError(f"tier {call_count} refused")

        with patch("app.llm._openai_compat.requests.get", side_effect=side_effect):
            result = provider.health()

        assert result.ok is False
        assert result.error is not None
        assert "FallbackProvider" in result.error
        assert call_count == 2

    def test_health_error_messages_include_provider_name(self):
        """Error messages should include the provider_name from spec."""
        provider = _make_provider(
            spec=ProviderSpec(
                provider_name="SpookyProvider",
                models_endpoint="/v1/models",
                models_key="data",
                name_key="id",
            )
        )

        # HTTP error
        with patch(
            "app.llm._openai_compat.requests.get",
            return_value=_make_mock_response(ok=False, status_code=503),
        ):
            result = provider.health()
        assert result.error is not None
        assert "SpookyProvider" in result.error

        # Timeout
        with patch(
            "app.llm._openai_compat.requests.get",
            side_effect=requests.exceptions.Timeout("timeout"),
        ):
            result = provider.health()
        assert result.error is not None
        assert "SpookyProvider" in result.error

        # Connection error (no fallback)
        with patch(
            "app.llm._openai_compat.requests.get",
            side_effect=requests.exceptions.ConnectionError("refused"),
        ):
            result = provider.health()
        assert result.error is not None
        assert "SpookyProvider" in result.error

    def test_health_empty_model_list(self):
        """health() should fall back to constructor model when list is empty."""
        provider = _make_provider()
        mock_response = _make_mock_response(json_data={"data": []})

        with patch("app.llm._openai_compat.requests.get", return_value=mock_response):
            result = provider.health()

        assert result.ok is True
        assert result.model == "test-model"

    def test_health_fallback_timeout_returns_unhealthy(self):
        """Unhealthy when fallback endpoint times out."""
        provider = _make_provider(spec=_TEST_SPEC_WITH_FALLBACKS)

        with patch(
            "app.llm._openai_compat.requests.get",
            side_effect=[
                requests.exceptions.ConnectionError("primary refused"),
                requests.exceptions.Timeout("fallback timeout"),
            ],
        ):
            result = provider.health()

        assert result.ok is False
        assert result.error is not None
        assert "FallbackProvider" in result.error
        assert "Timeout" in result.error

    def test_health_fallback_http_error_returns_unhealthy(self):
        """Unhealthy when fallback returns HTTP error."""
        provider = _make_provider(spec=_TEST_SPEC_WITH_FALLBACKS)

        with patch(
            "app.llm._openai_compat.requests.get",
            side_effect=[
                requests.exceptions.ConnectionError("primary refused"),
                _make_mock_response(ok=False, status_code=502, text="bad gateway"),
            ],
        ):
            result = provider.health()

        assert result.ok is False
        assert result.error is not None
        assert "FallbackProvider" in result.error
        assert "502" in result.error

    def test_health_fallback_connection_error_returns_unhealthy(self):
        """Unhealthy when fallback also has connection error."""
        provider = _make_provider(spec=_TEST_SPEC_WITH_FALLBACKS)

        with patch(
            "app.llm._openai_compat.requests.get",
            side_effect=[
                requests.exceptions.ConnectionError("primary refused"),
                requests.exceptions.ConnectionError("fallback refused"),
            ],
        ):
            result = provider.health()

        assert result.ok is False
        assert result.error is not None
        assert "FallbackProvider" in result.error


# ===========================================================================
# _headers() method tests
# ===========================================================================


class TestHeadersMethod:
    """Tests for the internal _headers() method."""

    def test_headers_content_type(self):
        """_headers() should always include Content-Type."""
        provider = _make_provider(api_key=None)
        headers = provider._headers()
        assert "Content-Type" in headers
        assert headers["Content-Type"] == "application/json"

    def test_headers_authorization_with_api_key(self):
        """_headers() should include Bearer token when api_key is set."""
        provider = _make_provider(api_key="sk-secret")
        headers = provider._headers()
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer sk-secret"

    def test_headers_no_authorization_without_api_key(self):
        """_headers() should not include Authorization when api_key is None."""
        provider = _make_provider(api_key=None)
        headers = provider._headers()
        assert "Authorization" not in headers

    def test_headers_no_authorization_with_empty_string_api_key(self):
        """_headers() should not include Authorization when api_key is empty string."""
        provider = _make_provider(api_key="")
        headers = provider._headers()
        assert "Authorization" not in headers


# ===========================================================================
# Init and attribute tests
# ===========================================================================


class TestInitAndAttributes:
    """Tests for __init__ and base-level attributes."""

    def test_base_url_strips_trailing_slash(self):
        """base_url should have trailing slashes removed."""
        provider = _make_provider(base_url="http://localhost:11434///")
        assert provider.base_url == "http://localhost:11434"

    def test_base_url_strips_single_trailing_slash(self):
        """base_url should remove a single trailing slash."""
        provider = _make_provider(base_url="http://localhost:11434/")
        assert provider.base_url == "http://localhost:11434"

    def test_base_url_strips_multiple_trailing_slashes(self):
        """base_url should remove multiple trailing slashes."""
        provider = _make_provider(base_url="http://localhost:11434////")
        assert provider.base_url == "http://localhost:11434"

    def test_base_url_strips_leading_whitespace(self):
        """base_url should have leading whitespace stripped."""
        provider = _make_provider(base_url="  http://localhost:11434")
        assert provider.base_url == "http://localhost:11434"

    def test_base_url_strips_trailing_whitespace(self):
        """base_url should have trailing whitespace stripped."""
        provider = _make_provider(base_url="http://localhost:11434  ")
        assert provider.base_url == "http://localhost:11434"

    def test_base_url_strips_both_whitespace_and_slashes(self):
        """base_url should strip whitespace and trailing slashes together."""
        provider = _make_provider(base_url="  http://localhost:11434/  ")
        assert provider.base_url == "http://localhost:11434"

    def test_default_spec_when_no_spec_provided(self):
        """When spec is not a ProviderSpec, defaults should be used."""
        provider = OpenAICompatibleProvider(
            base_url="http://localhost:11434",
            model="test-model",
        )
        assert provider._spec.provider_name == "OpenAI-Compatible"
        assert provider._spec.models_endpoint == "/v1/models"
        assert provider._spec.models_key == "data"
        assert provider._spec.name_key == "id"

    def test_default_spec_fallback_defaults(self):
        """Default spec should have None for optional fields."""
        provider = OpenAICompatibleProvider(
            base_url="http://localhost:11434",
            model="test-model",
        )
        assert provider._spec.name_key_fallback is None
        assert provider._spec.health_endpoint is None
        assert provider._spec.health_fallback_endpoint is None

    def test_last_stream_usage_is_instance_attribute(self):
        """Each instance should have its own _last_stream_usage, not shared."""
        provider_a = _make_provider()
        provider_b = _make_provider()

        # Initially both are None
        assert provider_a._last_stream_usage is None
        assert provider_b._last_stream_usage is None

        # Set one to a dict — the other should remain None
        provider_a._last_stream_usage = {"total_tokens": 42}
        assert provider_a._last_stream_usage == {"total_tokens": 42}
        assert provider_b._last_stream_usage is None

    def test_last_stream_usage_is_not_shared_with_class(self):
        """Modifying _last_stream_usage on one instance should not affect another."""
        provider_a = _make_provider()
        provider_b = _make_provider()

        provider_a._last_stream_usage = {"prompt_tokens": 10}
        provider_b._last_stream_usage = {"prompt_tokens": 20}

        assert provider_a._last_stream_usage["prompt_tokens"] == 10
        assert provider_b._last_stream_usage["prompt_tokens"] == 20

    def test_attributes_stored_correctly(self):
        """All constructor arguments should be stored as instance attributes."""
        provider = _make_provider(
            base_url="http://host:8080",
            model="my-model",
            api_key="sk-abc",
            max_tokens=128,
            temperature=0.3,
            timeout=60,
        )
        assert provider.base_url == "http://host:8080"
        assert provider.model == "my-model"
        assert provider.api_key == "sk-abc"
        assert provider.max_tokens == 128
        assert provider.temperature == 0.3
        assert provider.timeout == 60

    def test_timeout_default_is_300(self):
        """timeout should default to 300 seconds."""
        provider = _make_provider()
        assert provider.timeout == 300

    def test_max_tokens_default_is_none(self):
        """max_tokens should default to None."""
        provider = _make_provider()
        assert provider.max_tokens is None

    def test_temperature_default_is_none(self):
        """temperature should default to None."""
        provider = _make_provider()
        assert provider.temperature is None
