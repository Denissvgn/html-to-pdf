"""Utility functions for HTML to PDF conversion."""

import os
import shutil
import urllib.parse
from pathlib import Path
from typing import Optional, Tuple


def is_url(source: str) -> bool:
    """Check if the source string is a web URL."""
    source_clean = source.strip()
    return source_clean.startswith("http://") or source_clean.startswith("https://")


def is_file_url(source: str) -> bool:
    """Check if source is a file:// URL."""
    return source.strip().startswith("file://")


def normalize_source(source: str) -> Tuple[str, bool]:
    """
    Normalize source to either a valid URL or an absolute file URL.
    Returns: (normalized_url, is_remote_url)
    """
    source_clean = source.strip()
    
    if is_url(source_clean):
        return source_clean, True
    
    if is_file_url(source_clean):
        # Extract path from file:// URL
        parsed = urllib.parse.urlparse(source_clean)
        file_path = urllib.parse.unquote(parsed.path)
        abs_path = os.path.abspath(os.path.expanduser(file_path))
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"Local file does not exist: {abs_path}")
        return f"file://{abs_path}", False

    # Local file path
    abs_path = os.path.abspath(os.path.expanduser(source_clean))
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"Local file does not exist: {abs_path}")
    return f"file://{abs_path}", False


def find_system_chrome() -> Optional[str]:
    """Find installed Chrome / Chromium binary if available."""
    candidates = [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
    ]
    for candidate in candidates:
        if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def get_companion_folder(file_path: str) -> Optional[Path]:
    """
    Detect browser-saved companion assets directory.
    E.g. for 'document.html', looks for 'document_files'.
    """
    path = Path(file_path)
    base_stem = path.stem
    parent = path.parent
    
    possible_companion_names = [
        f"{base_stem}_files",
        f"{base_stem}.files",
        f"{path.name}_files",
    ]
    for comp in possible_companion_names:
        comp_dir = parent / comp
        if comp_dir.is_dir():
            return comp_dir
    return None
