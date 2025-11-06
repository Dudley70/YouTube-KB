"""
AnalysisWorkflow orchestrates LLM analysis and knowledge synthesis.

This module provides the main orchestration for the analysis workflow:
1. Load Template V2.1
2. Analyze each transcript
3. Track token usage and costs
4. Show progress with Rich UI
5. Run knowledge synthesis
6. Generate markdown knowledge base
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from youtube_processor.core.discovery import VideoMetadata
from youtube_processor.core.extractor import DirectoryManager, PathGenerator
from youtube_processor.llm.anthropic_client import AnthropicClient
from youtube_processor.llm.template_processor import TemplateProcessor
from youtube_processor.llm.transcript_analyzer import TranscriptAnalyzer
from youtube_processor.llm.knowledge_synthesizer import KnowledgeSynthesizer

logger = logging.getLogger(__name__)


class AnalysisWorkflow:
    """Orchestrates LLM analysis and knowledge synthesis"""

    def __init__(self, api_key: str, model: str, console: Console):
        """Initialize the analysis workflow.

        Args:
            api_key: Anthropic API key
            model: Claude model to use
            console: Rich console for output
        """
        self.console = console
        self.client = AnthropicClient(api_key=api_key)
        processor = TemplateProcessor()
        self.template = processor.load_template("v2.1")
        self.analyzer = TranscriptAnalyzer(
            api_key=api_key,
            model=model
        )
        self.synthesizer = KnowledgeSynthesizer()
        self.total_tokens = 0
        self.total_cost = 0.0

    def run(self, channel_name: str, channel_dir: Path, videos: List[VideoMetadata]) -> None:
        """Run complete analysis and synthesis workflow.

        Args:
            channel_name: Name of the channel
            channel_dir: Path to channel directory (channels/{name}/)
            videos: List of videos that were extracted
        """
        if not videos:
            self.console.print("[yellow]No videos to analyze[/yellow]")
            return

        self.console.print(f"\n[bold blue]Step 4: Analyzing transcripts...[/bold blue]")

        # Create analyses directory
        analyses_dir = DirectoryManager.create_channel_analyses_dir(
            channel_dir.parent.parent, channel_name
        )

        # Analyze transcripts
        analyses = []
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=self.console
        ) as progress:

            task = progress.add_task("Analyzing videos...", total=len(videos))

            for video in videos:
                # Read transcript
                transcript_path = PathGenerator.get_transcript_txt_path(
                    channel_dir.parent.parent,  # base_path (output/)
                    channel_name,
                    video.video_id,
                    video.title
                )

                if not transcript_path.exists():
                    self.console.print(f"[yellow]Warning: No transcript found for {video.video_id}[/yellow]")
                    progress.update(task, advance=1)
                    continue

                transcript = transcript_path.read_text()

                # Analyze
                result = self.analyzer.analyze_transcript(
                    transcript=transcript,
                    video_id=video.video_id,
                    video_title=video.title,
                    video_url=f"https://www.youtube.com/watch?v={video.video_id}"
                )

                analyses.append(result)

                # Save analysis
                analysis_path = analyses_dir / f"{video.video_id}-analysis.json"
                self._save_analysis(result, analysis_path)

                # Track costs
                self.total_tokens += result.usage.total
                self.total_cost += result.cost

                progress.update(task, advance=1)

        # Step 5: Synthesize knowledge
        self.console.print(f"\n[bold blue]Step 5: Synthesizing knowledge...[/bold blue]")

        kb_dir = DirectoryManager.create_channel_kb_dir(
            channel_dir.parent.parent, channel_name
        )
        knowledge_base = self.synthesizer.synthesize(analyses)

        # Generate markdown
        self._generate_knowledge_base(knowledge_base, kb_dir)

        # Show summary
        self.console.print(f"\n[green]✓ Analysis Complete![/green]")
        self.console.print(f"  Analyzed: {len(videos)} videos")
        self.console.print(f"  Knowledge Units: {len(knowledge_base)}")
        self.console.print(f"  Total Tokens: {self.total_tokens:,}")
        self.console.print(f"  Total Cost: ${self.total_cost:.2f}")

    def _save_analysis(self, result, path: Path) -> None:
        """Save analysis result as JSON.

        Args:
            result: AnalysisResult object
            path: Path to save the JSON file
        """
        path.write_text(json.dumps(result.to_dict(), indent=2))

    def _generate_knowledge_base(self, knowledge_base, kb_dir: Path) -> None:
        """Generate markdown knowledge base.

        Args:
            knowledge_base: KnowledgeBase object
            kb_dir: Path to knowledge base directory
        """
        kb_dir.mkdir(exist_ok=True)

        # Create category directories
        categories = [
            'techniques', 'patterns', 'use-cases', 'capabilities',
            'integrations', 'antipatterns', 'components',
            'troubleshooting', 'configurations', 'snippets'
        ]

        for category in categories:
            (kb_dir / category).mkdir(exist_ok=True)

        # Generate markdown files (knowledge_base is dict[str, SynthesizedUnit])
        for unit_id, unit in knowledge_base.items():
            self._generate_unit_markdown(unit, kb_dir)

        # Generate README and metadata
        self._generate_readme(knowledge_base, kb_dir)
        self._generate_metadata_yaml(knowledge_base, kb_dir)

    def _generate_unit_markdown(self, unit, kb_dir: Path) -> None:
        """Generate markdown file for a synthesized knowledge unit.

        Args:
            unit: SynthesizedUnit object
            kb_dir: Knowledge base directory
        """
        # Determine category directory
        category = unit.type.lower()
        if category not in ['techniques', 'patterns', 'use-cases', 'capabilities',
                           'integrations', 'antipatterns', 'components',
                           'troubleshooting', 'configurations', 'snippets']:
            category = 'techniques'  # Default fallback

        # Generate filename
        safe_title = unit.name.lower().replace(' ', '-').replace('/', '-')
        filename = f"{safe_title}.md"
        filepath = kb_dir / category / filename

        # Generate markdown content
        source_videos_str = '\n'.join([f"- {video_id}" for video_id in unit.source_videos])
        cross_refs_str = ', '.join(unit.cross_references) if unit.cross_references else "None"
        
        content = f"""# {unit.name}

