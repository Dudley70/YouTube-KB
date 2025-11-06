"""
Integration tests for deterministic extraction E2E flow.
"""
import pytest
import json
from pathlib import Path
from youtube_processor.extractors.deterministic_wrapper import DeterministicExtractor


@pytest.fixture
def extractor():
    return DeterministicExtractor()


@pytest.fixture
def real_transcript():
    """Load a real transcript for testing"""
    # Try to use existing transcript from output/
    import glob
    transcript_files = glob.glob("output/channels/*/transcripts/*.md")
    
    if not transcript_files:
        pytest.skip("No transcripts found")
    
    # Use the first available transcript
    transcript_path = Path(transcript_files[0])
    
    content = transcript_path.read_text()
    # Extract just the transcript part (skip markdown headers)
    if "## Transcript" in content:
        content = content.split("## Transcript")[1]
    
    return content.strip()


def test_e2e_single_video(extractor, real_transcript):
    """Test complete extraction flow on real video"""
    
    # Extract
    result = extractor.extract("test_video_001", real_transcript)
    
    # Verify output structure
    assert result['video_id'] == "test_video_001"
    assert 'transcript_hash' in result
    assert 'units' in result
    assert isinstance(result['units'], list)
    assert len(result['units']) > 0
    assert len(result['units']) < 150  # Reasonable upper bound
    
    # Verify all units are valid
    for unit in result['units']:
        assert len(unit['text']) >= 4  # Min words check
        assert unit['start'] < unit['end']
        assert 0 <= unit['score'] <= 3.0  # Score can be high for strong matches


def test_e2e_determinism(extractor, real_transcript):
    """Test E2E determinism on real video"""
    
    # Extract 3 times
    results = [
        extractor.extract("test_video_001", real_transcript)
        for _ in range(3)
    ]
    
    # All should be identical
    first = results[0]
    for result in results[1:]:
        assert result['units'] == first['units'], "Extraction is not deterministic"
        assert result['transcript_hash'] == first['transcript_hash']


def test_e2e_performance(extractor, real_transcript):
    """Test extraction performance is reasonable"""
    import time
    
    start = time.time()
    result = extractor.extract("test_video_001", real_transcript)
    elapsed = time.time() - start
    
    # Should complete in under 5 seconds for typical video
    assert elapsed < 5.0, f"Extraction too slow: {elapsed:.2f}s"
    
    # Should extract reasonable number of units
    assert len(result['units']) > 0, "No units extracted"
