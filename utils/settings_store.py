"""Tiny persistent settings store (theme, intro preference).

Settings live in a JSON file in the per-user app-data folder
(``%APPDATA%\\QR Code Studio\\settings.json`` on Windows,
``~/.qr_code_studio/settings.json`` elsewhere). Every read is tolerant: a
missing or corrupt file simply yields the defaults, and a failed write never
interrupts the app.
"""
import json
import os
import sys

from config import SETTINGS_DIR_NAME


def _settings_path():
    if sys.platform.startswith("win") and os.environ.get("APPDATA"):
        folder = os.path.join(os.environ["APPDATA"], SETTINGS_DIR_NAME)
    else:
        folder = os.path.join(os.path.expanduser("~"), ".qr_code_studio")
    return os.path.join(folder, "settings.json")


_cache = None


def _load():
    global _cache
    if _cache is None:
        try:
            with open(_settings_path(), "r", encoding="utf-8") as fh:
                data = json.load(fh)
            _cache = data if isinstance(data, dict) else {}
        except Exception:
            _cache = {}
    return _cache


def get(key, default=None):
    """Return a stored value, or ``default`` when it is not set."""
    return _load().get(key, default)


def set(key, value):  # noqa: A001 - mirrors get()
    """Store a value and write the file (best effort)."""
    data = _load()
    if data.get(key) == value:
        return
    data[key] = value
    path = _settings_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp, path)
    except Exception:
        pass
