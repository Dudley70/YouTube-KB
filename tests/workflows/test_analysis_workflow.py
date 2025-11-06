import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from rich.console import Console
from io import StringIO
from youtube_processor.workflows.analysis import AnalysisWorkflow
from youtube_processor.core.discovery import VideoMetadata


class TestAnalysisWorkflowBugFix:
    """Test suite for analysis workflow bug fix"""

    def test_knowledge_base_dict_handling(self):
        """Test 1: Workflow handles knowledge_base as dict correctly"""
        workflow = AnalysisWorkflow(
            api_key="test_key",
            model="claude-sonnet-4-5-20250929",
            console=Mock()
        )

        # Mock knowledge base as dict (current synthesizer output)
        mock_kb = {
            'units': [
                {'id': 'test-1', 'type': 'technique', 'title': 'Test'},
            ],
            'metadata': {'total_units': 1},
            'summary': 'Test summary'
        }

        kb_dir = Path('/tmp/test_kb')
        kb_dir.mkdir(parents=True, exist_ok=True)

        # Should not raise AttributeError
        try:
            workflow._generate_metadata_yaml(mock_kb, kb_dir)
            assert True
        except AttributeError as e:
            pytest.fail(f"AttributeError raised: {e}")

    def test_metadata_yaml_generation(self):
        """Test 2: Generates valid metadata.yaml from dict knowledge base"""
        workflow = AnalysisWorkflow(
            api_key="test_key",
            model="claude-sonnet-4-5-20250929",
            console=Mock()
        )

        mock_kb = {
            'units': [
                {'id': 'tech-1', 'type': 'technique', 'title': 'Test Technique'},
                {'id': 'pat-1', 'type': 'pattern', 'title': 'Test Pattern'},
            ],
            'metadata': {'total_units': 2},
            'summary': 'Test knowledge base'
        }

        kb_dir = Path('/tmp/test_kb')
        kb_dir.mkdir(parents=True, exist_ok=True)

        workflow._generate_metadata_yaml(mock_kb, kb_dir)

        units_file = kb_dir / 'metadata' / 'units.yaml'
        synthesis_file = kb_dir / 'metadata' / 'synthesis.yaml'
        assert units_file.exists()
        assert synthesis_file.exists()

        # Verify units.yaml content structure
        import yaml
        with open(units_file, 'r') as f:
            units_data = yaml.safe_load(f)

        assert 'units' in units_data
        assert len(units_data['units']) == 2

        # Verify synthesis.yaml content structure
        with open(synthesis_file, 'r') as f:
            synthesis_data = yaml.safe_load(f)

        assert 'total_units' in synthesis_data
        assert synthesis_data['total_units'] == 2

    def test_markdown_generation_with_dict_kb(self):
        """Test 3: Generates markdown files from dict knowledge base"""
        workflow = AnalysisWorkflow(
            api_key="test_key",
            model="claude-sonnet-4-5-20250929",
            console=Mock()
        )

        mock_kb = {
            'units': [
                {
                    'id': 'tech-hooks',
                    'type': 'technique',
                    'title': 'Claude Code Hooks',
                    'content': 'Test content',
                    'source_videos': ['video1']
                }
            ],
            'metadata': {'total_units': 1}
        }

        kb_dir = Path('/tmp/test_kb')
        kb_dir.mkdir(parents=True, exist_ok=True)

        workflow._generate_knowledge_base_markdown(mock_kb, kb_dir)

        # Verify technique file created
        tech_file = kb_dir / 'techniques' / 'tech-hooks.md'
        assert tech_file.exists()

    def test_full_workflow_with_single_video(self):
        """Test 4: Complete workflow runs without AttributeError"""
        # Use real Console with StringIO to capture output
        string_io = StringIO()
        console = Console(file=string_io, force_terminal=False)

        workflow = AnalysisWorkflow(
            api_key="test_key",
            model="claude-sonnet-4-5-20250929",
            console=console
        )

        # Mock the analyzer, synthesizer, and directory manager
        with patch.object(workflow.analyzer, 'analyze_transcript') as mock_analyze, \
             patch.object(workflow.synthesizer, 'synthesize') as mock_synthesize, \
             patch('youtube_processor.workflows.analysis.DirectoryManager') as mock_dir_mgr:

            # Configure mocks
            mock_dir_mgr.create_channel_analyses_dir.return_value = Path('/tmp/test_analyses')
            mock_dir_mgr.create_channel_kb_dir.return_value = Path('/tmp/test_kb')

            mock_analyze.return_value = {
                'video_id': 'test123',
                'analysis': {'techniques': []},
                'usage': {'input_tokens': 100, 'output_tokens': 50}
            }

            # Create a mock SynthesizedUnit object with all required attributes
            mock_synthesized_unit = Mock()
            mock_synthesized_unit.category = 'techniques'
            mock_synthesized_unit.type = 'technique'
            mock_synthesized_unit.id = 'test'
            mock_synthesized_unit.name = 'Test'
            mock_synthesized_unit.title = 'Test Unit'
            mock_synthesized_unit.description = 'Test description'
            mock_synthesized_unit.implementation = 'Test implementation'
            mock_synthesized_unit.examples = 'Test examples'
            mock_synthesized_unit.content = 'Test content'
            mock_synthesized_unit.source_videos = ['test123']
            mock_synthesized_unit.cross_references = []
            mock_synthesized_unit.video_references = []  # Empty list to avoid iteration error
            mock_synthesized_unit.tags = []  # Empty list to avoid iteration error

            mock_synthesize.return_value = {
                'test': mock_synthesized_unit
            }

            # Ensure test directories exist
            Path('/tmp/test_analyses').mkdir(parents=True, exist_ok=True)
            Path('/tmp/test_kb').mkdir(parents=True, exist_ok=True)

            videos = [
                VideoMetadata(
                    video_id='test123',
                    title='Test Video',
                    duration_seconds=300,
                    view_count=1000
                )
            ]

            channel_dir = Path('/tmp/test_channel')
            channel_dir.mkdir(parents=True, exist_ok=True)

            # Should complete without AttributeError
            try:
                workflow.run(
                    channel_name='TestChannel',
                    channel_dir=channel_dir,
                    videos=videos
                )
                assert True
            except AttributeError as e:
                pytest.fail(f"AttributeError in workflow: {e}")

    def test_empty_knowledge_base_handling(self):
        """Test 5: Handles empty knowledge base gracefully"""
        workflow = AnalysisWorkflow(
            api_key="test_key",
            model="claude-sonnet-4-5-20250929",
            console=Mock()
        )

        mock_kb = {
            'units': [],
            'metadata': {'total_units': 0}
        }

        kb_dir = Path('/tmp/test_kb')
        kb_dir.mkdir(parents=True, exist_ok=True)

        # Should handle empty KB without errors
        workflow._generate_metadata_yaml(mock_kb, kb_dir)
        workflow._generate_knowledge_base_markdown(mock_kb, kb_dir)

        units_file = kb_dir / 'metadata' / 'units.yaml'
        synthesis_file = kb_dir / 'metadata' / 'synthesis.yaml'
        assert units_file.exists()
        assert synthesis_file.exists()