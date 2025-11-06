"""Video selection interface."""

import logging
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import asdict

import questionary

from ..core.discovery import VideoMetadata

# Configure logging
logger = logging.getLogger(__name__)


class SelectionError(Exception):
    """Base exception for selection operations."""
    pass


class InvalidVideoDataError(SelectionError):
    """Raised when video data is invalid."""
    pass


class UserCancelledError(SelectionError):
    """Raised when user cancels the selection."""
    pass


def format_duration(duration_seconds: int) -> str:
    """Format duration from seconds to HH:MM:SS or MM:SS format.

    Args:
        duration_seconds: Duration in seconds

    Returns:
        Formatted duration string
    """
    if duration_seconds < 0:
        duration_seconds = 0

    hours = duration_seconds // 3600
    minutes = (duration_seconds % 3600) // 60
    seconds = duration_seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes}:{seconds:02d}"


def format_view_count(view_count: int) -> str:
    """Format view count with appropriate units.

    Args:
        view_count: Number of views

    Returns:
        Formatted view count string
    """
    if view_count >= 1000000:
        if view_count % 1000000 == 0:
            return f"{view_count // 1000000}M views"
        else:
            return f"{view_count / 1000000:.1f}M views"
    elif view_count >= 1000:
        if view_count % 1000 == 0:
            return f"{view_count // 1000}K views"
        else:
            return f"{view_count / 1000:.1f}K views"
    elif view_count == 1:
        return "1 view"
    else:
        return f"{view_count} views"


def format_video_display(
    video: VideoMetadata,
    max_title_length: int = 60,
    status: Optional[str] = None
) -> str:
    """Format video metadata for display in selection interface.

    Args:
        video: VideoMetadata object
        max_title_length: Maximum characters for title before truncation
        status: Optional status indicator ("new" or "extracted")

    Returns:
        Formatted string for display
    """
    title = video.title

    # Add status indicator if provided
    status_indicator = ""
    if status == "new":
        status_indicator = "🆕 "
    elif status == "extracted":
        status_indicator = "✅ "

    # Format duration
    duration_str = format_duration(video.duration_seconds)

    # Format view count
    view_str = format_view_count(video.view_count)

    # Format date
    upload_date = video.upload_date or "Unknown"

    # Calculate space needed for non-title parts
    suffix = f" ({duration_str}) - {upload_date} - {view_str}"
    suffix_length = len(status_indicator + suffix)

    # Adjust title length to keep total line reasonable
    available_title_length = min(max_title_length, 80 - suffix_length)

    # Truncate title if too long
    if len(title) > available_title_length:
        title = title[:available_title_length - 3] + "..."

    return f"{status_indicator}{title}{suffix}"


def validate_video_data(videos: Any) -> bool:
    """Validate video data structure.

    Args:
        videos: Video data to validate

    Returns:
        True if valid

    Raises:
        InvalidVideoDataError: If data is invalid
    """
    if not isinstance(videos, list):
        raise InvalidVideoDataError("Videos must be a list")

    for i, video in enumerate(videos):
        if isinstance(video, VideoMetadata):
            # VideoMetadata objects are always valid
            continue
        elif isinstance(video, dict):
            # Validate required fields for dictionary
            required_fields = ["video_id", "title", "duration_seconds", "upload_date"]
            for field in required_fields:
                if field not in video:
                    raise InvalidVideoDataError(f"Missing required field '{field}' in video {i}")

            # Validate data types
            if not isinstance(video["duration_seconds"], int):
                raise InvalidVideoDataError(f"Invalid duration in video {i}: must be integer")
        else:
            raise InvalidVideoDataError(f"Invalid video data type at index {i}: must be VideoMetadata or dict")

    return True


def group_videos_by_status(
    videos: List[VideoMetadata],
    history_manager: Any
) -> Dict[str, List[VideoMetadata]]:
    """Group videos by extraction status.

    Args:
        videos: List of VideoMetadata objects
        history_manager: History manager with identify methods

    Returns:
        Dictionary with 'new' and 'extracted' keys

    Raises:
        InvalidVideoDataError: If videos data is invalid
        TypeError: If history_manager is invalid
    """
    validate_video_data(videos)

    # Validate history manager
    required_methods = ["identify_new_videos", "identify_extracted_videos"]
    for method in required_methods:
        if not hasattr(history_manager, method):
            raise TypeError("history_manager must have required methods")

    new_videos = history_manager.identify_new_videos(videos)
    extracted_videos = history_manager.identify_extracted_videos(videos)

    return {
        "new": new_videos,
        "extracted": extracted_videos
    }


def get_selection_summary(videos: List[VideoMetadata]) -> Dict[str, Any]:
    """Generate summary statistics for selected videos.

    Args:
        videos: List of selected VideoMetadata objects

    Returns:
        Dictionary with summary statistics
    """
    total_videos = len(videos)
    total_duration_seconds = sum(video.duration_seconds for video in videos)
    total_views = sum(video.view_count for video in videos)

    # Format total duration as human-readable
    if total_duration_seconds == 0:
        duration_formatted = "0 seconds"
    elif total_duration_seconds < 60:
        duration_formatted = f"{total_duration_seconds} seconds"
    elif total_duration_seconds < 3600:
        minutes = total_duration_seconds // 60
        duration_formatted = f"{minutes} minutes"
    else:
        hours = total_duration_seconds // 3600
        remaining_minutes = (total_duration_seconds % 3600) // 60
        if remaining_minutes > 0:
            duration_formatted = f"{hours} hour{'s' if hours != 1 else ''} {remaining_minutes} minutes"
        else:
            duration_formatted = f"{hours} hour{'s' if hours != 1 else ''}"

    return {
        "total_videos": total_videos,
        "total_duration_seconds": total_duration_seconds,
        "total_duration_formatted": duration_formatted,
        "total_views": total_views
    }


