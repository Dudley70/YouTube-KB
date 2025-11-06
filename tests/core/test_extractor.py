"""Test suite for CP-REFACTOR-4: Parallel Extractor (30 tests)."""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from pathlib import Path
import time
import tempfile
from concurrent.futures import Future
from datetime import datetime

from youtube_processor.core.extractor import (
    ParallelExtractor,
    ExtractionStats,
    ExtractionResult,
    ExtractionError,
    TORConnectionError,
    VideoExtractionError,
    extract_single_video,
    check_tor_connection,
    setup_tor_proxy
)
from youtube_processor.core.discovery import VideoMetadata


@pytest.fixture
def extractor():
    """Create a ParallelExtractor instance for testing."""
    return ParallelExtractor()


@pytest.fixture
def sample_videos():
    """Sample video data for testing."""
    return [
        VideoMetadata(
            video_id="abc123",
            title="Test Video 1",
            duration_seconds=300,
            upload_date="2024-01-15",
            view_count=1000
        ),
        VideoMetadata(
            video_id="def456",
            title="Test Video 2",
            duration_seconds=600,
            upload_date="2024-01-20",
            view_count=2000
        ),
        VideoMetadata(
            video_id="ghi789",
            title="Test Video 3",
            duration_seconds=900,
            upload_date="2024-01-25",
            view_count=3000
        )
    ]


@pytest.fixture
def mock_history_manager():
    """Mock history manager for testing."""
    mock = Mock()
    mock.get_extraction_status.return_value = "new"
    mock.record_extraction_start.return_value = None
    mock.record_extraction_complete.return_value = None
    mock.record_extraction_error.return_value = None
    return mock


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


class TestParallelExtractorInitialization:
    """Test ParallelExtractor initialization and configuration."""

    def test_init_default_parameters(self):
        """Test initialization with default parameters."""
        extractor = ParallelExtractor()
        assert extractor.max_workers == 10
        assert extractor.use_tor is True
        assert extractor.tor_port == 9050
        assert extractor.timeout == 300
        assert extractor.retry_attempts == 3

    def test_init_custom_parameters(self):
        """Test initialization with custom parameters."""
        extractor = ParallelExtractor(
            max_workers=15,
            use_tor=False,
            tor_port=9051,
            timeout=600,
            retry_attempts=5
        )

        assert extractor.max_workers == 15
        assert extractor.use_tor is False
        assert extractor.tor_port == 9051
        assert extractor.timeout == 600
        assert extractor.retry_attempts == 5

    def test_init_validates_parameters(self):
        """Test parameter validation during initialization."""
        # Test invalid max_workers
        with pytest.raises(ValueError, match="max_workers must be positive"):
            ParallelExtractor(max_workers=0)

        # Test invalid timeout
        with pytest.raises(ValueError, match="timeout must be positive"):
            ParallelExtractor(timeout=-1)

        # Test invalid retry_attempts
        with pytest.raises(ValueError, match="retry_attempts must be non-negative"):
            ParallelExtractor(retry_attempts=-1)


class TestExtractionStats:
    """Test ExtractionStats tracking functionality."""

    def test_stats_initialization(self):
        """Test stats initialization."""
        stats = ExtractionStats(total_videos=10)
        assert stats.total_videos == 10
        assert stats.completed == 0
        assert stats.failed == 0
        assert stats.skipped == 0
        assert len(stats.errors) == 0
        assert stats.start_time is not None

    def test_record_success(self):
        """Test recording successful extraction."""
        stats = ExtractionStats(total_videos=5)
        stats.record_success("abc123")

        assert stats.completed == 1
        assert stats.failed == 0
        assert stats.skipped == 0

    def test_record_failure(self):
        """Test recording failed extraction."""
        stats = ExtractionStats(total_videos=5)
        stats.record_failure("abc123", "Test error")

        assert stats.completed == 0
        assert stats.failed == 1
        assert stats.skipped == 0
        assert len(stats.errors) == 1
        assert stats.errors[0] == ("abc123", "Test error")

    def test_record_skip(self):
        """Test recording skipped extraction."""
        stats = ExtractionStats(total_videos=5)
        stats.record_skip("abc123", "Already extracted")

        assert stats.completed == 0
        assert stats.failed == 0
        assert stats.skipped == 1

    def test_get_progress_percentage(self):
        """Test progress percentage calculation."""
        stats = ExtractionStats(total_videos=10)
        assert stats.get_progress_percentage() == 0.0

        stats.record_success("abc123")
        assert stats.get_progress_percentage() == 10.0

        stats.record_failure("def456", "Error")
        assert stats.get_progress_percentage() == 20.0

        stats.record_skip("ghi789", "Skip")
        assert stats.get_progress_percentage() == 30.0

    def test_get_rate_per_minute(self):
        """Test extraction rate calculation."""
        stats = ExtractionStats(total_videos=10)

        # Mock start time to control rate calculation
        stats.start_time = time.time() - 60  # 1 minute ago
        stats.record_success("abc123")
        stats.record_success("def456")

        rate = stats.get_rate_per_minute()
        assert rate == pytest.approx(2.0, rel=0.1)

    def test_get_eta_minutes(self):
        """Test ETA calculation."""
        stats = ExtractionStats(total_videos=10)
        stats.start_time = time.time() - 60  # 1 minute ago
        stats.record_success("abc123")
        stats.record_success("def456")

        eta = stats.get_eta_minutes()
        remaining = 8  # 10 - 2 completed
        expected_eta = remaining / 2.0  # 2 videos per minute
        assert eta == pytest.approx(expected_eta, rel=0.1)

    def test_get_summary(self):
        """Test generating summary statistics."""
        stats = ExtractionStats(total_videos=5)
        stats.record_success("abc123")
        stats.record_failure("def456", "Error")
        stats.record_skip("ghi789", "Skip")

        summary = stats.get_summary()

        assert summary["total_videos"] == 5
        assert summary["completed"] == 1
        assert summary["failed"] == 1
        assert summary["skipped"] == 1
        assert summary["progress_percentage"] == 60.0
        assert "elapsed_time" in summary
        assert "rate_per_minute" in summary


