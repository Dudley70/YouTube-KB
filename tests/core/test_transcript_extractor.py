"""
Tests for TranscriptExtractor class.

Following TDD methodology - these tests are written FIRST and should fail initially.
"""

import pytest
from unittest.mock import patch, MagicMock
from youtube_processor.core.transcript_extractor import TranscriptExtractor


class TestTranscriptExtractor:
    """Test TranscriptExtractor functionality"""

    def test_extract_transcript_text(self):
        """Test 1: Returns transcript string for valid video"""
        # This test will fail initially because TranscriptExtractor doesn't exist yet
        extractor = TranscriptExtractor()

        # Use a known video ID that typically has transcripts
        # Note: This will be mocked in real tests to avoid API calls
        with patch('youtube_processor.core.transcript_extractor.YouTubeTranscriptApi') as mock_api:
            # Mock the API response
            mock_transcript_list = MagicMock()
            mock_transcript = MagicMock()
            mock_transcript.fetch.return_value = [
                {'text': 'Hello everyone', 'start': 0.0, 'duration': 2.0},
                {'text': 'Welcome to my channel', 'start': 2.0, 'duration': 3.0},
                {'text': 'Today we will learn programming', 'start': 5.0, 'duration': 4.0}
            ]
            mock_transcript_list.find_manually_created_transcript.return_value = mock_transcript
            mock_api.list_transcripts.return_value = mock_transcript_list

            text = extractor.extract("dQw4w9WgXcQ")

            assert text is not None
            assert isinstance(text, str)
            assert len(text) > 10
            assert "Hello everyone" in text
            assert "Welcome to my channel" in text
            assert "Today we will learn programming" in text

    def test_extract_transcript_with_timestamps(self):
        """Test 2: Returns timestamped entries with proper structure"""
        extractor = TranscriptExtractor()

        with patch('youtube_processor.core.transcript_extractor.YouTubeTranscriptApi') as mock_api:
            # Mock timestamped response
            mock_transcript_list = MagicMock()
            mock_transcript = MagicMock()
            expected_data = [
                {'text': 'Introduction', 'start': 0.0, 'duration': 2.5},
                {'text': 'Main content', 'start': 2.5, 'duration': 5.0}
            ]
            mock_transcript.fetch.return_value = expected_data
            mock_transcript_list.find_manually_created_transcript.return_value = mock_transcript
            mock_api.list_transcripts.return_value = mock_transcript_list

            entries = extractor.extract_with_timestamps("test_video_id")

            assert entries is not None
            assert isinstance(entries, list)
            assert len(entries) == 2
            assert entries[0]['text'] == 'Introduction'
            assert entries[0]['start'] == 0.0
            assert entries[1]['text'] == 'Main content'
            assert entries[1]['start'] == 2.5

    def test_extract_handles_no_transcript(self):
        """Test 3: Graceful failure when no transcript available"""
        extractor = TranscriptExtractor()

        with patch('youtube_processor.core.transcript_extractor.YouTubeTranscriptApi') as mock_api:
            # Mock exception for no transcript
            mock_api.list_transcripts.side_effect = Exception("No transcript available")

            text = extractor.extract("invalid_video_id")

            # Should return None, not raise exception
            assert text is None

    def test_extract_multiple_languages(self):
        """Test 4: Gets English transcript when multiple languages available"""
        extractor = TranscriptExtractor()

        with patch('youtube_processor.core.transcript_extractor.YouTubeTranscriptApi') as mock_api:
            mock_transcript_list = MagicMock()
            mock_transcript = MagicMock()
            mock_transcript.fetch.return_value = [
                {'text': 'Hello in English', 'start': 0.0, 'duration': 2.0}
            ]
            # Should try to find English transcript specifically
            mock_transcript_list.find_manually_created_transcript.return_value = mock_transcript
            mock_api.list_transcripts.return_value = mock_transcript_list

            text = extractor.extract("multi_lang_video", languages=['en', 'es', 'fr'])

            assert text is not None
            assert "Hello in English" in text
            # Verify it was called with the language preference
            mock_transcript_list.find_manually_created_transcript.assert_called_with(['en', 'es', 'fr'])

    def test_extract_auto_generated_fallback(self):
        """Test 5: Falls back to auto-generated captions when manual not available"""
        extractor = TranscriptExtractor()

        with patch('youtube_processor.core.transcript_extractor.YouTubeTranscriptApi') as mock_api:
            mock_transcript_list = MagicMock()
            mock_auto_transcript = MagicMock()
            mock_auto_transcript.fetch.return_value = [
                {'text': 'Auto-generated content', 'start': 0.0, 'duration': 3.0}
            ]

            # Manual transcript not available
            mock_transcript_list.find_manually_created_transcript.side_effect = Exception("No manual transcript")
            # But auto-generated is available
            mock_transcript_list.find_generated_transcript.return_value = mock_auto_transcript
            mock_api.list_transcripts.return_value = mock_transcript_list

            text = extractor.extract("auto_gen_video")

            assert text is not None
            assert "Auto-generated content" in text
            # Verify fallback was attempted
            mock_transcript_list.find_manually_created_transcript.assert_called_once()
            mock_transcript_list.find_generated_transcript.assert_called_once()