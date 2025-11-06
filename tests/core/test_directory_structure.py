"""
Tests for directory structure creation and management.

Following TDD methodology - these tests are written FIRST and should fail initially.
Tests the new spec-compliant directory structure: output/channels/{name}/transcripts/
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from youtube_processor.core.discovery import ChannelDiscovery, VideoMetadata


class TestDirectoryStructure:
    """Test directory structure creation and management"""

    def test_creates_channel_directory(self):
        """Test 1: Creates channels/{name}/ directory structure"""
        # This test will fail initially because ChannelDiscovery doesn't return channel name yet
        discovery = ChannelDiscovery(api_key="test_key")

        with patch.object(discovery, '_api_request') as mock_api_request:
            # Mock the _api_request method responses
            def side_effect(endpoint, params):
                if endpoint == "channels":
                    # Check if this is for channel ID resolution or channel info
                    if 'forHandle' in params or 'forUsername' in params:
                        # Channel ID resolution request
                        return {
                            'items': [{
                                'id': 'UC123456789'
                            }]
                        }
                    else:
                        # Channel info request
                        return {
                            'items': [{
                                'snippet': {
                                    'title': 'IndyDevDan',
                                    'description': 'Indie game development videos',
                                    'customUrl': '@IndyDevDan'
                                }
                            }]
                        }
                elif endpoint == "search":
                    return {
                        'items': [{
                            'id': {'videoId': 'test123'},
                            'snippet': {
                                'title': 'Test Video',
                                'description': 'Test Description',
                                'publishedAt': '2023-01-01T00:00:00Z',
                                'channelId': 'UC123',
                                'channelTitle': 'IndyDevDan',
                                'tags': ['gamedev'],
                                'categoryId': '20'
                            }
                        }]
                    }
                elif endpoint == "videos":
                    return {
                        'items': [{
                            'id': 'test123',
                            'snippet': {
                                'title': 'Test Video',
                                'description': 'Test Description',
                                'publishedAt': '2023-01-01T00:00:00Z',
                                'channelId': 'UC123',
                                'channelTitle': 'IndyDevDan',
                                'tags': ['gamedev'],
                                'categoryId': '20'
                            },
                            'statistics': {
                                'viewCount': '1000',
                                'likeCount': '50',
                                'commentCount': '10'
                            },
                            'contentDetails': {
                                'duration': 'PT5M30S'
                            }
                        }]
                    }
                return {}

            mock_api_request.side_effect = side_effect

            # Test that discover_videos returns channel name and videos
            channel_name, videos = discovery.discover_videos("https://www.youtube.com/@IndyDevDan")

            assert channel_name == "IndyDevDan"
            assert isinstance(videos, list)
            assert len(videos) > 0

    def test_creates_transcripts_subdirectory(self):
        """Test 2: Creates transcripts/ subdirectory within channel directory"""
        from youtube_processor.core.extractor import DirectoryManager

        # Mock a DirectoryManager that creates the full path structure
        manager = DirectoryManager()

        # Should create output/channels/{channel_name}/transcripts/
        base_path = Path("/tmp/test_output")
        channel_name = "TestChannel"

        result_path = manager.create_channel_transcripts_dir(base_path, channel_name)

        expected_path = base_path / "channels" / channel_name / "transcripts"
        assert result_path == expected_path

    def test_output_path_format(self):
        """Test 3: Correct file naming in new structure"""
        from youtube_processor.core.extractor import PathGenerator

        generator = PathGenerator()

        # Test file path generation
        base_path = Path("/tmp/output")
        channel_name = "IndyDevDan"
        video_id = "abc123"
        video_title = "How to Make Games"

        # Should generate paths for both .json and .txt files
        json_path = generator.get_transcript_json_path(base_path, channel_name, video_id)
        txt_path = generator.get_transcript_txt_path(base_path, channel_name, video_id, video_title)

        expected_json = base_path / "channels" / channel_name / "transcripts" / f"{video_id}.json"
        expected_txt = base_path / "channels" / channel_name / "transcripts" / f"How to Make Games_{video_id}.txt"

        assert json_path == expected_json
        assert txt_path == expected_txt

    def test_channel_name_extraction(self):
        """Test 4: Gets channel name from discovery properly"""
        discovery = ChannelDiscovery(api_key="test_key")

        # Test various channel URL formats
        test_cases = [
            ("https://www.youtube.com/@IndyDevDan", "IndyDevDan"),
            ("https://www.youtube.com/channel/UC123456", "Channel Name Here"),
            ("https://www.youtube.com/c/TestChannel", "Test Channel"),
        ]

        for url, expected_name in test_cases:
            with patch.object(discovery, '_api_request') as mock_api_request:
                # Mock the _api_request method responses
                def side_effect(endpoint, params):
                    if endpoint == "channels":
                        # Check if this is for channel ID resolution or channel info
                        if 'forHandle' in params or 'forUsername' in params:
                            # Channel ID resolution request
                            return {
                                'items': [{
                                    'id': 'UC123456789'
                                }]
                            }
                        else:
                            # Channel info request
                            return {
                                'items': [{
                                    'snippet': {
                                        'title': expected_name,
                                    }
                                }]
                            }
                    elif endpoint == "search":
                        return {'items': []}
                    elif endpoint == "videos":
                        return {'items': []}
                    return {}

                mock_api_request.side_effect = side_effect

                channel_name, _ = discovery.discover_videos(url)
                assert channel_name == expected_name

    def test_analyses_directory_creation(self):
        """Test 5: Creates analyses/ directory for future analysis output"""
        from youtube_processor.core.extractor import DirectoryManager

        manager = DirectoryManager()

        base_path = Path("/tmp/test_output")
        channel_name = "TestChannel"

        # Should create output/channels/{channel_name}/analyses/
        analyses_path = manager.create_channel_analyses_dir(base_path, channel_name)

        expected_path = base_path / "channels" / channel_name / "analyses"
        assert analyses_path == expected_path

        # Should also create knowledge-base directory
        kb_path = manager.create_channel_kb_dir(base_path, channel_name)
        expected_kb_path = base_path / "channels" / channel_name / "knowledge-base"
        assert kb_path == expected_kb_path