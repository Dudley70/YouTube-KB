"""
TranscriptExtractor for extracting YouTube video transcripts.

This module provides functionality to extract transcripts from YouTube videos
using the youtube-transcript-api library. It handles both manual and auto-generated
transcripts, with graceful fallback and error handling.
"""

from youtube_transcript_api import YouTubeTranscriptApi
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class TranscriptExtractor:
    """Extract transcripts from YouTube videos using youtube-transcript-api"""

    @staticmethod
    def extract(video_id: str, languages: List[str] = ['en']) -> Optional[str]:
        """Extract transcript text for a video.

        Args:
            video_id: YouTube video ID
            languages: Preferred languages in order (default: ['en'])

        Returns:
            Full transcript text or None if unavailable
        """
        try:
            # Get available transcripts for the video
            api = YouTubeTranscriptApi()
            transcript_list = api.list(video_id)

            # Try to find a transcript in preferred languages
            try:
                transcript = transcript_list.find_transcript(languages)
                logger.debug(f"Found transcript for video {video_id} in {transcript.language_code}")
            except Exception as e:
                logger.warning(f"No transcript found for video {video_id}: {e}")
                return None

            # Fetch and format the transcript
            entries = transcript.fetch()
            return '\n'.join([entry.text for entry in entries])

        except Exception as e:
            # No transcript available or other error
            logger.warning(f"Failed to extract transcript for video {video_id}: {e}")
            return None

    @staticmethod
    def extract_with_timestamps(video_id: str, languages: List[str] = ['en']) -> Optional[List[Dict]]:
        """Extract transcript with timestamp information.

        Args:
            video_id: YouTube video ID
            languages: Preferred languages in order (default: ['en'])

        Returns:
            List of transcript entries with timestamps or None if unavailable
        """
        try:
            # Get available transcripts for the video
            api = YouTubeTranscriptApi()
            transcript_list = api.list(video_id)

            # Try to find a transcript in preferred languages
            try:
                transcript = transcript_list.find_transcript(languages)
                logger.debug(f"Found timestamped transcript for video {video_id}")
            except Exception as e:
                logger.warning(f"No timestamped transcript found for video {video_id}: {e}")
                return None

            # Fetch the transcript with timestamps
            entries = transcript.fetch()
            return entries

        except Exception as e:
            # No transcript available or other error
            logger.warning(f"Failed to extract timestamped transcript for video {video_id}: {e}")
            return None

    @staticmethod
    def get_available_languages(video_id: str) -> List[str]:
        """Get list of available transcript languages for a video.

        Args:
            video_id: YouTube video ID

        Returns:
            List of available language codes
        """
        try:
            api = YouTubeTranscriptApi()
            transcript_list = api.list(video_id)
            languages = []

            # Get all available transcript languages
            for transcript in transcript_list:
                lang_code = transcript.language_code
                if transcript.is_generated:
                    languages.append(f"{lang_code} (auto)")
                else:
                    languages.append(lang_code)

            return languages

        except Exception as e:
            logger.warning(f"Failed to get available languages for video {video_id}: {e}")
            return []

    @staticmethod
    def is_transcript_available(video_id: str, languages: List[str] = ['en']) -> bool:
        """Check if transcript is available for a video.

        Args:
            video_id: YouTube video ID
            languages: Preferred languages to check

        Returns:
            True if transcript is available, False otherwise
        """
        try:
            api = YouTubeTranscriptApi()
            transcript_list = api.list(video_id)

            # Try to find a transcript in preferred languages
            try:
                transcript_list.find_transcript(languages)
                return True
            except Exception:
                return False

        except Exception:
            return False