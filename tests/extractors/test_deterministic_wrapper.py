"""
Unit tests for deterministic_wrapper.py
"""
import pytest
import json
from pathlib import Path
from youtube_processor.extractors.deterministic_wrapper import DeterministicExtractor


@pytest.fixture
def extractor():
    return DeterministicExtractor()


@pytest.fixture
def sample_transcript():
    return """
    In this video we will discuss artificial intelligence and machine learning.
    We'll cover neural networks, deep learning, and natural language processing.
    These are fundamental concepts in modern AI development.
    """


def test_extractor_initialization(extractor):
    """Test extractor initializes correctly"""
    assert extractor.node_path == "node"
    assert extractor.timeout == 60
    assert extractor.extractor_path.exists()
    assert extractor.cli_path.exists()


def test_extract_basic(extractor, sample_transcript):
    """Test basic extraction works"""
    result = extractor.extract("test_video", sample_transcript)
    
    # Verify structure
    assert 'video_id' in result
    assert 'transcript_hash' in result
    assert 'units' in result
    assert result['video_id'] == "test_video"
    assert isinstance(result['units'], list)
    assert len(result['units']) > 0


def test_extract_unit_structure(extractor, sample_transcript):
    """Test each unit has required fields"""
    result = extractor.extract("test_video", sample_transcript)
    
    for unit in result['units']:
        assert 'id' in unit
        assert 'text' in unit
        assert 'start' in unit
        assert 'end' in unit
        assert 'score' in unit
        assert 'window' in unit
        assert isinstance(unit['id'], str)
        assert isinstance(unit['text'], str)
        assert isinstance(unit['start'], int)
        assert isinstance(unit['end'], int)
        assert isinstance(unit['score'], (int, float))
        assert isinstance(unit['window'], int)


def test_extract_with_meta(extractor, sample_transcript):
    """Test metadata inclusion"""
    result = extractor.extract("test_video", sample_transcript, include_meta=True)
    
    assert 'meta' in result
    assert isinstance(result['meta'], dict)


def test_extract_without_meta(extractor, sample_transcript):
    """Test metadata exclusion"""
    result = extractor.extract("test_video", sample_transcript, include_meta=False)
    
    # Should not have meta when include_meta=False
    assert 'meta' not in result or result.get('meta') is None


def test_extract_determinism(extractor, sample_transcript):
    """Test extraction is deterministic"""
    results = [
        extractor.extract("test", sample_transcript)
        for _ in range(5)
    ]
    
    # All results should have same units
    first_units = results[0]['units']
    for result in results[1:]:
        assert result['units'] == first_units, "Extraction is not deterministic"


def test_extract_empty_transcript(extractor):
    """Test extraction with empty transcript"""
    result = extractor.extract("test_video", "")
    assert result['units'] == []


def test_extract_short_transcript(extractor):
    """Test extraction with very short transcript"""
    result = extractor.extract("test_video", "This is short")
    # Should handle gracefully (may or may not have units)
    assert isinstance(result['units'], list)


def test_compute_transcript_hash(extractor):
    """Test transcript hash computation"""
    transcript = "test transcript"
    hash1 = extractor.compute_transcript_hash(transcript)
    hash2 = extractor.compute_transcript_hash(transcript)
    
    # Same transcript = same hash
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256 hex length


def test_validation_missing_fields(extractor):
    """Test output validation catches missing fields"""
    invalid = {'video_id': 'test'}  # Missing required fields
    
    with pytest.raises(ValueError, match="Missing required fields"):
        extractor._validate_output(invalid)


def test_validation_invalid_units(extractor):
    """Test output validation catches invalid units"""
    invalid = {
        'video_id': 'test',
        'transcript_hash': 'abc',
        'units': [{'id': 'test'}]  # Missing required unit fields
    }
    
    with pytest.raises(ValueError, match="missing required fields"):
        extractor._validate_output(invalid)


def test_validation_units_not_list(extractor):
    """Test output validation catches non-list units"""
    invalid = {
        'video_id': 'test',
        'transcript_hash': 'abc',
        'units': 'not a list'
    }
    
    with pytest.raises(ValueError, match="must be a list"):
        extractor._validate_output(invalid)
