from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def presets_path(base_dir: Path) -> Path:
    # Stored under web-app/var so it's not committed.
    return base_dir / "var" / "presets.json"


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_presets(base_dir: Path) -> dict[str, dict[str, Any]]:
    path = presets_path(base_dir)
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    presets = data.get("presets", {})
    if not isinstance(presets, dict):
        return {}
    return presets


def save_presets(base_dir: Path, presets: dict[str, dict[str, Any]]) -> None:
    path = presets_path(base_dir)
    _ensure_parent(path)
    path.write_text(json.dumps({"presets": presets}, indent=2), encoding="utf-8")


def normalize_preset_name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        raise ValueError("Preset name is required")
    # Keep it filename/URL safe-ish
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_ .")
    if any(ch not in allowed for ch in name):
        raise ValueError("Preset name contains invalid characters")
    return name


def upsert_preset(base_dir: Path, name: str, values: dict[str, Any]) -> None:
    presets = load_presets(base_dir)
    presets[name] = values
    save_presets(base_dir, presets)


def delete_preset(base_dir: Path, name: str) -> None:
    presets = load_presets(base_dir)
    if name in presets:
        del presets[name]
        save_presets(base_dir, presets)

