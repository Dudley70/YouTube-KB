"""Tests for normalizer cache."""

import pytest
import tempfile
from pathlib import Path
from youtube_processor.llm.normalizer_cache import (
    NormalizerCache,
    CacheRecord,
    compute_normalizer_signature
)


@pytest.fixture
def temp_cache_file():
    """Create temporary cache file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        cache_path = f.name
    yield cache_path
    # Cleanup
    Path(cache_path).unlink(missing_ok=True)


def test_cache_save_and_load(temp_cache_file):
    """Test that cache persists and loads correctly."""
    # Create cache and add record
    cache = NormalizerCache(temp_cache_file)
    record = CacheRecord(
        type="technique",
        name="Test Technique",
        summary="A test summary",
        confidence=0.85,
        normalizer_sig="sig123"
    )
    cache.set("vid1", "unit1", record)
    cache.save()
    
    # Load fresh cache
    cache2 = NormalizerCache(temp_cache_file)
    retrieved = cache2.get("vid1", "unit1")
    
    assert retrieved is not None
    assert retrieved.type == "technique"
    assert retrieved.name == "Test Technique"
    assert retrieved.summary == "A test summary"
    assert retrieved.confidence == 0.85
    assert retrieved.normalizer_sig == "sig123"


def test_cache_has(temp_cache_file):
    """Test cache membership check."""
    cache = NormalizerCache(temp_cache_file)
    
    assert not cache.has("vid1", "unit1")
    
    record = CacheRecord(
        type="technique",
        name="Test",
        summary="Test",
        confidence=0.85,
        normalizer_sig="sig123"
    )
    cache.set("vid1", "unit1", record)
    
    assert cache.has("vid1", "unit1")
    assert not cache.has("vid1", "unit2")


def test_signature_invalidation(temp_cache_file):
    """Test that signature mismatch invalidates cache entry."""
    cache = NormalizerCache(temp_cache_file)
    
    record = CacheRecord(
        type="technique",
        name="Test",
        summary="Test",
        confidence=0.85,
        normalizer_sig="old_sig"
    )
    cache.set("vid1", "unit1", record)
    
    # Same signature - no invalidation
    invalidated = cache.invalidate_if_sig_mismatch("vid1", "unit1", "old_sig")
    assert not invalidated
    assert cache.has("vid1", "unit1")
    
    # Different signature - should invalidate
    invalidated = cache.invalidate_if_sig_mismatch("vid1", "unit1", "new_sig")
    assert invalidated
    assert not cache.has("vid1", "unit1")


def test_compute_signature_deterministic():
    """Test that signature computation is deterministic."""
    sig1 = compute_normalizer_signature(
        model="claude-haiku",
        template_version="v2.1",
        taxonomy=["technique", "pattern"]
    )
    
    sig2 = compute_normalizer_signature(
        model="claude-haiku",
        template_version="v2.1",
        taxonomy=["technique", "pattern"]
    )
    
    assert sig1 == sig2


def test_compute_signature_changes_on_config_change():
    """Test that signature changes when config changes."""
    sig1 = compute_normalizer_signature(
        model="claude-haiku",
        template_version="v2.1",
        taxonomy=["technique", "pattern"]
    )
    
    # Different model
    sig2 = compute_normalizer_signature(
        model="claude-sonnet",
        template_version="v2.1",
        taxonomy=["technique", "pattern"]
    )
    
    assert sig1 != sig2
    
    # Different template
    sig3 = compute_normalizer_signature(
        model="claude-haiku",
        template_version="v2.2",
        taxonomy=["technique", "pattern"]
    )
    
    assert sig1 != sig3


def test_cache_multiple_videos(temp_cache_file):
    """Test caching for multiple videos."""
    cache = NormalizerCache(temp_cache_file)
    
    # Video 1
    cache.set("vid1", "u1", CacheRecord("technique", "T1", "S1", 0.8, "sig"))
    cache.set("vid1", "u2", CacheRecord("pattern", "P1", "S2", 0.9, "sig"))
    
    # Video 2
    cache.set("vid2", "u1", CacheRecord("use-case", "UC1", "S3", 0.7, "sig"))
    
    # All should be retrievable
    assert cache.get("vid1", "u1").type == "technique"
    assert cache.get("vid1", "u2").type == "pattern"
    assert cache.get("vid2", "u1").type == "use-case"
    
    # Different videos don't interfere
    assert cache.get("vid1", "u1").name == "T1"
    assert cache.get("vid2", "u1").name == "UC1"
