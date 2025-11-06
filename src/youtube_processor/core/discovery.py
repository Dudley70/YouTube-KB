"""Channel and video discovery functionality."""

import re
import json
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import urllib.parse
import isodate
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Configure logging
logger = logging.getLogger(__name__)


class DiscoveryError(Exception):
    """Base exception for discovery operations."""
    pass


class InvalidChannelError(DiscoveryError):
    """Raised when channel URL or ID is invalid."""
    pass


class APIError(DiscoveryError):
    """Raised when YouTube API encounters an error."""
    pass


@dataclass
class VideoMetadata:
    """Video metadata container."""
    video_id: str
    title: str
    description: str = ""
    duration_seconds: int = 0
    upload_date: str = ""
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    channel_id: str = ""
    channel_title: str = ""
    thumbnail_url: str = ""
    tags: List[str] = None
    category: str = ""

    def __post_init__(self):
        """Initialize default values."""
        if self.tags is None:
            self.tags = []

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VideoMetadata":
        """Create VideoMetadata from dictionary."""
        return cls(
            video_id=data["video_id"],
            title=data["title"],
            description=data.get("description", ""),
            duration_seconds=data.get("duration_seconds", 0),
            upload_date=data.get("upload_date", ""),
            view_count=data.get("view_count", 0),
            like_count=data.get("like_count", 0),
            comment_count=data.get("comment_count", 0),
            channel_id=data.get("channel_id", ""),
            channel_title=data.get("channel_title", ""),
            thumbnail_url=data.get("thumbnail_url", ""),
            tags=data.get("tags", []),
            category=data.get("category", "")
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class ChannelMetadata:
    """Channel metadata container."""
    channel_id: str
    channel_title: str
    channel_url: str = ""
    description: str = ""
    subscriber_count: int = 0
    video_count: int = 0
    created_date: str = ""
    thumbnail_url: str = ""
    country: str = ""
    default_language: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChannelMetadata":
        """Create ChannelMetadata from dictionary."""
        return cls(
            channel_id=data["channel_id"],
            channel_title=data["channel_title"],
            channel_url=data.get("channel_url", ""),
            description=data.get("description", ""),
            subscriber_count=data.get("subscriber_count", 0),
            video_count=data.get("video_count", 0),
            created_date=data.get("created_date", ""),
            thumbnail_url=data.get("thumbnail_url", ""),
            country=data.get("country", ""),
            default_language=data.get("default_language", "")
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class ChannelDiscovery:
    """Discovers videos from YouTube channels."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        max_results: int = 50,
        use_cache: bool = True,
        cache_dir: Optional[Path] = None
    ):
        """Initialize channel discovery.

        Args:
            api_key: YouTube Data API key
            max_results: Maximum results per request
            use_cache: Whether to use caching
            cache_dir: Cache directory path
        """
        self.api_key = api_key
        self.max_results = max_results
        self.use_cache = use_cache
        self.cache_dir = cache_dir or Path.home() / ".youtube_processor" / "cache"

        # Create cache directory
        if self.use_cache:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Initialize YouTube API client
        self._youtube = None
        if self.api_key:
            try:
                self._youtube = build('youtube', 'v3', developerKey=self.api_key)
            except Exception as e:
                logger.warning(f"Failed to initialize YouTube API client: {e}")

    def discover_videos(
        self,
        channel_url: str,
        max_results: Optional[int] = None,
        order: str = "relevance",
        published_after: Optional[str] = None,
        published_before: Optional[str] = None
    ) -> Tuple[str, List[VideoMetadata]]:
        """Discover videos from a channel URL.

        Args:
            channel_url: YouTube channel URL
            max_results: Maximum number of videos to discover
            order: Sort order (relevance, date, viewCount, etc.)
            published_after: Filter videos published after this date (YYYY-MM-DD)
            published_before: Filter videos published before this date (YYYY-MM-DD)

        Returns:
            Tuple of (channel_name, list_of_videos)
        """
        logger.info(f"Discovering videos from: {channel_url}")

        try:
            # Parse and resolve channel URL to channel ID
            url_type, identifier = self._parse_channel_url(channel_url)
            channel_id = self._resolve_channel_id(url_type, identifier)

            # Get channel information to extract channel name
            channel_response = self._api_request("channels", {
                "part": "snippet",
                "id": channel_id
            })

            channel_name = "Unknown Channel"
            if channel_response.get("items"):
                channel_name = channel_response["items"][0]["snippet"]["title"]

            logger.info(f"Channel: {channel_name} (ID: {channel_id})")

            # Prepare search parameters
            max_results = max_results or self.max_results
            params = {
                "part": "id,snippet",
                "channelId": channel_id,
                "type": "video",
                "maxResults": min(max_results, 50),  # API limit
                "order": order
            }

            # Add date filters if provided
            if published_after:
                params["publishedAfter"] = f"{published_after}T00:00:00Z"
            if published_before:
                params["publishedBefore"] = f"{published_before}T23:59:59Z"

            # Get video list from search
            search_response = self._api_request("search", params)
            video_ids = []
            for item in search_response.get("items", []):
                video_id = item.get("id", {})
                if isinstance(video_id, dict) and "videoId" in video_id:
                    video_ids.append(video_id["videoId"])
                elif isinstance(video_id, str):
                    video_ids.append(video_id)

            if not video_ids:
                logger.info("No videos found")
                return channel_name, []

            # Get detailed video information
            videos_response = self._api_request("videos", {
                "part": "snippet,contentDetails,statistics",
                "id": ",".join(video_ids)
            })

            # Convert to VideoMetadata objects
            videos = []
            for item in videos_response.get("items", []):
                try:
                    video = self._parse_video_item(item)
                    videos.append(video)
                except Exception as e:
                    logger.warning(f"Failed to parse video {item.get('id')}: {e}")
                    continue

            logger.info(f"Discovered {len(videos)} videos")
            return channel_name, videos

        except Exception as e:
            if isinstance(e, (InvalidChannelError, APIError)):
                raise
            raise DiscoveryError(f"Failed to discover videos: {e}")

    def get_channel_metadata(self, channel_url: str) -> ChannelMetadata:
        """Get channel metadata.

        Args:
            channel_url: YouTube channel URL

        Returns:
            ChannelMetadata object
        """
        logger.info(f"Getting channel metadata for: {channel_url}")

        try:
            # Parse and resolve channel URL to channel ID
            url_type, identifier = self._parse_channel_url(channel_url)
            channel_id = self._resolve_channel_id(url_type, identifier)

            # Get channel information
            response = self._api_request("channels", {
                "part": "snippet,statistics,contentDetails",
                "id": channel_id
            })

            items = response.get("items", [])
            if not items:
                raise InvalidChannelError(f"Channel not found: {channel_url}")

            return self._parse_channel_item(items[0], channel_url)

        except Exception as e:
            if isinstance(e, (InvalidChannelError, APIError)):
                raise
            raise DiscoveryError(f"Failed to get channel metadata: {e}")

    def _parse_channel_url(self, url: str) -> Tuple[str, str]:
        """Parse channel URL to extract type and identifier.

        Args:
            url: Channel URL

        Returns:
            Tuple of (url_type, identifier)
        """
        # Add protocol if missing
        if not url.startswith(('http://', 'https://')):
            url = f"https://{url}"

        # Normalize URL
        url = url.replace('www.', '').replace('m.', '')

        # Parse different URL formats
        patterns = [
            (r'youtube\.com/@([^/?]+)', 'handle'),
            (r'youtube\.com/channel/([^/?]+)', 'channel_id'),
            (r'youtube\.com/user/([^/?]+)', 'user'),
            (r'youtube\.com/c/([^/?]+)', 'c'),
        ]

        for pattern, url_type in patterns:
            match = re.search(pattern, url)
            if match:
                return url_type, match.group(1)

        raise InvalidChannelError(f"Invalid channel URL: {url}")

    def _resolve_channel_id(self, url_type: str, identifier: str) -> str:
        """Resolve channel identifier to channel ID.

        Args:
            url_type: Type of URL (handle, channel_id, user, c)
            identifier: Channel identifier

        Returns:
            Channel ID (starts with UC)
        """
        if url_type == "channel_id":
            return identifier

        # For other types, use API to resolve
        if url_type == "handle":
            params = {
                "part": "id",
                "forHandle": identifier
            }
        elif url_type == "user":
            params = {
                "part": "id",
                "forUsername": identifier
            }
        else:  # url_type == "c"
            # For /c/ format, try as handle first
            params = {
                "part": "id",
                "forHandle": identifier
            }

        try:
            response = self._api_request("channels", params)
            items = response.get("items", [])

            if not items:
                # If /c/ format failed, try search
                if url_type == "c":
                    search_response = self._api_request("search", {
                        "part": "snippet",
                        "q": identifier,
                        "type": "channel",
                        "maxResults": 1
                    })
                    items = search_response.get("items", [])
                    if items:
                        return items[0]["snippet"]["channelId"]

                raise InvalidChannelError(f"Channel not found: {identifier}")

            return items[0]["id"]

        except APIError:
            raise
        except Exception as e:
            raise InvalidChannelError(f"Failed to resolve channel: {e}")

    def _api_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make authenticated API request with caching.

        Args:
            endpoint: API endpoint (search, videos, channels)
            params: Request parameters

        Returns:
            API response data
        """
        if not self._youtube:
            raise APIError("YouTube API client not initialized")

        # Check cache first
        cache_key = self._get_cache_key(endpoint, params)
        if self.use_cache:
            cached_data = self._load_from_cache(cache_key)
            if cached_data is not None:
                logger.debug(f"Cache hit for {endpoint} request")
                return cached_data

        try:
            # Make API request
            if endpoint == "search":
                response = self._youtube.search().list(**params).execute()
            elif endpoint == "videos":
                response = self._youtube.videos().list(**params).execute()
            elif endpoint == "channels":
                response = self._youtube.channels().list(**params).execute()
            else:
                raise APIError(f"Unsupported endpoint: {endpoint}")

            # Cache response
            if self.use_cache:
                self._save_to_cache(cache_key, response)

            logger.debug(f"API request successful: {endpoint}")
            return response

        except HttpError as e:
            if e.resp.status == 403:
                raise APIError("API quota exceeded or invalid API key")
            elif e.resp.status == 404:
                raise APIError("Resource not found")
            else:
                raise APIError(f"API request failed: {e}")
        except Exception as e:
            raise APIError(f"API request failed: {e}")

    def _parse_video_item(self, item: Dict[str, Any]) -> VideoMetadata:
        """Parse YouTube API video item to VideoMetadata.

        Args:
            item: Video item from API response

        Returns:
            VideoMetadata object
        """
        snippet = item.get("snippet", {})
        content_details = item.get("contentDetails", {})
        statistics = item.get("statistics", {})

        return VideoMetadata(
            video_id=item["id"],
            title=snippet.get("title", ""),
            description=snippet.get("description", ""),
            duration_seconds=self._parse_duration(content_details.get("duration", "")),
            upload_date=self._format_date(snippet.get("publishedAt", "")),
            view_count=self._safe_int(statistics.get("viewCount")),
            like_count=self._safe_int(statistics.get("likeCount")),
            comment_count=self._safe_int(statistics.get("commentCount")),
            channel_id=snippet.get("channelId", ""),
            channel_title=snippet.get("channelTitle", ""),
            thumbnail_url=snippet.get("thumbnails", {}).get("maxresdefault", {}).get("url", ""),
            tags=snippet.get("tags", []),
            category=snippet.get("categoryId", "")
        )

    def _parse_channel_item(self, item: Dict[str, Any], channel_url: str) -> ChannelMetadata:
        """Parse YouTube API channel item to ChannelMetadata.

        Args:
            item: Channel item from API response
            channel_url: Original channel URL

        Returns:
            ChannelMetadata object
        """
        snippet = item.get("snippet", {})
        statistics = item.get("statistics", {})

        return ChannelMetadata(
            channel_id=item["id"],
            channel_title=snippet.get("title", ""),
            channel_url=channel_url,
            description=snippet.get("description", ""),
            subscriber_count=self._safe_int(statistics.get("subscriberCount")),
            video_count=self._safe_int(statistics.get("videoCount")),
            created_date=self._format_date(snippet.get("publishedAt", "")),
            thumbnail_url=snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
            country=snippet.get("country", ""),
            default_language=snippet.get("defaultLanguage", "")
        )

    def _get_cache_key(self, endpoint: str, params: Dict[str, Any]) -> str:
        """Generate cache key for request.

        Args:
            endpoint: API endpoint
            params: Request parameters

        Returns:
            Cache key string
        """
        # Sort parameters for consistent keys
        sorted_params = sorted(params.items())
        param_str = urllib.parse.urlencode(sorted_params)
        cache_string = f"{endpoint}:{param_str}"

        # Hash for shorter filenames
        return hashlib.md5(cache_string.encode()).hexdigest()

    def _load_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Load data from cache.

        Args:
            cache_key: Cache key

        Returns:
            Cached data or None if not found
        """
        cache_file = self.cache_dir / f"{cache_key}.json"

        if cache_file.exists():
            try:
                return json.loads(cache_file.read_text())
            except Exception as e:
                logger.warning(f"Failed to load cache {cache_key}: {e}")

        return None

    def _save_to_cache(self, cache_key: str, data: Dict[str, Any]) -> None:
        """Save data to cache.

        Args:
            cache_key: Cache key
            data: Data to cache
        """
        cache_file = self.cache_dir / f"{cache_key}.json"

        try:
            cache_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.warning(f"Failed to save cache {cache_key}: {e}")

    def _parse_duration(self, duration_str: str) -> int:
        """Parse ISO 8601 duration to seconds.

        Args:
            duration_str: ISO 8601 duration string (e.g., "PT5M30S")

        Returns:
            Duration in seconds
        """
        if not duration_str:
            return 0

        try:
            duration = isodate.parse_duration(duration_str)
            return int(duration.total_seconds())
        except Exception:
            return 0

    def _format_date(self, date_str: str) -> str:
        """Format ISO date string to YYYY-MM-DD.

        Args:
            date_str: ISO date string

        Returns:
            Formatted date string
        """
        if not date_str:
            return "unknown"

        try:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d')
        except Exception:
            return "unknown"

    def _safe_int(self, value: Any) -> int:
        """Safely convert value to integer.

        Args:
            value: Value to convert

        Returns:
            Integer value or 0 if conversion fails
        """
        if value is None:
            return 0

        try:
            return int(value)
        except (ValueError, TypeError):
            return 0

    def get_channel_info(self, channel_url: str) -> Dict[str, Any]:
        """Get basic channel information for display.

        Args:
            channel_url: YouTube channel URL

        Returns:
            Dictionary with channel information

        Raises:
            InvalidChannelError: If channel URL is invalid
            APIError: If API request fails
        """
        if not self._youtube:
            raise APIError("YouTube API client not initialized")

        # Get channel metadata
        channel_metadata = self.get_channel_metadata(channel_url)

        # Return formatted info
        return {
            'title': channel_metadata.channel_title,
            'subscriber_count': channel_metadata.subscriber_count,
            'video_count': channel_metadata.video_count,
            'view_count': channel_metadata.view_count,
            'description': channel_metadata.description,
            'published_at': channel_metadata.created_date,
            'thumbnail_url': channel_metadata.thumbnail_url,
            'custom_url': channel_metadata.custom_url,
            'channel_id': channel_metadata.channel_id
        }