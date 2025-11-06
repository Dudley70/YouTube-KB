"""
Wrapper to call TypeScript deterministic extractor from Python.
"""
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional
import hashlib


class DeterministicExtractor:
    """
    Python interface to TypeScript deterministic extractor.
    
    Calls Node.js CLI via subprocess, handles JSON serialization,
    error handling, and timeout management.
    """
    
    def __init__(
        self, 
        node_path: str = "node",
        timeout: int = 60
    ):
        """
        Initialize extractor.
        
        Args:
            node_path: Path to node executable (default: "node")
            timeout: Subprocess timeout in seconds (default: 60)
        """
        self.node_path = node_path
        self.timeout = timeout
        
        # Find extractor path (relative to this file)
        self.extractor_path = Path(__file__).parent.parent.parent / "src" / "extractors" / "deterministic"
        self.cli_path = self.extractor_path / "src" / "cli" / "extract.js"
        
        # Validate paths exist
        if not self.extractor_path.exists():
            raise FileNotFoundError(
                f"Deterministic extractor not found at {self.extractor_path}"
            )
        if not self.cli_path.exists():
            raise FileNotFoundError(
                f"CLI script not found at {self.cli_path}"
            )
    
    def extract(
        self, 
        video_id: str, 
        transcript: str,
        include_meta: bool = True
    ) -> Dict[str, Any]:
        """
        Extract knowledge units deterministically.
        
        Args:
            video_id: Video identifier
            transcript: Raw transcript text
            include_meta: Include metadata in output (default: True)
            
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
                        'window': int,
                        'words': int
                    }
                ],
                'meta': {  # if include_meta=True
                    'windows_generated': int,
                    'candidates_scored': int,
                    'units_extracted': int,
                    'extraction_time_ms': int
                }
            }
            
        Raises:
            RuntimeError: If extraction fails
            subprocess.TimeoutExpired: If extraction times out
            json.JSONDecodeError: If output is not valid JSON
        """
        # Prepare input
        input_data = {
            'video_id': video_id,
            'transcript': transcript,
            'include_meta': include_meta
        }
        
        # Call Node.js extractor
        try:
            result = subprocess.run(
                [self.node_path, str(self.cli_path)],
                input=json.dumps(input_data),
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False  # Don't raise on non-zero exit
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(
                f"Extraction timed out after {self.timeout}s for video {video_id}"
            ) from e
        
        # Check for errors
        if result.returncode != 0:
            error_msg = result.stderr.strip() if result.stderr else "Unknown error"
            raise RuntimeError(
                f"Extraction failed for video {video_id}: {error_msg}"
            )
        
        # Parse output
        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"Invalid JSON output from extractor: {result.stdout[:200]}"
            ) from e
        
        # Validate output structure
        self._validate_output(output)
        
        return output
    
    def _validate_output(self, output: Dict[str, Any]) -> None:
        """
        Validate extraction output has required structure.
        
        Args:
            output: Extraction output to validate
            
        Raises:
            ValueError: If output is invalid
        """
        required_fields = ['video_id', 'transcript_hash', 'units']
        missing = [f for f in required_fields if f not in output]
        if missing:
            raise ValueError(f"Missing required fields: {missing}")
        
        if not isinstance(output['units'], list):
            raise ValueError("'units' must be a list")
        
        # Validate each unit
        for i, unit in enumerate(output['units']):
            unit_required = ['id', 'text', 'start', 'end', 'score', 'window']
            unit_missing = [f for f in unit_required if f not in unit]
            if unit_missing:
                raise ValueError(
                    f"Unit {i} missing required fields: {unit_missing}"
                )
    
    def compute_transcript_hash(self, transcript: str) -> str:
        """
        Compute SHA-256 hash of transcript (for determinism checking).
        
        Args:
            transcript: Raw transcript text
            
        Returns:
            Hex-encoded SHA-256 hash
        """
        return hashlib.sha256(transcript.encode('utf-8')).hexdigest()
