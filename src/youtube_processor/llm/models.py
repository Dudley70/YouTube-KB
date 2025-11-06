"""
Data models for LLM API interactions.

This module provides data structures for handling LLM requests, responses,
and tracking usage metrics across different API providers.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
from pathlib import Path


class LLMProvider(Enum):
    """Supported LLM API providers."""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"  # Future support
    LOCAL = "local"    # Future support


class MessageRole(Enum):
    """Message roles in conversation."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class LLMMessage:
    """Represents a message in an LLM conversation."""
    role: MessageRole
    content: str
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for API calls."""
        return {
            "role": self.role.value,
            "content": self.content
        }


@dataclass
class LLMUsageMetrics:
    """Tracks token usage and costs for LLM API calls."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    request_count: int = 0

    def add_usage(self, input_tokens: int, output_tokens: int, cost: float = 0.0):
        """Add usage from a single API call."""
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_tokens += (input_tokens + output_tokens)
        self.cost_usd += cost
        self.request_count += 1

    def __str__(self) -> str:
        return (f"Requests: {self.request_count}, "
                f"Tokens: {self.total_tokens} ({self.input_tokens}in/{self.output_tokens}out), "
                f"Cost: ${self.cost_usd:.4f}")


@dataclass
class LLMRequest:
    """Represents a request to an LLM API."""
    messages: List[LLMMessage]
    model: str
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    stop_sequences: Optional[List[str]] = None
    system_prompt: Optional[str] = None
    provider: LLMProvider = LLMProvider.ANTHROPIC
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: MessageRole, content: str):
        """Add a message to the conversation."""
        self.messages.append(LLMMessage(role=role, content=content))

    def to_api_format(self) -> Dict[str, Any]:
        """Convert to format expected by the API provider."""
        base_request = {
            "model": self.model,
            "messages": [msg.to_dict() for msg in self.messages]
        }

        # Add optional parameters
        if self.max_tokens is not None:
            base_request["max_tokens"] = self.max_tokens
        if self.temperature is not None:
            base_request["temperature"] = self.temperature
        if self.top_p is not None:
            base_request["top_p"] = self.top_p
        if self.stop_sequences:
            base_request["stop"] = self.stop_sequences
        if self.system_prompt:
            base_request["system"] = self.system_prompt

        return base_request


@dataclass
class LLMResponse:
    """Represents a response from an LLM API."""
    content: str
    model: str
    provider: LLMProvider
    usage_metrics: LLMUsageMetrics
    finish_reason: Optional[str] = None
    response_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    raw_response: Optional[Dict[str, Any]] = None

    def __str__(self) -> str:
        return f"LLMResponse(model={self.model}, tokens={self.usage_metrics.total_tokens}, content_length={len(self.content)})"


@dataclass
class LLMError:
    """Represents an error from LLM API interaction."""
    error_type: str
    message: str
    provider: LLMProvider
    status_code: Optional[int] = None
    retry_after: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)
    raw_error: Optional[Dict[str, Any]] = None

    def __str__(self) -> str:
        return f"LLMError({self.error_type}): {self.message}"


class RateLimitError(Exception):
    """Raised when API rate limits are exceeded."""
    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


class LLMAPIError(Exception):
    """Base exception for LLM API errors."""
    def __init__(self, message: str, error_type: str = "api_error", status_code: Optional[int] = None):
        super().__init__(message)
        self.error_type = error_type
        self.status_code = status_code


class TokenLimitError(LLMAPIError):
    """Raised when token limits are exceeded."""
    pass


class AuthenticationError(LLMAPIError):
    """Raised when API authentication fails."""
    pass


class ValidationError(LLMAPIError):
    """Raised when request validation fails."""
    pass


# CP-9: Simplified models for transcript analysis and knowledge extraction
import re
from typing import Optional


@dataclass
class TokenUsage:
    """Simplified token usage for CP-9 compatibility"""
    input_tokens: int
    output_tokens: int

    @property
    def total(self) -> int:
        """Total tokens used"""
        return self.input_tokens + self.output_tokens


