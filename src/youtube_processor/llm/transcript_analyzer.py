"""Transcript analysis using Claude API with Template V2.1"""
from typing import Optional, List, Dict, Any
import re
import json

from .anthropic_client import AnthropicClient
from .template_processor import TemplateProcessor
from .models import AnalysisResult, KnowledgeUnit, TokenUsage, LLMMessage, MessageRole
from .normalizer_runner import NormalizerRunner
from .llm_normalizer import LLMNormalizer


class TranscriptAnalyzer:
    """Analyzes video transcripts to extract structured knowledge"""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-haiku-4-5-20251001",
        template_version: str = "v2.1"
    ):
        """
        Initialize transcript analyzer.

        Args:
            api_key: Anthropic API key
            model: Claude model to use
            template_version: Extraction template version
        """
        self.client = AnthropicClient(api_key=api_key)
        self.model = model
        self.template_processor = TemplateProcessor()
        self.template_version = template_version

        # Load and validate template
        self.template = self.template_processor.load_template(template_version)
        self.template_processor.validate_template(self.template)

    def analyze_transcript(
        self,
        transcript: str,
        video_id: str,
        video_title: str,
        video_url: Optional[str] = None
    ) -> AnalysisResult:
        """
        Analyze transcript to extract structured knowledge.

        Args:
            transcript: Full video transcript text
            video_id: YouTube video ID
            video_title: Video title
            video_url: Optional YouTube URL

        Returns:
            AnalysisResult with parsed knowledge units
        """
        # Build user prompt with video metadata
        user_prompt = self._build_user_prompt(
            transcript, video_id, video_title, video_url
        )

        # Create message list for the AnthropicClient
        messages = [LLMMessage(role=MessageRole.USER, content=user_prompt)]

        # Call Claude with template as system prompt
        response = self.client.generate(
            messages=messages,
            model=self.model,
            system_prompt=self.template,
            max_tokens=64000,  # Haiku 4.5 supports up to 64K output tokens
            temperature=0  # Deterministic output for reproducible analysis
        )

        # Parse response into knowledge units
        knowledge_units = self._parse_knowledge_units(
            response.content,
            video_id
        )

        # Convert AnthropicClient usage to CP-9 format
        usage = TokenUsage(
            input_tokens=response.usage_metrics.input_tokens,
            output_tokens=response.usage_metrics.output_tokens
        )

        return AnalysisResult(
            video_id=video_id,
            video_title=video_title,
            raw_output=response.content,
            knowledge_units=knowledge_units,
            usage=usage,
            cost=response.usage_metrics.cost_usd
        )

    def _build_user_prompt(
        self,
        transcript: str,
        video_id: str,
        video_title: str,
        video_url: Optional[str]
    ) -> str:
        """Build user prompt with video metadata and transcript"""
        metadata_lines = [
            f"**Video ID**: {video_id}",
            f"**Title**: {video_title}"
        ]

        if video_url:
            metadata_lines.append(f"**URL**: {video_url}")

        metadata = "\n".join(metadata_lines)

        return f"""Analyze this video transcript and extract knowledge using the template provided in the system prompt.

{metadata}

---

## Transcript

{transcript}

---

Please extract all knowledge units according to the template structure."""

    def _parse_knowledge_units(
        self,
        raw_output: str,
        source_video_id: str
    ) -> list[KnowledgeUnit]:
        """
        Parse knowledge units from Claude response.

        Looks for template sections and extracts units with:
        - Type (from section header)
        - ID (from `id` field in content)
        - Name (from heading)
        - Content (full section content)

        Args:
            raw_output: Raw Claude response text
            source_video_id: Video ID to tag units with

        Returns:
            List of parsed KnowledgeUnit objects
        """
        units = []

        # Map section numbers to types
        type_mapping = {
            "1. Techniques Extracted": "technique",
            "2. Patterns Extracted": "pattern",
            "3. Use Cases Extracted": "use-case",
            "4. Capabilities Catalog": "capability",
            "5. Integration Methods": "integration",
            "6. Anti-Patterns Catalog": "antipattern",
            "7. Architecture Components": "component",
            "8. Troubleshooting Knowledge": "issue",
            "9. Configuration Recipes": "config",
            "10. Code Snippets Library": "snippet"
        }

        for section_header, unit_type in type_mapping.items():
            # Find section in output (case-insensitive to handle UPPERCASE headers)
            section_match = re.search(
                rf"##\s*{re.escape(section_header)}(.*?)(?=##\s*\d+\.|$)",
                raw_output,
                re.DOTALL | re.IGNORECASE
            )

            if not section_match:
                continue

            section_content = section_match.group(1)

            # Parse individual units within section
            # Look for ### Technique: Name or ### Use Case: Name patterns (case-insensitive)
            unit_pattern = r'###\s*(?:Technique|Pattern|Use Case|Capability|Integration|Anti-Pattern|Component|Issue|Config|Snippet):\s*(.+?)\n\*\*ID\*\*:\s*`(.+?)`(.*?)(?=###|##|$)'

            for match in re.finditer(unit_pattern, section_content, re.DOTALL | re.IGNORECASE):
                name = match.group(1).strip()
                unit_id = match.group(2).strip()
                content = match.group(3).strip()

                # Build full content including header
                full_content = f"### {unit_type.title()}: {name}\n**ID**: `{unit_id}`\n{content}"

                unit = KnowledgeUnit(
                    type=unit_type,
                    id=unit_id,
                    name=name,
                    content=full_content,
                    source_video_id=source_video_id
                )

                units.append(unit)

        return units

    def analyze_units(
        self,
        candidates: List[Dict[str, Any]],
        video_id: str,
        video_title: str
    ) -> AnalysisResult:
        """
        Analyze pre-selected candidate units (from DeterministicExtractor).

        This method categorizes existing units rather than selecting new ones.
        Uses LLM normalizer with caching for deterministic categorization.

        Args:
            candidates: Units from DeterministicExtractor
                       Each has: {id, text, start, end, window, score}
            video_id: YouTube video ID
            video_title: Video title

        Returns:
            AnalysisResult with categorized KnowledgeUnits
        """
        # Create normalizer
        normalizer = LLMNormalizer(
            api_key=self.client.api_key,
            model=self.model,
            template_version=self.template_version
        )

        # Run with cache/retry/fallback
        runner = NormalizerRunner(normalizer)
        normalized = runner.run(video_id, candidates)

        # Convert to KnowledgeUnit format
        knowledge_units = []
        for unit in normalized['units']:
            # Build content from normalized data
            content = f"""### {unit['type'].title()}: {unit['name']}
**ID**: `{unit['id']}`
**Summary**: {unit['summary']}
**Confidence**: {unit['confidence']:.2f}
"""

            ku = KnowledgeUnit(
                type=unit['type'],
                id=unit['id'],
                name=unit['name'],
                content=content,
                source_video_id=video_id
            )
            knowledge_units.append(ku)

        # Create result (note: cache hits don't have detailed token usage)
        usage = TokenUsage(
            input_tokens=0,  # Not tracked for cached results
            output_tokens=0
        )

        return AnalysisResult(
            video_id=video_id,
            video_title=video_title,
            raw_output=json.dumps(normalized, indent=2),
            knowledge_units=knowledge_units,
            usage=usage,
            cost=0.0  # Cache hits have zero cost
        )