"""Integration tests for Phase A normalizer pipeline."""

import pytest
from youtube_processor.llm.transcript_analyzer import TranscriptAnalyzer


class MockDeterministicExtractor:
    """Mock extractor for testing."""
    
    def extract(self, video_id, transcript):
        """Return mock candidates."""
        # Return simple test units
        return {
            'units': [
                {
                    'id': 'unit-0-100',
                    'text': 'This is a technique for building agents with memory',
                    'start': 0,
                    'end': 100,
                    'window': 0,
                    'score': 0.95
                },
                {
                    'id': 'unit-100-200',
                    'text': 'A pattern for handling tool failures gracefully',
                    'start': 100,
                    'end': 200,
                    'window': 1,
                    'score': 0.88
                }
            ]
        }


def test_analyze_units_returns_analysis_result():
    """Test that analyze_units returns proper AnalysisResult."""
    # Use mock analyzer
    import os
    if 'ANTHROPIC_API_KEY' not in os.environ:
        pytest.skip("No API key available")

    analyzer = TranscriptAnalyzer(
        api_key=os.environ['ANTHROPIC_API_KEY'],
        model="claude-haiku-4-5-20251001"
    )

    candidates = [
        {
            'id': 'unit-0-100',
            'text': 'This is a technique for building agents with memory',
            'start': 0,
            'end': 100,
            'window': 0,
            'score': 0.95
        },
        {
            'id': 'unit-100-200',
            'text': 'A pattern for handling tool failures gracefully',
            'start': 100,
            'end': 200,
            'window': 1,
            'score': 0.88
        }
    ]

    result = analyzer.analyze_units(
        candidates=candidates,
        video_id="test_video",
        video_title="Test Video"
    )

    # Verify result structure
    assert result.video_id == "test_video"
    assert result.video_title == "Test Video"
    assert len(result.knowledge_units) == len(candidates)

    # Verify each unit
    for ku in result.knowledge_units:
        assert ku.type in [
            "technique", "pattern", "use-case", "capability",
            "integration", "anti-pattern", "component",
            "troubleshooting", "configuration", "code-snippet"
        ]
        assert len(ku.name) > 0
        assert ku.id.startswith("unit-")


def test_analyze_units_with_mock():
    """Test analyze_units with a mock normalizer (no API call)."""
    from unittest.mock import Mock, patch

    # Create analyzer
    analyzer = TranscriptAnalyzer(api_key="test-key")

    candidates = [
        {
            'id': 'u1',
            'text': 'test content 1',
            'start': 0,
            'end': 100,
            'window': 0,
            'score': 0.9
        }
    ]

    # Mock the normalizer to return valid result
    with patch('youtube_processor.llm.transcript_analyzer.NormalizerRunner') as mock_runner_class:
        mock_runner = Mock()
        mock_runner_class.return_value = mock_runner
        mock_runner.run.return_value = {
            'video_id': 'test_video',
            'units': [
                {
                    'id': 'u1',
                    'type': 'technique',
                    'name': 'Test Technique',
                    'summary': 'A test summary',
                    'confidence': 0.85
                }
            ]
        }

        result = analyzer.analyze_units(
            candidates=candidates,
            video_id="test_video",
            video_title="Test Video"
        )

        # Verify result
        assert result.video_id == "test_video"
        assert result.video_title == "Test Video"
        assert len(result.knowledge_units) == 1

        # Verify unit was created
        unit = result.knowledge_units[0]
        assert unit.id == 'u1'
        assert unit.type == 'technique'
        assert unit.name == 'Test Technique'
        assert unit.source_video_id == 'test_video'
