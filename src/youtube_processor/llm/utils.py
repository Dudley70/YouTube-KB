"""
Utility functions for LLM API interactions.

This module provides helper functions for token counting, cost calculation,
retry logic, and other common operations needed for LLM API clients.
"""

import time
import math
from typing import Dict, Any, Optional
from .models import LLMProvider, LLMUsageMetrics


# Anthropic Claude pricing (updated November 2024)
ANTHROPIC_PRICING = {
    # Claude 3 models (legacy)
    "claude-3-opus-20240229": {
        "input": 0.000015,   # $15 per 1M input tokens
        "output": 0.000075   # $75 per 1M output tokens
    },
    "claude-3-sonnet-20240229": {
        "input": 0.000003,   # $3 per 1M input tokens
        "output": 0.000015   # $15 per 1M output tokens
    },
    "claude-3-haiku-20240307": {
        "input": 0.00000025, # $0.25 per 1M input tokens
        "output": 0.00000125 # $1.25 per 1M output tokens
    },
    # Claude 4 models (current)
    "claude-opus-4-1-20250805": {
        "input": 0.000015,   # $15 per 1M input tokens
        "output": 0.000075   # $75 per 1M output tokens
    },
    "claude-sonnet-4-5-20250929": {
        "input": 0.000003,   # $3 per 1M input tokens
        "output": 0.000015   # $15 per 1M output tokens
    },
    "claude-haiku-4-5-20251001": {
        "input": 0.00000025, # $0.25 per 1M input tokens
        "output": 0.00000125 # $1.25 per 1M output tokens
    },
    "claude-sonnet-4-20250514": {
        "input": 0.000003,   # $3 per 1M input tokens
        "output": 0.000015   # $15 per 1M output tokens
    },
    "claude-opus-4-20250514": {
        "input": 0.000015,   # $15 per 1M input tokens
        "output": 0.000075   # $75 per 1M output tokens
    }
}


def calculate_anthropic_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """
    Calculate the cost of an Anthropic API call based on token usage.

    Args:
        model: The model name (e.g., "claude-3-opus-20240229")
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Cost in USD

    Raises:
        ValueError: If model is not recognized
    """
    if model not in ANTHROPIC_PRICING:
        # Default to most expensive pricing if model not found
        pricing = ANTHROPIC_PRICING["claude-3-opus-20240229"]
    else:
        pricing = ANTHROPIC_PRICING[model]

    input_cost = input_tokens * pricing["input"]
    output_cost = output_tokens * pricing["output"]

    return input_cost + output_cost


def exponential_backoff_delay(attempt: int, base_delay: float = 1.0, max_delay: float = 60.0) -> float:
    """
    Calculate exponential backoff delay with jitter.

    Args:
        attempt: The retry attempt number (0-based)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds

    Returns:
        Delay in seconds
    """
    # Calculate exponential delay: 2^attempt seconds
    delay = min(base_delay * (2 ** attempt), max_delay)

    # Add jitter to avoid thundering herd
    jitter = delay * 0.1 * time.time() % 1

    return delay + jitter


def should_retry_error(error: Exception, attempt: int, max_retries: int = 3) -> bool:
    """
    Determine if an error should trigger a retry.

    Args:
        error: The exception that occurred
        attempt: Current retry attempt number
        max_retries: Maximum number of retries allowed

    Returns:
        True if should retry, False otherwise
    """
    if attempt >= max_retries:
        return False

    # Always retry on connection/timeout errors
    if isinstance(error, (ConnectionError, TimeoutError)):
        return True

    # Retry on 5xx server errors and rate limiting
    if hasattr(error, 'status_code'):
        return error.status_code >= 500 or error.status_code == 429

    # Check for common retryable error messages
    error_msg = str(error).lower()
    retryable_keywords = [
        'timeout', 'connection', 'rate limit', 'server error',
        'service unavailable', 'internal error'
    ]

    return any(keyword in error_msg for keyword in retryable_keywords)


def validate_anthropic_request(request_data: Dict[str, Any]) -> None:
    """
    Validate an Anthropic API request.

    Args:
        request_data: The request dictionary

    Raises:
        ValueError: If request is invalid
    """
    required_fields = ["model", "messages"]
    for field in required_fields:
        if field not in request_data:
            raise ValueError(f"Missing required field: {field}")

    # Validate messages format
    messages = request_data["messages"]
    if not isinstance(messages, list) or not messages:
        raise ValueError("Messages must be a non-empty list")

    for i, message in enumerate(messages):
        if not isinstance(message, dict):
            raise ValueError(f"Message {i} must be a dictionary")

        if "role" not in message or "content" not in message:
            raise ValueError(f"Message {i} must have 'role' and 'content' fields")

        if message["role"] not in ["user", "assistant", "system"]:
            raise ValueError(f"Message {i} has invalid role: {message['role']}")

    # Validate token limits
    if "max_tokens" in request_data:
        max_tokens = request_data["max_tokens"]
        if not isinstance(max_tokens, int) or max_tokens <= 0:
            raise ValueError("max_tokens must be a positive integer")

        # Claude models have different token limits
        model_limits = {
            "claude-3-opus-20240229": 4096,
            "claude-3-sonnet-20240229": 4096,
            "claude-3-haiku-20240307": 4096
        }

        model = request_data["model"]
        if model in model_limits and max_tokens > model_limits[model]:
            raise ValueError(f"max_tokens {max_tokens} exceeds limit for {model}")


def format_usage_summary(usage: LLMUsageMetrics) -> str:
    """
    Format usage metrics for display.

    Args:
        usage: Usage metrics to format

    Returns:
        Formatted string
    """
    return (
        f"API Usage Summary:\n"
        f"  Requests: {usage.request_count}\n"
        f"  Total Tokens: {usage.total_tokens:,}\n"
        f"  Input Tokens: {usage.input_tokens:,}\n"
        f"  Output Tokens: {usage.output_tokens:,}\n"
        f"  Total Cost: ${usage.cost_usd:.4f}"
    )