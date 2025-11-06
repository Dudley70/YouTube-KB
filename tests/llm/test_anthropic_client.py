"""
Comprehensive tests for AnthropicClient implementation.

These tests follow TDD methodology - written before implementation to define
expected behavior and API contracts.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from typing import Dict, Any

from youtube_processor.llm.models import (
    LLMRequest, LLMResponse, LLMMessage, LLMUsageMetrics,
    MessageRole, LLMProvider, RateLimitError, LLMAPIError,
    TokenLimitError, AuthenticationError, ValidationError
)
from youtube_processor.llm.anthropic_client import AnthropicClient


class TestAnthropicClientInitialization:
    """Test client initialization and configuration."""

    def test_init_with_api_key(self):
        """Test client initialization with API key."""
        client = AnthropicClient(api_key="test-key")
        assert client.api_key == "test-key"
        assert client.usage_metrics.request_count == 0
        assert client.usage_metrics.total_tokens == 0

    def test_init_without_api_key_uses_env(self):
        """Test client initialization uses environment variable when no key provided."""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'env-key'}):
            client = AnthropicClient()
            assert client.api_key == "env-key"

    def test_init_without_api_key_raises_error(self):
        """Test client initialization raises error when no API key available."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="API key must be provided"):
                AnthropicClient()

    def test_init_with_custom_base_url(self):
        """Test client initialization with custom base URL."""
        client = AnthropicClient(api_key="test-key", base_url="https://custom.api.com")
        assert client.base_url == "https://custom.api.com"

    def test_init_with_custom_timeout(self):
        """Test client initialization with custom timeout."""
        client = AnthropicClient(api_key="test-key", timeout=60.0)
        assert client.timeout == 60.0


class TestAnthropicClientBasicOperations:
    """Test basic client operations and message handling."""

    @pytest.fixture
    def client(self):
        """Create test client instance."""
        return AnthropicClient(api_key="test-key")

    def test_create_message(self, client):
        """Test creating LLM messages."""
        message = client._create_message(MessageRole.USER, "Hello, Claude!")
        assert message.role == MessageRole.USER
        assert message.content == "Hello, Claude!"
        assert isinstance(message.timestamp, datetime)

    def test_build_request_basic(self, client):
        """Test building basic request."""
        messages = [
            LLMMessage(MessageRole.USER, "What is Python?")
        ]
        request = client._build_request(messages, "claude-3-haiku-20240307")

        assert request.model == "claude-3-haiku-20240307"
        assert len(request.messages) == 1
        assert request.provider == LLMProvider.ANTHROPIC

    def test_build_request_with_system_prompt(self, client):
        """Test building request with system prompt."""
        messages = [
            LLMMessage(MessageRole.USER, "Explain quantum physics")
        ]
        request = client._build_request(
            messages,
            "claude-3-sonnet-20240229",
            system_prompt="You are a physics professor."
        )

        assert request.system_prompt == "You are a physics professor."

    def test_build_request_with_parameters(self, client):
        """Test building request with generation parameters."""
        messages = [
            LLMMessage(MessageRole.USER, "Generate creative text")
        ]
        request = client._build_request(
            messages,
            "claude-3-opus-20240229",
            max_tokens=1000,
            temperature=0.8,
            top_p=0.9
        )

        assert request.max_tokens == 1000
        assert request.temperature == 0.8
        assert request.top_p == 0.9

    def test_usage_tracking(self, client):
        """Test usage metrics tracking."""
        client._update_usage(input_tokens=100, output_tokens=50, cost=0.005)

        assert client.usage_metrics.input_tokens == 100
        assert client.usage_metrics.output_tokens == 50
        assert client.usage_metrics.total_tokens == 150
        assert client.usage_metrics.cost_usd == 0.005
        assert client.usage_metrics.request_count == 1


