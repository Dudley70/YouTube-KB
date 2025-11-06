"""Runner for normalizer with validation, retry, and fallback."""

import logging
from typing import List, Dict, Any
from .llm_normalizer import LLMNormalizer, TAXONOMY
from .normalizer_cache import (
    NormalizerCache, 
    CacheRecord, 
    compute_normalizer_signature
)
from .normalizer_schema import validate_normalized


logger = logging.getLogger(__name__)


class NormalizerRunner:
    """
    Orchestrates normalization with:
    - Cache lookup/write
    - Validation
    - Retry on failure
    - Fallback to safe defaults
    """
    
    def __init__(
        self,
        normalizer: LLMNormalizer,
        cache_path: str = ".cache/normalized.json",
        max_retries: int = 1
    ):
        """Initialize runner.
        
        Args:
            normalizer: LLM normalizer instance
            cache_path: Path to cache file
            max_retries: Max number of retries on failure
        """
        self.normalizer = normalizer
        self.cache = NormalizerCache(cache_path)
        self.max_retries = max_retries
        
        # Compute signature for cache invalidation
        self.normalizer_sig = compute_normalizer_signature(
            model=normalizer.model,
            template_version=normalizer.template_version,
            taxonomy=TAXONOMY
        )
    
    def run(
        self,
        video_id: str,
        candidates: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Run normalization with full pipeline.
        
        Steps:
        1. Check cache (with signature validation)
        2. If cache miss: Call normalizer
        3. Validate output
        4. Retry once on failure
        5. Fallback to safe defaults if still failing
        6. Save to cache
        
        Args:
            video_id: Video identifier
            candidates: List from DeterministicExtractor
        
        Returns:
            Normalized output matching schema
        """
        # Invalidate mismatched signatures
        for c in candidates:
            self.cache.invalidate_if_sig_mismatch(
                video_id, 
                c['id'], 
                self.normalizer_sig
            )
        
        # Check if all cached
        all_cached = all(
            self.cache.has(video_id, c['id'])
            for c in candidates
        )
        
        if all_cached:
            logger.info(f"Cache hit for all {len(candidates)} units")
            return self._reconstruct_from_cache(video_id, candidates)
        
        # Cache miss - call normalizer with retry
        result = self._normalize_with_retry(video_id, candidates)
        
        # Save to cache
        self._save_to_cache(video_id, result)
        
        return result
    
    def _reconstruct_from_cache(
        self,
        video_id: str,
        candidates: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Reconstruct output from cached records.
        
        Args:
            video_id: Video identifier
            candidates: Original candidates
            
        Returns:
            Reconstructed output
        """
        units = []
        for c in candidates:
            record = self.cache.get(video_id, c['id'])
            if not record:
                raise ValueError(f"Cache miss for unit {c['id']}")
            
            units.append({
                'id': c['id'],
                'type': record.type,
                'name': record.name,
                'summary': record.summary,
                'confidence': record.confidence
            })
        
        return {'video_id': video_id, 'units': units}
    
    def _normalize_with_retry(
        self,
        video_id: str,
        candidates: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Call normalizer with validation and retry.
        
        Args:
            video_id: Video identifier
            candidates: Candidates to normalize
            
        Returns:
            Valid result or fallback
        """
        for attempt in range(self.max_retries + 1):
            try:
                result = self.normalizer.normalize(video_id, candidates)
                
                # Validate invariants
                if not self._validate_invariants(result, candidates):
                    logger.warning(
                        f"Attempt {attempt + 1}: Invariant check failed"
                    )
                    if attempt < self.max_retries:
                        continue
                    else:
                        break
                
                # Validate schema
                is_valid, errors = validate_normalized(result)
                if not is_valid:
                    logger.warning(
                        f"Attempt {attempt + 1}: Schema validation failed: {errors}"
                    )
                    if attempt < self.max_retries:
                        continue
                    else:
                        break
                
                # Success!
                logger.info(f"Normalization succeeded on attempt {attempt + 1}")
                return result
                
            except Exception as e:
                logger.error(
                    f"Attempt {attempt + 1}: Exception during normalization: {e}"
                )
                if attempt >= self.max_retries:
                    break
        
        # All attempts failed - use fallback
        logger.warning("All normalization attempts failed, using fallback")
        return self._create_fallback(video_id, candidates)
    
    def _validate_invariants(
        self,
        result: Dict[str, Any],
        candidates: List[Dict[str, Any]]
    ) -> bool:
        """
        Validate critical invariants.
        
        Checks:
        - Same number of units
        - Same IDs in same order
        
        Args:
            result: Normalization result
            candidates: Original candidates
            
        Returns:
            True if valid, False otherwise
        """
        if len(result.get('units', [])) != len(candidates):
            logger.error(
                f"Length mismatch: got {len(result.get('units', []))}, "
                f"expected {len(candidates)}"
            )
            return False
        
        for i, (result_unit, candidate) in enumerate(
            zip(result['units'], candidates)
        ):
            if result_unit.get('id') != candidate['id']:
                logger.error(
                    f"ID mismatch at position {i}: "
                    f"got '{result_unit.get('id')}', "
                    f"expected '{candidate['id']}'"
                )
                return False
        
        return True
    
    def _create_fallback(
        self,
        video_id: str,
        candidates: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Create safe fallback output.
        
        Preserves determinism by using candidate text as summary.
        Marks as low confidence and unclear.
        
        Args:
            video_id: Video identifier
            candidates: Original candidates
            
        Returns:
            Fallback output
        """
        units = []
        for c in candidates:
            units.append({
                'id': c['id'],
                'type': 'component',  # Safe default type
                'name': '(unclear)',
                'summary': c['text'][:280],  # Truncate for schema
                'confidence': 0.3  # Low confidence marker
            })
        
        return {'video_id': video_id, 'units': units}
    
    def _save_to_cache(
        self,
        video_id: str,
        result: Dict[str, Any]
    ) -> None:
        """Save all units to cache.
        
        Args:
            video_id: Video identifier
            result: Normalization result
        """
        for unit in result['units']:
            record = CacheRecord(
                type=unit['type'],
                name=unit['name'],
                summary=unit['summary'],
                confidence=unit['confidence'],
                normalizer_sig=self.normalizer_sig
            )
            self.cache.set(video_id, unit['id'], record)
        
        self.cache.save()
        logger.info(f"Cached {len(result['units'])} units for video {video_id}")
