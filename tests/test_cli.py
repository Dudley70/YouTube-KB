"""Comprehensive CLI tests."""

import pytest
import json
import os
from unittest.mock import Mock, patch, MagicMock, call
from click.testing import CliRunner
from pathlib import Path
from io import StringIO

from youtube_processor.cli import (
    main,
    extract_command,
    list_command,
    info_command,
    status_command,
    setup_config,
    get_api_key
)
from youtube_processor.core.discovery import VideoMetadata, ChannelDiscovery
from youtube_processor.core.extractor import ExtractionResult, ParallelExtractor
from youtube_processor.ui.selection import VideoSelector
from youtube_processor.core.history import ExtractionHistory
from youtube_processor.utils.config import Config


class TestCLIBasics:
    """Test basic CLI functionality."""

    def test_cli_help(self):
        """CLI --help displays usage."""
        runner = CliRunner()
        result = runner.invoke(main, ['--help'])

        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert "extract" in result.output
        assert "list" in result.output
        assert "info" in result.output
        assert "status" in result.output

    def test_cli_version(self):
        """CLI --version displays version."""
        runner = CliRunner()
        result = runner.invoke(main, ['--version'])

        assert result.exit_code == 0
        assert "version" in result.output.lower()

    def test_extract_command_exists(self):
        """extract command is available."""
        runner = CliRunner()
        result = runner.invoke(main, ['extract', '--help'])

        assert result.exit_code == 0
        assert "extract" in result.output.lower()

    def test_list_command_exists(self):
        """list command is available."""
        runner = CliRunner()
        result = runner.invoke(main, ['list', '--help'])

        assert result.exit_code == 0
        assert "list" in result.output.lower()

    def test_info_command_exists(self):
        """info command is available."""
        runner = CliRunner()
        result = runner.invoke(main, ['info', '--help'])

        assert result.exit_code == 0
        assert "info" in result.output.lower()

    def test_status_command_exists(self):
        """status command is available."""
        runner = CliRunner()
        result = runner.invoke(main, ['status', '--help'])

        assert result.exit_code == 0
        assert "status" in result.output.lower()


class TestConfigurationManagement:
    """Test configuration and API key management."""

    def test_get_api_key_from_env(self):
        """get_api_key retrieves key from environment."""
        with patch.dict(os.environ, {'YOUTUBE_API_KEY': 'test_key'}):
            api_key = get_api_key()
            assert api_key == 'test_key'

    def test_get_api_key_from_config(self):
        """get_api_key retrieves key from config when env not set."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('youtube_processor.cli.Config') as mock_config:
                mock_config.return_value.get.return_value = 'config_key'
                api_key = get_api_key()
                assert api_key == 'config_key'

    def test_get_api_key_missing(self):
        """get_api_key returns None when no key available."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('youtube_processor.cli.Config') as mock_config:
                mock_config.return_value.get.return_value = None
                api_key = get_api_key()
                assert api_key is None

    def test_setup_config_creates_config(self):
        """setup_config creates configuration file."""
        with patch('youtube_processor.cli.Config') as mock_config:
            mock_config_instance = Mock()
            mock_config.return_value = mock_config_instance

            config = setup_config()

            mock_config.assert_called_once()
            assert config == mock_config_instance

    def test_setup_config_with_custom_path(self):
        """setup_config accepts custom config path."""
        test_path = Path("/tmp/test_config.json")
        with patch('youtube_processor.cli.Config') as mock_config:
            setup_config(config_path=test_path)
            mock_config.assert_called_once_with(test_path)