class VideoSelector:
    """Interactive video selection interface."""

    def __init__(
        self,
        max_title_length: int = 60,
        use_enhanced_display: bool = True,
        show_status_indicators: bool = True,
        group_by_status: bool = False
    ):
        """Initialize video selector.

        Args:
            max_title_length: Maximum title length before truncation
            use_enhanced_display: Whether to use enhanced display formatting
            show_status_indicators: Whether to show status indicators
            group_by_status: Whether to group videos by extraction status
        """
        self.max_title_length = max_title_length
        self.use_enhanced_display = use_enhanced_display
        self.show_status_indicators = show_status_indicators
        self.group_by_status = group_by_status

    def select_videos(
        self,
        videos: List[VideoMetadata],
        history_manager: Optional[Any] = None,
        message: Optional[str] = None,
        instruction: Optional[str] = None
    ) -> List[VideoMetadata]:
        """Show interactive video selection interface.

        Args:
            videos: List of available VideoMetadata objects
            history_manager: Optional history manager for status grouping
            message: Custom selection message
            instruction: Custom instruction text

        Returns:
            List of selected VideoMetadata objects

        Raises:
            InvalidVideoDataError: If video data is invalid
            UserCancelledError: If user cancels selection
        """
        logger.info(f"Starting video selection with {len(videos)} videos")

        # Validate input data
        validate_video_data(videos)

        if not videos:
            logger.info("No videos available for selection")
            return []

        try:
            # Prepare choices and video mapping
            choices, video_map = self._prepare_choices(videos, history_manager)

            # Create selection message
            if message is None:
                message = self._create_selection_message(videos)

            # Set default instruction
            if instruction is None:
                instruction = "(Space to toggle, Enter to confirm, Ctrl+C to cancel)"

            # Display interactive checkbox
            selected_displays = questionary.checkbox(
                message=message,
                choices=choices,
                instruction=instruction
            ).ask()

            # Handle user cancellation
            if selected_displays is None:
                logger.info("User cancelled video selection")
                raise UserCancelledError("User cancelled selection")

            # Map selected display strings back to video objects
            selected_videos = self._map_selected_videos(selected_displays, video_map)

            logger.info(f"User selected {len(selected_videos)} videos")
            return selected_videos

        except KeyboardInterrupt:
            logger.info("User cancelled selection with keyboard interrupt")
            raise UserCancelledError("User cancelled selection")

    def _prepare_choices(
        self,
        videos: List[VideoMetadata],
        history_manager: Optional[Any] = None
    ) -> Tuple[List[str], Dict[str, VideoMetadata]]:
        """Prepare choices for selection interface.

        Args:
            videos: List of VideoMetadata objects
            history_manager: Optional history manager for status grouping

        Returns:
            Tuple of (choice_list, video_mapping_dict)
        """
        choices = []
        video_map = {}

        # Group videos by status if requested and history manager available
        if self.group_by_status and history_manager:
            grouped_videos = group_videos_by_status(videos, history_manager)

            # Add new videos first
            for video in grouped_videos["new"]:
                status = "new" if self.show_status_indicators else None
                display_text = format_video_display(
                    video,
                    max_title_length=self.max_title_length,
                    status=status
                )
                choices.append(display_text)
                video_map[display_text] = video

            # Add extracted videos
            for video in grouped_videos["extracted"]:
                status = "extracted" if self.show_status_indicators else None
                display_text = format_video_display(
                    video,
                    max_title_length=self.max_title_length,
                    status=status
                )
                choices.append(display_text)
                video_map[display_text] = video
        else:
            # Standard display without grouping
            for video in videos:
                display_text = format_video_display(
                    video,
                    max_title_length=self.max_title_length
                )
                choices.append(display_text)
                video_map[display_text] = video

        return choices, video_map

    def _map_selected_videos(
        self,
        selected_displays: List[str],
        video_map: Dict[str, VideoMetadata]
    ) -> List[VideoMetadata]:
        """Map selected display strings back to VideoMetadata objects.

        Args:
            selected_displays: List of selected display strings
            video_map: Mapping from display string to VideoMetadata

        Returns:
            List of selected VideoMetadata objects
        """
        selected_videos = []
        for display in selected_displays:
            if display in video_map:
                selected_videos.append(video_map[display])
            else:
                logger.warning(f"Selected display string not found in mapping: {display}")

        return selected_videos

    def _create_selection_message(self, videos: List[VideoMetadata]) -> str:
        """Create selection message for the interface.

        Args:
            videos: List of available videos

        Returns:
            Formatted selection message
        """
        channel_title = videos[0].channel_title if videos else "Unknown Channel"
        video_count = len(videos)

        return f"📺 {channel_title} - {video_count} videos available\n\nSelect videos to process:"