class TestAnthropicClientAPIInteraction:
    """Test actual API interaction and response handling."""

    @pytest.fixture
    def client(self):
        """Create test client instance."""
        return AnthropicClient(api_key="test-key")

    @pytest.fixture
    def mock_anthropic_response(self):
        """Mock successful Anthropic API response."""
        return {
            "id": "msg_test123",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Hello! I'm Claude."}],
            "model": "claude-3-haiku-20240307",
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {
                "input_tokens": 10,
                "output_tokens": 6
            }
        }

    @patch('anthropic.Anthropic')
    def test_generate_success(self, mock_anthropic_class, client, mock_anthropic_response):
        """Test successful message generation."""
        # Setup mock
        mock_anthropic = Mock()
        mock_anthropic_class.return_value = mock_anthropic
        mock_anthropic.messages.create.return_value = Mock(**mock_anthropic_response)

        client.anthropic = mock_anthropic

        # Test request
        messages = [LLMMessage(MessageRole.USER, "Hello")]
        response = client.generate(messages, "claude-3-haiku-20240307")

        # Assertions
        assert isinstance(response, LLMResponse)
        assert response.content == "Hello! I'm Claude."
        assert response.model == "claude-3-haiku-20240307"
        assert response.usage_metrics.input_tokens == 10
        assert response.usage_metrics.output_tokens == 6

    @patch('anthropic.Anthropic')
    def test_generate_with_system_prompt(self, mock_anthropic_class, client, mock_anthropic_response):
        """Test generation with system prompt."""
        mock_anthropic = Mock()
        mock_anthropic_class.return_value = mock_anthropic
        mock_anthropic.messages.create.return_value = Mock(**mock_anthropic_response)

        client.anthropic = mock_anthropic

        messages = [LLMMessage(MessageRole.USER, "Explain AI")]
        response = client.generate(
            messages,
            "claude-3-haiku-20240307",
            system_prompt="You are a helpful AI assistant."
        )

        # Check that system prompt was passed to API
        call_args = mock_anthropic.messages.create.call_args[1]
        assert call_args["system"] == "You are a helpful AI assistant."

    @patch('anthropic.Anthropic')
    def test_generate_handles_rate_limit(self, mock_anthropic_class, client):
        """Test handling of rate limit errors."""
        mock_anthropic = Mock()
        mock_anthropic_class.return_value = mock_anthropic

        # Create a proper mock RateLimitError class
        class MockRateLimitError(Exception):
            pass

        # Mock the anthropic.RateLimitError in the client module
        with patch('youtube_processor.llm.anthropic_client.anthropic.RateLimitError', MockRateLimitError):
            mock_anthropic.messages.create.side_effect = MockRateLimitError("Rate limit exceeded")
            client.anthropic = mock_anthropic

            messages = [LLMMessage(MessageRole.USER, "Test")]

            with pytest.raises(RateLimitError):
                client.generate(messages, "claude-3-haiku-20240307")

    @patch('anthropic.Anthropic')
    def test_generate_handles_auth_error(self, mock_anthropic_class, client):
        """Test handling of authentication errors."""
        mock_anthropic = Mock()
        mock_anthropic_class.return_value = mock_anthropic

        # Create a proper mock AuthenticationError class
        class MockAuthenticationError(Exception):
            pass

        # Mock the anthropic.AuthenticationError in the client module
        with patch('youtube_processor.llm.anthropic_client.anthropic.AuthenticationError', MockAuthenticationError):
            mock_anthropic.messages.create.side_effect = MockAuthenticationError("Invalid API key")
            client.anthropic = mock_anthropic

            messages = [LLMMessage(MessageRole.USER, "Test")]

            with pytest.raises(AuthenticationError):
                client.generate(messages, "claude-3-haiku-20240307")


