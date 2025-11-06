"""Tests for normalizer runner."""

import pytest
import tempfile
from pathlib import Path
from youtube_processor.llm.normalizer_runner import NormalizerRunner


class MockNormalizer:
    """Mock normalizer for testing."""
    
    def __init__(self, return_value=None, raise_error=False):
        self.return_value = return_value
        self.raise_error = raise_error
        self.model = "test-model"
        self.template_version = "test-version"
        self.call_count = 0
    
    def normalize(self, video_id, candidates):
        self.call_count += 1
        if self.raise_error:
            raise ValueError("Test error")
        if self.return_value:
            return self.return_value
        # Default: valid output
        return {
            "video_id": video_id,
            "units": [
                {
                    "id": c['id'],
                    "type": "technique",
                    "name": f"Name {i}",
                    "summary": f"Summary {i}",
                    "confidence": 0.85
                }
                for i, c in enumerate(candidates)
            ]
        }


@pytest.fixture
def temp_cache():
    """Create temporary cache file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        cache_path = f.name
    yield cache_path
    Path(cache_path).unlink(missing_ok=True)


def test_length_mismatch_triggers_fallback(temp_cache):
    """Test that output length must match input."""
    candidates = [
        {"id": "u1", "text": "test1", "start": 0, "end": 10, "window": 0, "score": 0.9},
        {"id": "u2", "text": "test2", "start": 10, "end": 20, "window": 1, "score": 0.8}
    ]
    
    # Mock normalizer that drops a unit
    bad_normalizer = MockNormalizer(return_value={
        "video_id": "vid1",
        "units": [{"id": "u1", "type": "technique", "name": "Test", 
                  "summary": "Test", "confidence": 0.8}]
        # Missing u2!
    })
    
    runner = NormalizerRunner(bad_normalizer, cache_path=temp_cache, max_retries=0)
    result = runner.run("vid1", candidates)
    
    # Should fall back and preserve both units
    assert len(result['units']) == 2
    assert result['units'][0]['id'] == "u1"
    assert result['units'][1]['id'] == "u2"
    assert result['units'][1]['name'] == "(unclear)"  # Fallback marker


def test_id_mismatch_triggers_fallback(temp_cache):
    """Test that IDs must match exactly."""
    candidates = [{"id": "u1", "text": "test", "start": 0, "end": 10, 
                   "window": 0, "score": 0.9}]
    
    bad_normalizer = MockNormalizer(return_value={
        "video_id": "vid1",
        "units": [{"id": "WRONG_ID", "type": "technique", 
                  "name": "Test", "summary": "Test", "confidence": 0.8}]
    })
    
    runner = NormalizerRunner(bad_normalizer, cache_path=temp_cache, max_retries=0)
    result = runner.run("vid1", candidates)
    
    # Should fall back with correct ID
    assert result['units'][0]['id'] == "u1"
    assert result['units'][0]['name'] == "(unclear)"


def test_schema_validation_failure_triggers_fallback(temp_cache):
    """Test that schema validation failure triggers fallback."""
    candidates = [{"id": "u1", "text": "test", "start": 0, "end": 10, 
                   "window": 0, "score": 0.9}]
    
    bad_normalizer = MockNormalizer(return_value={
        "video_id": "vid1",
        "units": [{"id": "u1", "type": "INVALID_TYPE",  # Wrong enum
                  "name": "Test", "summary": "Test", "confidence": 0.8}]
    })
    
    runner = NormalizerRunner(bad_normalizer, cache_path=temp_cache, max_retries=0)
    result = runner.run("vid1", candidates)
    
    # Should fall back
    assert result['units'][0]['name'] == "(unclear)"
    assert result['units'][0]['confidence'] == 0.3


def test_exception_triggers_fallback(temp_cache):
    """Test that exceptions trigger fallback."""
    candidates = [{"id": "u1", "text": "test", "start": 0, "end": 10, 
                   "window": 0, "score": 0.9}]
    
    bad_normalizer = MockNormalizer(raise_error=True)
    
    runner = NormalizerRunner(bad_normalizer, cache_path=temp_cache, max_retries=0)
    result = runner.run("vid1", candidates)
    
    # Should fall back
    assert result['units'][0]['name'] == "(unclear)"


def test_retry_logic(temp_cache):
    """Test that normalizer is retried on failure."""
    candidates = [{"id": "u1", "text": "test", "start": 0, "end": 10, 
                   "window": 0, "score": 0.9}]
    
    bad_normalizer = MockNormalizer(return_value={
        "video_id": "vid1",
        "units": []  # Invalid length
    })
    
    runner = NormalizerRunner(bad_normalizer, cache_path=temp_cache, max_retries=2)
    result = runner.run("vid1", candidates)
    
    # Should retry 3 times (initial + 2 retries)
    assert bad_normalizer.call_count == 3
    # Should eventually fall back
    assert result['units'][0]['name'] == "(unclear)"


def test_cache_hit_skips_normalization(temp_cache):
    """Test that cache hits skip LLM calls."""
    candidates = [{"id": "u1", "text": "test", "start": 0, "end": 10, 
                   "window": 0, "score": 0.9}]
    
    normalizer = MockNormalizer()
    runner = NormalizerRunner(normalizer, cache_path=temp_cache)
    
    # First call - should hit normalizer
    result1 = runner.run("vid1", candidates)
    assert normalizer.call_count == 1
    
    # Second call - should hit cache
    result2 = runner.run("vid1", candidates)
    assert normalizer.call_count == 1  # No additional call
    
    # Results should be identical
    assert result1 == result2


def test_fallback_preserves_determinism(temp_cache):
    """Test that fallback output is deterministic."""
    candidates = [
        {"id": "u1", "text": "test content 1", "start": 0, "end": 10, 
         "window": 0, "score": 0.9},
        {"id": "u2", "text": "test content 2", "start": 10, "end": 20, 
         "window": 1, "score": 0.8}
    ]
    
    bad_normalizer = MockNormalizer(raise_error=True)
    runner = NormalizerRunner(bad_normalizer, cache_path=temp_cache, max_retries=0)
    
    # Multiple runs should produce identical fallback
    result1 = runner.run("vid1", candidates)
    result2 = runner.run("vid1", candidates)
    
    assert result1 == result2
    assert result1['units'][0]['summary'] == candidates[0]['text'][:280]
    assert result1['units'][1]['summary'] == candidates[1]['text'][:280]


def test_cache_reconstruction(temp_cache):
    """Test that cache is properly reconstructed from individual records."""
    candidates = [
        {"id": "u1", "text": "test1", "start": 0, "end": 10, 
         "window": 0, "score": 0.9},
        {"id": "u2", "text": "test2", "start": 10, "end": 20, 
         "window": 1, "score": 0.8}
    ]
    
    normalizer = MockNormalizer()
    runner = NormalizerRunner(normalizer, cache_path=temp_cache)
    
    # First run primes cache
    result1 = runner.run("vid1", candidates)
    
    # Second run should reconstruct from cache
    result2 = runner.run("vid1", candidates)
    
    # Should be identical
    assert result1 == result2
    assert len(result2['units']) == 2
    assert result2['units'][0]['type'] == 'technique'
    assert result2['units'][1]['type'] == 'technique'
