"""Tests for knowledge synthesizer"""
import pytest
from pathlib import Path
import tempfile
import yaml

from youtube_processor.llm.knowledge_synthesizer import KnowledgeSynthesizer
from youtube_processor.llm.models import (
    KnowledgeUnit,
    SynthesizedUnit,
    AnalysisResult,
    TokenUsage
)

class TestSynthesizedUnit:
    """Test SynthesizedUnit model"""

    def test_from_knowledge_units_single(self):
        """Creates synthesized unit from single knowledge unit"""
        unit = KnowledgeUnit(
            type="technique",
            id="technique-test",
            name="Test Technique",
            content="Content here",
            source_video_id="video1"
        )

        synthesized = SynthesizedUnit.from_knowledge_units([unit])

        assert synthesized.id == "technique-test"
        assert synthesized.name == "Test Technique"
        assert synthesized.type == "technique"
        assert len(synthesized.source_videos) == 1
        assert "video1" in synthesized.source_videos

    def test_from_knowledge_units_multiple(self):
        """Merges multiple units with same ID"""
        units = [
            KnowledgeUnit("technique", "technique-test", "Test", "Content A", "video1"),
            KnowledgeUnit("technique", "technique-test", "Test", "Content B", "video2"),
            KnowledgeUnit("technique", "technique-test", "Test", "Content C", "video3"),
        ]

        synthesized = SynthesizedUnit.from_knowledge_units(units)

        assert len(synthesized.source_videos) == 3
        assert "video1" in synthesized.source_videos
        assert "video2" in synthesized.source_videos
        assert "video3" in synthesized.source_videos

    def test_merge_content_deduplicates(self):
        """Merges content and removes duplicates"""
        units = [
            KnowledgeUnit(
                "technique", "technique-test", "Test",
                "Unique to video 1\n\nShared content\n\nMore unique 1",
                "video1"
            ),
            KnowledgeUnit(
                "technique", "technique-test", "Test",
                "Shared content\n\nUnique to video 2",
                "video2"
            ),
        ]

        synthesized = SynthesizedUnit.from_knowledge_units(units)

        # Shared content should appear only once
        assert synthesized.content.count("Shared content") == 1
        # Unique content should be preserved
        assert "Unique to video 1" in synthesized.content
        assert "Unique to video 2" in synthesized.content

    def test_extract_cross_references_from_all_units(self):
        """Collects cross-references from all units"""
        units = [
            KnowledgeUnit(
                "technique", "technique-test", "Test",
                "Related: technique-other, pattern-test",
                "video1"
            ),
            KnowledgeUnit(
                "technique", "technique-test", "Test",
                "See also: use-case-example",
                "video2"
            ),
        ]

        synthesized = SynthesizedUnit.from_knowledge_units(units)

        # Should have all references from both units
        assert "technique-other" in synthesized.cross_references
        assert "pattern-test" in synthesized.cross_references
        assert "use-case-example" in synthesized.cross_references

    def test_from_empty_list_raises(self):
        """Raises error for empty units list"""
        with pytest.raises(ValueError, match="empty units list"):
            SynthesizedUnit.from_knowledge_units([])

    def test_from_mismatched_ids_raises(self):
        """Raises error when units have different IDs"""
        units = [
            KnowledgeUnit("technique", "technique-a", "A", "Content", "video1"),
            KnowledgeUnit("technique", "technique-b", "B", "Content", "video2"),
        ]

        with pytest.raises(ValueError, match="same ID"):
            SynthesizedUnit.from_knowledge_units(units)

    def test_to_markdown(self):
        """Generates markdown document"""
        synthesized = SynthesizedUnit(
            type="technique",
            id="technique-test",
            name="Test Technique",
            content="Test content here",
            source_videos=["video1", "video2"],
            cross_references=["pattern-related"]
        )

        markdown = synthesized.to_markdown(Path("./output"))

        assert "# Test Technique" in markdown
        assert "`technique-test`" in markdown
        assert "video1" in markdown
        assert "video2" in markdown
        assert "Test content here" in markdown
        assert "pattern-related" in markdown

    def test_to_metadata_dict(self):
        """Exports metadata dictionary"""
        synthesized = SynthesizedUnit(
            type="pattern",
            id="pattern-test",
            name="Test Pattern",
            content="Content here",
            source_videos=["v1", "v2"],
            cross_references=["technique-a"]
        )

        metadata = synthesized.to_metadata_dict()

        assert metadata["id"] == "pattern-test"
        assert metadata["name"] == "Test Pattern"
        assert metadata["type"] == "pattern"
        assert len(metadata["source_videos"]) == 2
        assert len(metadata["cross_references"]) == 1

    def test_merge_content_preserves_order(self):
        """Content merging preserves first occurrence order"""
        contents = [
            "First paragraph\n\nSecond paragraph",
            "Second paragraph\n\nThird paragraph",
            "First paragraph\n\nFourth paragraph"
        ]

        merged = SynthesizedUnit._merge_content(contents)

        # Should preserve order of first occurrence
        lines = merged.split('\n\n')
        assert lines[0] == "First paragraph"
        assert lines[1] == "Second paragraph"
        assert lines[2] == "Third paragraph"
        assert lines[3] == "Fourth paragraph"

    def test_merge_content_handles_empty_paragraphs(self):
        """Content merging handles empty paragraphs gracefully"""
        contents = [
            "Content 1\n\n\n\nContent 2",  # Extra newlines
            "\n\nContent 3\n\n",  # Leading/trailing spaces
            ""  # Empty content
        ]

        merged = SynthesizedUnit._merge_content(contents)

        assert "Content 1" in merged
        assert "Content 2" in merged
        assert "Content 3" in merged
        # Should not have excessive whitespace
        assert "\n\n\n" not in merged


