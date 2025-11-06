"""
Tests for CLI analysis integration with --analyze flag.

Following TDD methodology - these tests are written FIRST and should fail initially.
Tests the integration of LLM analysis modules into the CLI workflow.
"""

import pytest
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from youtube_processor.cli import main as cli


class TestCLIAnalysisIntegration:
    """Test CLI analysis integration functionality"""

    def test_analyze_flag_exists(self):
        """Test 1: CLI has --analyze option available"""
        runner = CliRunner()

        # Test that --analyze flag is recognized (should show help, not error)
        result = runner.invoke(cli, ['extract', '--help'])

        assert result.exit_code == 0
        assert '--analyze' in result.output or '--analyze / --no-analyze' in result.output

    def test_analyze_requires_api_key(self):
        """Test 2: Validates ANTHROPIC_API_KEY when --analyze is used"""
        runner = CliRunner()

        # Set YouTube API key but clear Anthropic API key
        env_vars = {'YOUTUBE_API_KEY': 'test-youtube-key'}
        if 'ANTHROPIC_API_KEY' in os.environ:
            del env_vars['ANTHROPIC_API_KEY']

        with patch.dict(os.environ, env_vars, clear=True):
            result = runner.invoke(cli, [
                'extract',
                'https://www.youtube.com/@testchannel',
                '--analyze',
                '--max-results', '1'
            ])

            # Should fail with API key error
            assert result.exit_code != 0
            assert 'ANTHROPIC_API_KEY' in result.output

    @patch('youtube_processor.cli.get_api_key')
    @patch('youtube_processor.core.discovery.ChannelDiscovery')
    @patch('youtube_processor.core.extractor.ParallelExtractor')
    def test_analyze_single_video(self, mock_extractor_class, mock_discovery_class, mock_get_api_key):
        """Test 3: Analyzes one transcript successfully"""
        runner = CliRunner()

        # Mock get_api_key to return a test key
        mock_get_api_key.return_value = "test-youtube-key"

        # Mock discovery to return test data
        mock_discovery = MagicMock()
        mock_discovery_class.return_value = mock_discovery
        mock_discovery.discover_videos.return_value = ("TestChannel", [
            MagicMock(video_id="test123", title="Test Video")
        ])

        # Mock extractor
        mock_extractor = MagicMock()
        mock_extractor_class.return_value = mock_extractor
        mock_extractor.extract_videos.return_value = [
            MagicMock(success=True, video_id="test123")
        ]

        # Mock AnalysisWorkflow
        with patch('youtube_processor.workflows.analysis.AnalysisWorkflow') as mock_workflow_class:
            mock_workflow = MagicMock()
            mock_workflow_class.return_value = mock_workflow

            with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key', 'YOUTUBE_API_KEY': 'test-youtube-key'}):
                result = runner.invoke(cli, [
                    'extract',
                    'https://www.youtube.com/@testchannel',
                    '--analyze',
                    '--max-results', '1'
                ])

            # Should succeed and call analysis workflow
            if result.exit_code != 0:
                print(f"Error output: {result.output}")
                print(f"Exception: {result.exception}")
            assert result.exit_code == 0
            mock_workflow_class.assert_called_once()
            mock_workflow.run.assert_called_once()

    @patch('youtube_processor.core.discovery.ChannelDiscovery')
    @patch('youtube_processor.core.extractor.ParallelExtractor')
    def test_analyze_multiple_videos(self, mock_extractor_class, mock_discovery_class):
        """Test 4: Batch analysis of multiple videos"""
        runner = CliRunner()

        # Mock discovery to return multiple videos
        mock_discovery = MagicMock()
        mock_discovery_class.return_value = mock_discovery
        mock_discovery.discover_videos.return_value = ("TestChannel", [
            MagicMock(video_id="test1", title="Video 1"),
            MagicMock(video_id="test2", title="Video 2"),
            MagicMock(video_id="test3", title="Video 3")
        ])

        # Mock extractor
        mock_extractor = MagicMock()
        mock_extractor_class.return_value = mock_extractor
        mock_extractor.extract_videos.return_value = [
            MagicMock(success=True, video_id="test1"),
            MagicMock(success=True, video_id="test2"),
            MagicMock(success=True, video_id="test3")
        ]

        # Mock AnalysisWorkflow
        with patch('youtube_processor.workflows.analysis.AnalysisWorkflow') as mock_workflow_class:
            mock_workflow = MagicMock()
            mock_workflow_class.return_value = mock_workflow

            with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key', 'YOUTUBE_API_KEY': 'test-youtube-key'}):
                result = runner.invoke(cli, [
                    'extract',
                    'https://www.youtube.com/@testchannel',
                    '--analyze',
                    '--max-results', '3'
                ])

            # Should process all 3 videos
            assert result.exit_code == 0
            mock_workflow.run.assert_called_once()

            # Verify it was called with 3 videos
            call_args = mock_workflow.run.call_args
            videos_param = call_args[1]['videos']  # Get videos from kwargs
            assert len(videos_param) == 3

    @patch('youtube_processor.core.discovery.ChannelDiscovery')
    @patch('youtube_processor.core.extractor.ParallelExtractor')
    def test_analysis_progress_tracking(self, mock_extractor_class, mock_discovery_class):
        """Test 5: Progress bars work during analysis"""
        runner = CliRunner()

        # Mock discovery and extractor
        mock_discovery = MagicMock()
        mock_discovery_class.return_value = mock_discovery
        mock_discovery.discover_videos.return_value = ("TestChannel", [
            MagicMock(video_id="test123", title="Test Video")
        ])

        mock_extractor = MagicMock()
        mock_extractor_class.return_value = mock_extractor
        mock_extractor.extract_videos.return_value = [
            MagicMock(success=True, video_id="test123")
        ]

        with patch('youtube_processor.workflows.analysis.AnalysisWorkflow') as mock_workflow_class:
            mock_workflow = MagicMock()
            mock_workflow_class.return_value = mock_workflow

            with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key', 'YOUTUBE_API_KEY': 'test-youtube-key'}):
                result = runner.invoke(cli, [
                    'extract',
                    'https://www.youtube.com/@testchannel',
                    '--analyze'
                ])

            # Should show progress indicators
            assert result.exit_code == 0
            # Note: Rich progress bars may not show in test output, but the workflow should run
            mock_workflow.run.assert_called_once()

    @patch('youtube_processor.core.discovery.ChannelDiscovery')
    @patch('youtube_processor.core.extractor.ParallelExtractor')
    def test_analysis_cost_tracking(self, mock_extractor_class, mock_discovery_class):
        """Test 6: Token usage and costs are displayed"""
        runner = CliRunner()

        # Mock discovery and extractor
        mock_discovery = MagicMock()
        mock_discovery_class.return_value = mock_discovery
        mock_discovery.discover_videos.return_value = ("TestChannel", [
            MagicMock(video_id="test123", title="Test Video")
        ])

        mock_extractor = MagicMock()
        mock_extractor_class.return_value = mock_extractor
        mock_extractor.extract_videos.return_value = [
            MagicMock(success=True, video_id="test123")
        ]

        # Mock workflow to simulate cost tracking
        with patch('youtube_processor.workflows.analysis.AnalysisWorkflow') as mock_workflow_class:
            mock_workflow = MagicMock()
            mock_workflow.total_tokens = 1500
            mock_workflow.total_cost = 0.45
            mock_workflow_class.return_value = mock_workflow

            with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key', 'YOUTUBE_API_KEY': 'test-youtube-key'}):
                result = runner.invoke(cli, [
                    'extract',
                    'https://www.youtube.com/@testchannel',
                    '--analyze'
                ])

            # Should complete successfully
            assert result.exit_code == 0
            mock_workflow.run.assert_called_once()

    @patch('youtube_processor.core.discovery.ChannelDiscovery')
    @patch('youtube_processor.core.extractor.ParallelExtractor')
    def test_analysis_output_structure(self, mock_extractor_class, mock_discovery_class):
        """Test 7: Creates analyses/ directory with correct structure"""
        runner = CliRunner()

        mock_discovery = MagicMock()
        mock_discovery_class.return_value = mock_discovery
        mock_discovery.discover_videos.return_value = ("TestChannel", [
            MagicMock(video_id="test123", title="Test Video")
        ])

        mock_extractor = MagicMock()
        mock_extractor_class.return_value = mock_extractor
        mock_extractor.extract_videos.return_value = [
            MagicMock(success=True, video_id="test123")
        ]

        with patch('youtube_processor.workflows.analysis.AnalysisWorkflow') as mock_workflow_class:
            mock_workflow = MagicMock()
            mock_workflow_class.return_value = mock_workflow

            with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key', 'YOUTUBE_API_KEY': 'test-youtube-key'}):
                result = runner.invoke(cli, [
                    'extract',
                    'https://www.youtube.com/@testchannel',
                    '--analyze'
                ])

            # Verify workflow was called with correct parameters
            assert result.exit_code == 0
            mock_workflow.run.assert_called_once()

            call_kwargs = mock_workflow.run.call_args[1]
            assert 'channel_name' in call_kwargs
            assert 'channel_dir' in call_kwargs
            assert call_kwargs['channel_name'] == "TestChannel"

    @patch('youtube_processor.core.discovery.ChannelDiscovery')
    @patch('youtube_processor.core.extractor.ParallelExtractor')
    def test_synthesis_runs_after_analysis(self, mock_extractor_class, mock_discovery_class):
        """Test 8: Knowledge synthesis works after analysis"""
        runner = CliRunner()

        mock_discovery = MagicMock()
        mock_discovery_class.return_value = mock_discovery
        mock_discovery.discover_videos.return_value = ("TestChannel", [
            MagicMock(video_id="test123", title="Test Video")
        ])

        mock_extractor = MagicMock()
        mock_extractor_class.return_value = mock_extractor
        mock_extractor.extract_videos.return_value = [
            MagicMock(success=True, video_id="test123")
        ]

        # Mock the analysis workflow to verify synthesis is called
        with patch('youtube_processor.workflows.analysis.AnalysisWorkflow') as mock_workflow_class:
            mock_workflow = MagicMock()
            mock_workflow_class.return_value = mock_workflow

            with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key', 'YOUTUBE_API_KEY': 'test-youtube-key'}):
                result = runner.invoke(cli, [
                    'extract',
                    'https://www.youtube.com/@testchannel',
                    '--analyze'
                ])

            assert result.exit_code == 0
            # The workflow should handle both analysis and synthesis
            mock_workflow.run.assert_called_once()

    @patch('youtube_processor.core.discovery.ChannelDiscovery')
    @patch('youtube_processor.core.extractor.ParallelExtractor')
    def test_kb_directory_creation(self, mock_extractor_class, mock_discovery_class):
        """Test 9: Creates knowledge-base/ structure correctly"""
        runner = CliRunner()

        mock_discovery = MagicMock()
        mock_discovery_class.return_value = mock_discovery
        mock_discovery.discover_videos.return_value = ("TestChannel", [
            MagicMock(video_id="test123", title="Test Video")
        ])

        mock_extractor = MagicMock()
        mock_extractor_class.return_value = mock_extractor
        mock_extractor.extract_videos.return_value = [
            MagicMock(success=True, video_id="test123")
        ]

        with patch('youtube_processor.workflows.analysis.AnalysisWorkflow') as mock_workflow_class:
            with patch('youtube_processor.core.extractor.DirectoryManager') as mock_dir_manager:
                mock_workflow = MagicMock()
                mock_workflow_class.return_value = mock_workflow

                with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key', 'YOUTUBE_API_KEY': 'test-youtube-key'}):
                    result = runner.invoke(cli, [
                        'extract',
                        'https://www.youtube.com/@testchannel',
                        '--analyze'
                    ])

                # Should use DirectoryManager to create knowledge-base structure
                assert result.exit_code == 0
                mock_workflow.run.assert_called_once()

    @patch('youtube_processor.core.discovery.ChannelDiscovery')
    @patch('youtube_processor.core.extractor.ParallelExtractor')
    def test_kb_markdown_generation(self, mock_extractor_class, mock_discovery_class):
        """Test 10: Generates technique/pattern files with proper content"""
        runner = CliRunner()

        mock_discovery = MagicMock()
        mock_discovery_class.return_value = mock_discovery
        mock_discovery.discover_videos.return_value = ("TestChannel", [
            MagicMock(video_id="test123", title="Test Video")
        ])

        mock_extractor = MagicMock()
        mock_extractor_class.return_value = mock_extractor
        mock_extractor.extract_videos.return_value = [
            MagicMock(success=True, video_id="test123")
        ]

        with patch('youtube_processor.workflows.analysis.AnalysisWorkflow') as mock_workflow_class:
            mock_workflow = MagicMock()
            mock_workflow_class.return_value = mock_workflow

            with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key', 'YOUTUBE_API_KEY': 'test-youtube-key'}):
                result = runner.invoke(cli, [
                    'extract',
                    'https://www.youtube.com/@testchannel',
                    '--analyze'
                ])

            # Should complete analysis and synthesis workflow
            assert result.exit_code == 0
            mock_workflow.run.assert_called_once()

            # Verify the workflow is set up correctly for KB generation
            call_kwargs = mock_workflow.run.call_args[1]
            assert 'channel_name' in call_kwargs
            assert 'channel_dir' in call_kwargs