"""Extraction history management."""

import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)


class ExtractionHistory:
    """Manages extraction history and checkpoints."""

    def __init__(self, history_file: Optional[Path] = None):
        """Initialize extraction history manager.

        Args:
            history_file: Path to history file
        """
        self.history_file = history_file or Path.home() / ".youtube_processor" / "history.json"

        # Ensure directory exists
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

        # Initialize empty history if file doesn't exist
        if not self.history_file.exists():
            self._save_history([])

    def add_extraction(self, video_id: str, metadata: Dict[str, Any]) -> None:
        """Add an extraction record.

        Args:
            video_id: YouTube video ID
            metadata: Extraction metadata
        """
        try:
            history = self._load_history()

            # Create extraction record
            record = {
                'video_id': video_id,
                'timestamp': metadata.get('timestamp', datetime.now().isoformat()),
                'success': metadata.get('success', False),
                'output_path': metadata.get('output_path'),
                'error': metadata.get('error'),
                'file_size': metadata.get('file_size'),
                'title': metadata.get('title', ''),
                'status': 'completed' if metadata.get('success', False) else 'failed'
            }

            # Add to history (most recent first)
            history.insert(0, record)

            # Keep only last 1000 records
            if len(history) > 1000:
                history = history[:1000]

            self._save_history(history)

        except Exception as e:
            logger.error(f"Failed to add extraction record: {e}")

    def get_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get extraction history.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of extraction records
        """
        try:
            history = self._load_history()

            if limit:
                return history[:limit]

            return history

        except Exception as e:
            logger.error(f"Failed to load history: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """Get extraction statistics.

        Returns:
            Dictionary with statistics
        """
        try:
            history = self._load_history()

            total_extractions = len(history)
            successful_extractions = len([r for r in history if r.get('success', False)])
            failed_extractions = total_extractions - successful_extractions

            # Calculate total size
            total_size = sum(
                r.get('file_size', 0) or 0
                for r in history
                if r.get('success', False) and r.get('file_size')
            )

            return {
                'total_extractions': total_extractions,
                'successful_extractions': successful_extractions,
                'failed_extractions': failed_extractions,
                'total_size': total_size,
                'success_rate': (successful_extractions / total_extractions * 100) if total_extractions > 0 else 0
            }

        except Exception as e:
            logger.error(f"Failed to calculate stats: {e}")
            return {
                'total_extractions': 0,
                'successful_extractions': 0,
                'failed_extractions': 0,
                'total_size': 0,
                'success_rate': 0
            }

    def _load_history(self) -> List[Dict[str, Any]]:
        """Load history from file.

        Returns:
            List of extraction records
        """
        try:
            if not self.history_file.exists():
                return []

            with open(self.history_file, 'r') as f:
                return json.load(f)

        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load history file: {e}")
            return []

    def _save_history(self, history: List[Dict[str, Any]]) -> None:
        """Save history to file.

        Args:
            history: List of extraction records
        """
        try:
            with open(self.history_file, 'w') as f:
                json.dump(history, f, indent=2, default=str)

        except IOError as e:
            logger.error(f"Failed to save history file: {e}")