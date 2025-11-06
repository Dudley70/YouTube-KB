"""Test suite for CP-REFACTOR-3: Video Selection UI (30 tests)."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import json
from datetime import datetime

from youtube_processor.ui.selection import (
    VideoSelector,
    SelectionError,
    InvalidVideoDataError,
    UserCancelledError,
    format_video_display,
    format_duration,
    format_view_count,
    validate_video_data,
    group_videos_by_status,
    get_selection_summary
)
from youtube_processor.core.discovery import VideoMetadata


@pytest.fixture
def video_selector():
    """Create a VideoSelector instance for testing."""
    return VideoSelector()


@pytest.fixture
def sample_videos():
    """Sample video data for testing."""
    return [
        VideoMetadata(
            video_id="abc123",
            title="Introduction to Python Programming",
            description="Learn Python basics",
            duration_seconds=1800,  # 30 minutes
            upload_date="2024-01-15",
            view_count=15000,
            like_count=200,
            comment_count=50,
            channel_id="UC123456789",
            channel_title="CodeChannel",
            tags=["python", "programming"]
        ),
        VideoMetadata(
            video_id="def456",
            title="Advanced JavaScript Concepts - ES6 and Beyond",
            description="Deep dive into modern JS",
            duration_seconds=3900,  # 65 minutes
            upload_date="2024-01-20",
            view_count=8500,
            like_count=120,
            comment_count=25,
            channel_id="UC123456789",
            channel_title="CodeChannel",
            tags=["javascript", "es6"]
        ),
        VideoMetadata(
            video_id="ghi789",
            title="Quick Tips",
            description="Short tips",
            duration_seconds=300,  # 5 minutes
            upload_date="2024-01-25",
            view_count=2500,
            like_count=50,
            comment_count=10,
            channel_id="UC123456789",
            channel_title="CodeChannel",
            tags=["tips"]
        )
    ]


@pytest.fixture
def mock_history_manager():
    """Mock history manager for testing."""
    mock = Mock()
    mock.identify_new_videos.return_value = []
    mock.identify_extracted_videos.return_value = []
    return mock


class TestVideoSelectorInitialization:
    """Test VideoSelector initialization and configuration."""

    def test_init_default_parameters(self):
        """Test initialization with default parameters."""
        selector = VideoSelector()
        assert selector.max_title_length == 60
        assert selector.use_enhanced_display is True
        assert selector.show_status_indicators is True
        assert selector.group_by_status is False

    def test_init_custom_parameters(self):
        """Test initialization with custom parameters."""
        selector = VideoSelector(
            max_title_length=80,
            use_enhanced_display=False,
            show_status_indicators=False,
            group_by_status=True
        )

        assert selector.max_title_length == 80
        assert selector.use_enhanced_display is False
        assert selector.show_status_indicators is False
        assert selector.group_by_status is True


class TestVideoDisplayFormatting:
    """Test video display formatting functions."""

    def test_format_duration_minutes_seconds(self):
        """Test formatting duration for minutes and seconds."""
        assert format_duration(300) == "5:00"
        assert format_duration(90) == "1:30"
        assert format_duration(45) == "0:45"

    def test_format_duration_hours_minutes_seconds(self):
        """Test formatting duration with hours."""
        assert format_duration(3661) == "1:01:01"
        assert format_duration(7200) == "2:00:00"
        assert format_duration(3900) == "1:05:00"

    def test_format_duration_edge_cases(self):
        """Test duration formatting edge cases."""
        assert format_duration(0) == "0:00"
        assert format_duration(1) == "0:01"
        assert format_duration(59) == "0:59"
        assert format_duration(60) == "1:00"

    def test_format_view_count_regular(self):
        """Test formatting view count for regular numbers."""
        assert format_view_count(999) == "999 views"
        assert format_view_count(500) == "500 views"
        assert format_view_count(1) == "1 view"

    def test_format_view_count_thousands(self):
        """Test formatting view count in thousands."""
        assert format_view_count(1000) == "1K views"
        assert format_view_count(1500) == "1.5K views"
        assert format_view_count(15000) == "15K views"
        assert format_view_count(999999) == "1000.0K views"

    def test_format_view_count_millions(self):
        """Test formatting view count in millions."""
        assert format_view_count(1000000) == "1M views"
        assert format_view_count(1500000) == "1.5M views"
        assert format_view_count(15000000) == "15M views"

    def test_format_video_display_basic(self, sample_videos):
        """Test basic video display formatting."""
        video = sample_videos[0]
        display = format_video_display(video)

        assert "Introduction to Python Programming" in display
        assert "30:00" in display
        assert "2024-01-15" in display
        assert "15K views" in display

    def test_format_video_display_long_title(self, sample_videos):
        """Test video display with long title truncation."""
        video = sample_videos[1]
        display = format_video_display(video, max_title_length=30)

        # Title should be truncated
        assert len(display.split(" (")[0]) <= 30
        assert "..." in display or len(video.title) <= 30

    def test_format_video_display_with_status(self, sample_videos):
        """Test video display with status indicator."""
        video = sample_videos[0]
        display = format_video_display(video, status="new")

        assert "🆕" in display
        assert "Introduction to Python Programming" in display

    def test_format_video_display_extracted_status(self, sample_videos):
        """Test video display with extracted status."""
        video = sample_videos[0]
        display = format_video_display(video, status="extracted")

        assert "✅" in display
        assert "Introduction to Python Programming" in display


class TestVideoDataValidation:
    """Test video data validation."""

    def test_validate_video_data_valid_videometadata(self, sample_videos):
        """Test validation with valid VideoMetadata objects."""
        result = validate_video_data(sample_videos)
        assert result is True

    def test_validate_video_data_valid_dict_list(self):
        """Test validation with valid dictionary list."""
        videos = [
            {
                "video_id": "abc123",
                "title": "Test Video",
                "duration_seconds": 300,
                "upload_date": "2024-01-15",
                "view_count": 1000
            }
        ]
        result = validate_video_data(videos)
        assert result is True

    def test_validate_video_data_empty_list(self):
        """Test validation with empty list."""
        result = validate_video_data([])
        assert result is True

    def test_validate_video_data_invalid_type(self):
        """Test validation with invalid data type."""
        with pytest.raises(InvalidVideoDataError, match="Videos must be a list"):
            validate_video_data("not a list")

    def test_validate_video_data_missing_required_field(self):
        """Test validation with missing required fields."""
        videos = [
            {
                "title": "Test Video",
                "duration_seconds": 300
                # Missing video_id
            }
        ]
        with pytest.raises(InvalidVideoDataError, match="Missing required field"):
            validate_video_data(videos)

    def test_validate_video_data_invalid_duration(self):
        """Test validation with invalid duration."""
        videos = [
            {
                "video_id": "abc123",
                "title": "Test Video",
                "duration_seconds": "invalid",  # Should be int
                "upload_date": "2024-01-15"
            }
        ]
        with pytest.raises(InvalidVideoDataError, match="Invalid duration"):
            validate_video_data(videos)


class TestVideoGrouping:
    """Test video grouping functionality."""

    def test_group_videos_by_status_with_new_and_extracted(self, sample_videos, mock_history_manager):
        """Test grouping videos with both new and extracted videos."""
        # Mock history manager responses
        mock_history_manager.identify_new_videos.return_value = [sample_videos[0], sample_videos[2]]
        mock_history_manager.identify_extracted_videos.return_value = [sample_videos[1]]

        result = group_videos_by_status(sample_videos, mock_history_manager)

        assert "new" in result
        assert "extracted" in result
        assert len(result["new"]) == 2
        assert len(result["extracted"]) == 1
        assert result["new"][0].video_id == "abc123"
        assert result["extracted"][0].video_id == "def456"

    def test_group_videos_by_status_all_new(self, sample_videos, mock_history_manager):
        """Test grouping when all videos are new."""
        mock_history_manager.identify_new_videos.return_value = sample_videos
        mock_history_manager.identify_extracted_videos.return_value = []

        result = group_videos_by_status(sample_videos, mock_history_manager)

        assert len(result["new"]) == 3
        assert len(result["extracted"]) == 0

    def test_group_videos_by_status_all_extracted(self, sample_videos, mock_history_manager):
        """Test grouping when all videos are extracted."""
        mock_history_manager.identify_new_videos.return_value = []
        mock_history_manager.identify_extracted_videos.return_value = sample_videos

        result = group_videos_by_status(sample_videos, mock_history_manager)

        assert len(result["new"]) == 0
        assert len(result["extracted"]) == 3

    def test_group_videos_by_status_invalid_videos(self, mock_history_manager):
        """Test grouping with invalid video data."""
        with pytest.raises(InvalidVideoDataError):
            group_videos_by_status("not a list", mock_history_manager)

    def test_group_videos_by_status_invalid_history_manager(self, sample_videos):
        """Test grouping with invalid history manager."""
        with pytest.raises(TypeError, match="history_manager must have required methods"):
            group_videos_by_status(sample_videos, "not a history manager")


class TestSelectionSummary:
    """Test selection summary functionality."""

    def test_get_selection_summary_multiple_videos(self, sample_videos):
        """Test summary generation for multiple videos."""
        summary = get_selection_summary(sample_videos)

        assert summary["total_videos"] == 3
        assert summary["total_duration_seconds"] == 6000  # 1800 + 3900 + 300
        assert summary["total_duration_formatted"] == "1 hour 40 minutes"
        assert summary["total_views"] == 26000  # 15000 + 8500 + 2500

    def test_get_selection_summary_single_video(self, sample_videos):
        """Test summary generation for single video."""
        summary = get_selection_summary([sample_videos[0]])

        assert summary["total_videos"] == 1
        assert summary["total_duration_seconds"] == 1800
        assert summary["total_duration_formatted"] == "30 minutes"
        assert summary["total_views"] == 15000

    def test_get_selection_summary_empty_list(self):
        """Test summary generation for empty selection."""
        summary = get_selection_summary([])

        assert summary["total_videos"] == 0
        assert summary["total_duration_seconds"] == 0
        assert summary["total_duration_formatted"] == "0 seconds"
        assert summary["total_views"] == 0

    def test_get_selection_summary_short_duration(self):
        """Test summary with videos under 1 minute."""
        videos = [VideoMetadata(
            video_id="test",
            title="Short video",
            duration_seconds=45,
            upload_date="2024-01-01",
            view_count=100
        )]

        summary = get_selection_summary(videos)
        assert summary["total_duration_formatted"] == "45 seconds"

    def test_get_selection_summary_hour_only(self):
        """Test summary with exact hour duration."""
        videos = [VideoMetadata(
            video_id="test",
            title="Hour video",
            duration_seconds=3600,
            upload_date="2024-01-01",
            view_count=100
        )]

        summary = get_selection_summary(videos)
        assert summary["total_duration_formatted"] == "1 hour"


class TestInteractiveSelection:
    """Test interactive video selection."""

    @patch('questionary.checkbox')
    def test_select_videos_success(self, mock_checkbox, video_selector, sample_videos):
        """Test successful video selection."""
        # Mock user selecting first two videos
        mock_checkbox.return_value.ask.return_value = [
            format_video_display(sample_videos[0]),
            format_video_display(sample_videos[1])
        ]

        result = video_selector.select_videos(sample_videos)

        assert len(result) == 2
        assert result[0].video_id == "abc123"
        assert result[1].video_id == "def456"

    @patch('questionary.checkbox')
    def test_select_videos_user_cancelled(self, mock_checkbox, video_selector, sample_videos):
        """Test video selection when user cancels."""
        mock_checkbox.return_value.ask.return_value = None  # User cancelled

        with pytest.raises(UserCancelledError):
            video_selector.select_videos(sample_videos)

    @patch('questionary.checkbox')
    def test_select_videos_empty_selection(self, mock_checkbox, video_selector, sample_videos):
        """Test video selection with empty selection."""
        mock_checkbox.return_value.ask.return_value = []  # User selected nothing

        result = video_selector.select_videos(sample_videos)
        assert result == []

    @patch('questionary.checkbox')
    def test_select_videos_keyboard_interrupt(self, mock_checkbox, video_selector, sample_videos):
        """Test video selection with keyboard interrupt."""
        mock_checkbox.return_value.ask.side_effect = KeyboardInterrupt()

        with pytest.raises(UserCancelledError):
            video_selector.select_videos(sample_videos)

    def test_select_videos_invalid_data(self, video_selector):
        """Test video selection with invalid video data."""
        with pytest.raises(InvalidVideoDataError):
            video_selector.select_videos("not a list")

    @patch('questionary.checkbox')
    def test_select_videos_with_history_manager(self, mock_checkbox, mock_history_manager, sample_videos):
        """Test video selection with history manager grouping."""
        # Create selector with grouping enabled
        selector = VideoSelector(group_by_status=True)

        # Mock history manager responses
        mock_history_manager.identify_new_videos.return_value = [sample_videos[0]]
        mock_history_manager.identify_extracted_videos.return_value = [sample_videos[1], sample_videos[2]]

        # Mock user selection
        mock_checkbox.return_value.ask.return_value = [
            format_video_display(sample_videos[0], status="new")
        ]

        result = selector.select_videos(sample_videos, history_manager=mock_history_manager)

        assert len(result) == 1
        assert result[0].video_id == "abc123"

    @patch('questionary.checkbox')
    def test_select_videos_with_custom_message(self, mock_checkbox, video_selector, sample_videos):
        """Test video selection with custom message."""
        mock_checkbox.return_value.ask.return_value = []

        video_selector.select_videos(
            sample_videos,
            message="Custom selection message",
            instruction="Custom instruction"
        )

        # Verify custom message was used
        call_args = mock_checkbox.call_args
        assert "Custom selection message" in call_args[1]["message"]
        assert call_args[1]["instruction"] == "Custom instruction"


class TestErrorHandling:
    """Test error handling and custom exceptions."""

    def test_selection_error_creation(self):
        """Test SelectionError exception."""
        error = SelectionError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)

    def test_invalid_video_data_error_creation(self):
        """Test InvalidVideoDataError exception."""
        error = InvalidVideoDataError("Invalid data")
        assert str(error) == "Invalid data"
        assert isinstance(error, SelectionError)

    def test_user_cancelled_error_creation(self):
        """Test UserCancelledError exception."""
        error = UserCancelledError("User cancelled")
        assert str(error) == "User cancelled"
        assert isinstance(error, SelectionError)


class TestUtilityMethods:
    """Test utility and helper methods."""

    def test_video_selector_prepare_choices_basic(self, video_selector, sample_videos):
        """Test preparing choices for basic display."""
        choices, video_map = video_selector._prepare_choices(sample_videos)

        assert len(choices) == 3
        assert len(video_map) == 3
        assert all(isinstance(choice, str) for choice in choices)
        assert all(isinstance(video, VideoMetadata) for video in video_map.values())

    def test_video_selector_prepare_choices_with_status(self, mock_history_manager, sample_videos):
        """Test preparing choices with status grouping."""
        selector = VideoSelector(group_by_status=True, show_status_indicators=True)

        # Mock history responses
        mock_history_manager.identify_new_videos.return_value = [sample_videos[0]]
        mock_history_manager.identify_extracted_videos.return_value = [sample_videos[1], sample_videos[2]]

        choices, video_map = selector._prepare_choices(sample_videos, mock_history_manager)

        # Check that status indicators are included
        new_choices = [c for c in choices if "🆕" in c]
        extracted_choices = [c for c in choices if "✅" in c]

        assert len(new_choices) == 1
        assert len(extracted_choices) == 2

    def test_video_selector_map_selected_videos(self, video_selector, sample_videos):
        """Test mapping selected display strings back to video objects."""
        choices, video_map = video_selector._prepare_choices(sample_videos)
        selected_displays = choices[:2]  # Select first two

        result = video_selector._map_selected_videos(selected_displays, video_map)

        assert len(result) == 2
        assert all(isinstance(video, VideoMetadata) for video in result)

    def test_video_selector_create_selection_message(self, video_selector, sample_videos):
        """Test creating selection message."""
        message = video_selector._create_selection_message(sample_videos)

        assert "3 videos available" in message
        assert "Select videos" in message
        assert "📺" in message