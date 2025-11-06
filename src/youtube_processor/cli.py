"""Main CLI entry point for YouTube Processor."""

import os
import sys
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.prompt import Confirm

from youtube_processor import __version__
from youtube_processor.core.discovery import ChannelDiscovery, VideoMetadata
from youtube_processor.core.extractor import ParallelExtractor, ExtractionResult
from youtube_processor.ui.selection import VideoSelector
from youtube_processor.core.history import ExtractionHistory
from youtube_processor.utils.config import Config
from youtube_processor.docker import check_docker_available, DockerTORManager

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

console = Console()


def get_api_key() -> Optional[str]:
    """Get YouTube API key from environment or config.

    Returns:
        API key if found, None otherwise
    """
    # Try environment variable first
    api_key = os.getenv('YOUTUBE_API_KEY')
    if api_key:
        return api_key

    # Try config file
    try:
        config = Config()
        return config.get('youtube_api_key')
    except Exception:
        return None


def setup_config(config_path: Optional[Path] = None) -> Config:
    """Setup and return configuration instance.

    Args:
        config_path: Optional path to config file

    Returns:
        Configuration instance
    """
    return Config(config_path)


def format_duration(seconds: int) -> str:
    """Format duration from seconds to readable format.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string
    """
    if seconds < 60:
        return f"0:{seconds:02d}"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}:{secs:02d}"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:02d}"


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted size string
    """
    if size_bytes == 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    size = float(size_bytes)

    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1

    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    else:
        return f"{size:.1f} {units[unit_index]}"


def format_number(number: int) -> str:
    """Format number with thousands separator.

    Args:
        number: Number to format

    Returns:
        Formatted number string
    """
    return f"{number:,}"


@click.group()
@click.version_option(version=__version__)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
def main(verbose: bool) -> None:
    """YouTube Processor - Professional CLI for YouTube video extraction and analysis."""
    if verbose:
        console.print(f"[bold green]YouTube Processor v{__version__}[/bold green]")
        console.print("Verbose mode enabled")
        logging.getLogger().setLevel(logging.INFO)


@main.command("list")
@click.argument("channel_url")
@click.option("--max-results", default=50, help="Maximum number of videos to discover")
@click.option("--order", default="relevance", help="Sort order (relevance, date, viewCount, etc.)")
@click.option("--published-after", help="Filter videos published after this date (YYYY-MM-DD)")
@click.option("--published-before", help="Filter videos published before this date (YYYY-MM-DD)")
@click.option("--output", "-o", type=click.Path(), help="Save results to JSON file")
def list_command(
    channel_url: str,
    max_results: int,
    order: str,
    published_after: Optional[str],
    published_before: Optional[str],
    output: Optional[str]
) -> None:
    """List videos from a YouTube channel."""
    try:
        # Get API key
        api_key = get_api_key()
        if not api_key:
            console.print("[red]Error: YouTube API key not found.[/red]")
            console.print("Set YOUTUBE_API_KEY environment variable or configure in settings.")
            sys.exit(1)

        # Show progress while discovering
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Discovering videos...", total=None)

            discovery = ChannelDiscovery(api_key=api_key, max_results=max_results)
            channel_name, videos = discovery.discover_videos(
                channel_url=channel_url,
                max_results=max_results,
                order=order,
                published_after=published_after,
                published_before=published_before
            )

            progress.update(task, completed=True)

        if not videos:
            console.print("[yellow]No videos found for this channel.[/yellow]")
            return

        # Create table for results
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Title", style="cyan", no_wrap=False, max_width=50)
        table.add_column("Duration", justify="center")
        table.add_column("Views", justify="right")
        table.add_column("Upload Date", justify="center")

        for video in videos:
            table.add_row(
                video.title,
                format_duration(video.duration_seconds),
                format_number(video.view_count),
                video.upload_date[:10] if video.upload_date else "Unknown"
            )

        console.print(f"\n[bold green]Found {len(videos)} videos[/bold green]")
        console.print(table)

        # Save to file if requested
        if output:
            import json
            output_path = Path(output)
            data = [video.__dict__ for video in videos]
            output_path.write_text(json.dumps(data, indent=2, default=str))
            console.print(f"\n[green]Results saved to {output_path}[/green]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        sys.exit(1)


@main.command("extract")
@click.argument("channel_url")
@click.option("--max-results", default=50, help="Maximum number of videos to discover")
@click.option("--output-dir", "-o", type=click.Path(), help="Output directory for extracted videos")
@click.option(
    "--workers",
    default=None,
    type=int,
    help="Number of parallel workers (default: 10, recommended with TOR: 15)"
)
@click.option(
    "--use-tor/--no-tor",
    default=None,
    help="Use TOR proxy to avoid rate limits. Requires Docker or manual TOR setup."
)
@click.option(
    "--auto-start-tor/--no-auto-start-tor",
    default=True,
    help="Automatically start TOR via Docker if available (default: True)"
)
@click.option("--non-interactive", is_flag=True, help="Skip video selection (extract all)")
@click.option("--analyze/--no-analyze", default=False, help="Analyze transcripts with Claude API")
@click.option("--model", default="claude-haiku-4-5-20251001", help="Claude model to use for analysis")
@click.option("--haiku", "model_shortcut", flag_value="haiku", help="Use Haiku 4.5 (fastest, cheapest: ~$0.007/video)")
@click.option("--sonnet", "model_shortcut", flag_value="sonnet", help="Use Sonnet 4.5 (balanced: ~$0.08/video)")
@click.option("--opus", "model_shortcut", flag_value="opus", help="Use Opus 4.1 (best quality: ~$0.40/video)")
def extract_command(
    channel_url: str,
    max_results: int,
    output_dir: Optional[str],
    workers: Optional[int],
    use_tor: Optional[bool],
    auto_start_tor: bool,
    non_interactive: bool,
    analyze: bool,
    model: str,
    model_shortcut: Optional[str]
) -> None:
    """Extract transcripts from a YouTube channel.

    This command fetches all videos from the specified channel, allows you to
    select which videos to extract, and downloads transcripts in parallel.

    Examples:

        # Basic extraction
        youtube-processor extract @channelname

        # High-performance extraction with TOR
        youtube-processor extract @channelname --use-tor --workers 15

        # Custom output directory
        youtube-processor extract @channelname --output-dir ./my-output

    The tool tracks extraction history, so re-running only processes new videos.
    """
    try:
        # Handle model shortcuts
        if model_shortcut:
            model_map = {
                "haiku": "claude-haiku-4-5-20251001",
                "sonnet": "claude-sonnet-4-5-20250929",
                "opus": "claude-opus-4-1-20250805"
            }
            model = model_map[model_shortcut]
        
        # Get API key
        api_key = get_api_key()
        if not api_key:
            console.print("[red]Error: YouTube API key not found.[/red]")
            console.print("Set YOUTUBE_API_KEY environment variable or configure in settings.")
            sys.exit(1)

        # Validate Anthropic API key if analysis is requested
        if analyze:
            anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
            if not anthropic_api_key:
                console.print("[red]Error: ANTHROPIC_API_KEY not set[/red]")
                console.print("Set ANTHROPIC_API_KEY environment variable to use --analyze flag.")
                sys.exit(1)

        # Setup configuration
        config = setup_config()

        # Use config defaults if not specified
        if workers is None:
            workers = config.get('parallel_workers', 10)
        if use_tor is None:
            use_tor = config.get('use_tor', False)
        if output_dir is None:
            output_dir = config.get('output_dir', 'output')

        # TOR Setup
        if use_tor:
            # Check Docker and auto-start if needed
            if auto_start_tor and check_docker_available():
                manager = DockerTORManager()

                if not manager.is_running():
                    console.print("[cyan]Starting TOR proxy...[/cyan]")
                    if manager.start_tor():
                        console.print("[green]✓[/green] TOR started")
                        import time
                        time.sleep(5)  # Wait for TOR initialization
                    else:
                        console.print("[yellow]Warning:[/yellow] Failed to start TOR")
                        console.print("Continuing without proxy")
                        use_tor = False
                else:
                    console.print("[green]✓[/green] TOR proxy already running")
            elif use_tor and not check_docker_available() and auto_start_tor:
                console.print("[yellow]Warning:[/yellow] Docker not available for TOR auto-start")
                console.print("Please start TOR manually or install Docker")
                console.print("Continuing without proxy")
                use_tor = False

        # Step 1: Discover videos
        console.print("[bold blue]Step 1: Discovering videos...[/bold blue]")
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Discovering videos...", total=None)

            discovery = ChannelDiscovery(api_key=api_key, max_results=max_results)
            channel_name, videos = discovery.discover_videos(
                channel_url=channel_url,
                max_results=max_results
            )

            progress.update(task, completed=True)

        if not videos:
            console.print("[yellow]No videos found for this channel.[/yellow]")
            return

        console.print(f"[green]Found {len(videos)} videos[/green]")

        # Step 2: Select videos (unless non-interactive)
        if non_interactive:
            selected_videos = videos
            console.print("[blue]Non-interactive mode: all videos selected[/blue]")
        else:
            console.print("\n[bold blue]Step 2: Select videos to extract...[/bold blue]")
            selector = VideoSelector()
            selected_videos = selector.select_videos(videos)

        if not selected_videos:
            console.print("[yellow]No videos selected for extraction.[/yellow]")
            return

        console.print(f"[green]Selected {len(selected_videos)} videos for extraction[/green]")

        # Step 3: Extract videos
        console.print(f"\n[bold blue]Step 3: Extracting videos...[/bold blue]")

        extractor = ParallelExtractor(
            max_workers=workers,
            use_tor=use_tor
        )

        # Show extraction progress
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Extracting videos...", total=len(selected_videos))

            def progress_callback(completed: int, total: int, current_video: str):
                progress.update(task, completed=completed, description=f"Extracting: {current_video}")

            results = extractor.extract_videos(
                videos=selected_videos,
                output_dir=Path(output_dir),
                channel_name=channel_name,
                progress_callback=progress_callback
            )

        # Step 4: Run analysis if requested
        if analyze:
            from youtube_processor.workflows.analysis import AnalysisWorkflow

            workflow = AnalysisWorkflow(
                api_key=anthropic_api_key,
                model=model,
                console=console
            )

            # Get the channel directory path
            channel_dir = Path(output_dir) / "channels" / channel_name

            # Run analysis on successful extractions only
            successful_videos = [video for video, result in zip(selected_videos, results) if result.success]

            workflow.run(
                channel_name=channel_name,
                channel_dir=channel_dir,
                videos=successful_videos
            )

        # Step 5: Save results and show summary
        history = ExtractionHistory()
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        # Save to history
        for result in results:
            history.add_extraction(result.video_id, {
                'success': result.success,
                'output_path': str(result.output_path) if result.output_path else None,
                'error': result.error,
                'timestamp': result.timestamp.isoformat() if result.timestamp else None,
                'file_size': result.file_size
            })

        # Show results summary
        console.print(f"\n[bold green]Extraction Complete![/bold green]")
        console.print(f"[green]✓ Successful: {len(successful)}[/green]")
        if failed:
            console.print(f"[red]✗ Failed: {len(failed)}[/red]")

        # Show detailed results table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Video", style="cyan", no_wrap=False, max_width=40)
        table.add_column("Status", justify="center")
        table.add_column("Size", justify="right")
        table.add_column("Output", style="green", no_wrap=False, max_width=30)

        for result in results:
            video = next((v for v in selected_videos if v.video_id == result.video_id), None)
            video_title = video.title if video else result.video_id

            status = "[green]✓ Success[/green]" if result.success else "[red]✗ Failed[/red]"
            size = format_file_size(result.file_size) if result.file_size else "-"
            output_path = str(result.output_path.name) if result.output_path else result.error or "-"

            table.add_row(video_title, status, size, output_path)

        console.print(table)

    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        logger.exception("Extraction failed")
        sys.exit(1)


@main.command("info")
@click.argument("channel_url")
def info_command(channel_url: str) -> None:
    """Show detailed information about a YouTube channel."""
    try:
        # Get API key
        api_key = get_api_key()
        if not api_key:
            console.print("[red]Error: YouTube API key not found.[/red]")
            console.print("Set YOUTUBE_API_KEY environment variable or configure in settings.")
            sys.exit(1)

        # Get channel info
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Getting channel info...", total=None)

            discovery = ChannelDiscovery(api_key=api_key)
            channel_info = discovery.get_channel_info(channel_url)

            progress.update(task, completed=True)

        # Display channel information
        panel_content = f"""
