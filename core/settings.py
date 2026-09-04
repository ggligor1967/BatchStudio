"""
BatchStudio - Settings Module
Manages user preferences and application settings.
"""

import os
import json
from typing import Any, Dict, Optional
from pathlib import Path
from copy import deepcopy


class Settings:
    """
    Manages application settings with persistent storage.
    Settings are stored in a JSON file in the user's home directory.
    """
    
    # Default settings
    DEFAULTS = {
        # General
        'language': 'en',
        'dark_mode': False,
        'check_updates': True,
        
        # Processing
        'default_workers': 4,
        'default_output_dir': '',
        'default_naming_pattern': '{original}_processed',
        'generate_report': True,
        'report_format': 'html',
        
        # UI
        'window_width': 1200,
        'window_height': 800,
        'window_x': None,
        'window_y': None,
        'show_preview': True,
        'confirm_clear': True,
        
        # File handling
        'max_file_size_mb': 500,
        'recursive_folder_scan': True,
        'skip_hidden_files': True,
        
        # Recent items
        'recent_workflows': [],
        'recent_output_dirs': [],
        'max_recent_items': 10,
        
        # Advanced
        'debug_mode': False,
        'log_to_file': False,
        'log_file_path': ''
    }
    
    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize settings manager.
        
        Args:
            config_dir: Custom config directory. Defaults to ~/.batchstudio
        """
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            self.config_dir = Path.home() / '.batchstudio'
        
        self.config_file = self.config_dir / 'settings.json'
        self._settings: Dict[str, Any] = {}
        self._load()
    
    def _load(self) -> None:
        """Load settings from file."""
        # Start with defaults
        self._settings = deepcopy(self.DEFAULTS)
        
        # Load from file if exists
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                    # Merge with defaults (keeps new default keys)
                    self._settings.update(saved)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load settings: {e}")
    
    def _save(self) -> bool:
        """Save settings to file."""
        try:
            # Create config directory if needed
            self.config_dir.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, indent=2)
            return True
        except IOError as e:
            print(f"Warning: Could not save settings: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a setting value.
        
        Args:
            key: Setting key
            default: Default value if key not found
            
        Returns:
            Setting value
        """
        return self._settings.get(key, default)
    
    def set(self, key: str, value: Any, save: bool = True) -> None:
        """
        Set a setting value.
        
        Args:
            key: Setting key
            value: Setting value
            save: Whether to immediately save to disk
        """
        self._settings[key] = value
        if save:
            self._save()
    
    def update(self, settings: Dict[str, Any], save: bool = True) -> None:
        """
        Update multiple settings at once.
        
        Args:
            settings: Dictionary of settings to update
            save: Whether to immediately save to disk
        """
        self._settings.update(settings)
        if save:
            self._save()
    
    def reset(self, key: Optional[str] = None) -> None:
        """
        Reset setting(s) to default.
        
        Args:
            key: Specific key to reset, or None to reset all
        """
        if key:
            if key in self.DEFAULTS:
                self._settings[key] = deepcopy(self.DEFAULTS[key])
        else:
            self._settings = deepcopy(self.DEFAULTS)
        self._save()
    
    def get_all(self) -> Dict[str, Any]:
        """Get all settings."""
        return self._settings.copy()
    
    # Convenience methods for common settings
    
    def add_recent_workflow(self, filepath: str) -> None:
        """Add a workflow to recent list."""
        recent = self._settings.get('recent_workflows', [])
        
        # Remove if already exists (to move to front)
        if filepath in recent:
            recent.remove(filepath)
        
        # Add to front
        recent.insert(0, filepath)
        
        # Trim to max
        max_items = self._settings.get('max_recent_items', 10)
        self._settings['recent_workflows'] = recent[:max_items]
        self._save()
    
    def add_recent_output_dir(self, dirpath: str) -> None:
        """Add an output directory to recent list."""
        recent = self._settings.get('recent_output_dirs', [])
        
        if dirpath in recent:
            recent.remove(dirpath)
        
        recent.insert(0, dirpath)
        
        max_items = self._settings.get('max_recent_items', 10)
        self._settings['recent_output_dirs'] = recent[:max_items]
        self._save()
    
    def get_recent_workflows(self) -> list:
        """Get recent workflows list."""
        return self._settings.get('recent_workflows', [])
    
    def get_recent_output_dirs(self) -> list:
        """Get recent output directories list."""
        return self._settings.get('recent_output_dirs', [])
    
    def save_window_geometry(self, width: int, height: int, x: int, y: int) -> None:
        """Save window position and size."""
        self.update({
            'window_width': width,
            'window_height': height,
            'window_x': x,
            'window_y': y
        })
    
    def get_window_geometry(self) -> tuple:
        """Get saved window geometry."""
        return (
            self._settings.get('window_width', 1200),
            self._settings.get('window_height', 800),
            self._settings.get('window_x'),
            self._settings.get('window_y')
        )


# Global settings instance
_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance


def reset_settings_instance() -> None:
    """Reset the global settings instance (mainly for testing)."""
    global _settings_instance
    _settings_instance = None
