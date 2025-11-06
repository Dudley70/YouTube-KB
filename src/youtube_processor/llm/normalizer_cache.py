"""Cache for normalized units with version signature."""

import json
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict


@dataclass
class CacheRecord:
    """Single cached normalization result."""
    type: str
    name: str
    summary: str
    confidence: float
    normalizer_sig: str


class NormalizerCache:
    """
    Version-aware cache for normalized units.
    
    Key format: {video_id}:{unit_id}
    Value: CacheRecord with signature
    
    Invalidates entries when normalizer signature changes.
    """
    
    def __init__(self, cache_path: str = ".cache/normalized.json"):
        """Initialize cache.
        
        Args:
            cache_path: Path to cache file
        """
        self.cache_path = Path(cache_path)
        self.data: Dict[str, Dict[str, Any]] = {}
        self._load()
    
    def _load(self) -> None:
        """Load cache from disk."""
        if self.cache_path.exists():
            try:
                raw = json.loads(self.cache_path.read_text())
                self.data = raw
            except (json.JSONDecodeError, TypeError):
                self.data = {}
    
    def _key(self, video_id: str, unit_id: str) -> str:
        """Generate cache key."""
        return f"{video_id}:{unit_id}"
    
    def get(self, video_id: str, unit_id: str) -> Optional[CacheRecord]:
        """Get cached record.
        
        Args:
            video_id: Video identifier
            unit_id: Unit identifier
            
        Returns:
            CacheRecord if found, None otherwise
        """
        raw = self.data.get(self._key(video_id, unit_id))
        if raw:
            return CacheRecord(**raw)
        return None
    
    def set(self, video_id: str, unit_id: str, record: CacheRecord) -> None:
        """Set cached record.
        
        Args:
            video_id: Video identifier
            unit_id: Unit identifier
            record: Record to cache
        """
        self.data[self._key(video_id, unit_id)] = asdict(record)
    
    def has(self, video_id: str, unit_id: str) -> bool:
        """Check if record exists.
        
        Args:
            video_id: Video identifier
            unit_id: Unit identifier
            
        Returns:
            True if cached, False otherwise
        """
        return self._key(video_id, unit_id) in self.data
    
    def invalidate_if_sig_mismatch(
        self, 
        video_id: str, 
        unit_id: str, 
        current_sig: str
    ) -> bool:
        """
        Invalidate cached entry if signature doesn't match.
        
        Args:
            video_id: Video identifier
            unit_id: Unit identifier
            current_sig: Current normalizer signature
            
        Returns:
            True if invalidated, False if not found or sig matches
        """
        record = self.get(video_id, unit_id)
        if record and record.normalizer_sig != current_sig:
            del self.data[self._key(video_id, unit_id)]
            return True
        return False
    
    def save(self) -> None:
        """Save cache to disk."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self.data, indent=2))


def compute_normalizer_signature(
    model: str,
    template_version: str,
    taxonomy: list[str]
) -> str:
    """
    Compute version signature for normalizer configuration.
    
    Changes to model, template, or taxonomy invalidate cache.
    
    Args:
        model: Model name
        template_version: Template version
        taxonomy: List of allowed types
        
    Returns:
        SHA-256 hex digest of configuration
    """
    config = {
        "model": model,
        "template_version": template_version,
        "taxonomy": sorted(taxonomy)
    }
    config_str = json.dumps(config, sort_keys=True)
    return hashlib.sha256(config_str.encode()).hexdigest()