class TestExtractionResult:
    """Test ExtractionResult data class."""

    def test_result_success(self):
        """Test successful extraction result."""
        result = ExtractionResult(
            video_id="abc123",
            success=True,
            output_path=Path("/test/output.md"),
            duration=120.5,
            file_size=1024
        )

        assert result.video_id == "abc123"
        assert result.success is True
        assert result.output_path == Path("/test/output.md")
        assert result.duration == 120.5
        assert result.file_size == 1024
        assert result.error is None

    def test_result_failure(self):
        """Test failed extraction result."""
        result = ExtractionResult(
            video_id="abc123",
            success=False,
            error="Extraction failed"
        )

        assert result.video_id == "abc123"
        assert result.success is False
        assert result.error == "Extraction failed"
        assert result.output_path is None
        assert result.duration is None
        assert result.file_size is None

    def test_result_to_dict(self):
        """Test converting result to dictionary."""
        result = ExtractionResult(
            video_id="abc123",
            success=True,
            output_path=Path("/test/output.md")
        )

        result_dict = result.to_dict()

        assert result_dict["video_id"] == "abc123"
        assert result_dict["success"] is True
        assert result_dict["output_path"] == "/test/output.md"


class TestTORSupport:
    """Test TOR proxy support functionality."""

    @patch('socket.socket')
    def test_check_tor_connection_success(self, mock_socket):
        """Test successful TOR connection check."""
        mock_sock = Mock()
        mock_socket.return_value = mock_sock
        mock_sock.connect.return_value = None

        result = check_tor_connection(port=9050)
        assert result is True

        mock_sock.connect.assert_called_once_with(('127.0.0.1', 9050))
        mock_sock.close.assert_called_once()

    @patch('socket.socket')
    def test_check_tor_connection_failure(self, mock_socket):
        """Test failed TOR connection check."""
        mock_sock = Mock()
        mock_socket.return_value = mock_sock
        mock_sock.connect.side_effect = ConnectionRefusedError()

        result = check_tor_connection(port=9050)
        assert result is False

    @patch('youtube_processor.core.extractor.check_tor_connection')
    def test_setup_tor_proxy_available(self, mock_check):
        """Test TOR proxy setup when TOR is available."""
        mock_check.return_value = True

        result = setup_tor_proxy(port=9050)
        assert result is True

    @patch('youtube_processor.core.extractor.check_tor_connection')
    def test_setup_tor_proxy_unavailable(self, mock_check):
        """Test TOR proxy setup when TOR is unavailable."""
        mock_check.return_value = False

        with pytest.raises(TORConnectionError, match="TOR proxy not available"):
            setup_tor_proxy(port=9050, required=True)

    @patch('youtube_processor.core.extractor.check_tor_connection')
    def test_setup_tor_proxy_optional(self, mock_check):
        """Test optional TOR proxy setup."""
        mock_check.return_value = False

        result = setup_tor_proxy(port=9050, required=False)
        assert result is False