class TestKnowledgeSynthesizer:
    """Test knowledge synthesizer"""

    def test_group_by_id(self):
        """Groups knowledge units by ID"""
        units = [
            KnowledgeUnit("technique", "technique-a", "A", "Content", "v1"),
            KnowledgeUnit("technique", "technique-a", "A", "Content", "v2"),
            KnowledgeUnit("pattern", "pattern-b", "B", "Content", "v1"),
            KnowledgeUnit("pattern", "pattern-b", "B", "Content", "v3"),
        ]

        synthesizer = KnowledgeSynthesizer()
        grouped = synthesizer.group_by_id(units)

        assert len(grouped) == 2
        assert len(grouped["technique-a"]) == 2
        assert len(grouped["pattern-b"]) == 2

    def test_synthesize_basic(self):
        """Synthesizes knowledge from analysis results"""
        # Create mock analysis results
        results = [
            AnalysisResult(
                video_id="video1",
                video_title="Video 1",
                raw_output="Output 1",
                knowledge_units=[
                    KnowledgeUnit("technique", "technique-test", "Test", "Content 1", "video1")
                ],
                usage=TokenUsage(100, 50),
                cost=0.001
            ),
            AnalysisResult(
                video_id="video2",
                video_title="Video 2",
                raw_output="Output 2",
                knowledge_units=[
                    KnowledgeUnit("technique", "technique-test", "Test", "Content 2", "video2")
                ],
                usage=TokenUsage(100, 50),
                cost=0.001
            )
        ]

        synthesizer = KnowledgeSynthesizer()
        synthesized = synthesizer.synthesize(results, create_files=False)

        assert len(synthesized) == 1
        assert "technique-test" in synthesized

        unit = synthesized["technique-test"]
        assert len(unit.source_videos) == 2
        assert "video1" in unit.source_videos
        assert "video2" in unit.source_videos

    def test_synthesize_multiple_types(self):
        """Handles multiple knowledge unit types"""
        results = [
            AnalysisResult(
                video_id="video1",
                video_title="Video 1",
                raw_output="Output",
                knowledge_units=[
                    KnowledgeUnit("technique", "technique-a", "A", "Content", "video1"),
                    KnowledgeUnit("pattern", "pattern-b", "B", "Content", "video1"),
                    KnowledgeUnit("use-case", "use-case-c", "C", "Content", "video1"),
                ],
                usage=TokenUsage(100, 50),
                cost=0.001
            )
        ]

        synthesizer = KnowledgeSynthesizer()
        synthesized = synthesizer.synthesize(results, create_files=False)

        assert len(synthesized) == 3
        assert "technique-a" in synthesized
        assert "pattern-b" in synthesized
        assert "use-case-c" in synthesized

    def test_resolve_cross_references(self):
        """Filters invalid cross-references"""
        results = [
            AnalysisResult(
                video_id="video1",
                video_title="Video 1",
                raw_output="Output",
                knowledge_units=[
                    KnowledgeUnit(
                        "technique", "technique-a", "A",
                        "Related: pattern-b, pattern-nonexistent",
                        "video1"
                    ),
                    KnowledgeUnit("pattern", "pattern-b", "B", "Content", "video1"),
                ],
                usage=TokenUsage(100, 50),
                cost=0.001
            )
        ]

        synthesizer = KnowledgeSynthesizer()
        synthesized = synthesizer.synthesize(results, create_files=False)

        # technique-a should reference pattern-b but not pattern-nonexistent
        refs = synthesized["technique-a"].cross_references
        assert "pattern-b" in refs
        assert "pattern-nonexistent" not in refs

    def test_detect_circular_references(self):
        """Detects circular reference chains"""
        units = {
            "technique-a": SynthesizedUnit(
                "technique", "technique-a", "A", "Content",
                ["v1"], ["technique-b"]
            ),
            "technique-b": SynthesizedUnit(
                "technique", "technique-b", "B", "Content",
                ["v1"], ["technique-a"]
            ),
        }

        synthesizer = KnowledgeSynthesizer()
        circular = synthesizer.detect_circular_references(units)

        assert len(circular) > 0
        # Should detect the A<->B cycle
        assert ("technique-a", "technique-b") in circular or \
               ("technique-b", "technique-a") in circular

    def test_generate_index(self):
        """Generates README index"""
        units = {
            "technique-a": SynthesizedUnit(
                "technique", "technique-a", "Technique A", "Content",
                ["v1"], []
            ),
            "pattern-b": SynthesizedUnit(
                "pattern", "pattern-b", "Pattern B", "Content",
                ["v1", "v2"], []
            ),
        }

        synthesizer = KnowledgeSynthesizer()
        index = synthesizer.generate_index(units)

        assert "# Knowledge Base Index" in index
        assert "Technique A" in index
        assert "Pattern B" in index
        assert "2 source(s)" in index  # Pattern B has 2 sources

    def test_synthesize_with_file_creation(self):
        """Creates output files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "knowledge-base"

            results = [
                AnalysisResult(
                    video_id="video1",
                    video_title="Video 1",
                    raw_output="Output",
                    knowledge_units=[
                        KnowledgeUnit("technique", "technique-test", "Test", "Content", "video1")
                    ],
                    usage=TokenUsage(100, 50),
                    cost=0.001
                )
            ]

            synthesizer = KnowledgeSynthesizer(output_dir=output_dir)
            synthesized = synthesizer.synthesize(results, create_files=True)

            # Check directories created
            assert output_dir.exists()
            assert (output_dir / "techniques").exists()
            assert (output_dir / "metadata").exists()

            # Check markdown file created
            md_file = output_dir / "techniques" / "technique-test.md"
            assert md_file.exists()
            content = md_file.read_text()
            assert "Test" in content

            # Check metadata files created
            units_yaml = output_dir / "metadata" / "units.yaml"
            assert units_yaml.exists()

            stats_yaml = output_dir / "metadata" / "synthesis.yaml"
            assert stats_yaml.exists()

            # Verify YAML content
            with stats_yaml.open() as f:
                stats = yaml.safe_load(f)
            assert stats["total_videos_analyzed"] == 1
            assert stats["total_units_synthesized"] == 1

    def test_write_index_file(self):
        """Writes README.md index file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "knowledge-base"
            output_dir.mkdir(parents=True)

            units = {
                "technique-a": SynthesizedUnit(
                    "technique", "technique-a", "Test Technique", "Content",
                    ["v1"], []
                ),
            }

            synthesizer = KnowledgeSynthesizer(output_dir=output_dir)
            synthesizer.write_index(units)

            # Check README created
            readme = output_dir / "README.md"
            assert readme.exists()

            content = readme.read_text()
            assert "# Knowledge Base Index" in content
            assert "Test Technique" in content

    def test_synthesizer_default_output_dir(self):
        """Uses default output directory when none specified"""
        synthesizer = KnowledgeSynthesizer()
        assert synthesizer.output_dir == Path("./knowledge-base")

    def test_synthesizer_custom_output_dir(self):
        """Uses custom output directory when specified"""
        custom_dir = Path("/tmp/custom-kb")
        synthesizer = KnowledgeSynthesizer(output_dir=custom_dir)
        assert synthesizer.output_dir == custom_dir

    def test_no_circular_references_detected(self):
        """Returns empty list when no circular references exist"""
        units = {
            "technique-a": SynthesizedUnit(
                "technique", "technique-a", "A", "Content",
                ["v1"], ["pattern-b"]
            ),
            "pattern-b": SynthesizedUnit(
                "pattern", "pattern-b", "B", "Content",
                ["v1"], ["use-case-c"]
            ),
            "use-case-c": SynthesizedUnit(
                "use-case", "use-case-c", "C", "Content",
                ["v1"], []
            ),
        }

        synthesizer = KnowledgeSynthesizer()
        circular = synthesizer.detect_circular_references(units)

        assert len(circular) == 0


