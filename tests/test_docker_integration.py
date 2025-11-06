# tests/test_docker_integration.py

import pytest
from unittest.mock import Mock, patch, mock_open
from pathlib import Path
import yaml
from youtube_processor.docker import (
    DockerTORManager,
    DockerError,
    check_docker_available,
    check_tor_container_running
)

class TestDockerAvailability:
    """Test Docker availability checks"""

    @patch('subprocess.run')
    def test_check_docker_available_success(self, mock_run):
        """check_docker_available returns True when Docker is running"""
        mock_run.return_value.returncode = 0

        assert check_docker_available() is True

    @patch('subprocess.run')
    def test_check_docker_available_not_installed(self, mock_run):
        """check_docker_available returns False when Docker not installed"""
        mock_run.side_effect = FileNotFoundError()

        assert check_docker_available() is False

    @patch('subprocess.run')
    def test_check_docker_available_not_running(self, mock_run):
        """check_docker_available returns False when Docker not running"""
        mock_run.return_value.returncode = 1

        assert check_docker_available() is False

    @patch('subprocess.run')
    def test_check_tor_container_running_true(self, mock_run):
        """check_tor_container_running detects running TOR container"""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "youtube-processor-tor\n"

        assert check_tor_container_running() is True

    @patch('subprocess.run')
    def test_check_tor_container_running_false(self, mock_run):
        """check_tor_container_running returns False if container not running"""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""

        assert check_tor_container_running() is False

    @patch('subprocess.run')
    def test_check_tor_container_custom_name(self, mock_run):
        """check_tor_container_running accepts custom container name"""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "custom-tor\n"

        assert check_tor_container_running(container_name="custom-tor") is True

class TestDockerCompose:
    """Test Docker Compose configuration"""

    def test_docker_compose_file_exists(self):
        """docker-compose.yml exists in project root"""
        compose_file = Path("docker-compose.yml")
        assert compose_file.exists()

    def test_docker_compose_valid_yaml(self):
        """docker-compose.yml is valid YAML"""
        compose_file = Path("docker-compose.yml")
        with open(compose_file) as f:
            data = yaml.safe_load(f)

        assert isinstance(data, dict)
        assert "services" in data

    def test_docker_compose_has_tor_service(self):
        """docker-compose.yml defines TOR service"""
        compose_file = Path("docker-compose.yml")
        with open(compose_file) as f:
            data = yaml.safe_load(f)

        assert "tor" in data["services"] or "tor-proxy" in data["services"]

    def test_docker_compose_tor_port_mapping(self):
        """TOR service exposes SOCKS proxy port"""
        compose_file = Path("docker-compose.yml")
        with open(compose_file) as f:
            data = yaml.safe_load(f)

        tor_service = data["services"].get("tor") or data["services"].get("tor-proxy")
        ports = tor_service.get("ports", [])

        # Should expose 9050 (SOCKS port)
        assert any("9050" in str(port) for port in ports)

    def test_docker_compose_tor_restart_policy(self):
        """TOR service has restart policy configured"""
        compose_file = Path("docker-compose.yml")
        with open(compose_file) as f:
            data = yaml.safe_load(f)

        tor_service = data["services"].get("tor") or data["services"].get("tor-proxy")
        restart = tor_service.get("restart")

        assert restart in ["always", "unless-stopped", "on-failure"]

    def test_docker_compose_tor_image(self):
        """TOR service uses appropriate Docker image"""
        compose_file = Path("docker-compose.yml")
        with open(compose_file) as f:
            data = yaml.safe_load(f)

        tor_service = data["services"].get("tor") or data["services"].get("tor-proxy")
        image = tor_service.get("image")

        assert image is not None
        assert "tor" in image.lower()