class TestListCommand:
    """Test list command functionality."""

    @patch('youtube_processor.cli.get_api_key')
    @patch('youtube_processor.cli.ChannelDiscovery')
    def test_list_command_success(self, mock_discovery, mock_get_api_key):
        """list command successfully discovers and displays videos."""
        # Mock API key
        mock_get_api_key.return_value = 'test_api_key'

        # Mock video metadata
        mock_videos = [
            VideoMetadata(
                video_id='test_id_1',
                title='Test Video 1',
                duration_seconds=300,
                view_count=1000
            ),
            VideoMetadata(
                video_id='test_id_2',
                title='Test Video 2',
                duration_seconds=450,
                view_count=2000
            )
        ]

        # Mock discovery
        mock_discovery_instance = Mock()
        mock_discovery_instance.discover_videos.return_value = mock_videos
        mock_discovery.return_value = mock_discovery_instance

        runner = CliRunner()
        result = runner.invoke(main, ['list', 'https://www.youtube.com/c/testchannel'])

        assert result.exit_code == 0
        assert 'Test Video 1' in result.output
        assert 'Test Video 2' in result.output
        assert '5:00' in result.output  # 300 seconds formatted
        assert '7:30' in result.output  # 450 seconds formatted

    def test_list_command_no_api_key(self):
        """list command fails gracefully without API key."""
        with patch('youtube_processor.cli.get_api_key', return_value=None):
            runner = CliRunner()
            result = runner.invoke(main, ['list', 'https://www.youtube.com/c/testchannel'])

            assert result.exit_code != 0
            assert 'API key' in result.output

    @patch('youtube_processor.cli.get_api_key')
    @patch('youtube_processor.cli.ChannelDiscovery')
    def test_list_command_invalid_channel(self, mock_discovery, mock_get_api_key):
        """list command handles invalid channel URL."""
        mock_get_api_key.return_value = 'test_api_key'

        mock_discovery_instance = Mock()
        mock_discovery_instance.discover_videos.side_effect = Exception("Invalid channel")
        mock_discovery.return_value = mock_discovery_instance

        runner = CliRunner()
        result = runner.invoke(main, ['list', 'invalid_url'])

        assert result.exit_code != 0
        assert 'error' in result.output.lower()

    @patch('youtube_processor.cli.get_api_key')
    @patch('youtube_processor.cli.ChannelDiscovery')
    def test_list_command_with_max_results(self, mock_discovery, mock_get_api_key):
        """list command respects max_results parameter."""
        mock_get_api_key.return_value = 'test_api_key'

        mock_discovery_instance = Mock()
        mock_discovery_instance.discover_videos.return_value = []  # Return empty list
        mock_discovery.return_value = mock_discovery_instance

        runner = CliRunner()
        result = runner.invoke(main, ['list', 'https://www.youtube.com/c/testchannel', '--max-results', '10'])

        assert result.exit_code == 0
        mock_discovery_instance.discover_videos.assert_called_once()
        args, kwargs = mock_discovery_instance.discover_videos.call_args
        assert kwargs.get('max_results') == 10

    @patch('youtube_processor.cli.get_api_key')
    @patch('youtube_processor.cli.ChannelDiscovery')
    def test_list_command_with_order(self, mock_discovery, mock_get_api_key):
        """list command respects order parameter."""
        mock_get_api_key.return_value = 'test_api_key'

        mock_discovery_instance = Mock()
        mock_discovery_instance.discover_videos.return_value = []  # Return empty list
        mock_discovery.return_value = mock_discovery_instance

        runner = CliRunner()
        result = runner.invoke(main, ['list', 'https://www.youtube.com/c/testchannel', '--order', 'date'])

        assert result.exit_code == 0
        mock_discovery_instance.discover_videos.assert_called_once()
        args, kwargs = mock_discovery_instance.discover_videos.call_args
        assert kwargs.get('order') == 'date'


