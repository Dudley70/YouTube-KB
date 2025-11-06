"""
LLM API integration module.

This module provides clients and utilities for interacting with various
Large Language Model APIs, including Anthropic's Claude.
"""

from .models import (
    LLMProvider, MessageRole, LLMMessage, LLMUsageMetrics,
    LLMRequest, LLMResponse, LLMError,
    RateLimitError, LLMAPIError, TokenLimitError,
    AuthenticationError, ValidationError,
    # CP-9 models
    TokenUsage, KnowledgeUnit, AnalysisResult,
    # CP-10 models
    SynthesizedUnit
)
from .anthropic_client import AnthropicClient
from .template_processor import TemplateProcessor, TemplateError
from .transcript_analyzer import TranscriptAnalyzer
from .knowledge_synthesizer import KnowledgeSynthesizer
from .utils import (
    calculate_anthropic_cost, exponential_backoff_delay,
    should_retry_error, validate_anthropic_request,
    format_usage_summary
)

__all__ = [
    # Models
    "LLMProvider", "MessageRole", "LLMMessage", "LLMUsageMetrics",
    "LLMRequest", "LLMResponse", "LLMError",

    # Exceptions
    "RateLimitError", "LLMAPIError", "TokenLimitError",
    "AuthenticationError", "ValidationError",

    # Clients
    "AnthropicClient",

    # Utilities
    "calculate_anthropic_cost", "exponential_backoff_delay",
    "should_retry_error", "validate_anthropic_request",
    "format_usage_summary",

    # CP-9 exports
    "TemplateProcessor", "TemplateError",
    "TranscriptAnalyzer",
    "TokenUsage", "KnowledgeUnit", "AnalysisResult",

    # CP-10 exports
    "KnowledgeSynthesizer", "SynthesizedUnit"
]