**Type**: {unit.type}  
**ID**: {unit.id}

## Content

{unit.content}

## Source Videos

{source_videos_str}

## Cross-References

{cross_refs_str}

---

*Synthesized from YouTube transcript analysis*
"""

        filepath.write_text(content)

    def _generate_readme(self, knowledge_base, kb_dir: Path) -> None:
        """Generate README.md for the knowledge base.

        Args:
            knowledge_base: Dict of SynthesizedUnit objects
            kb_dir: Knowledge base directory
        """
        content = f"""# Knowledge Base

This knowledge base was automatically generated from YouTube video transcripts.

## Statistics

- **Total Units:** {len(knowledge_base)}
- **Types:** {len(set(unit.type for unit in knowledge_base.values()))}

## By Type

"""

        # Group by type
        by_type = {}
        for unit in knowledge_base.values():
            unit_type = unit.type
            if unit_type not in by_type:
                by_type[unit_type] = []
            by_type[unit_type].append(unit)

        for unit_type, units in sorted(by_type.items()):
            content += f"\n### {unit_type.replace('-', ' ').title()}\n\n"
            for unit in sorted(units, key=lambda u: u.name):
                safe_name = unit.name.lower().replace(' ', '-').replace('/', '-')
                content += f"- [{unit.name}](./{unit_type}/{safe_name}.md)\n"

        content += """
## Usage

This knowledge base contains synthesized techniques, patterns, and insights from video transcripts.
Each file includes merged content across all source videos, implementation details, and cross-references.
"""

        (kb_dir / "README.md").write_text(content)

    def _generate_metadata_yaml(self, knowledge_base: Dict, kb_dir: Path) -> None:
        """Generate metadata YAML files.

        Args:
            knowledge_base: Knowledge base dict with units and metadata
            kb_dir: Knowledge base directory
        """
        # Create metadata directory
        metadata_dir = kb_dir / "metadata"
        metadata_dir.mkdir(exist_ok=True)

        units = knowledge_base.get('units', [])
        metadata = knowledge_base.get('metadata', {})

        # Generate units.yaml
        units_data = {
            'units': [
                {
                    'id': unit.get('id', ''),
                    'title': unit.get('title', ''),
                    'category': unit.get('category', ''),
                    'tags': unit.get('tags', []),
                    'confidence': unit.get('confidence', 0.0),
                    'video_references': unit.get('video_references', [])
                }
                for unit in units
            ]
        }

        import yaml
        (metadata_dir / "units.yaml").write_text(yaml.dump(units_data, default_flow_style=False))

        # Generate synthesis.yaml
        synthesis_data = {
            'metadata': metadata,
            'cross_references': metadata.get('cross_references', []),
            'generated_at': metadata.get('generated_at'),
            'total_units': len(units)
        }

        (metadata_dir / "synthesis.yaml").write_text(yaml.dump(synthesis_data, default_flow_style=False))

    def _generate_knowledge_base_markdown(self, knowledge_base: Dict, kb_dir: Path) -> None:
        """Generate markdown files from knowledge base dict.

        Args:
            knowledge_base: Knowledge base dict with units and metadata
            kb_dir: Knowledge base directory
        """
        kb_dir.mkdir(exist_ok=True)

        # Create category directories
        categories = [
            'techniques', 'patterns', 'use-cases', 'capabilities',
            'integrations', 'antipatterns', 'components',
            'troubleshooting', 'configurations', 'snippets'
        ]

        for category in categories:
            (kb_dir / category).mkdir(exist_ok=True)

        units = knowledge_base.get('units', [])

        # Generate markdown files for each unit
        for unit in units:
            unit_id = unit.get('id', 'unknown')
            unit_type = unit.get('type', 'technique')
            title = unit.get('title', 'Untitled')
            content = unit.get('content', 'No content available')

            # Determine category directory
            category_dir = kb_dir / f"{unit_type}s" if f"{unit_type}s" in categories else kb_dir / "techniques"

            # Create markdown file
            md_content = f"""# {title}

## Overview
{content}

## Source Videos
"""
            source_videos = unit.get('source_videos', [])
            if source_videos:
                for video in source_videos:
                    md_content += f"- {video}\n"
            else:
                md_content += "No source videos listed\n"

            md_file = category_dir / f"{unit_id}.md"
            md_file.write_text(md_content)