class TestExtractCommand:
    """Test extract command functionality."""

    @patch('youtube_processor.cli.get_api_key')
    @patch('youtube_processor.cli.ChannelDiscovery')
    @patch('youtube_processor.cli.VideoSelector')
    @patch('youtube_processor.cli.ParallelExtractor')
    @patch('youtube_processor.cli.ExtractionHistory')
    def test_extract_command_success(self, mock_history, mock_extractor, mock_selector, mock_discovery, mock_get_api_key):
        """extract command successfully runs end-to-end."""
        # Mock API key
        mock_get_api_key.return_value = 'test_api_key'

        # Mock discovered videos
        mock_videos = [
            VideoMetadata(video_id='test_id_1', title='Test Video 1'),
            VideoMetadata(video_id='test_id_2', title='Test Video 2')
        ]

        mock_discovery_instance = Mock()
        mock_discovery_instance.discover_videos.return_value = mock_videos
        mock_discovery.return_value = mock_discovery_instance

        # Mock video selection
        selected_videos = [mock_videos[0]]  # User selects first video
        mock_selector_instance = Mock()
        mock_selector_instance.select_videos.return_value = selected_videos
        mock_selector.return_value = mock_selector_instance

        # Mock extraction
        extraction_results = [
            ExtractionResult(video_id='test_id_1', success=True, output_path=Path('/tmp/test.mp4'))
        ]
        mock_extractor_instance = Mock()
        mock_extractor_instance.extract_videos.return_value = extraction_results
        mock_extractor.return_value = mock_extractor_instance

        # Mock history
        mock_history_instance = Mock()
        mock_history.return_value = mock_history_instance

        runner = CliRunner()
        result = runner.invoke(main, ['extract', 'https://www.youtube.com/c/testchannel'])

        assert result.exit_code == 0
        assert 'success' in result.output.lower()

        # Verify the workflow
        mock_discovery_instance.discover_videos.assert_called_once()
        mock_selector_instance.select_videos.assert_called_once()
        mock_extractor_instance.extract_videos.assert_called_once()

    def test_extract_command_no_api_key(self):
        """extract command fails gracefully without API key."""
        with patch('youtube_processor.cli.get_api_key', return_value=None):
            runner = CliRunner()
            result = runner.invoke(main, ['extract', 'https://www.youtube.com/c/testchannel'])

            assert result.exit_code != 0
            assert 'API key' in result.output

    @patch('youtube_processor.cli.get_api_key')
    @patch('youtube_processor.cli.ChannelDiscovery')
    @patch('youtube_processor.cli.VideoSelector')
    def test_extract_command_no_videos_selected(self, mock_selector, mock_discovery, mock_get_api_key):
        """extract command handles no videos selected gracefully."""
        mock_get_api_key.return_value = 'test_api_key'

        mock_videos = [VideoMetadata(video_id='test_id_1', title='Test Video 1')]
        mock_discovery_instance = Mock()
        mock_discovery_instance.discover_videos.return_value = mock_videos
        mock_discovery.return_value = mock_discovery_instance

        # User selects no videos
        mock_selector_instance = Mock()
        mock_selector_instance.select_videos.return_value = []
        mock_selector.return_value = mock_selector_instance

        runner = CliRunner()
        result = runner.invoke(main, ['extract', 'https://www.youtube.com/c/testchannel'])

        assert result.exit_code == 0
        assert 'no videos selected' in result.output.lower()

    @patch('youtube_processor.cli.get_api_key')
    @patch('youtube_processor.cli.setup_config')
    @patch('youtube_processor.cli.ChannelDiscovery')
    @patch('youtube_processor.cli.VideoSelector')
    @patch('youtube_processor.cli.ParallelExtractor')
    def test_extract_command_with_config_options(self, mock_extractor, mock_selector, mock_discovery, mock_config, mock_get_api_key):
        """extract command respects configuration options."""
        mock_get_api_key.return_value = 'test_api_key'

        # Mock config
        mock_config_instance = Mock()
        mock_config_instance.get.side_effect = lambda key, default: {
            'parallel_workers': 8,
            'use_tor': True,
            'output_dir': '/tmp/test_output'
        }.get(key, default)
        mock_config.return_value = mock_config_instance

        # Mock discovery
        mock_videos = [VideoMetadata(video_id='test_id_1', title='Test Video 1')]
        mock_discovery_instance = Mock()
        mock_discovery_instance.discover_videos.return_value = mock_videos
        mock_discovery.return_value = mock_discovery_instance

        # Mock selection
        mock_selector_instance = Mock()
        mock_selector_instance.select_videos.return_value = mock_videos
        mock_selector.return_value = mock_selector_instance

        runner = CliRunner()
        result = runner.invoke(main, ['extract', 'https://www.youtube.com/c/testchannel'])

        # Verify extractor was created with config values
        mock_extractor.assert_called_once()
        args, kwargs = mock_extractor.call_args
        assert kwargs.get('max_workers') == 8
        assert kwargs.get('use_tor') == True