class TestIntegration:
    """Integration tests"""

    def test_end_to_end_synthesis(self):
        """Complete synthesis workflow"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "knowledge-base"

            # Create realistic analysis results
            results = [
                AnalysisResult(
                    video_id="video1",
                    video_title="Video 1",
                    raw_output="Output 1",
                    knowledge_units=[
                        KnowledgeUnit(
                            "technique", "technique-memory-sweep", "Memory Sweep",
                            "Clears conversation memory\n\nRelated: pattern-cleanup",
                            "video1"
                        ),
                        KnowledgeUnit(
                            "pattern", "pattern-cleanup", "Cleanup Pattern",
                            "Regular maintenance pattern",
                            "video1"
                        ),
                    ],
                    usage=TokenUsage(1000, 500),
                    cost=0.01
                ),
                AnalysisResult(
                    video_id="video2",
                    video_title="Video 2",
                    raw_output="Output 2",
                    knowledge_units=[
                        KnowledgeUnit(
                            "technique", "technique-memory-sweep", "Memory Sweep",
                            "Alternative description\n\nUsed for context management",
                            "video2"
                        ),
                    ],
                    usage=TokenUsage(800, 400),
                    cost=0.008
                )
            ]

            # Synthesize
            synthesizer = KnowledgeSynthesizer(output_dir=output_dir)
            synthesized = synthesizer.synthesize(results, create_files=True)

            # Verify synthesis
            assert len(synthesized) == 2

            # Check memory-sweep merged from both videos
            memory_sweep = synthesized["technique-memory-sweep"]
            assert len(memory_sweep.source_videos) == 2
            assert "video1" in memory_sweep.source_videos
            assert "video2" in memory_sweep.source_videos

            # Check cross-reference resolved
            assert "pattern-cleanup" in memory_sweep.cross_references

            # Verify files created
            assert (output_dir / "techniques" / "technique-memory-sweep.md").exists()
            assert (output_dir / "patterns" / "pattern-cleanup.md").exists()
            assert (output_dir / "metadata" / "units.yaml").exists()
            assert (output_dir / "metadata" / "synthesis.yaml").exists()

            # Write and verify index
            synthesizer.write_index(synthesized)
            assert (output_dir / "README.md").exists()

    def test_complex_cross_reference_resolution(self):
        """Tests complex cross-reference scenarios"""
        results = [
            AnalysisResult(
                video_id="video1",
                video_title="Video 1",
                raw_output="Output",
                knowledge_units=[
                    KnowledgeUnit(
                        "technique", "technique-a", "A",
                        "References: pattern-b, technique-nonexistent, use-case-c",
                        "video1"
                    ),
                    KnowledgeUnit("pattern", "pattern-b", "B", "Content", "video1"),
                    KnowledgeUnit("use-case", "use-case-c", "C", "Content", "video1"),
                ],
                usage=TokenUsage(100, 50),
                cost=0.001
            )
        ]

        synthesizer = KnowledgeSynthesizer()
        synthesized = synthesizer.synthesize(results, create_files=False)

        # Should only keep valid references
        refs = synthesized["technique-a"].cross_references
        assert "pattern-b" in refs
        assert "use-case-c" in refs
        assert "technique-nonexistent" not in refs

    def test_synthesis_statistics_accuracy(self):
        """Verifies synthesis statistics are accurate"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "knowledge-base"

            results = [
                AnalysisResult(
                    video_id="video1",
                    video_title="Video 1",
                    raw_output="Output",
                    knowledge_units=[
                        KnowledgeUnit("technique", "technique-a", "A", "Content", "video1"),
                        KnowledgeUnit("pattern", "pattern-b", "B", "Content", "video1"),
                    ],
                    usage=TokenUsage(100, 50),
                    cost=0.001
                ),
                AnalysisResult(
                    video_id="video2",
                    video_title="Video 2",
                    raw_output="Output",
                    knowledge_units=[
                        KnowledgeUnit("use-case", "use-case-c", "C", "Content", "video2"),
                    ],
                    usage=TokenUsage(100, 50),
                    cost=0.001
                )
            ]

            synthesizer = KnowledgeSynthesizer(output_dir=output_dir)
            synthesizer.synthesize(results, create_files=True)

            # Load and verify synthesis statistics
            stats_file = output_dir / "metadata" / "synthesis.yaml"
            with stats_file.open() as f:
                stats = yaml.safe_load(f)

            assert stats["total_videos_analyzed"] == 2
            assert stats["total_units_synthesized"] == 3
            assert stats["units_by_type"]["technique"] == 1
            assert stats["units_by_type"]["pattern"] == 1
            assert stats["units_by_type"]["use-case"] == 1
            assert "video1" in stats["source_videos"]
            assert "video2" in stats["source_videos"]

    def test_markdown_cross_reference_links(self):
        """Verifies cross-reference links in markdown are properly formatted"""
        synthesized = SynthesizedUnit(
            type="technique",
            id="technique-test",
            name="Test Technique",
            content="Test content",
            source_videos=["video1"],
            cross_references=["pattern-cleanup", "use-case-example"]
        )

        markdown = synthesized.to_markdown(Path("./output"))

        # Check that cross-references become proper links
        assert "[pattern-cleanup](../patterns/pattern-cleanup.md)" in markdown
        assert "[use-case-example](../use-cases/use-case-example.md)" in markdown