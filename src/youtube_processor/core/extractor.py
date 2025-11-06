"""Parallel video extraction with TOR support."""

import logging
import socket
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import re

import yt_dlp

from .discovery import VideoMetadata
from .transcript_extractor import TranscriptExtractor
from ..utils.filename import sanitize_filename

# Configure logging
logger = logging.getLogger(__name__)


class ExtractionError(Exception):
    """Base exception for extraction operations."""
    pass


class TORConnectionError(ExtractionError):
    """Raised when TOR connection fails."""
    pass


class VideoExtractionError(ExtractionError):
    """Raised when video extraction fails."""

    def __init__(self, message: str, video_id: Optional[str] = None):
        super().__init__(message)
        self.video_id = video_id


@dataclass
class ExtractionResult:
    """Result of video extraction operation."""
    video_id: str
    success: bool
    output_path: Optional[Path] = None
    duration: Optional[float] = None
    file_size: Optional[int] = None
    error: Optional[str] = None
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        """Set timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = asdict(self)
        if result['output_path']:
            result['output_path'] = str(result['output_path'])
        if result['timestamp']:
            result['timestamp'] = result['timestamp'].isoformat()
        return result


class ExtractionStats:
    """Track statistics during parallel extraction."""

    def __init__(self, total_videos: int):
        """Initialize extraction statistics.

        Args:
            total_videos: Total number of videos to extract
        """
        self.total_videos = total_videos
        self.completed = 0
        self.failed = 0
        self.skipped = 0
        self.start_time = time.time()
        self.errors: List[Tuple[str, str]] = []

    def record_success(self, video_id: str) -> None:
        """Record successful extraction.

        Args:
            video_id: ID of successfully extracted video
        """
        self.completed += 1
        logger.debug(f"✅ [{self.completed}/{self.total_videos}] {video_id} extracted successfully")

    def record_failure(self, video_id: str, error: str) -> None:
        """Record failed extraction.

        Args:
            video_id: ID of failed video
            error: Error message
        """
        self.failed += 1
        self.errors.append((video_id, error))
        logger.warning(f"❌ [{self.failed} failed] {video_id}: {error}")

    def record_skip(self, video_id: str, reason: str) -> None:
        """Record skipped extraction.

        Args:
            video_id: ID of skipped video
            reason: Reason for skipping
        """
        self.skipped += 1
        logger.info(f"⏭️  [{self.skipped} skipped] {video_id}: {reason}")

    def get_progress_percentage(self) -> float:
        """Get current progress percentage.

        Returns:
            Progress percentage (0-100)
        """
        processed = self.completed + self.failed + self.skipped
        if self.total_videos == 0:
            return 100.0
        return (processed / self.total_videos) * 100.0

    def get_rate_per_minute(self) -> float:
        """Get extraction rate per minute.

        Returns:
            Extractions per minute
        """
        elapsed = time.time() - self.start_time
        if elapsed == 0:
            return 0.0
        return (self.completed * 60) / elapsed

    def get_eta_minutes(self) -> float:
        """Get estimated time to completion in minutes.

        Returns:
            ETA in minutes
        """
        rate = self.get_rate_per_minute()
        if rate == 0:
            return 0.0
        remaining = self.total_videos - self.completed - self.failed - self.skipped
        return remaining / rate

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics.

        Returns:
            Dictionary with summary statistics
        """
        elapsed = time.time() - self.start_time
        return {
            "total_videos": self.total_videos,
            "completed": self.completed,
            "failed": self.failed,
            "skipped": self.skipped,
            "progress_percentage": self.get_progress_percentage(),
            "elapsed_time": elapsed,
            "rate_per_minute": self.get_rate_per_minute(),
            "eta_minutes": self.get_eta_minutes(),
            "errors": self.errors.copy()
        }


