import json
import re
from pathlib import Path
from typing import Dict, Any, Optional

from app.core.config import settings


def normalize_preset_name(name: str) -> str:
    """Normalize preset name to be filesystem-safe"""
    # Convert to lowercase, replace spaces with underscores, remove special chars
    normalized = re.sub(r'\s+', '_', name.strip())
    normalized = re.sub(r'[^a-zA-Z0-9_\-]', '', normalized.lower())
    
    if not normalized:
        raise ValueError("Preset name cannot be empty after normalization")
    
    if len(normalized) > 50:
        raise ValueError("Preset name too long (max 50 characters)")
    
    return normalized


def get_presets_file_path(base_dir: Optional[Path] = None) -> Path:
    """Get the presets file path (same as Django version)"""
    if base_dir is None:
        base_dir = settings.BASE_DIR
    return base_dir / "var" / "presets.json"


def load_presets(base_dir: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """Load all presets from JSON file (same as Django version)"""
    if base_dir is None:
        base_dir = settings.BASE_DIR
    
    presets_file = get_presets_file_path(base_dir)
    
    if not presets_file.exists():
        return {}
    
    try:
        data = presets_file.read_text(encoding="utf-8")
        presets_data = json.loads(data)
        if not isinstance(presets_data, dict):
            return {}
        
        raw_presets = presets_data.get("presets", {})
        
        # Create case-insensitive lookup by normalizing all keys
        normalized_presets = {}
        for name, preset_data in raw_presets.items():
            try:
                normalized_name = normalize_preset_name(name)
                normalized_presets[normalized_name] = preset_data
                # Also keep the original name for backward compatibility
                if name != normalized_name:
                    normalized_presets[name] = preset_data
            except ValueError:
                # Skip invalid preset names
                continue
        
        return normalized_presets
    except Exception:
        return {}


def upsert_preset(base_dir: Optional[Path], name: str, values: Dict[str, Any]) -> None:
    """Save or update a preset (same format as Django)"""
    if base_dir is None:
        base_dir = settings.BASE_DIR
    
    normalized_name = normalize_preset_name(name)
    presets_file = get_presets_file_path(base_dir)
    
    # Ensure var directory exists
    presets_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Load existing presets
    presets = load_presets(base_dir)
    
    # Update or add the preset
    presets[normalized_name] = values
    
    # Save back to file
    presets_data = {"presets": presets}
    presets_file.write_text(json.dumps(presets_data, indent=2), encoding="utf-8")


def delete_preset(base_dir: Optional[Path], name: str) -> None:
    """Delete a preset (same format as Django)"""
    if base_dir is None:
        base_dir = settings.BASE_DIR
    
    normalized_name = normalize_preset_name(name)
    presets_file = get_presets_file_path(base_dir)
    
    if not presets_file.exists():
        raise FileNotFoundError(f"Presets file not found at {presets_file}")
    
    # Load existing presets
    presets = load_presets(base_dir)
    
    # Remove the preset if it exists
    if normalized_name not in presets:
        raise FileNotFoundError(f"Preset '{name}' not found")
    
    del presets[normalized_name]
    
    # Save back to file
    presets_data = {"presets": presets}
    presets_file.write_text(json.dumps(presets_data, indent=2), encoding="utf-8")


def get_preset(base_dir: Optional[Path], name: str) -> Dict[str, Any]:
    """Get a specific preset"""
    if base_dir is None:
        base_dir = settings.BASE_DIR
    
    normalized_name = normalize_preset_name(name)
    presets = load_presets(base_dir)
    
    if normalized_name not in presets:
        raise FileNotFoundError(f"Preset '{name}' not found")
    
    return presets[normalized_name]