class TestAnthropicClientRetryLogic:
    """Test retry logic and error handling."""

    @pytest.fixture
    def client(self):
        """Create test client instance."""
        return AnthropicClient(api_key="test-key")

    @pytest.fixture
    def mock_anthropic_response(self):
        """Mock successful Anthropic API response."""
        return {
            "id": "msg_test123",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Hello! I'm Claude."}],
            "model": "claude-3-haiku-20240307",
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {
                "input_tokens": 10,
                "output_tokens": 6
            }
        }

    @patch('anthropic.Anthropic')
    @patch('time.sleep')  # Mock sleep to speed up tests
    def test_retry_on_server_error(self, mock_sleep, mock_anthropic_class, client, mock_anthropic_response):
        """Test retry logic on server errors."""
        mock_anthropic = Mock()
        mock_anthropic_class.return_value = mock_anthropic

        # First call fails, second succeeds
        mock_anthropic.messages.create.side_effect = [
            Exception("Server error"),
            Mock(**mock_anthropic_response)
        ]

        client.anthropic = mock_anthropic

        messages = [LLMMessage(MessageRole.USER, "Test")]
        response = client.generate(messages, "claude-3-haiku-20240307")

        # Should have retried once
        assert mock_anthropic.messages.create.call_count == 2
        assert isinstance(response, LLMResponse)

    @patch('anthropic.Anthropic')
    @patch('time.sleep')
    def test_max_retries_exceeded(self, mock_sleep, mock_anthropic_class, client):
        """Test behavior when max retries exceeded."""
        mock_anthropic = Mock()
        mock_anthropic_class.return_value = mock_anthropic

        # Always fail with a retryable error message
        mock_anthropic.messages.create.side_effect = Exception("Server error")

        client.anthropic = mock_anthropic

        messages = [LLMMessage(MessageRole.USER, "Test")]

        with pytest.raises(LLMAPIError):
            client.generate(messages, "claude-3-haiku-20240307", max_retries=2)

        # Should have tried 3 times (original + 2 retries)
        assert mock_anthropic.messages.create.call_count == 3

    def test_exponential_backoff_calculation(self, client):
        """Test exponential backoff delay calculation."""
        # Test the backoff delays increase exponentially
        delay1 = client._calculate_retry_delay(0)  # 2^0 = 1 second
        delay2 = client._calculate_retry_delay(1)  # 2^1 = 2 seconds
        delay3 = client._calculate_retry_delay(2)  # 2^2 = 4 seconds

        assert delay1 >= 1.0 and delay1 < 2.0  # Should be around 1 second with jitter
        assert delay2 >= 2.0 and delay2 < 4.0  # Should be around 2 seconds with jitter
        assert delay3 >= 4.0 and delay3 < 8.0  # Should be around 4 seconds with jitter


class TestAnthropicClientAsyncOperations:
    """Test async operations (if implemented)."""

    @pytest.fixture
    def client(self):
        """Create test client instance."""
        return AnthropicClient(api_key="test-key")

    @pytest.fixture
    def mock_anthropic_response(self):
        """Mock successful Anthropic API response."""
        return {
            "id": "msg_test123",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Hello! I'm Claude."}],
            "model": "claude-3-haiku-20240307",
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {
                "input_tokens": 10,
                "output_tokens": 6
            }
        }

    @pytest.mark.asyncio
    @patch('anthropic.AsyncAnthropic')
    async def test_async_generate_success(self, mock_async_anthropic_class, client, mock_anthropic_response):
        """Test async message generation."""
        mock_async_anthropic = AsyncMock()
        mock_async_anthropic_class.return_value = mock_async_anthropic
        mock_async_anthropic.messages.create.return_value = Mock(**mock_anthropic_response)

        client.async_anthropic = mock_async_anthropic

        messages = [LLMMessage(MessageRole.USER, "Hello async")]
        response = await client.generate_async(messages, "claude-3-haiku-20240307")

        assert isinstance(response, LLMResponse)
        assert response.content == "Hello! I'm Claude."

    @pytest.mark.asyncio
    @patch('anthropic.AsyncAnthropic')
    async def test_async_batch_generation(self, mock_async_anthropic_class, client, mock_anthropic_response):
        """Test async batch message generation."""
        mock_async_anthropic = AsyncMock()
        mock_async_anthropic_class.return_value = mock_async_anthropic
        mock_async_anthropic.messages.create.return_value = Mock(**mock_anthropic_response)

        client.async_anthropic = mock_async_anthropic

        requests = [
            [LLMMessage(MessageRole.USER, "Question 1")],
            [LLMMessage(MessageRole.USER, "Question 2")],
            [LLMMessage(MessageRole.USER, "Question 3")]
        ]

        responses = await client.generate_batch_async(requests, "claude-3-haiku-20240307")

        assert len(responses) == 3
        assert all(isinstance(r, LLMResponse) for r in responses)


