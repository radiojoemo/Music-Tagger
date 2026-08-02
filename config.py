"""
config.py
Loads and saves persistent app settings (API keys, last-used folder, etc.)
Stored as JSON in the user's AppData folder on Windows.
"""

import json
import os

APP_NAME = "MusicTagger"


def _config_dir() -> str:
    base = os.getenv("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def _config_path() -> str:
    return os.path.join(_config_dir(), "config.json")


DEFAULTS = {
    "acoustid_api_key": "",
    "discogs_token": "",
    "fpcalc_path": "",          # optional override, otherwise expects fpcalc on PATH
    "auto_write_threshold": 85,  # confidence 0-100; >= this writes automatically
    "download_cover_art": True,
    "last_folder": "",
    "musicbrainz_contact_email": "you@example.com",
}


def load_config() -> dict:
    path = _config_path()
    if not os.path.exists(path):
        return dict(DEFAULTS)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(DEFAULTS)
        merged.update(data)
        return merged
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULTS)


def save_config(cfg: dict) -> None:
    path = _config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
