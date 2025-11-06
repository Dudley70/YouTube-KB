"""Test suite for CP-REFACTOR-2: Channel Discovery Module (33 tests)."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import json
from datetime import datetime

from youtube_processor.core.discovery import (
    ChannelDiscovery,
    VideoMetadata,
    ChannelMetadata,
    DiscoveryError,
    InvalidChannelError,
    APIError
)


@pytest.fixture
def discovery():
    """Create a ChannelDiscovery instance for testing."""
    return ChannelDiscovery()


@pytest.fixture
def sample_video_metadata():
    """Sample video metadata for testing."""
    return {
        "video_id": "abc123",
        "title": "Sample Video Title",
        "description": "Sample video description",
        "duration_seconds": 300,
        "upload_date": "2024-01-15",
        "view_count": 1000,
        "like_count": 50,
        "comment_count": 10,
        "channel_id": "UC123456789",
        "channel_title": "Sample Channel",
        "thumbnail_url": "https://i.ytimg.com/vi/abc123/maxresdefault.jpg",
        "tags": ["python", "tutorial"],
        "category": "Education"
    }


@pytest.fixture
def sample_channel_metadata():
    """Sample channel metadata for testing."""
    return {
        "channel_id": "UC123456789",
        "channel_title": "Sample Channel",
        "channel_url": "https://youtube.com/@samplechannel",
        "description": "Sample channel description",
        "subscriber_count": 10000,
        "video_count": 150,
        "created_date": "2020-01-01",
        "thumbnail_url": "https://yt3.ggpht.com/channel_thumbnail.jpg",
        "country": "US",
        "default_language": "en"
    }


class TestChannelDiscoveryInitialization:
    """Test ChannelDiscovery initialization and configuration."""

    def test_init_default_parameters(self):
        """Test initialization with default parameters."""
        discovery = ChannelDiscovery()
        assert discovery.api_key is None
        assert discovery.max_results == 50
        assert discovery.use_cache is True
        assert discovery.cache_dir == Path.home() / ".youtube_processor" / "cache"

    def test_init_custom_parameters(self):
        """Test initialization with custom parameters."""
        api_key = "test_api_key"
        max_results = 100
        cache_dir = Path("/tmp/test_cache")

        discovery = ChannelDiscovery(
            api_key=api_key,
            max_results=max_results,
            use_cache=False,
            cache_dir=cache_dir
        )

        assert discovery.api_key == api_key
        assert discovery.max_results == max_results
        assert discovery.use_cache is False
        assert discovery.cache_dir == cache_dir

    def test_cache_directory_creation(self):
        """Test that cache directory is created if it doesn't exist."""
        with patch('pathlib.Path.mkdir') as mock_mkdir:
            ChannelDiscovery()
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)


class TestVideoMetadata:
    """Test VideoMetadata data class."""

    def test_from_dict_complete(self, sample_video_metadata):
        """Test creating VideoMetadata from complete dictionary."""
        video = VideoMetadata.from_dict(sample_video_metadata)

        assert video.video_id == "abc123"
        assert video.title == "Sample Video Title"
        assert video.duration_seconds == 300
        assert video.upload_date == "2024-01-15"
        assert video.view_count == 1000
        assert video.tags == ["python", "tutorial"]

    def test_from_dict_minimal(self):
        """Test creating VideoMetadata with minimal required fields."""
        minimal_data = {
            "video_id": "xyz789",
            "title": "Minimal Video",
            "duration_seconds": 120,
            "upload_date": "2024-02-01"
        }

        video = VideoMetadata.from_dict(minimal_data)

        assert video.video_id == "xyz789"
        assert video.title == "Minimal Video"
        assert video.view_count == 0  # Default value
        assert video.tags == []  # Default value

    def test_from_dict_missing_required_field(self):
        """Test error when required field is missing."""
        incomplete_data = {
            "title": "Missing Video ID",
            "duration_seconds": 120
        }

        with pytest.raises(KeyError, match="video_id"):
            VideoMetadata.from_dict(incomplete_data)

    def test_to_dict(self, sample_video_metadata):
        """Test converting VideoMetadata to dictionary."""
        video = VideoMetadata.from_dict(sample_video_metadata)
        result_dict = video.to_dict()

        assert result_dict["video_id"] == "abc123"
        assert result_dict["title"] == "Sample Video Title"
        assert isinstance(result_dict, dict)
        assert len(result_dict) == len(sample_video_metadata)


