"""
Anthropic Claude API client implementation.

This module provides a comprehensive client for interacting with Anthropic's
Claude API, including usage tracking, retry logic, and error handling.
"""

import os
import time
import asyncio
import json
import logging
from typing import List, Optional, Dict, Any, Union
from datetime import datetime

import anthropic
from anthropic import Anthropic, AsyncAnthropic

logger = logging.getLogger(__name__)

from .models import (
    LLMRequest, LLMResponse, LLMMessage, LLMUsageMetrics,
    MessageRole, LLMProvider, RateLimitError, LLMAPIError,
    TokenLimitError, AuthenticationError, ValidationError
)
from .utils import (
    calculate_anthropic_cost, exponential_backoff_delay,
    should_retry_error, validate_anthropic_request
)


class AnthropicClient:
    """
    Client for interacting with Anthropic's Claude API.

    Provides synchronous and asynchronous message generation with comprehensive
    error handling, retry logic, and usage tracking.
    """

    # Supported Claude models
    SUPPORTED_MODELS = {
        # Claude 3 models
        "claude-3-opus-20240229": 4096,
        "claude-3-sonnet-20240229": 4096,
        "claude-3-haiku-20240307": 4096,
        # Claude 4 models
        "claude-opus-4-1-20250805": 4096,
        "claude-sonnet-4-5-20250929": 8192,
        "claude-haiku-4-5-20251001": 64000,  # Haiku 4.5 supports 64K output
        "claude-sonnet-4-20250514": 8192,
        "claude-opus-4-20250514": 4096
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 600.0,  # 10 minutes for 64K token generation (worst case ~10-20 min)
        max_retries: int = 1  # Reduced to 1 retry to prevent credit waste
    ):
        """
        Initialize the Anthropic client.

        Args:
            api_key: Anthropic API key (uses ANTHROPIC_API_KEY env var if not provided)
            base_url: Custom API base URL (optional)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests

        Raises:
            ValueError: If no API key is provided and ANTHROPIC_API_KEY env var is not set
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("API key must be provided either as parameter or ANTHROPIC_API_KEY environment variable")

        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries

        # Initialize usage tracking
        self.usage_metrics = LLMUsageMetrics()

        # Initialize Anthropic clients
        # CRITICAL: Set max_retries=0 to disable SDK's internal retry logic
        # We handle retries ourselves in the generate() method
        client_kwargs = {
            "api_key": self.api_key,
            "timeout": self.timeout,
            "max_retries": 0  # Disable SDK retries - we handle retries ourselves
        }
        if self.base_url:
            client_kwargs["base_url"] = self.base_url

        self.anthropic = Anthropic(**client_kwargs)
        self.async_anthropic = AsyncAnthropic(**client_kwargs)

    def _create_message(self, role: MessageRole, content: str) -> LLMMessage:
        """Create an LLM message."""
        return LLMMessage(role=role, content=content)

    def _build_request(
        self,
        messages: List[LLMMessage],
        model: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        stop_sequences: Optional[List[str]] = None,
        system_prompt: Optional[str] = None
    ) -> LLMRequest:
        """Build an LLM request object."""
        return LLMRequest(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stop_sequences=stop_sequences,
            system_prompt=system_prompt,
            provider=LLMProvider.ANTHROPIC
        )

    def _update_usage(self, input_tokens: int, output_tokens: int, cost: float):
        """Update cumulative usage metrics."""
        self.usage_metrics.add_usage(input_tokens, output_tokens, cost)

    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay for retry attempts."""
        return exponential_backoff_delay(attempt, base_delay=1.0, max_delay=60.0)

    def _validate_request(
        self,
        messages: List[LLMMessage],
        model: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None
    ) -> None:
        """
        Validate request parameters.

        Raises:
            ValidationError: If validation fails
        """
        # Validate messages
        if not messages:
            raise ValidationError("Messages cannot be empty")

        # Validate model
        if model not in self.SUPPORTED_MODELS:
            raise ValidationError(f"Unsupported model: {model}")

        # Validate max_tokens
        if max_tokens is not None:
            if max_tokens <= 0:
                raise ValidationError("max_tokens must be positive")
            if max_tokens > self.SUPPORTED_MODELS[model]:
                raise ValidationError(f"max_tokens {max_tokens} exceeds limit for {model}")

        # Validate temperature
        if temperature is not None and (temperature < 0 or temperature > 1):
            raise ValidationError("Temperature must be between 0 and 1")

        # Validate top_p
        if top_p is not None and (top_p <= 0 or top_p > 1):
            raise ValidationError("top_p must be between 0 and 1")

    def _parse_response(self, response: Any, model: str) -> LLMResponse:
        """Parse Anthropic API response into LLMResponse object."""
        # Extract content - handle both real API response and mock objects
        content = ""
        if hasattr(response, 'content') and response.content:
            if isinstance(response.content, list) and len(response.content) > 0:
                first_content = response.content[0]
                if hasattr(first_content, 'text'):
                    content = first_content.text
                elif hasattr(first_content, 'type') and first_content.type == 'text':
                    content = getattr(first_content, 'text', "")
                elif isinstance(first_content, dict) and first_content.get('type') == 'text':
                    content = first_content.get('text', "")

        # Extract usage metrics - handle both real API response and mock objects
        usage = getattr(response, 'usage', None)
        if usage:
            if hasattr(usage, 'input_tokens'):
                input_tokens = usage.input_tokens
                output_tokens = usage.output_tokens
            elif isinstance(usage, dict):
                input_tokens = usage.get('input_tokens', 0)
                output_tokens = usage.get('output_tokens', 0)
            else:
                input_tokens = 0
                output_tokens = 0
        else:
            input_tokens = 0
            output_tokens = 0

        # Calculate cost
        cost = calculate_anthropic_cost(model, input_tokens, output_tokens)

        # Create usage metrics
        usage_metrics = LLMUsageMetrics()
        usage_metrics.add_usage(input_tokens, output_tokens, cost)

        # Update client usage
        self._update_usage(input_tokens, output_tokens, cost)

        return LLMResponse(
            content=content,
            model=model,
            provider=LLMProvider.ANTHROPIC,
            usage_metrics=usage_metrics,
            finish_reason=getattr(response, 'stop_reason', None),
            response_id=getattr(response, 'id', None),
            raw_response=response.__dict__ if hasattr(response, '__dict__') else None
        )

    def _handle_api_error(self, error: Exception) -> None:
        """Convert Anthropic API errors to our custom exceptions."""
        if isinstance(error, anthropic.RateLimitError):
            retry_after = getattr(error.response, 'headers', {}).get('retry-after')
            raise RateLimitError(str(error), retry_after=retry_after)
        elif isinstance(error, anthropic.AuthenticationError):
            raise AuthenticationError(str(error))
        elif isinstance(error, anthropic.BadRequestError):
            if "token" in str(error).lower():
                raise TokenLimitError(str(error))
            else:
                raise ValidationError(str(error))
        else:
            raise LLMAPIError(str(error))

    def generate(
        self,
        messages: List[LLMMessage],
        model: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        stop_sequences: Optional[List[str]] = None,
        system_prompt: Optional[str] = None,
        max_retries: Optional[int] = None
    ) -> LLMResponse:
        """
        Generate a response using the Anthropic API.

        Args:
            messages: List of conversation messages
            model: Claude model to use
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            top_p: Nucleus sampling parameter (0-1)
            stop_sequences: Sequences that stop generation
            system_prompt: System prompt for the conversation
            max_retries: Override default max retries

        Returns:
            LLMResponse object with generated content and metadata

        Raises:
            ValidationError: If request parameters are invalid
            RateLimitError: If rate limits are exceeded
            AuthenticationError: If API key is invalid
            TokenLimitError: If token limits are exceeded
            LLMAPIError: For other API errors
        """
        # Validate request
        self._validate_request(messages, model, max_tokens, temperature, top_p)

        # Build request object
        request = self._build_request(
            messages, model, max_tokens, temperature, top_p, stop_sequences, system_prompt
        )

        # Convert to API format
        api_request = request.to_api_format()

        # Validate API request format
        validate_anthropic_request(api_request)

        # Retry logic
        max_retries = max_retries if max_retries is not None else self.max_retries
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                response = self.anthropic.messages.create(**api_request)
                return self._parse_response(response, model)

            except Exception as error:
                last_error = error

                # Check for non-retryable errors first
                if isinstance(error, anthropic.RateLimitError):
                    retry_after = getattr(error.response, 'headers', {}).get('retry-after') if hasattr(error, 'response') else None
                    raise RateLimitError(str(error), retry_after=retry_after)
                elif isinstance(error, anthropic.AuthenticationError):
                    raise AuthenticationError(str(error))
                elif isinstance(error, anthropic.BadRequestError):
                    if "token" in str(error).lower():
                        raise TokenLimitError(str(error))
                    else:
                        raise ValidationError(str(error))

                # Check if we should retry
                if attempt < max_retries and should_retry_error(error, attempt, max_retries):
                    delay = self._calculate_retry_delay(attempt)
                    time.sleep(delay)
                    continue
                else:
                    # Final attempt failed
                    break

        # All retries exhausted
        if last_error:
            self._handle_api_error(last_error)
        else:
            raise LLMAPIError("Unknown error occurred")

    async def generate_async(
        self,
        messages: List[LLMMessage],
        model: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        stop_sequences: Optional[List[str]] = None,
        system_prompt: Optional[str] = None,
        max_retries: Optional[int] = None
    ) -> LLMResponse:
        """
        Async version of generate method.

        Same parameters and behavior as generate(), but runs asynchronously.
        """
        # Validate request
        self._validate_request(messages, model, max_tokens, temperature, top_p)

        # Build request object
        request = self._build_request(
            messages, model, max_tokens, temperature, top_p, stop_sequences, system_prompt
        )

        # Convert to API format
        api_request = request.to_api_format()

        # Validate API request format
        validate_anthropic_request(api_request)

        # Retry logic
        max_retries = max_retries if max_retries is not None else self.max_retries
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                response = await self.async_anthropic.messages.create(**api_request)
                return self._parse_response(response, model)

            except Exception as error:
                last_error = error

                # Check for non-retryable errors first
                if isinstance(error, anthropic.RateLimitError):
                    retry_after = getattr(error.response, 'headers', {}).get('retry-after') if hasattr(error, 'response') else None
                    raise RateLimitError(str(error), retry_after=retry_after)
                elif isinstance(error, anthropic.AuthenticationError):
                    raise AuthenticationError(str(error))
                elif isinstance(error, anthropic.BadRequestError):
                    if "token" in str(error).lower():
                        raise TokenLimitError(str(error))
                    else:
                        raise ValidationError(str(error))

                # Check if we should retry
                if attempt < max_retries and should_retry_error(error, attempt, max_retries):
                    delay = self._calculate_retry_delay(attempt)
                    await asyncio.sleep(delay)
                    continue
                else:
                    # Final attempt failed
                    break

        # All retries exhausted
        if last_error:
            self._handle_api_error(last_error)
        else:
            raise LLMAPIError("Unknown error occurred")

    async def generate_batch_async(
        self,
        message_lists: List[List[LLMMessage]],
        model: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        stop_sequences: Optional[List[str]] = None,
        system_prompt: Optional[str] = None,
        max_retries: Optional[int] = None
    ) -> List[LLMResponse]:
        """
        Generate responses for multiple message lists concurrently.

        Args:
            message_lists: List of message lists to process
            Other parameters: Same as generate_async()

        Returns:
            List of LLMResponse objects in the same order as input
        """
        tasks = [
            self.generate_async(
                messages, model, max_tokens, temperature, top_p,
                stop_sequences, system_prompt, max_retries
            )
            for messages in message_lists
        ]

        return await asyncio.gather(*tasks)

    def chat(
        self,
        message: str,
        model: str = "claude-3-haiku-20240307",
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Simple chat interface for single message interactions.

        Args:
            message: User message
            model: Claude model to use
            system_prompt: Optional system prompt
            **kwargs: Additional parameters for generate()

        Returns:
            Generated response content as string
        """
        messages = [self._create_message(MessageRole.USER, message)]
        response = self.generate(messages, model, system_prompt=system_prompt, **kwargs)
        return response.content

    def estimate_cost(
        self,
        messages: List[LLMMessage],
        model: str,
        max_tokens: Optional[int] = None
    ) -> float:
        """
        Estimate the cost of a request without making the API call.

        Args:
            messages: List of messages to estimate
            model: Model to use for estimation
            max_tokens: Maximum tokens to generate

        Returns:
            Estimated cost in USD
        """
        # Rough estimation based on message length
        # This is a simplified estimation - actual tokens may vary
        input_chars = sum(len(msg.content) for msg in messages)
        estimated_input_tokens = input_chars // 4  # Rough chars-to-tokens ratio

        estimated_output_tokens = max_tokens or 100  # Default estimate

        return calculate_anthropic_cost(model, estimated_input_tokens, estimated_output_tokens)

    def get_usage_summary(self) -> str:
        """Get a formatted summary of API usage."""
        from .utils import format_usage_summary
        return format_usage_summary(self.usage_metrics)

    def reset_usage_metrics(self) -> None:
        """Reset cumulative usage metrics."""
        self.usage_metrics = LLMUsageMetrics()

    def get_supported_models(self) -> List[str]:
        """Get list of supported Claude models."""
        return list(self.SUPPORTED_MODELS.keys())

    def _strip_markdown_wrapper(self, content: str) -> str:
        """
        Strip markdown code fence wrapper from JSON content.

        Handles formats like:
        - ```json\n{json}\n```
        - ```\n{json}\n```
        - Plain JSON without wrapper

        Args:
            content: Content that may be wrapped in markdown

        Returns:
            Unwrapped JSON string
        """
        if not content:
            return content

        content = content.strip()

        # Check if content starts with markdown fence
        if content.startswith('```'):
            # Find the end of opening fence (first newline)
            first_newline = content.find('\n')
            if first_newline != -1:
                content = content[first_newline + 1:]

            # Remove closing fence
            if content.endswith('```'):
                content = content[:-3].rstrip()
            # Handle case where closing fence has trailing content
            elif '```' in content:
                content = content[:content.rfind('```')].rstrip()
            
            # Strip any remaining whitespace from the content
            content = content.strip()

        return content

    def generate_json(
        self,
        messages: List[LLMMessage],
        model: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        stop_sequences: Optional[List[str]] = None,
        system_prompt: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        max_retries: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate JSON response with automatic markdown wrapper stripping.

        Automatically handles markdown code blocks (```json...```) that Claude
        may wrap around JSON responses. Optionally validates the JSON against
        a provided schema. Logs statistics about wrapper frequency.

        Args:
            messages: List of conversation messages
            model: Claude model to use
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            top_p: Nucleus sampling parameter (0-1)
            stop_sequences: Sequences that stop generation
            system_prompt: System prompt for the conversation
            schema: Optional JSON schema for validation (jsonschema format)
            max_retries: Override default max retries

        Returns:
            Parsed JSON response as dictionary

        Raises:
            ValueError: If response content is not valid JSON
            ValidationError: If schema validation fails or request is invalid
            RateLimitError: If rate limits are exceeded
            AuthenticationError: If API key is invalid
            TokenLimitError: If token limits are exceeded
            LLMAPIError: For other API errors
        """
        # Generate response using base method
        response = self.generate(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stop_sequences=stop_sequences,
            system_prompt=system_prompt,
            max_retries=max_retries
        )

        # Strip markdown wrapper if present
        content = self._strip_markdown_wrapper(response.content)

        # Log if wrapper was detected
        if content != response.content.strip():
            logger.info(
                "Markdown wrapper detected and stripped in JSON response. "
                f"Original length: {len(response.content)}, Unwrapped length: {len(content)}"
            )

        # Parse JSON
        try:
            json_data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in response: {e}")

        # Validate against schema if provided
        if schema:
            try:
                from jsonschema import validate
                validate(instance=json_data, schema=schema)
            except ImportError:
                logger.warning("jsonschema not installed, skipping schema validation")
            except Exception as e:
                raise ValidationError(f"Schema validation failed: {e}")

        return json_data