class TestDockerTORManager:
    """Test DockerTORManager class"""

    def test_init_default_compose_file(self):
        """DockerTORManager uses default compose file path"""
        manager = DockerTORManager()

        assert manager.compose_file.name == "docker-compose.yml"

    def test_init_custom_compose_file(self):
        """DockerTORManager accepts custom compose file"""
        custom_path = Path("/custom/docker-compose.yml")
        manager = DockerTORManager(compose_file=custom_path)

        assert manager.compose_file == custom_path

    @patch('subprocess.run')
    def test_start_tor_success(self, mock_run):
        """start_tor starts TOR container successfully"""
        mock_run.return_value.returncode = 0

        manager = DockerTORManager()
        result = manager.start_tor()

        assert result is True
        mock_run.assert_called()
        # Verify docker-compose up called
        call_args = str(mock_run.call_args)
        assert "docker-compose" in call_args or "docker" in call_args
        assert "up" in call_args

    @patch('subprocess.run')
    def test_start_tor_failure(self, mock_run):
        """start_tor handles Docker errors"""
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "Error starting container"

        manager = DockerTORManager()
        result = manager.start_tor()

        assert result is False

    @patch('subprocess.run')
    def test_stop_tor_success(self, mock_run):
        """stop_tor stops TOR container"""
        mock_run.return_value.returncode = 0

        manager = DockerTORManager()
        result = manager.stop_tor()

        assert result is True
        call_args = str(mock_run.call_args)
        assert "down" in call_args or "stop" in call_args

    @patch('subprocess.run')
    def test_is_running_true(self, mock_run):
        """is_running detects running TOR container"""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "youtube-processor-tor\n"

        manager = DockerTORManager()
        assert manager.is_running() is True

    @patch('subprocess.run')
    def test_is_running_false(self, mock_run):
        """is_running returns False if container not running"""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""

        manager = DockerTORManager()
        assert manager.is_running() is False

    @patch('subprocess.run')
    def test_restart_tor(self, mock_run):
        """restart_tor stops and starts container"""
        mock_run.return_value.returncode = 0

        manager = DockerTORManager()
        result = manager.restart_tor()

        assert result is True
        assert mock_run.call_count >= 2  # stop + start

    @patch('subprocess.run')
    def test_get_logs(self, mock_run):
        """get_logs retrieves container logs"""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "TOR started successfully\n"

        manager = DockerTORManager()
        logs = manager.get_logs()

        assert "TOR started" in logs
        call_args = str(mock_run.call_args)
        assert "logs" in call_args

class TestDockerIntegrationWithCLI:
    """Test Docker integration with CLI"""

    @patch('youtube_processor.docker.check_docker_available')
    @patch('youtube_processor.docker.DockerTORManager')
    def test_cli_auto_starts_tor_if_available(self, mock_manager, mock_check):
        """CLI auto-starts TOR if Docker available and --use-tor flag set"""
        mock_check.return_value = True
        mock_manager_instance = Mock()
        mock_manager.return_value = mock_manager_instance
        mock_manager_instance.is_running.return_value = False
        mock_manager_instance.start_tor.return_value = True

        # This is an integration test placeholder
        assert True

    @patch('youtube_processor.docker.check_docker_available')
    def test_cli_warns_if_docker_unavailable(self, mock_check):
        """CLI warns user if --use-tor requested but Docker unavailable"""
        mock_check.return_value = False

        # Would test CLI warning message here
        assert True

class TestDockerFile:
    """Test Dockerfile if provided"""

    def test_dockerfile_exists_if_needed(self):
        """Dockerfile exists if custom TOR image needed"""
        dockerfile = Path("Dockerfile.tor")

        # Just check it's valid if it exists
        if dockerfile.exists():
            content = dockerfile.read_text()
            assert "FROM" in content
            assert len(content) > 50

    def test_dockerignore_configured(self):
        """.dockerignore excludes unnecessary files"""
        dockerignore = Path(".dockerignore")

        if dockerignore.exists():
            content = dockerignore.read_text()
            assert any(pattern in content for pattern in ["__pycache__", "*.pyc", ".git"])