class TestChannelMetadata:
    """Test ChannelMetadata data class."""

    def test_from_dict_complete(self, sample_channel_metadata):
        """Test creating ChannelMetadata from complete dictionary."""
        channel = ChannelMetadata.from_dict(sample_channel_metadata)

        assert channel.channel_id == "UC123456789"
        assert channel.channel_title == "Sample Channel"
        assert channel.subscriber_count == 10000
        assert channel.video_count == 150

    def test_to_dict(self, sample_channel_metadata):
        """Test converting ChannelMetadata to dictionary."""
        channel = ChannelMetadata.from_dict(sample_channel_metadata)
        result_dict = channel.to_dict()

        assert result_dict["channel_id"] == "UC123456789"
        assert result_dict["channel_title"] == "Sample Channel"
        assert isinstance(result_dict, dict)


class TestChannelURLParsing:
    """Test channel URL parsing functionality."""

    def test_parse_channel_url_handle(self, discovery):
        """Test parsing @handle format URL."""
        url = "https://youtube.com/@samplechannel"
        result = discovery._parse_channel_url(url)
        assert result == ("handle", "samplechannel")

    def test_parse_channel_url_channel_id(self, discovery):
        """Test parsing channel ID format URL."""
        url = "https://youtube.com/channel/UC123456789"
        result = discovery._parse_channel_url(url)
        assert result == ("channel_id", "UC123456789")

    def test_parse_channel_url_user(self, discovery):
        """Test parsing legacy user format URL."""
        url = "https://youtube.com/user/sampleuser"
        result = discovery._parse_channel_url(url)
        assert result == ("user", "sampleuser")

    def test_parse_channel_url_c_format(self, discovery):
        """Test parsing /c/ format URL."""
        url = "https://youtube.com/c/SampleChannel"
        result = discovery._parse_channel_url(url)
        assert result == ("c", "SampleChannel")

    def test_parse_channel_url_invalid(self, discovery):
        """Test error for invalid channel URL."""
        invalid_url = "https://example.com/invalid"
        with pytest.raises(InvalidChannelError, match="Invalid channel URL"):
            discovery._parse_channel_url(invalid_url)

    def test_parse_channel_url_no_protocol(self, discovery):
        """Test parsing URL without protocol."""
        url = "youtube.com/@samplechannel"
        result = discovery._parse_channel_url(url)
        assert result == ("handle", "samplechannel")


class TestChannelResolution:
    """Test channel resolution to channel ID."""

    @patch('youtube_processor.core.discovery.ChannelDiscovery._api_request')
    def test_resolve_channel_id_from_handle(self, mock_api, discovery):
        """Test resolving channel ID from @handle."""
        mock_api.return_value = {
            "items": [{
                "id": "UC123456789",
                "snippet": {"title": "Sample Channel"}
            }]
        }

        channel_id = discovery._resolve_channel_id("handle", "samplechannel")
        assert channel_id == "UC123456789"

        # Verify API call
        mock_api.assert_called_once()
        call_args = mock_api.call_args
        assert call_args[0][0] == "channels"  # First positional arg is endpoint
        params = call_args[0][1]  # Second positional arg is params dict
        assert "forHandle" in params
        assert params["forHandle"] == "samplechannel"

    @patch('youtube_processor.core.discovery.ChannelDiscovery._api_request')
    def test_resolve_channel_id_direct(self, mock_api, discovery):
        """Test when channel ID is already provided."""
        channel_id = discovery._resolve_channel_id("channel_id", "UC123456789")
        assert channel_id == "UC123456789"
        mock_api.assert_not_called()

    @patch('youtube_processor.core.discovery.ChannelDiscovery._api_request')
    def test_resolve_channel_id_not_found(self, mock_api, discovery):
        """Test error when channel is not found."""
        mock_api.return_value = {"items": []}

        with pytest.raises(InvalidChannelError, match="Channel not found"):
            discovery._resolve_channel_id("handle", "nonexistent")