class TestInfoCommand:
    """Test info command functionality."""

    @patch('youtube_processor.cli.get_api_key')
    @patch('youtube_processor.cli.ChannelDiscovery')
    def test_info_command_success(self, mock_discovery, mock_get_api_key):
        """info command successfully displays channel information."""
        mock_get_api_key.return_value = 'test_api_key'

        # Mock channel info
        mock_discovery_instance = Mock()
        mock_discovery_instance.get_channel_info.return_value = {
            'title': 'Test Channel',
            'subscriber_count': 10000,
            'video_count': 50,
            'description': 'Test channel description'
        }
        mock_discovery.return_value = mock_discovery_instance

        runner = CliRunner()
        result = runner.invoke(main, ['info', 'https://www.youtube.com/c/testchannel'])

        assert result.exit_code == 0
        assert 'Test Channel' in result.output
        assert '10,000' in result.output  # Formatted subscriber count
        assert '50' in result.output  # Video count

    def test_info_command_no_api_key(self):
        """info command fails gracefully without API key."""
        with patch('youtube_processor.cli.get_api_key', return_value=None):
            runner = CliRunner()
            result = runner.invoke(main, ['info', 'https://www.youtube.com/c/testchannel'])

            assert result.exit_code != 0
            assert 'API key' in result.output

    @patch('youtube_processor.cli.get_api_key')
    @patch('youtube_processor.cli.ChannelDiscovery')
    def test_info_command_invalid_channel(self, mock_discovery, mock_get_api_key):
        """info command handles invalid channel gracefully."""
        mock_get_api_key.return_value = 'test_api_key'

        mock_discovery_instance = Mock()
        mock_discovery_instance.get_channel_info.side_effect = Exception("Channel not found")
        mock_discovery.return_value = mock_discovery_instance

        runner = CliRunner()
        result = runner.invoke(main, ['info', 'invalid_channel'])

        assert result.exit_code != 0
        assert 'error' in result.output.lower()


class TestStatusCommand:
    """Test status command functionality."""

    @patch('youtube_processor.cli.ExtractionHistory')
    def test_status_command_success(self, mock_history):
        """status command displays extraction history."""
        # Mock history data
        mock_history_instance = Mock()
        mock_history_instance.get_history.return_value = [
            {
                'video_id': 'test_id_1',
                'title': 'Test Video 1',
                'status': 'completed',
                'timestamp': '2023-01-01T10:00:00',
                'file_size': 50000000  # 50MB
            },
            {
                'video_id': 'test_id_2',
                'title': 'Test Video 2',
                'status': 'failed',
                'timestamp': '2023-01-01T11:00:00',
                'error': 'Network error'
            }
        ]
        mock_history_instance.get_stats.return_value = {
            'total_extractions': 2,
            'successful_extractions': 1,
            'failed_extractions': 1,
            'total_size': 50000000
        }
        mock_history.return_value = mock_history_instance

        runner = CliRunner()
        result = runner.invoke(main, ['status'])

        assert result.exit_code == 0
        assert 'Test Video 1' in result.output
        assert 'Test Video 2' in result.output
        assert '✓ Success' in result.output
        assert '✗ Failed' in result.output
        assert '47.7 MB' in result.output  # Formatted file size

    @patch('youtube_processor.cli.ExtractionHistory')
    def test_status_command_empty_history(self, mock_history):
        """status command handles empty history gracefully."""
        mock_history_instance = Mock()
        mock_history_instance.get_history.return_value = []
        mock_history_instance.get_stats.return_value = {
            'total_extractions': 0,
            'successful_extractions': 0,
            'failed_extractions': 0,
            'total_size': 0
        }
        mock_history.return_value = mock_history_instance

        runner = CliRunner()
        result = runner.invoke(main, ['status'])

        assert result.exit_code == 0
        assert 'no extractions' in result.output.lower()

    @patch('youtube_processor.cli.ExtractionHistory')
    def test_status_command_with_limit(self, mock_history):
        """status command respects limit parameter."""
        mock_history_instance = Mock()
        mock_history_instance.get_history.return_value = []
        mock_history_instance.get_stats.return_value = {
            'total_extractions': 0,
            'successful_extractions': 0,
            'failed_extractions': 0,
            'total_size': 0
        }
        mock_history.return_value = mock_history_instance

        runner = CliRunner()
        result = runner.invoke(main, ['status', '--limit', '10'])

        assert result.exit_code == 0
        mock_history_instance.get_history.assert_called_once_with(limit=10)


