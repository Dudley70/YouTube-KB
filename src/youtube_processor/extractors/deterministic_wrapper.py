"""
Wrapper for deterministic knowledge unit extraction.

This module provides a simple interface to the deterministic extractor,
handling input validation, hash computation, and output formatting.
"""
import hashlib
from typing import Dict, Any
from .deterministic_extractor import (
    extract_deterministic_units,
    ExtractOptions,
    Unit
)


class DeterministicExtractor:
    """
    Python interface to deterministic extractor.
    
    Provides a clean API for extracting knowledge units from transcripts
    with deterministic, reproducible results.
    """
    
    def __init__(self, **kwargs):
        """
        Initialize extractor.
        
        Accepts any keyword arguments for compatibility, but they are not used.
        The Python implementation has no external dependencies.
        """
        pass
    
    def extract(
        self, 
        video_id: str, 
        transcript: str,
        include_meta: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Extract knowledge units deterministically.
        
        Args:
            video_id: Video identifier
            transcript: Raw transcript text
            include_meta: Include metadata in output (default: True)
            **kwargs: Additional options passed to extractor
            
        Returns:
            {
                'video_id': str,
                'transcript_hash': str,
                'units': [
                    {
                        'id': str,
                        'text': str,
                        'start': int,
                        'end': int,
                        'score': float,
                        'window': int
                    }
                ],
                'meta': {  # if include_meta=True
                    'extractor_version': str,
                    'window_chars': int,
                    'min_words': int,
                    'max_words': int,
                    'jaccard_threshold': float,
                    'per_window_quota': int | None,
                    'python_version': str
                }
            }
            
        Raises:
            ValueError: If transcript is empty or invalid
        """
        # Validate inputs
        if not transcript or not transcript.strip():
            raise ValueError("Transcript cannot be empty")
        
        # Build extraction options from kwargs
        opts = ExtractOptions(include_meta=include_meta)
        
        # Override defaults with any provided kwargs
        if 'window_chars' in kwargs:
            opts.window_chars = kwargs['window_chars']
        if 'target_count' in kwargs:
            opts.target_count = kwargs['target_count']
        if 'min_words' in kwargs:
            opts.min_words = kwargs['min_words']
        if 'max_words' in kwargs:
            opts.max_words = kwargs['max_words']
        if 'jaccard_threshold' in kwargs:
            opts.jaccard_threshold = kwargs['jaccard_threshold']
        if 'per_window_quota' in kwargs:
            opts.per_window_quota = kwargs['per_window_quota']
        
        # Extract units
        result = extract_deterministic_units(transcript, opts)
        
        # Compute transcript hash for determinism verification
        transcript_hash = self.compute_transcript_hash(transcript)
        
        # Format output
        output = {
            'video_id': video_id,
            'transcript_hash': transcript_hash,
            'units': [
                {
                    'id': u.id,
                    'text': u.text,
                    'start': u.start,
                    'end': u.end,
                    'score': u.score,
                    'window': u.window
                }
                for u in result.units
            ]
        }
        
        # Add metadata if requested
        if include_meta and result.meta:
            output['meta'] = result.meta
        
        return output
    
    def compute_transcript_hash(self, transcript: str) -> str:
        """
        Compute SHA-256 hash of transcript (for determinism checking).
        
        Args:
            transcript: Raw transcript text
            
        Returns:
            Hex-encoded SHA-256 hash
        """
        return hashlib.sha256(transcript.encode('utf-8')).hexdigest()
