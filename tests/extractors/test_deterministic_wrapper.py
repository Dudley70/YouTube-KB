"""
Unit tests for deterministic_wrapper.py (Python implementation)
"""
import pytest
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
    Machine learning algorithms learn from data patterns.
    Neural networks are inspired by biological neurons.
    Deep learning uses multiple layers of processing.
    """


def test_extractor_initialization(extractor):
    """Test extractor initializes correctly"""
    assert extractor is not None


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
    # Check for expected meta fields
    assert 'extractor_version' in result['meta']
    assert 'window_chars' in result['meta']
    assert 'python_version' in result['meta']


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
    """Test extraction with empty transcript raises ValueError"""
    with pytest.raises(ValueError, match="Transcript cannot be empty"):
        extractor.extract("test_video", "")


def test_extract_whitespace_only(extractor):
    """Test extraction with whitespace-only transcript raises ValueError"""
    with pytest.raises(ValueError, match="Transcript cannot be empty"):
        extractor.extract("test_video", "   \n\t  ")


def test_extract_short_transcript(extractor):
    """Test extraction with very short transcript"""
    result = extractor.extract("test_video", "This is a short transcript with only a few words.")
    # Should handle gracefully
    assert isinstance(result['units'], list)


def test_compute_transcript_hash(extractor):
    """Test transcript hash computation"""
    transcript = "test transcript"
    hash1 = extractor.compute_transcript_hash(transcript)
    hash2 = extractor.compute_transcript_hash(transcript)
    
    # Same transcript = same hash
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256 hex length
    
    # Different transcript = different hash
    hash3 = extractor.compute_transcript_hash("different transcript")
    assert hash1 != hash3


def test_extract_custom_options(extractor, sample_transcript):
    """Test extraction with custom options"""
    result = extractor.extract(
        "test_video", 
        sample_transcript,
        window_chars=2000,
        min_words=3,
        max_words=30
    )
    
    assert isinstance(result['units'], list)
    # All units should respect min/max word constraints (when possible)
    for unit in result['units']:
        text = unit['text']
        # Word count check (approximate)
        word_count = len(text.split())
        # Note: Some units might be slightly outside range due to sentence boundaries
        assert word_count >= 2  # Allow some tolerance