class TestVideoDiscovery:
    """Test video discovery functionality."""

    @patch('youtube_processor.core.discovery.ChannelDiscovery._api_request')
    @patch('youtube_processor.core.discovery.ChannelDiscovery._resolve_channel_id')
    def test_discover_videos_success(self, mock_resolve, mock_api, discovery, sample_video_metadata):
        """Test successful video discovery."""
        mock_resolve.return_value = "UC123456789"

        # Mock the two different API calls - search and videos
        search_response = {
            "items": [{
                "id": {"videoId": "abc123"}
            }]
        }

        videos_response = {
            "items": [{
                "id": "abc123",
                "snippet": {
                    "title": "Sample Video Title",
                    "description": "Sample video description",
                    "publishedAt": "2024-01-15T10:00:00Z",
                    "channelId": "UC123456789",
                    "channelTitle": "Sample Channel",
                    "thumbnails": {"maxresdefault": {"url": "https://i.ytimg.com/vi/abc123/maxresdefault.jpg"}},
                    "tags": ["python", "tutorial"],
                    "categoryId": "27"
                },
                "contentDetails": {
                    "duration": "PT5M"
                },
                "statistics": {
                    "viewCount": "1000",
                    "likeCount": "50",
                    "commentCount": "10"
                }
            }]
        }

        # Return different responses based on endpoint
        def api_side_effect(endpoint, params):
            if endpoint == "search":
                return search_response
            elif endpoint == "videos":
                return videos_response
            return {}

        mock_api.side_effect = api_side_effect

        channel_name, videos = discovery.discover_videos("https://youtube.com/@samplechannel")

        assert channel_name == "Unknown Channel"  # Since we're not mocking channel info request
        assert len(videos) == 1
        assert isinstance(videos[0], VideoMetadata)
        assert videos[0].video_id == "abc123"
        assert videos[0].title == "Sample Video Title"

    @patch('youtube_processor.core.discovery.ChannelDiscovery._resolve_channel_id')
    def test_discover_videos_invalid_channel(self, mock_resolve, discovery):
        """Test error for invalid channel URL."""
        mock_resolve.side_effect = InvalidChannelError("Channel not found")

        with pytest.raises(InvalidChannelError):
            discovery.discover_videos("https://youtube.com/@nonexistent")

    @patch('youtube_processor.core.discovery.ChannelDiscovery._api_request')
    @patch('youtube_processor.core.discovery.ChannelDiscovery._resolve_channel_id')
    def test_discover_videos_api_error(self, mock_resolve, mock_api, discovery):
        """Test handling of API errors."""
        mock_resolve.return_value = "UC123456789"
        mock_api.side_effect = APIError("API quota exceeded")

        with pytest.raises(APIError):
            discovery.discover_videos("https://youtube.com/@samplechannel")

    @patch('youtube_processor.core.discovery.ChannelDiscovery._api_request')
    @patch('youtube_processor.core.discovery.ChannelDiscovery._resolve_channel_id')
    def test_discover_videos_with_filters(self, mock_resolve, mock_api, discovery):
        """Test video discovery with filters."""
        mock_resolve.return_value = "UC123456789"
        mock_api.return_value = {"items": []}

        discovery.discover_videos(
            "https://youtube.com/@samplechannel",
            max_results=25,
            order="date",
            published_after="2024-01-01"
        )

        # Verify API call parameters
        call_args = mock_api.call_args
        params = call_args[0][1]  # Second positional arg is params dict
        assert params["maxResults"] == 25
        assert params["order"] == "date"
        assert "publishedAfter" in params