def check_tor_connection(host: str = "127.0.0.1", port: int = 9050, timeout: int = 5) -> bool:
    """Check if TOR proxy is available.

    Args:
        host: TOR proxy host
        port: TOR proxy port
        timeout: Connection timeout in seconds

    Returns:
        True if TOR proxy is available
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.close()
        return True
    except (socket.error, socket.timeout):
        return False


def setup_tor_proxy(port: int = 9050, required: bool = True) -> bool:
    """Setup TOR proxy connection.

    Args:
        port: TOR proxy port
        required: Whether TOR is required (raises error if not available)

    Returns:
        True if TOR proxy is available

    Raises:
        TORConnectionError: If TOR is required but not available
    """
    logger.info(f"Checking TOR proxy on port {port}")

    if check_tor_connection(port=port):
        logger.info("✅ TOR proxy is available")
        return True
    else:
        if required:
            raise TORConnectionError(f"TOR proxy not available on port {port}")
        else:
            logger.warning("⚠️  TOR proxy not available, proceeding without")
            return False


def extract_single_video(
    video: VideoMetadata,
    output_dir: Path,
    use_tor: bool = False,
    tor_port: int = 9050,
    timeout: int = 300
) -> ExtractionResult:
    """Extract a single video.

    Args:
        video: VideoMetadata object
        output_dir: Output directory
        use_tor: Whether to use TOR proxy
        tor_port: TOR proxy port
        timeout: Extraction timeout in seconds

    Returns:
        ExtractionResult object
    """
    logger.info(f"Extracting video {video.video_id}: {video.title}")

    try:
        # Prepare output directory
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate output filename
        safe_title = sanitize_filename(video.title) or video.video_id
        output_path = output_dir / f"{safe_title}_{video.video_id}.md"

        # Prepare yt-dlp options
        ydl_opts = {
            'writesubtitles': True,
            'writeautomaticsub': True,
            'writeinfojson': True,
            'extract_flat': False,
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': timeout,
        }

        # Add TOR proxy if requested
        if use_tor:
            ydl_opts['proxy'] = f'socks5://127.0.0.1:{tor_port}'

        # Extract video information
        start_time = time.time()
        video_url = f"https://www.youtube.com/watch?v={video.video_id}"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)

        # Extract transcript using youtube-transcript-api
        transcript_text = TranscriptExtractor.extract(video.video_id)
        logger.info(f"Transcript extracted for {video.video_id}: {'✅' if transcript_text else '❌'}")

        # Generate markdown content
        content = _generate_video_markdown(video, info, transcript_text)

        # Write to file
        output_path.write_text(content, encoding='utf-8')

        # Calculate extraction duration and file size
        duration = time.time() - start_time
        file_size = output_path.stat().st_size if output_path.exists() else 0

        logger.info(f"✅ Successfully extracted {video.video_id} in {duration:.1f}s")

        return ExtractionResult(
            video_id=video.video_id,
            success=True,
            output_path=output_path,
            duration=duration,
            file_size=file_size
        )

    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Failed to extract {video.video_id}: {error_msg}")

        return ExtractionResult(
            video_id=video.video_id,
            success=False,
            error=error_msg
        )


def _generate_video_markdown(video: VideoMetadata, info: Dict[str, Any], transcript_text: Optional[str] = None) -> str:
    """Generate markdown content for extracted video.

    Args:
        video: VideoMetadata object
        info: yt-dlp info dictionary
        transcript_text: Extracted transcript text (optional)

    Returns:
        Markdown content string
    """
    # Extract additional info from yt-dlp
    description = info.get('description', video.description)
    duration = info.get('duration', video.duration_seconds)
    upload_date = info.get('upload_date', video.upload_date)

    # Format duration
    if duration:
        hours = duration // 3600
        minutes = (duration % 3600) // 60
        seconds = duration % 60
        if hours > 0:
            duration_str = f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            duration_str = f"{minutes}:{seconds:02d}"
    else:
        duration_str = "Unknown"

    # Generate timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build markdown content
    content = f"""# {video.title}

**Video ID:** {video.video_id}
**Channel:** {video.channel_title}
**Upload Date:** {upload_date}
**Duration:** {duration_str}
**Views:** {video.view_count:,} views
**Extracted:** {timestamp}

