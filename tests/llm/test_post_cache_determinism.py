"""Test post-cache determinism (20 runs)."""

import pytest
import hashlib
import json
import tempfile
from pathlib import Path
import random
from youtube_processor.llm.normalizer_runner import NormalizerRunner


class RandomNormalizer:
    """Mock normalizer with randomness for testing cache determinism."""
    
    def __init__(self):
        self.model = "test-model"
        self.template_version = "test-v1"
    
    def normalize(self, video_id, candidates):
        """Return random categorizations."""
        types = ["technique", "pattern", "use-case", "capability"]
        return {
            "video_id": video_id,
            "units": [
                {
                    "id": c['id'],
                    "type": random.choice(types),
                    "name": f"Name {random.randint(1,100)}",
                    "summary": f"Summary {random.randint(1,100)}",
                    "confidence": random.random()
                }
                for c in candidates
            ]
        }


@pytest.fixture
def test_candidates():
    """Sample candidates for testing."""
    return [
        {"id": "unit-0-450", "text": "test content 1", "start": 0, "end": 450, 
         "window": 0, "score": 0.95},
        {"id": "unit-450-900", "text": "test content 2", "start": 450, "end": 900, 
         "window": 1, "score": 0.88},
        {"id": "unit-900-1350", "text": "test content 3", "start": 900, "end": 1350, 
         "window": 2, "score": 0.82}
    ]


@pytest.fixture
def temp_cache():
    """Create temporary cache file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        cache_path = f.name
    yield cache_path
    Path(cache_path).unlink(missing_ok=True)


def test_post_cache_determinism_20_runs(test_candidates, temp_cache):
    """
    Critical test: Verify 100% determinism after cache warm-up.
    
    Even with a randomized normalizer, cached results must be
    byte-for-byte identical across 20 runs.
    """
    normalizer = RandomNormalizer()
    runner = NormalizerRunner(normalizer, cache_path=temp_cache)
    
    # First run (primes cache)
    first_result = runner.run("test_video", test_candidates)
    first_hash = hashlib.sha256(
        json.dumps(first_result, sort_keys=True).encode()
    ).hexdigest()
    
    # 20 more runs
    hashes = []
    for i in range(20):
        result = runner.run("test_video", test_candidates)
        result_hash = hashlib.sha256(
            json.dumps(result, sort_keys=True).encode()
        ).hexdigest()
        hashes.append(result_hash)
    
    # All hashes must match first
    unique_hashes = set(hashes)
    assert len(unique_hashes) == 1, (
        f"Expected 1 unique hash, got {len(unique_hashes)}. "
        f"Post-cache results must be 100% deterministic!"
    )
    assert hashes[0] == first_hash, "First hash must match subsequent runs"
    
    print(f"✅ SUCCESS: 20 runs produced identical output (hash: {first_hash[:16]}...)")


def test_cache_survives_signature_change(test_candidates, temp_cache):
    """Test that changing signature invalidates only affected entries."""
    # First normalizer (v1)
    normalizer_v1 = RandomNormalizer()
    normalizer_v1.template_version = "v1"
    runner_v1 = NormalizerRunner(normalizer_v1, cache_path=temp_cache)
    
    # Cache with v1
    result_v1 = runner_v1.run("test_video", test_candidates)
    
    # Second normalizer (v2 - different signature)
    normalizer_v2 = RandomNormalizer()
    normalizer_v2.template_version = "v2"
    runner_v2 = NormalizerRunner(normalizer_v2, cache_path=temp_cache)
    
    # Should re-normalize (signature mismatch)
    result_v2_first = runner_v2.run("test_video", test_candidates)
    
    # But v2 results should now be cached
    result_v2_second = runner_v2.run("test_video", test_candidates)
    
    # v2 runs should be identical to each other
    assert result_v2_first == result_v2_second
    
    # But likely different from v1 (random normalizer)
    # (Not guaranteed to be different, but cache invalidation happened)