@dataclass
class KnowledgeUnit:
    """
    Represents a single knowledge unit extracted from a video.

    Knowledge units are atomic pieces of reusable knowledge:
    - Techniques, patterns, use cases
    - Capabilities, integrations, anti-patterns
    - Components, troubleshooting, configs, snippets
    """
    type: str  # technique, pattern, use-case, capability, etc.
    id: str    # Unique ID: lowercase-hyphen format
    name: str  # Human-readable name
    content: str  # Full markdown content
    source_video_id: Optional[str] = None  # Video this came from

    def is_valid_id(self) -> bool:
        """
        Validate ID format: lowercase-hyphen only.

        Valid: technique-memory-sweep, pattern-self-modifying-agent
        Invalid: Technique_Test, pattern, PATTERN-TEST
        """
        # Must be lowercase with hyphens only
        pattern = r'^[a-z0-9]+(-[a-z0-9]+)+$'
        return bool(re.match(pattern, self.id))

    def extract_cross_references(self) -> list[str]:
        """
        Extract related knowledge unit IDs from content.

        Looks for patterns like:
        - **Related Techniques**: technique-memory-sweep, technique-other
        - See also: pattern-self-modifying-agent

        Returns:
            List of referenced knowledge unit IDs
        """
        # Pattern to match knowledge unit IDs: type-kebab-case
        id_pattern = r'\b(technique|pattern|use-case|capability|integration|antipattern|component|issue|config|snippet)-[a-z0-9-]+\b'

        matches = re.findall(id_pattern, self.content, re.IGNORECASE)

        # Re-construct full IDs from tuple matches
        full_ids = []
        for match in re.finditer(id_pattern, self.content, re.IGNORECASE):
            full_ids.append(match.group(0))

        # Deduplicate and exclude self
        refs = list(set(full_ids))
        if self.id in refs:
            refs.remove(self.id)

        return sorted(refs)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            "type": self.type,
            "id": self.id,
            "name": self.name,
            "content": self.content,
            "source_video_id": self.source_video_id
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'KnowledgeUnit':
        """Create from dictionary"""
        return cls(
            type=data["type"],
            id=data["id"],
            name=data["name"],
            content=data["content"],
            source_video_id=data.get("source_video_id")
        )


@dataclass
class AnalysisResult:
    """Result from analyzing a video transcript"""
    video_id: str
    video_title: str
    raw_output: str  # Raw Claude response with template formatting
    knowledge_units: list[KnowledgeUnit]  # Parsed units
    usage: TokenUsage
    cost: float

    def get_units_by_type(self, unit_type: str) -> list[KnowledgeUnit]:
        """Get all knowledge units of a specific type"""
        return [u for u in self.knowledge_units if u.type == unit_type]

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            "video_id": self.video_id,
            "video_title": self.video_title,
            "raw_output": self.raw_output,
            "knowledge_units": [u.to_dict() for u in self.knowledge_units],
            "usage": {
                "input_tokens": self.usage.input_tokens,
                "output_tokens": self.usage.output_tokens,
                "total_tokens": self.usage.total
            },
            "cost": self.cost
        }