[bold cyan]Channel:[/bold cyan] {channel_info.get('title', 'Unknown')}
[bold cyan]Subscribers:[/bold cyan] {format_number(channel_info.get('subscriber_count', 0))}
[bold cyan]Videos:[/bold cyan] {format_number(channel_info.get('video_count', 0))}
[bold cyan]Views:[/bold cyan] {format_number(channel_info.get('view_count', 0))}
[bold cyan]Created:[/bold cyan] {channel_info.get('published_at', 'Unknown')[:10]}

[bold cyan]Description:[/bold cyan]
{channel_info.get('description', 'No description available')[:200]}{'...' if len(channel_info.get('description', '')) > 200 else ''}
        """.strip()

        console.print(Panel(panel_content, title="Channel Information", border_style="blue"))

    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        sys.exit(1)


@main.command("status")
@click.option("--limit", default=20, help="Number of recent extractions to show")
def status_command(limit: int) -> None:
    """Show extraction history and statistics."""
    try:
        history = ExtractionHistory()

        # Get history and stats
        recent_extractions = history.get_history(limit=limit)
        stats = history.get_stats()

        # Show statistics panel
        stats_content = f"""
[bold cyan]Total Extractions:[/bold cyan] {format_number(stats.get('total_extractions', 0))}
[bold cyan]Successful:[/bold cyan] [green]{format_number(stats.get('successful_extractions', 0))}[/green]
[bold cyan]Failed:[/bold cyan] [red]{format_number(stats.get('failed_extractions', 0))}[/red]
[bold cyan]Total Size:[/bold cyan] {format_file_size(stats.get('total_size', 0))}
        """.strip()

        console.print(Panel(stats_content, title="Extraction Statistics", border_style="green"))

        # Show recent extractions
        if not recent_extractions:
            console.print("\n[yellow]No extractions in history.[/yellow]")
            return

        console.print(f"\n[bold blue]Recent Extractions (last {len(recent_extractions)}):[/bold blue]")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Video", style="cyan", no_wrap=False, max_width=40)
        table.add_column("Status", justify="center")
        table.add_column("Size", justify="right")
        table.add_column("Date", justify="center")

        for extraction in recent_extractions:
            status = "[green]✓ Success[/green]" if extraction.get('status') == 'completed' else "[red]✗ Failed[/red]"
            size = format_file_size(extraction.get('file_size', 0)) if extraction.get('file_size') else "-"
            date = extraction.get('timestamp', '')[:16].replace('T', ' ') if extraction.get('timestamp') else "Unknown"

            table.add_row(
                extraction.get('title', extraction.get('video_id', 'Unknown')),
                status,
                size,
                date
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error reading history: {str(e)}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()