class TestSingleVideoExtraction:
    """Test single video extraction functionality."""

    @patch('youtube_processor.core.extractor.yt_dlp.YoutubeDL')
    def test_extract_single_video_success(self, mock_ydl_class, temp_dir):
        """Test successful single video extraction."""
        # Mock yt-dlp
        mock_ydl = Mock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {
            'title': 'Test Video',
            'description': 'Test description',
            'duration': 300
        }

        video = VideoMetadata(
            video_id="abc123",
            title="Test Video",
            duration_seconds=300,
            upload_date="2024-01-15"
        )

        result = extract_single_video(
            video=video,
            output_dir=temp_dir,
            use_tor=False
        )

        assert isinstance(result, ExtractionResult)
        assert result.success is True
        assert result.video_id == "abc123"
        assert result.output_path is not None

    @patch('youtube_processor.core.extractor.yt_dlp.YoutubeDL')
    def test_extract_single_video_failure(self, mock_ydl_class, temp_dir):
        """Test failed single video extraction."""
        # Mock yt-dlp to raise exception
        mock_ydl = Mock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.side_effect = Exception("Extraction failed")

        video = VideoMetadata(
            video_id="abc123",
            title="Test Video",
            duration_seconds=300,
            upload_date="2024-01-15"
        )

        result = extract_single_video(
            video=video,
            output_dir=temp_dir,
            use_tor=False
        )

        assert isinstance(result, ExtractionResult)
        assert result.success is False
        assert result.error == "Extraction failed"

    @patch('youtube_processor.core.extractor.yt_dlp.YoutubeDL')
    def test_extract_single_video_with_tor(self, mock_ydl_class, temp_dir):
        """Test single video extraction with TOR proxy."""
        mock_ydl = Mock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {
            'title': 'Test Video',
            'description': 'Test description'
        }

        video = VideoMetadata(
            video_id="abc123",
            title="Test Video",
            duration_seconds=300,
            upload_date="2024-01-15"
        )

        result = extract_single_video(
            video=video,
            output_dir=temp_dir,
            use_tor=True,
            tor_port=9050
        )

        # Verify TOR proxy configuration was passed to yt-dlp
        call_args = mock_ydl_class.call_args[0][0]
        assert 'proxy' in call_args
        assert 'socks5://127.0.0.1:9050' in call_args['proxy']


class TestParallelExtraction:
    """Test parallel video extraction."""

    @patch('youtube_processor.core.extractor.setup_tor_proxy')
    @patch('youtube_processor.core.extractor.extract_single_video')
    def test_extract_videos_success(self, mock_extract, mock_tor, extractor, sample_videos, temp_dir):
        """Test successful parallel extraction."""
        mock_tor.return_value = True

        # Mock successful extractions
        def mock_extract_side_effect(video, **kwargs):
            return ExtractionResult(
                video_id=video.video_id,
                success=True,
                output_path=Path(f"/test/{video.video_id}.md")
            )

        mock_extract.side_effect = mock_extract_side_effect

        results = extractor.extract_videos(
            videos=sample_videos,
            output_dir=temp_dir,
            channel_name="TestChannel"
        )

        assert len(results) == 3
        assert all(result.success for result in results)
        assert mock_extract.call_count == 3

    @patch('youtube_processor.core.extractor.setup_tor_proxy')
    @patch('youtube_processor.core.extractor.extract_single_video')
    def test_extract_videos_with_failures(self, mock_extract, mock_tor, extractor, sample_videos, temp_dir):
        """Test parallel extraction with some failures."""
        mock_tor.return_value = True

        # Mock mixed results
        def mock_extract_side_effect(video, **kwargs):
            if video.video_id == "def456":
                return ExtractionResult(
                    video_id=video.video_id,
                    success=False,
                    error="Extraction failed"
                )
            return ExtractionResult(
                video_id=video.video_id,
                success=True,
                output_path=Path(f"/test/{video.video_id}.md")
            )

        mock_extract.side_effect = mock_extract_side_effect

        results = extractor.extract_videos(
            videos=sample_videos,
            output_dir=temp_dir,
            channel_name="TestChannel"
        )

        assert len(results) == 3
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        assert len(successful) == 2
        assert len(failed) == 1
        assert failed[0].video_id == "def456"

    @patch('youtube_processor.core.extractor.setup_tor_proxy')
    def test_extract_videos_tor_failure(self, mock_tor, extractor, sample_videos, temp_dir):
        """Test parallel extraction when TOR setup fails."""
        mock_tor.side_effect = TORConnectionError("TOR not available")

        with pytest.raises(TORConnectionError):
            extractor.extract_videos(
                videos=sample_videos,
                output_dir=temp_dir,
                channel_name="TestChannel"
            )

    def test_extract_videos_empty_list(self, extractor):
        """Test parallel extraction with empty video list."""
        results = extractor.extract_videos(
            videos=[],
            output_dir=Path("/tmp"),  # Use /tmp for empty list test
            channel_name="TestChannel"
        )

        assert results == []

    @patch('youtube_processor.core.extractor.setup_tor_proxy')
    @patch('youtube_processor.core.extractor.extract_single_video')
    def test_extract_videos_with_history_manager(self, mock_extract, mock_tor, extractor, sample_videos, mock_history_manager, temp_dir):
        """Test parallel extraction with history manager."""
        mock_tor.return_value = True

        # Mock history manager to skip one video
        def get_status_side_effect(video_id):
            if video_id == "def456":
                return "completed"
            return "new"

        mock_history_manager.get_extraction_status.side_effect = get_status_side_effect

        mock_extract.return_value = ExtractionResult(
            video_id="test",
            success=True,
            output_path=Path("/test/test.md")
        )

        results = extractor.extract_videos(
            videos=sample_videos,
            output_dir=temp_dir,
            channel_name="TestChannel",
            history_manager=mock_history_manager
        )

        # Should only extract 2 videos (skipping the completed one)
        assert len(results) == 2  # Only new videos are extracted
        # All results should be successful since one video was skipped via history manager
        assert all(result.success for result in results)

    @patch('youtube_processor.core.extractor.setup_tor_proxy')
    @patch('youtube_processor.core.extractor.extract_single_video')
    def test_extract_videos_custom_workers(self, mock_extract, mock_tor, sample_videos, temp_dir):
        """Test parallel extraction with custom worker count."""
        mock_tor.return_value = True
        mock_extract.return_value = ExtractionResult(
            video_id="test",
            success=True,
            output_path=Path("/test/test.md")
        )

        extractor = ParallelExtractor(max_workers=5, use_tor=False)

        results = extractor.extract_videos(
            videos=sample_videos,
            output_dir=temp_dir,
            channel_name="TestChannel"
        )

        assert len(results) == 3
        assert extractor.max_workers == 5

    @patch('youtube_processor.core.extractor.setup_tor_proxy')
    @patch('youtube_processor.core.extractor.extract_single_video')
    def test_extract_videos_progress_callback(self, mock_extract, mock_tor, extractor, sample_videos, temp_dir):
        """Test parallel extraction with progress callback."""
        mock_tor.return_value = True
        mock_extract.return_value = ExtractionResult(
            video_id="test",
            success=True,
            output_path=Path("/test/test.md")
        )

        progress_calls = []

        def progress_callback(completed, total, video_id):
            progress_calls.append((completed, total, video_id))

        extractor.extract_videos(
            videos=sample_videos,
            output_dir=temp_dir,
            channel_name="TestChannel",
            progress_callback=progress_callback
        )

        # Should have received progress updates
        assert len(progress_calls) >= 3