class TestProgressAndFormatting:
    """Test progress bars and Rich formatting."""

    @patch('youtube_processor.cli.get_api_key')
    @patch('youtube_processor.cli.ChannelDiscovery')
    @patch('youtube_processor.cli.Progress')
    def test_progress_bar_during_discovery(self, mock_progress, mock_discovery, mock_get_api_key):
        """Progress bar is shown during video discovery."""
        mock_get_api_key.return_value = 'test_api_key'

        mock_discovery_instance = Mock()
        mock_discovery_instance.discover_videos.return_value = []
        mock_discovery.return_value = mock_discovery_instance

        runner = CliRunner()
        result = runner.invoke(main, ['list', 'https://www.youtube.com/c/testchannel'])

        # Verify progress was used
        mock_progress.assert_called()

    def test_rich_table_formatting(self):
        """Rich tables are used for formatted output."""
        # This will be verified through output formatting in integration tests
        pass

    def test_rich_console_error_formatting(self):
        """Errors are formatted with Rich console."""
        # This will be verified through error output formatting
        pass


class TestErrorHandling:
    """Test comprehensive error handling."""

    def test_graceful_keyboard_interrupt(self):
        """CLI handles KeyboardInterrupt gracefully."""
        with patch('youtube_processor.cli.get_api_key', side_effect=KeyboardInterrupt):
            runner = CliRunner()
            result = runner.invoke(main, ['list', 'https://www.youtube.com/c/testchannel'])

            assert result.exit_code != 0
            assert 'cancelled' in result.output.lower() or 'interrupted' in result.output.lower()

    @patch('youtube_processor.cli.get_api_key')
    @patch('youtube_processor.cli.ChannelDiscovery')
    def test_network_error_handling(self, mock_discovery, mock_get_api_key):
        """CLI handles network errors gracefully."""
        mock_get_api_key.return_value = 'test_api_key'

        mock_discovery_instance = Mock()
        mock_discovery_instance.discover_videos.side_effect = ConnectionError("Network error")
        mock_discovery.return_value = mock_discovery_instance

        runner = CliRunner()
        result = runner.invoke(main, ['list', 'https://www.youtube.com/c/testchannel'])

        assert result.exit_code != 0
        assert 'network' in result.output.lower() or 'connection' in result.output.lower()

    def test_invalid_arguments_handling(self):
        """CLI validates arguments properly."""
        runner = CliRunner()

        # Test extract without URL
        result = runner.invoke(main, ['extract'])
        assert result.exit_code != 0

        # Test list without URL
        result = runner.invoke(main, ['list'])
        assert result.exit_code != 0

        # Test info without URL
        result = runner.invoke(main, ['info'])
        assert result.exit_code != 0


class TestUtilityFunctions:
    """Test utility functions used by CLI."""

    def test_format_duration_helper(self):
        """Duration formatting helper works correctly."""
        from youtube_processor.cli import format_duration

        assert format_duration(0) == "0:00"
        assert format_duration(30) == "0:30"
        assert format_duration(90) == "1:30"
        assert format_duration(3600) == "1:00:00"
        assert format_duration(3661) == "1:01:01"

    def test_format_file_size_helper(self):
        """File size formatting helper works correctly."""
        from youtube_processor.cli import format_file_size

        assert format_file_size(0) == "0 B"
        assert format_file_size(1024) == "1.0 KB"
        assert format_file_size(1048576) == "1.0 MB"
        assert format_file_size(1073741824) == "1.0 GB"

    def test_format_number_helper(self):
        """Number formatting helper works correctly."""
        from youtube_processor.cli import format_number

        assert format_number(0) == "0"
        assert format_number(1000) == "1,000"
        assert format_number(1000000) == "1,000,000"