"""Tiny persistent settings store (theme, intro preference, history switches ...).

Settings live in a JSON file in the per-user app-data folder
(``%APPDATA%\\QR Code Studio\\settings.json`` on Windows,
``~/.qr_code_studio/settings.json`` elsewhere). Reading is tolerant: a missing or corrupt file
yields the defaults (a corrupt one is logged).

Writing is atomic (a temp file in the same folder, flushed to disk, then ``os.replace``), so a
crash or a full disk never leaves a half-written file. A failed write is never silent:

* ``update(mapping)`` writes several settings at once and raises ``SettingsWriteError`` (the
  in-memory values are rolled back, so what the app thinks matches the disk). The Settings
  dialog uses it and shows the error to the user.
* ``set(key, value)`` is for small conveniences (last folder, recent colours): it logs the
  failure to ``mosaiq.log`` and returns False instead of raising.
"""
import json
import os
import sys

from config import SETTINGS_DIR_NAME


class SettingsWriteError(OSError):
    """The settings file could not be written (the message is for the user)."""


def folder():
    """The per-user folder that holds the settings (and the history)."""
    if sys.platform.startswith("win") and os.environ.get("APPDATA"):
        return os.path.join(os.environ["APPDATA"], SETTINGS_DIR_NAME)
    return os.path.join(os.path.expanduser("~"), ".qr_code_studio")


def _settings_path():
    return os.path.join(folder(), "settings.json")


_cache = None


def _log(message, *args):
    # Imported here: app_log itself needs this module to find its folder.
    from utils.app_log import get_logger
    get_logger().error(message, *args, exc_info=True)


def reload():
    """Forget what was read and read the file again on the next ``get``."""
    global _cache
    _cache = None


def _load():
    global _cache
    if _cache is None:
        try:
            with open(_settings_path(), "r", encoding="utf-8") as fh:
                data = json.load(fh)
            _cache = data if isinstance(data, dict) else {}
        except FileNotFoundError:
            _cache = {}
        except (OSError, ValueError) as e:
            _log("The settings file could not be read (%s); defaults are used.", e)
            _cache = {}
    return _cache


def get(key, default=None):
    """Return a stored value, or ``default`` when it is not set."""
    return _load().get(key, default)


def _write(data):
    """Write ``data`` atomically. Raises SettingsWriteError."""
    path = _settings_path()
    tmp = path + ".tmp"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except (OSError, TypeError, ValueError) as e:
        try:
            os.remove(tmp)
        except OSError:
            pass
        reason = e.strerror if isinstance(e, OSError) and e.strerror else str(e)
        raise SettingsWriteError(f"Settings could not be saved to {path}: {reason}") from e


def update(values):
    """Store several settings in ONE write. Raises SettingsWriteError (nothing is changed then)."""
    data = _load()
    changed = {k: v for k, v in values.items() if k not in data or data[k] != v}
    if not changed:
        return
    new = dict(data)
    new.update(changed)
    _write(new)                       # raises before the in-memory copy is touched
    data.update(changed)


def set(key, value):  # noqa: A001 - mirrors get()
    """Store one value. Returns True when it is saved, False (and logs) when the write failed."""
    try:
        update({key: value})
        return True
    except SettingsWriteError as e:
        _log("%s", e)
        return False