class TestErrorHandling:
    """Test error handling and custom exceptions."""

    def test_extraction_error_creation(self):
        """Test ExtractionError exception."""
        error = ExtractionError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)

    def test_tor_connection_error_creation(self):
        """Test TORConnectionError exception."""
        error = TORConnectionError("TOR error")
        assert str(error) == "TOR error"
        assert isinstance(error, ExtractionError)

    def test_video_extraction_error_creation(self):
        """Test VideoExtractionError exception."""
        error = VideoExtractionError("Video error", video_id="abc123")
        assert str(error) == "Video error"
        assert error.video_id == "abc123"
        assert isinstance(error, ExtractionError)


class TestUtilityMethods:
    """Test utility and helper methods."""

    def test_extractor_validate_output_dir(self, extractor):
        """Test output directory validation."""
        # Valid directory should pass
        valid_dir = Path("/tmp")
        result = extractor._validate_output_dir(valid_dir)
        assert result is True

        # Non-existent directory should be created
        non_existent = Path("/tmp/test_youtube_processor_nonexistent")
        if non_existent.exists():
            non_existent.rmdir()

        result = extractor._validate_output_dir(non_existent)
        assert result is True
        # Cleanup
        if non_existent.exists():
            non_existent.rmdir()

    def test_extractor_prepare_ydl_opts(self, extractor):
        """Test yt-dlp options preparation."""
        opts = extractor._prepare_ydl_opts(use_tor=False)

        assert 'format' in opts
        assert 'writesubtitles' in opts
        assert 'writeautomaticsub' in opts

    def test_extractor_prepare_ydl_opts_with_tor(self, extractor):
        """Test yt-dlp options with TOR proxy."""
        opts = extractor._prepare_ydl_opts(use_tor=True, tor_port=9050)

        assert 'proxy' in opts
        assert 'socks5://127.0.0.1:9050' in opts['proxy']

    def test_extractor_generate_output_filename(self, extractor, sample_videos):
        """Test output filename generation."""
        video = sample_videos[0]
        filename = extractor._generate_output_filename(video)

        assert filename.endswith('.md')
        assert 'Test Video 1' in filename or 'abc123' in filename

    def test_extractor_estimate_completion_time(self, extractor):
        """Test completion time estimation."""
        stats = ExtractionStats(total_videos=10)
        stats.start_time = time.time() - 60  # 1 minute ago
        stats.record_success("test1")
        stats.record_success("test2")

        eta = extractor._estimate_completion_time(stats)
        assert eta > 0  # Should estimate some time remaining