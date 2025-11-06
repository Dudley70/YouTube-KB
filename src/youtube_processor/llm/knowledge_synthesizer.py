"""Knowledge synthesis across multiple video analyses"""
from pathlib import Path
from typing import Optional
from collections import defaultdict
import yaml

from .models import KnowledgeUnit, AnalysisResult, SynthesizedUnit

class KnowledgeSynthesizer:
    """
    Synthesizes knowledge units across multiple videos.

    Groups units by ID, merges duplicate content, resolves cross-references,
    and generates organized knowledge base documents.
    """

    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize synthesizer.

        Args:
            output_dir: Base directory for output files.
                       Default: ./knowledge-base/
        """
        self.output_dir = Path(output_dir) if output_dir else Path("./knowledge-base")
        self.type_dirs = {
            "technique": self.output_dir / "techniques",
            "pattern": self.output_dir / "patterns",
            "use-case": self.output_dir / "use-cases",
            "capability": self.output_dir / "capabilities",
            "integration": self.output_dir / "integrations",
            "antipattern": self.output_dir / "antipatterns",
            "component": self.output_dir / "components",
            "issue": self.output_dir / "troubleshooting",
            "config": self.output_dir / "configurations",
            "snippet": self.output_dir / "snippets"
        }

    def synthesize(
        self,
        analysis_results: list[AnalysisResult],
        create_files: bool = True
    ) -> dict[str, SynthesizedUnit]:
        """
        Synthesize knowledge from multiple video analyses.

        Process:
        1. Collect all knowledge units from all analyses
        2. Group units by ID
        3. Merge units with same ID into synthesized units
        4. Resolve cross-references
        5. Generate markdown documents (if create_files=True)
        6. Generate metadata YAML (if create_files=True)

        Args:
            analysis_results: List of AnalysisResult objects
            create_files: Whether to write markdown files to disk

        Returns:
            Dict mapping unit ID to SynthesizedUnit
        """
        # Step 1: Collect all units
        all_units = []
        for result in analysis_results:
            all_units.extend(result.knowledge_units)

        # Step 2: Group by ID
        grouped = self.group_by_id(all_units)

        # Step 3: Merge into synthesized units
        synthesized = {}
        for unit_id, units in grouped.items():
            synthesized[unit_id] = SynthesizedUnit.from_knowledge_units(units)

        # Step 4: Resolve cross-references (update with valid paths)
        self._resolve_all_cross_references(synthesized)

        # Step 5 & 6: Generate files if requested
        if create_files:
            self._create_output_directories()
            self._write_markdown_files(synthesized)
            self._write_metadata_files(synthesized, analysis_results)

        return synthesized

    def group_by_id(
        self,
        units: list[KnowledgeUnit]
    ) -> dict[str, list[KnowledgeUnit]]:
        """
        Group knowledge units by ID.

        Args:
            units: List of KnowledgeUnit objects

        Returns:
            Dict mapping unit ID to list of units with that ID
        """
        grouped = defaultdict(list)

        for unit in units:
            grouped[unit.id].append(unit)

        return dict(grouped)

    def _resolve_all_cross_references(
        self,
        synthesized_units: dict[str, SynthesizedUnit]
    ) -> None:
        """
        Resolve cross-references to valid paths.

        Filters out references to units that don't exist in synthesized set.

        Args:
            synthesized_units: Dict of synthesized units to update in-place
        """
        valid_ids = set(synthesized_units.keys())

        for unit in synthesized_units.values():
            # Filter to only valid references
            unit.cross_references = [
                ref for ref in unit.cross_references
                if ref in valid_ids
            ]

    def detect_circular_references(
        self,
        synthesized_units: dict[str, SynthesizedUnit]
    ) -> list[tuple[str, str]]:
        """
        Detect circular reference chains.

        A circular reference exists when:
        - Unit A references Unit B
        - Unit B references Unit A

        Args:
            synthesized_units: Dict of synthesized units

        Returns:
            List of (id1, id2) tuples representing circular refs
        """
        circular = []

        for unit_id, unit in synthesized_units.items():
            for ref_id in unit.cross_references:
                # Check if referenced unit also references back
                if ref_id in synthesized_units:
                    ref_unit = synthesized_units[ref_id]
                    if unit_id in ref_unit.cross_references:
                        # Add tuple (smaller_id, larger_id) to avoid duplicates
                        pair = tuple(sorted([unit_id, ref_id]))
                        if pair not in circular:
                            circular.append(pair)

        return circular

    def _create_output_directories(self) -> None:
        """Create output directory structure"""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        for type_dir in self.type_dirs.values():
            type_dir.mkdir(parents=True, exist_ok=True)

        # Create metadata directory
        (self.output_dir / "metadata").mkdir(exist_ok=True)

    def _write_markdown_files(
        self,
        synthesized_units: dict[str, SynthesizedUnit]
    ) -> None:
        """
        Write markdown files for each synthesized unit.

        Args:
            synthesized_units: Dict of synthesized units
        """
        for unit in synthesized_units.values():
            # Get directory for this unit type
            type_dir = self.type_dirs.get(unit.type)
            if not type_dir:
                continue

            # Generate markdown content
            markdown = unit.to_markdown(self.output_dir)

            # Write to file
            output_file = type_dir / f"{unit.id}.md"
            output_file.write_text(markdown, encoding="utf-8")

    def _write_metadata_files(
        self,
        synthesized_units: dict[str, SynthesizedUnit],
        analysis_results: list[AnalysisResult]
    ) -> None:
        """
        Write metadata YAML files.

        Creates:
        - metadata/units.yaml: All unit metadata
        - metadata/synthesis.yaml: Synthesis statistics

        Args:
            synthesized_units: Dict of synthesized units
            analysis_results: Original analysis results
        """
        metadata_dir = self.output_dir / "metadata"

        # Units metadata
        units_metadata = {
            unit_id: unit.to_metadata_dict()
            for unit_id, unit in synthesized_units.items()
        }

        units_file = metadata_dir / "units.yaml"
        with units_file.open('w', encoding='utf-8') as f:
            yaml.dump(units_metadata, f, default_flow_style=False, sort_keys=False)

        # Synthesis statistics
        type_counts = defaultdict(int)
        for unit in synthesized_units.values():
            type_counts[unit.type] += 1

        synthesis_stats = {
            "total_videos_analyzed": len(analysis_results),
            "total_units_synthesized": len(synthesized_units),
            "units_by_type": dict(type_counts),
            "source_videos": sorted(set(
                result.video_id for result in analysis_results
            ))
        }

        stats_file = metadata_dir / "synthesis.yaml"
        with stats_file.open('w', encoding='utf-8') as f:
            yaml.dump(synthesis_stats, f, default_flow_style=False, sort_keys=False)

    def generate_index(
        self,
        synthesized_units: dict[str, SynthesizedUnit]
    ) -> str:
        """
        Generate README.md index of all synthesized knowledge.

        Args:
            synthesized_units: Dict of synthesized units

        Returns:
            Markdown content for index
        """
        lines = [
            "# Knowledge Base Index",
            "",
            "Synthesized knowledge extracted from video analyses.",
            ""
        ]

        # Group by type
        by_type = defaultdict(list)
        for unit in synthesized_units.values():
            by_type[unit.type].append(unit)

        # Generate sections by type
        type_names = {
            "technique": "Techniques",
            "pattern": "Patterns",
            "use-case": "Use Cases",
            "capability": "Capabilities",
            "integration": "Integration Methods",
            "antipattern": "Anti-Patterns",
            "component": "Architecture Components",
            "issue": "Troubleshooting",
            "config": "Configuration Recipes",
            "snippet": "Code Snippets"
        }

        for unit_type in sorted(by_type.keys()):
            type_name = type_names.get(unit_type, unit_type.title())
            units = sorted(by_type[unit_type], key=lambda u: u.name)

            lines.append(f"## {type_name} ({len(units)})")
            lines.append("")

            for unit in units:
                # Link to unit file
                type_dir = unit_type + "s" if not unit_type.endswith('s') else unit_type
                link = f"{type_dir}/{unit.id}.md"

                # Show source count
                source_count = len(unit.source_videos)
                source_text = f"{source_count} source(s)"

                lines.append(f"- [{unit.name}]({link}) - {source_text}")

            lines.append("")

        return '\n'.join(lines)

    def write_index(self, synthesized_units: dict[str, SynthesizedUnit]) -> None:
        """Write README.md index file"""
        index_content = self.generate_index(synthesized_units)
        index_file = self.output_dir / "README.md"
        index_file.write_text(index_content, encoding="utf-8")