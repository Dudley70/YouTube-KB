"""Filename utilities for YouTube video processing."""

import re
from typing import Dict, Any


def generate_filename(video_metadata: Dict[str, Any]) -> str:
    """Generate a safe filename from video metadata.
    
    Args:
        video_metadata: Video metadata dictionary
        
    Returns:
        Safe filename string
    """
    # Will be implemented in CP-REFACTOR-2
    title = video_metadata.get("title", "untitled")
    # Basic sanitization
    safe_title = re.sub(r'[^\w\s-]', '', title)
    safe_title = re.sub(r'[-\s]+', '-', safe_title)
    return f"{safe_title}.md"


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename for filesystem safety.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    if not filename:
        return ""

    # Remove invalid filename characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Replace multiple whitespace with single space
    sanitized = re.sub(r'\s+', ' ', sanitized)
    # Remove leading/trailing whitespace and dots
    sanitized = sanitized.strip(' .')

    return sanitized