class TestChannelMetadataDiscovery:
    """Test channel metadata discovery."""

    @patch('youtube_processor.core.discovery.ChannelDiscovery._api_request')
    @patch('youtube_processor.core.discovery.ChannelDiscovery._resolve_channel_id')
    def test_get_channel_metadata_success(self, mock_resolve, mock_api, discovery, sample_channel_metadata):
        """Test successful channel metadata retrieval."""
        mock_resolve.return_value = "UC123456789"
        mock_api.return_value = {
            "items": [{
                "id": "UC123456789",
                "snippet": {
                    "title": "Sample Channel",
                    "description": "Sample channel description",
                    "thumbnails": {"default": {"url": "https://yt3.ggpht.com/channel_thumbnail.jpg"}},
                    "country": "US",
                    "defaultLanguage": "en"
                },
                "statistics": {
                    "subscriberCount": "10000",
                    "videoCount": "150"
                },
                "contentDetails": {
                    "relatedPlaylists": {"uploads": "UU123456789"}
                }
            }]
        }

        channel = discovery.get_channel_metadata("https://youtube.com/@samplechannel")

        assert isinstance(channel, ChannelMetadata)
        assert channel.channel_id == "UC123456789"
        assert channel.channel_title == "Sample Channel"
        assert channel.subscriber_count == 10000
        assert channel.video_count == 150


class TestCaching:
    """Test caching functionality."""

    def test_cache_key_generation(self, discovery):
        """Test cache key generation for requests."""
        params = {"channelId": "UC123456789", "maxResults": 50}
        key = discovery._get_cache_key("search", params)

        assert isinstance(key, str)
        assert len(key) == 32  # MD5 hash length

        # Same params should generate same key
        key2 = discovery._get_cache_key("search", params)
        assert key == key2

        # Different params should generate different key
        key3 = discovery._get_cache_key("search", {"channelId": "UC987654321", "maxResults": 50})
        assert key != key3

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.read_text')
    def test_load_from_cache_hit(self, mock_read, mock_exists, discovery):
        """Test loading data from cache when available."""
        mock_exists.return_value = True
        mock_read.return_value = '{"items": []}'

        result = discovery._load_from_cache("test_key")

        assert result == {"items": []}
        mock_read.assert_called_once()

    @patch('pathlib.Path.exists')
    def test_load_from_cache_miss(self, mock_exists, discovery):
        """Test cache miss scenario."""
        mock_exists.return_value = False

        result = discovery._load_from_cache("test_key")

        assert result is None

    @patch('pathlib.Path.write_text')
    def test_save_to_cache(self, mock_write, discovery):
        """Test saving data to cache."""
        data = {"items": []}
        discovery._save_to_cache("test_key", data)

        mock_write.assert_called_once()
        # Verify JSON was written
        written_data = mock_write.call_args[0][0]
        assert json.loads(written_data) == data


class TestErrorHandling:
    """Test error handling and custom exceptions."""

    def test_discovery_error_creation(self):
        """Test DiscoveryError exception."""
        error = DiscoveryError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)

    def test_invalid_channel_error_creation(self):
        """Test InvalidChannelError exception."""
        error = InvalidChannelError("Invalid channel")
        assert str(error) == "Invalid channel"
        assert isinstance(error, DiscoveryError)

    def test_api_error_creation(self):
        """Test APIError exception."""
        error = APIError("API error")
        assert str(error) == "API error"
        assert isinstance(error, DiscoveryError)


class TestUtilityMethods:
    """Test utility and helper methods."""

    def test_parse_duration_iso8601(self, discovery):
        """Test parsing ISO 8601 duration format."""
        assert discovery._parse_duration("PT5M") == 300
        assert discovery._parse_duration("PT1H30M") == 5400
        assert discovery._parse_duration("PT2H") == 7200
        assert discovery._parse_duration("PT45S") == 45
        assert discovery._parse_duration("PT1H2M3S") == 3723

    def test_parse_duration_invalid(self, discovery):
        """Test parsing invalid duration format."""
        assert discovery._parse_duration("invalid") == 0
        assert discovery._parse_duration("") == 0
        assert discovery._parse_duration(None) == 0

    def test_format_date_iso(self, discovery):
        """Test formatting date from ISO format."""
        iso_date = "2024-01-15T10:30:00Z"
        formatted = discovery._format_date(iso_date)
        assert formatted == "2024-01-15"

    def test_format_date_invalid(self, discovery):
        """Test formatting invalid date."""
        formatted = discovery._format_date("invalid")
        assert formatted == "unknown"

    def test_safe_int_conversion(self, discovery):
        """Test safe integer conversion."""
        assert discovery._safe_int("123") == 123
        assert discovery._safe_int("") == 0
        assert discovery._safe_int(None) == 0
        assert discovery._safe_int("invalid") == 0