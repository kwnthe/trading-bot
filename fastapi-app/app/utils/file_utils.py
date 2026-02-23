"""
File utility functions for reading text files
"""
from pathlib import Path
from typing import Optional


def read_text_file(file_path: Path) -> str:
    """Get full content of a text file"""
    try:
        if not file_path.exists():
            return ""
        
        with open(file_path, 'r') as f:
            return f.read()
    except Exception:
        return ""
