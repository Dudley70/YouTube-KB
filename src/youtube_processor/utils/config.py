"""Configuration management."""

from typing import Dict, Any, Optional
from pathlib import Path
import json


class Config:
    """Application configuration manager."""
    
    def __init__(self, config_file: Optional[Path] = None):
        """Initialize configuration manager.
        
        Args:
            config_file: Path to configuration file
        """
        self.config_file = config_file or Path("config.json")
        self._config: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    self._config = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._config = {}
        else:
            self._config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "output_dir": "output",
            "parallel_workers": 4,
            "use_tor": False,
            "tor_port": 9050
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value.
        
        Args:
            key: Configuration key
            value: Configuration value
        """
        self._config[key] = value
    
    def save(self) -> None:
        """Save configuration to file."""
        with open(self.config_file, 'w') as f:
            json.dump(self._config, f, indent=2)