# youtube_processor/docker.py
"""
Docker TOR Integration Module

This module provides Docker Compose integration for running TOR proxy containers
to enable rate limit avoidance during parallel video extraction.
"""

import subprocess
from pathlib import Path
from typing import Optional


class DockerError(Exception):
    """Raised when Docker operations fail"""
    pass


def check_docker_available() -> bool:
    """Check if Docker is installed and running

    Returns:
        True if Docker is available and running, False otherwise
    """
    try:
        result = subprocess.run(
            ["docker", "ps"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def check_tor_container_running(container_name: str = "youtube-processor-tor") -> bool:
    """Check if TOR container is running

    Args:
        container_name: Name of the TOR container to check

    Returns:
        True if container is running, False otherwise
    """
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={container_name}", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return container_name in result.stdout
    except Exception:
        return False


class DockerTORManager:
    """Manages TOR proxy container via Docker Compose

    This class provides methods to start, stop, and manage TOR proxy containers
    using Docker Compose for YouTube extraction rate limit avoidance.
    """

    def __init__(self, compose_file: Optional[Path] = None):
        """Initialize DockerTORManager

        Args:
            compose_file: Path to docker-compose.yml file. If None, uses default
                         in current working directory
        """
        if compose_file is None:
            compose_file = Path.cwd() / "docker-compose.yml"
        self.compose_file = compose_file
        self.container_name = "youtube-processor-tor"

    def start_tor(self, detached: bool = True) -> bool:
        """Start TOR container using docker-compose

        Args:
            detached: Whether to run container in background (default: True)

        Returns:
            True if container started successfully, False otherwise
        """
        try:
            cmd = ["docker-compose", "-f", str(self.compose_file), "up"]
            if detached:
                cmd.append("-d")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0
        except Exception as e:
            print(f"Failed to start TOR: {e}")
            return False

    def stop_tor(self) -> bool:
        """Stop TOR container

        Returns:
            True if container stopped successfully, False otherwise
        """
        try:
            result = subprocess.run(
                ["docker-compose", "-f", str(self.compose_file), "down"],
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0
        except Exception:
            return False

    def is_running(self) -> bool:
        """Check if TOR container is running

        Returns:
            True if container is running, False otherwise
        """
        return check_tor_container_running(self.container_name)

    def restart_tor(self) -> bool:
        """Restart TOR container

        Returns:
            True if restart successful, False otherwise
        """
        self.stop_tor()
        return self.start_tor()

    def get_logs(self, tail: int = 100) -> str:
        """Get TOR container logs

        Args:
            tail: Number of log lines to retrieve (default: 100)

        Returns:
            Container logs as string, empty string if error
        """
        try:
            result = subprocess.run(
                ["docker-compose", "-f", str(self.compose_file), "logs", "--tail", str(tail)],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.stdout
        except Exception:
            return ""