@dataclass
class SynthesizedUnit:
    """
    Knowledge unit synthesized from multiple videos.

    Combines multiple instances of the same knowledge unit ID,
    preserving all unique content and tracking all source videos.
    """
    type: str  # technique, pattern, use-case, etc.
    id: str    # Unique ID (same across all source videos)
    name: str  # Human-readable name
    content: str  # Merged content from all sources
    source_videos: list[str]  # All video IDs this unit appears in
    cross_references: list[str]  # Other knowledge unit IDs referenced

    @classmethod
    def from_knowledge_units(cls, units: list[KnowledgeUnit]) -> 'SynthesizedUnit':
        """
        Create synthesized unit from multiple knowledge units with same ID.

        Args:
            units: List of KnowledgeUnit objects with same ID

        Returns:
            SynthesizedUnit with merged content

        Raises:
            ValueError: If units list is empty or IDs don't match
        """
        if not units:
            raise ValueError("Cannot synthesize from empty units list")

        # Verify all units have same ID
        first_id = units[0].id
        if not all(u.id == first_id for u in units):
            raise ValueError("All units must have same ID for synthesis")

        # Merge content (deduplicate identical paragraphs)
        merged_content = cls._merge_content([u.content for u in units])

        # Collect all source videos
        source_videos = list(set(
            u.source_video_id for u in units if u.source_video_id
        ))

        # Extract cross-references from all units
        all_refs = []
        for unit in units:
            all_refs.extend(unit.extract_cross_references())
        cross_references = sorted(set(all_refs))

        return cls(
            type=units[0].type,
            id=first_id,
            name=units[0].name,
            content=merged_content,
            source_videos=sorted(source_videos),
            cross_references=cross_references
        )

    @staticmethod
    def _merge_content(contents: list[str]) -> str:
        """
        Merge multiple content strings, deduplicating identical paragraphs.

        Strategy:
        1. Split each content into paragraphs
        2. Track unique paragraphs (preserve order from first appearance)
        3. Reassemble into single content block

        Args:
            contents: List of content strings to merge

        Returns:
            Merged content with duplicates removed
        """
        seen_paragraphs = set()
        unique_paragraphs = []

        for content in contents:
            # Split by double newline (paragraph separator)
            paragraphs = content.split('\n\n')

            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue

                # Use normalized version for duplicate detection
                normalized = para.lower().strip()

                if normalized not in seen_paragraphs:
                    seen_paragraphs.add(normalized)
                    unique_paragraphs.append(para)

        return '\n\n'.join(unique_paragraphs)

    def to_markdown(self, output_dir) -> str:
        """
        Generate markdown document for this synthesized unit.

        Includes:
        - Header with metadata
        - Source videos section
        - Main content
        - Related knowledge units (cross-references with links)

        Args:
            output_dir: Base output directory (for calculating relative paths)

        Returns:
            Full markdown content
        """
        lines = [
            f"# {self.name}",
            "",
            f"**ID**: `{self.id}`  ",
            f"**Type**: {self.type}  ",
            f"**Sources**: {len(self.source_videos)} video(s)",
            ""
        ]

        # Source videos section
        if self.source_videos:
            lines.append("## Source Videos")
            lines.append("")
            for video_id in self.source_videos:
                lines.append(f"- `{video_id}`")
            lines.append("")

        # Main content
        lines.append("## Content")
        lines.append("")
        lines.append(self.content)
        lines.append("")

        # Cross-references section
        if self.cross_references:
            lines.append("## Related Knowledge")
            lines.append("")

            for ref_id in self.cross_references:
                # Calculate relative path: ../other-type/ref-id.md
                ref_type = ref_id.split('-')[0]  # Extract type from ID

                # Map type to directory name
                type_to_dir = {
                    "technique": "techniques",
                    "pattern": "patterns",
                    "use": "use-cases",  # Special case for use-case
                    "capability": "capabilities",
                    "integration": "integrations",
                    "antipattern": "antipatterns",
                    "component": "components",
                    "issue": "troubleshooting",
                    "config": "configurations",
                    "snippet": "snippets"
                }

                dir_name = type_to_dir.get(ref_type, f"{ref_type}s")
                rel_path = f"../{dir_name}/{ref_id}.md"
                lines.append(f"- [{ref_id}]({rel_path})")

            lines.append("")

        return '\n'.join(lines)

    def to_metadata_dict(self) -> dict:
        """
        Generate metadata dictionary for YAML export.

        Returns:
            Dict with metadata about this unit
        """
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "source_videos": self.source_videos,
            "cross_references": self.cross_references,
            "content_length": len(self.content),
            "paragraph_count": len(self.content.split('\n\n'))
        }