class TestAnthropicClientValidation:
    """Test request validation and error handling."""

    @pytest.fixture
    def client(self):
        """Create test client instance."""
        return AnthropicClient(api_key="test-key")

    def test_validate_empty_messages(self, client):
        """Test validation of empty messages list."""
        with pytest.raises(ValidationError, match="Messages cannot be empty"):
            client.generate([], "claude-3-haiku-20240307")

    def test_validate_invalid_model(self, client):
        """Test validation of invalid model name."""
        messages = [LLMMessage(MessageRole.USER, "Test")]

        with pytest.raises(ValidationError, match="Unsupported model"):
            client.generate(messages, "invalid-model")

    def test_validate_token_limits(self, client):
        """Test validation of token limits."""
        messages = [LLMMessage(MessageRole.USER, "Test")]

        with pytest.raises(ValidationError, match="max_tokens .* exceeds limit"):
            client.generate(messages, "claude-3-haiku-20240307", max_tokens=10000)

    def test_validate_temperature_range(self, client):
        """Test validation of temperature parameter range."""
        messages = [LLMMessage(MessageRole.USER, "Test")]

        with pytest.raises(ValidationError, match="Temperature must be between 0 and 1"):
            client.generate(messages, "claude-3-haiku-20240307", temperature=1.5)


class TestAnthropicClientUtilityMethods:
    """Test utility methods and helpers."""

    @pytest.fixture
    def client(self):
        """Create test client instance."""
        return AnthropicClient(api_key="test-key")

    def test_get_usage_summary(self, client):
        """Test usage summary generation."""
        client._update_usage(input_tokens=100, output_tokens=50, cost=0.005)

        summary = client.get_usage_summary()
        assert "100" in summary  # Input tokens
        assert "50" in summary   # Output tokens
        assert "0.005" in summary  # Cost

    def test_reset_usage_metrics(self, client):
        """Test resetting usage metrics."""
        client._update_usage(input_tokens=100, output_tokens=50, cost=0.005)
        client.reset_usage_metrics()

        assert client.usage_metrics.input_tokens == 0
        assert client.usage_metrics.output_tokens == 0
        assert client.usage_metrics.cost_usd == 0.0
        assert client.usage_metrics.request_count == 0

    def test_estimate_cost(self, client):
        """Test cost estimation for requests."""
        messages = [LLMMessage(MessageRole.USER, "Short message")]

        estimated_cost = client.estimate_cost(messages, "claude-3-haiku-20240307")
        assert isinstance(estimated_cost, float)
        assert estimated_cost > 0

    def test_simple_chat_interface(self, client):
        """Test simple chat interface method."""
        with patch.object(client, 'generate') as mock_generate:
            mock_response = LLMResponse(
                content="Hello there!",
                model="claude-3-haiku-20240307",
                provider=LLMProvider.ANTHROPIC,
                usage_metrics=LLMUsageMetrics(input_tokens=5, output_tokens=3)
            )
            mock_generate.return_value = mock_response

            response = client.chat("Hello", model="claude-3-haiku-20240307")

            assert response == "Hello there!"
            mock_generate.assert_called_once()


class TestStripMarkdownWrapper:
    """Test _strip_markdown_wrapper() helper method (CP1)."""

    @pytest.fixture
    def client(self):
        """Create test client instance."""
        return AnthropicClient(api_key="test-key")

    def test_strip_markdown_wrapper_simple_json(self, client):
        """Test stripping markdown from simple JSON response."""
        wrapped = '```json\n{"key": "value"}\n```'
        result = client._strip_markdown_wrapper(wrapped)
        assert result == '{"key": "value"}'

    def test_strip_markdown_wrapper_json_without_language(self, client):
        """Test stripping markdown without language specifier."""
        wrapped = '```\n{"key": "value"}\n```'
        result = client._strip_markdown_wrapper(wrapped)
        assert result == '{"key": "value"}'

    def test_strip_markdown_wrapper_multiline_json(self, client):
        """Test stripping markdown from multiline JSON."""
        wrapped = '```json\n{\n  "key": "value",\n  "nested": {"inner": "data"}\n}\n```'
        result = client._strip_markdown_wrapper(wrapped)
        assert result == '{\n  "key": "value",\n  "nested": {"inner": "data"}\n}'

    def test_strip_markdown_wrapper_no_wrapper(self, client):
        """Test handling JSON with no markdown wrapper."""
        plain = '{"key": "value"}'
        result = client._strip_markdown_wrapper(plain)
        assert result == '{"key": "value"}'

    def test_strip_markdown_wrapper_whitespace_handling(self, client):
        """Test proper whitespace handling around markdown."""
        wrapped = '  ```json\n  {"key": "value"}\n  ```  '
        result = client._strip_markdown_wrapper(wrapped)
        assert result == '{"key": "value"}'

    def test_strip_markdown_wrapper_multiple_closing_backticks(self, client):
        """Test handling of malformed markdown with extra backticks."""
        wrapped = '```json\n{"key": "value"}\n```\nextra```'
        result = client._strip_markdown_wrapper(wrapped)
        # Should strip the proper closing fence
        assert '{"key": "value"}' in result

    def test_strip_markdown_wrapper_empty_string(self, client):
        """Test handling of empty string."""
        result = client._strip_markdown_wrapper('')
        assert result == ''