## Description

{description}

## Video Information

- **Video URL:** https://www.youtube.com/watch?v={video.video_id}
- **Channel ID:** {video.channel_id}
- **Like Count:** {video.like_count:,}
- **Comment Count:** {video.comment_count:,}

## Tags

{', '.join(video.tags) if video.tags else 'No tags available'}

## Transcript

{transcript_text if transcript_text else 'No transcript available for this video'}

---

*Extracted using YouTube Processor*
"""

    return content


class ParallelExtractor:
    """Extracts video content using parallel processing with TOR."""

    def __init__(
        self,
        max_workers: int = 10,
        use_tor: bool = True,
        tor_port: int = 9050,
        timeout: int = 300,
        retry_attempts: int = 3
    ):
        """Initialize parallel extractor.

        Args:
            max_workers: Maximum number of concurrent workers
            use_tor: Whether to use TOR proxy
            tor_port: TOR proxy port
            timeout: Extraction timeout per video
            retry_attempts: Number of retry attempts for failed extractions

        Raises:
            ValueError: If parameters are invalid
        """
        if max_workers <= 0:
            raise ValueError("max_workers must be positive")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if retry_attempts < 0:
            raise ValueError("retry_attempts must be non-negative")

        self.max_workers = max_workers
        self.use_tor = use_tor
        self.tor_port = tor_port
        self.timeout = timeout
        self.retry_attempts = retry_attempts

        logger.info(f"Initialized ParallelExtractor: workers={max_workers}, tor={use_tor}")

    def extract_videos(
        self,
        videos: List[VideoMetadata],
        output_dir: Path,
        channel_name: str,
        history_manager: Optional[Any] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> List[ExtractionResult]:
        """Extract content from multiple videos in parallel.

        Args:
            videos: List of VideoMetadata objects to extract
            output_dir: Base output directory for extracted content
            channel_name: Channel name for directory structure
            history_manager: Optional history manager for tracking
            progress_callback: Optional callback for progress updates

        Returns:
            List of ExtractionResult objects

        Raises:
            TORConnectionError: If TOR is required but not available
            ExtractionError: If extraction setup fails
        """
        logger.info(f"Starting parallel extraction of {len(videos)} videos")

        if not videos:
            logger.info("No videos to extract")
            return []

        # Validate output directory
        self._validate_output_dir(output_dir)

        # Setup TOR proxy if requested
        if self.use_tor:
            setup_tor_proxy(port=self.tor_port, required=True)

        # Initialize statistics
        stats = ExtractionStats(total_videos=len(videos))

        # Filter videos if history manager is provided
        videos_to_extract = self._filter_videos(videos, history_manager, stats)

        if not videos_to_extract:
            logger.info("No new videos to extract")
            return []

        logger.info(f"🚀 Starting extraction: {len(videos_to_extract)} videos, {self.max_workers} workers")

        # Create channel-based directory structure
        transcripts_dir = DirectoryManager.create_channel_transcripts_dir(output_dir, channel_name)
        logger.info(f"Using channel directory: {transcripts_dir}")

        results = []

        # Use ThreadPoolExecutor for concurrent extraction
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit extraction tasks
            future_to_video = {}
            for video in videos_to_extract:
                future = executor.submit(
                    self._extract_video_with_retry,
                    video=video,
                    output_dir=transcripts_dir,
                    stats=stats
                )
                future_to_video[future] = video

            # Collect results as they complete
            for future in as_completed(future_to_video):
                video = future_to_video[future]
                try:
                    result = future.result()
                    results.append(result)

                    # Update history manager if provided
                    if history_manager:
                        if result.success:
                            history_manager.record_extraction_complete(
                                video.video_id,
                                str(result.output_path) if result.output_path else None
                            )
                        else:
                            history_manager.record_extraction_error(
                                video.video_id,
                                result.error or "Unknown error"
                            )

                    # Call progress callback if provided
                    if progress_callback:
                        progress_callback(
                            stats.completed + stats.failed,
                            stats.total_videos,
                            video.video_id
                        )

                except Exception as e:
                    logger.error(f"Unexpected error processing {video.video_id}: {e}")
                    result = ExtractionResult(
                        video_id=video.video_id,
                        success=False,
                        error=f"Unexpected error: {e}"
                    )
                    results.append(result)
                    stats.record_failure(video.video_id, str(e))

        # Print final summary
        self._print_summary(stats)

        return results

    def _filter_videos(
        self,
        videos: List[VideoMetadata],
        history_manager: Optional[Any],
        stats: ExtractionStats
    ) -> List[VideoMetadata]:
        """Filter videos based on extraction history.

        Args:
            videos: List of all videos
            history_manager: Optional history manager
            stats: Statistics tracker

        Returns:
            List of videos to extract
        """
        if not history_manager:
            return videos

        videos_to_extract = []
        for video in videos:
            status = history_manager.get_extraction_status(video.video_id)
            if status == "completed":
                stats.record_skip(video.video_id, "Already extracted")
            else:
                videos_to_extract.append(video)
                if hasattr(history_manager, 'record_extraction_start'):
                    history_manager.record_extraction_start(video.video_id)

        return videos_to_extract

    def _extract_video_with_retry(
        self,
        video: VideoMetadata,
        output_dir: Path,
        stats: ExtractionStats
    ) -> ExtractionResult:
        """Extract video with retry logic.

        Args:
            video: VideoMetadata object
            output_dir: Output directory
            stats: Statistics tracker

        Returns:
            ExtractionResult object
        """
        last_error = None

        for attempt in range(self.retry_attempts + 1):
            try:
                if attempt > 0:
                    logger.info(f"Retry attempt {attempt} for {video.video_id}")

                result = extract_single_video(
                    video=video,
                    output_dir=output_dir,
                    use_tor=self.use_tor,
                    tor_port=self.tor_port,
                    timeout=self.timeout
                )

                if result.success:
                    stats.record_success(video.video_id)
                    return result
                else:
                    last_error = result.error
                    if attempt == self.retry_attempts:
                        stats.record_failure(video.video_id, last_error or "Unknown error")
                        return result

            except Exception as e:
                last_error = str(e)
                if attempt == self.retry_attempts:
                    logger.error(f"All retry attempts failed for {video.video_id}: {last_error}")
                    stats.record_failure(video.video_id, last_error)
                    return ExtractionResult(
                        video_id=video.video_id,
                        success=False,
                        error=last_error
                    )

            # Wait before retry
            if attempt < self.retry_attempts:
                time.sleep(2 ** attempt)  # Exponential backoff

        # This should not be reached
        stats.record_failure(video.video_id, last_error or "Unknown error")
        return ExtractionResult(
            video_id=video.video_id,
            success=False,
            error=last_error or "All retry attempts failed"
        )

    def _validate_output_dir(self, output_dir: Path) -> bool:
        """Validate and create output directory.

        Args:
            output_dir: Output directory path

        Returns:
            True if valid

        Raises:
            ExtractionError: If directory cannot be created
        """
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            raise ExtractionError(f"Cannot create output directory {output_dir}: {e}")

    def _prepare_ydl_opts(self, use_tor: bool = False, tor_port: int = 9050) -> Dict[str, Any]:
        """Prepare yt-dlp options.

        Args:
            use_tor: Whether to use TOR proxy
            tor_port: TOR proxy port

        Returns:
            yt-dlp options dictionary
        """
        opts = {
            'format': 'best',
            'writesubtitles': True,
            'writeautomaticsub': True,
            'writeinfojson': True,
            'extract_flat': False,
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': self.timeout,
        }

        if use_tor:
            opts['proxy'] = f'socks5://127.0.0.1:{tor_port}'

        return opts

    def _generate_output_filename(self, video: VideoMetadata) -> str:
        """Generate output filename for video.

        Args:
            video: VideoMetadata object

        Returns:
            Safe filename string
        """
        safe_title = sanitize_filename(video.title) or video.video_id
        return f"{safe_title}_{video.video_id}.md"

    def _estimate_completion_time(self, stats: ExtractionStats) -> float:
        """Estimate completion time based on current stats.

        Args:
            stats: Current extraction statistics

        Returns:
            Estimated completion time in minutes
        """
        return stats.get_eta_minutes()

    def _print_summary(self, stats: ExtractionStats) -> None:
        """Print extraction summary.

        Args:
            stats: Final extraction statistics
        """
        summary = stats.get_summary()
        elapsed_minutes = summary['elapsed_time'] / 60

        logger.info("\n" + "=" * 60)
        logger.info("PARALLEL EXTRACTION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Total Videos:     {summary['total_videos']}")
        logger.info(f"✅ Successful:    {summary['completed']}")
        logger.info(f"❌ Failed:        {summary['failed']}")
        logger.info(f"⏭️  Skipped:       {summary['skipped']}")
        logger.info(f"⏱️  Total Time:    {elapsed_minutes:.1f} minutes")
        logger.info(f"📊 Average Rate:  {summary['rate_per_minute']:.1f} videos/min")

        if summary['errors']:
            logger.info(f"\n❌ Failed Videos ({len(summary['errors'])}):")
            for video_id, error in summary['errors']:
                logger.info(f"   - {video_id}: {error}")

        logger.info("=" * 60)


class DirectoryManager:
    """Manages directory structure creation for channel-based organization."""

    @staticmethod
    def create_channel_transcripts_dir(base_path: Path, channel_name: str) -> Path:
        """Create transcripts directory for a channel.

        Args:
            base_path: Base output directory
            channel_name: Channel name

        Returns:
            Path to transcripts directory
        """
        transcripts_dir = base_path / "channels" / channel_name / "transcripts"
        transcripts_dir.mkdir(parents=True, exist_ok=True)
        return transcripts_dir

    @staticmethod
    def create_channel_analyses_dir(base_path: Path, channel_name: str) -> Path:
        """Create analyses directory for a channel.

        Args:
            base_path: Base output directory
            channel_name: Channel name

        Returns:
            Path to analyses directory
        """
        analyses_dir = base_path / "channels" / channel_name / "analyses"
        analyses_dir.mkdir(parents=True, exist_ok=True)
        return analyses_dir

    @staticmethod
    def create_channel_kb_dir(base_path: Path, channel_name: str) -> Path:
        """Create knowledge-base directory for a channel.

        Args:
            base_path: Base output directory
            channel_name: Channel name

        Returns:
            Path to knowledge-base directory
        """
        kb_dir = base_path / "channels" / channel_name / "knowledge-base"
        kb_dir.mkdir(parents=True, exist_ok=True)
        return kb_dir


class PathGenerator:
    """Generates file paths for the new directory structure."""

    @staticmethod
    def get_transcript_json_path(base_path: Path, channel_name: str, video_id: str) -> Path:
        """Get path for transcript JSON file.

        Args:
            base_path: Base output directory
            channel_name: Channel name
            video_id: Video ID

        Returns:
            Path to transcript JSON file
        """
        return base_path / "channels" / channel_name / "transcripts" / f"{video_id}.json"

    @staticmethod
    def get_transcript_txt_path(base_path: Path, channel_name: str, video_id: str, video_title: str) -> Path:
        """Get path for transcript text file.

        Args:
            base_path: Base output directory
            channel_name: Channel name
            video_id: Video ID
            video_title: Video title

        Returns:
            Path to transcript text file
        """
        safe_title = sanitize_filename(video_title) or video_id
        return base_path / "channels" / channel_name / "transcripts" / f"{safe_title}_{video_id}.md"

    @staticmethod
    def get_analysis_path(base_path: Path, channel_name: str, video_id: str) -> Path:
        """Get path for analysis JSON file.

        Args:
            base_path: Base output directory
            channel_name: Channel name
            video_id: Video ID

        Returns:
            Path to analysis JSON file
        """
        return base_path / "channels" / channel_name / "analyses" / f"{video_id}-analysis.json"