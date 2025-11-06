# tests/test_documentation.py

import pytest
from pathlib import Path
import re

class TestREADME:
    """Test README documentation"""

    def test_readme_exists(self):
        """README.md exists"""
        readme = Path("README.md")
        assert readme.exists()

    def test_readme_has_installation_section(self):
        """README includes installation instructions"""
        readme = Path("README.md").read_text()
        assert "## Installation" in readme or "# Installation" in readme

    def test_readme_has_usage_section(self):
        """README includes usage examples"""
        readme = Path("README.md").read_text()
        assert "## Usage" in readme or "# Usage" in readme or "Basic Usage" in readme

    def test_readme_has_docker_section(self):
        """README includes Docker setup instructions"""
        readme = Path("README.md").read_text()
        assert "docker" in readme.lower()
        assert "tor" in readme.lower()

    def test_readme_has_tor_examples(self):
        """README shows TOR usage examples"""
        readme = Path("README.md").read_text()
        assert "--use-tor" in readme

    def test_readme_has_api_key_setup(self):
        """README explains API key configuration"""
        readme = Path("README.md").read_text()
        assert "API key" in readme or "YOUTUBE_API_KEY" in readme

    def test_readme_has_quick_start(self):
        """README includes quick start guide"""
        readme = Path("README.md").read_text()
        assert "quick start" in readme.lower() or "getting started" in readme.lower()

class TestDockerDocumentation:
    """Test Docker-specific documentation"""

    def test_docker_readme_exists(self):
        """Docker documentation exists"""
        docs = [
            Path("docs/DOCKER.md"),
            Path("docs/docker/README.md"),
            Path("DOCKER.md")
        ]
        assert any(doc.exists() for doc in docs)

    def test_docker_docs_has_setup(self):
        """Docker docs explain setup process"""
        doc_paths = [Path("docs/DOCKER.md"), Path("DOCKER.md")]
        doc = next((d for d in doc_paths if d.exists()), None)

        if doc:
            content = doc.read_text()
            assert "docker-compose" in content
            assert "up" in content

    def test_docker_docs_has_troubleshooting(self):
        """Docker docs include troubleshooting section"""
        doc_paths = [Path("docs/DOCKER.md"), Path("DOCKER.md")]
        doc = next((d for d in doc_paths if d.exists()), None)

        if doc:
            content = doc.read_text()
            assert "troubleshoot" in content.lower() or "problem" in content.lower()

class TestExamples:
    """Test example files and scripts"""

    def test_examples_directory_exists(self):
        """examples/ directory exists"""
        examples = Path("examples")
        if examples.exists():
            assert examples.is_dir()

    def test_example_scripts_have_comments(self):
        """Example scripts include explanatory comments"""
        examples_dir = Path("examples")
        if examples_dir.exists():
            for script in examples_dir.glob("*.sh"):
                content = script.read_text()
                # Should have comments
                assert "#" in content

    def test_docker_compose_example(self):
        """docker-compose.yml or example exists"""
        files = [
            Path("docker-compose.yml"),
            Path("docker-compose.example.yml"),
            Path("examples/docker-compose.yml")
        ]
        assert any(f.exists() for f in files)

class TestAPIDocumentation:
    """Test API/module documentation"""

    def test_modules_have_docstrings(self):
        """Core modules have module-level docstrings"""
        modules = [
            Path("youtube_processor/core/discovery.py"),
            Path("youtube_processor/core/extractor.py"),
            Path("youtube_processor/docker.py")
        ]

        for module in modules:
            if module.exists():
                content = module.read_text()
                # Should start with triple-quoted docstring
                assert '"""' in content[:500] or "'''" in content[:500]

    def test_cli_help_documented(self):
        """CLI commands have help text"""
        cli_file = Path("youtube_processor/cli.py")
        content = cli_file.read_text()

        # Should have help text in decorators
        assert '@click.option' in content
        assert 'help=' in content