class TestGenerateJson:
    """Test generate_json() method (CP2)."""

    @pytest.fixture
    def client(self):
        """Create test client instance."""
        return AnthropicClient(api_key="test-key")

    @pytest.fixture
    def mock_json_response(self):
        """Mock Anthropic API response with JSON content."""
        return {
            "id": "msg_test123",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": '```json\n{"result": "success"}\n```'}],
            "model": "claude-3-haiku-20240307",
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {
                "input_tokens": 50,
                "output_tokens": 25
            }
        }

    @patch('anthropic.Anthropic')
    def test_generate_json_basic(self, mock_anthropic_class, client, mock_json_response):
        """Test basic JSON generation with automatic unwrapping."""
        mock_anthropic = Mock()
        mock_anthropic_class.return_value = mock_anthropic
        mock_anthropic.messages.create.return_value = Mock(**mock_json_response)

        client.anthropic = mock_anthropic

        messages = [LLMMessage(MessageRole.USER, "Generate JSON")]
        result = client.generate_json(messages, "claude-3-haiku-20240307")

        assert isinstance(result, dict)
        assert result == {"result": "success"}

    @patch('anthropic.Anthropic')
    def test_generate_json_unwraps_markdown(self, mock_anthropic_class, client):
        """Test that markdown wrapper is automatically stripped."""
        mock_anthropic = Mock()
        mock_anthropic_class.return_value = mock_anthropic

        response_data = {
            "id": "msg_test123",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": '```json\n{"wrapped": true}\n```'}],
            "model": "claude-3-haiku-20240307",
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 50, "output_tokens": 25}
        }
        mock_anthropic.messages.create.return_value = Mock(**response_data)

        client.anthropic = mock_anthropic

        messages = [LLMMessage(MessageRole.USER, "Test")]
        result = client.generate_json(messages, "claude-3-haiku-20240307")

        assert result == {"wrapped": True}

    @patch('anthropic.Anthropic')
    def test_generate_json_with_system_prompt(self, mock_anthropic_class, client, mock_json_response):
        """Test JSON generation with system prompt."""
        mock_anthropic = Mock()
        mock_anthropic_class.return_value = mock_anthropic
        mock_anthropic.messages.create.return_value = Mock(**mock_json_response)

        client.anthropic = mock_anthropic

        messages = [LLMMessage(MessageRole.USER, "Generate")]
        result = client.generate_json(
            messages,
            "claude-3-haiku-20240307",
            system_prompt="You must return valid JSON"
        )

        # Verify system prompt was passed
        call_args = mock_anthropic.messages.create.call_args[1]
        assert call_args["system"] == "You must return valid JSON"
        assert isinstance(result, dict)

    @patch('anthropic.Anthropic')
    def test_generate_json_with_schema_validation(self, mock_anthropic_class, client, mock_json_response):
        """Test JSON generation with schema validation."""
        mock_anthropic = Mock()
        mock_anthropic_class.return_value = mock_anthropic
        mock_anthropic.messages.create.return_value = Mock(**mock_json_response)

        client.anthropic = mock_anthropic

        schema = {
            "type": "object",
            "properties": {
                "result": {"type": "string"}
            },
            "required": ["result"]
        }

        messages = [LLMMessage(MessageRole.USER, "Generate")]
        result = client.generate_json(
            messages,
            "claude-3-haiku-20240307",
            schema=schema
        )

        assert result == {"result": "success"}

    @patch('anthropic.Anthropic')
    def test_generate_json_schema_validation_failure(self, mock_anthropic_class, client, mock_json_response):
        """Test schema validation failure handling."""
        mock_anthropic = Mock()
        mock_anthropic_class.return_value = mock_anthropic

        # Return JSON that doesn't match schema
        bad_response = {
            "id": "msg_test123",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": '```json\n{"wrong_key": "value"}\n```'}],
            "model": "claude-3-haiku-20240307",
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 50, "output_tokens": 25}
        }
        mock_anthropic.messages.create.return_value = Mock(**bad_response)

        client.anthropic = mock_anthropic

        schema = {
            "type": "object",
            "properties": {
                "result": {"type": "string"}
            },
            "required": ["result"]
        }

        messages = [LLMMessage(MessageRole.USER, "Generate")]

        with pytest.raises(ValidationError, match="Schema validation failed"):
            client.generate_json(
                messages,
                "claude-3-haiku-20240307",
                schema=schema
            )

    @patch('anthropic.Anthropic')
    def test_generate_json_invalid_json_response(self, mock_anthropic_class, client):
        """Test handling of invalid JSON in response."""
        mock_anthropic = Mock()
        mock_anthropic_class.return_value = mock_anthropic

        bad_response = {
            "id": "msg_test123",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": 'not valid json'}],
            "model": "claude-3-haiku-20240307",
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 50, "output_tokens": 25}
        }
        mock_anthropic.messages.create.return_value = Mock(**bad_response)

        client.anthropic = mock_anthropic

        messages = [LLMMessage(MessageRole.USER, "Generate")]

        with pytest.raises(ValueError, match="Invalid JSON"):
            client.generate_json(messages, "claude-3-haiku-20240307")

    @patch('anthropic.Anthropic')
    def test_generate_json_with_temperature(self, mock_anthropic_class, client, mock_json_response):
        """Test JSON generation with temperature parameter."""
        mock_anthropic = Mock()
        mock_anthropic_class.return_value = mock_anthropic
        mock_anthropic.messages.create.return_value = Mock(**mock_json_response)

        client.anthropic = mock_anthropic

        messages = [LLMMessage(MessageRole.USER, "Generate")]
        result = client.generate_json(
            messages,
            "claude-3-haiku-20240307",
            temperature=0.5
        )

        call_args = mock_anthropic.messages.create.call_args[1]
        assert call_args["temperature"] == 0.5
        assert isinstance(result, dict)

    @patch('anthropic.Anthropic')
    def test_generate_json_logging_wrapper_detection(self, mock_anthropic_class, client):
        """Test that wrapper detection is logged."""
        mock_anthropic = Mock()
        mock_anthropic_class.return_value = mock_anthropic

        wrapped_response = {
            "id": "msg_test123",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": '```json\n{"wrapped": true}\n```'}],
            "model": "claude-3-haiku-20240307",
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 50, "output_tokens": 25}
        }
        mock_anthropic.messages.create.return_value = Mock(**wrapped_response)

        client.anthropic = mock_anthropic

        messages = [LLMMessage(MessageRole.USER, "Test")]

        with patch('youtube_processor.llm.anthropic_client.logging') as mock_logging:
            result = client.generate_json(messages, "claude-3-haiku-20240307")

            # Verify result is correct
            assert result == {"wrapped": True}

    @patch('anthropic.Anthropic')
    def test_generate_json_complex_nested_structure(self, mock_anthropic_class, client):
        """Test JSON generation with complex nested structure."""
        mock_anthropic = Mock()
        mock_anthropic_class.return_value = mock_anthropic

        complex_json = {
            "id": "msg_test123",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": '```json\n{"units": [{"id": "u1", "type": "technique", "name": "Test", "confidence": 0.95}], "video_id": "vid123"}\n```'}],
            "model": "claude-3-haiku-20240307",
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 100, "output_tokens": 50}
        }
        mock_anthropic.messages.create.return_value = Mock(**complex_json)

        client.anthropic = mock_anthropic

        messages = [LLMMessage(MessageRole.USER, "Generate")]
        result = client.generate_json(messages, "claude-3-haiku-20240307")

        assert result["video_id"] == "vid123"
        assert len(result["units"]) == 1
        assert result["units"][0]["id"] == "u1"
        assert result["units"][0]["confidence"] == 0.95


if __name__ == "__main__":
    pytest.main([__file__, "-v"])