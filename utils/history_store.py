"""Local history of generated and scanned QR codes.

Everything stays on this PC, in the settings folder:
    history.json        the list (newest first)
    history\\thumbs\\    one small PNG preview per entry

Privacy rules (see PRIVACY.md):
* "Save history" can be switched off in Settings (then nothing is written).
* WiFi passwords are NOT saved unless "Save WiFi passwords" is switched on. Without it a WiFi
  entry keeps the network name and type, its password is blank, and NO preview picture is
  stored for it (the picture of a WiFi QR contains the password).
* At most ``max_entries()`` entries (default 200) are kept; older ones and their previews go.
* Clear history removes the list and every preview file.
"""
import datetime
import json
import os
import shutil
import time
import uuid

from PIL import Image

from utils import settings_store
from utils.app_log import get_logger

KEY_ENABLED = "history_enabled"
KEY_WIFI_PASSWORDS = "history_save_wifi_passwords"
KEY_MAX = "history_max_entries"
DEFAULT_MAX = 200
MIN_MAX, MAX_MAX = 10, 1000
THUMB_SIZE = 128

GENERATED, SCANNED = "generated", "scanned"


# ------------------------------------------------------------------ settings

def enabled():
    return bool(settings_store.get(KEY_ENABLED, True))


def set_enabled(value):
    settings_store.set(KEY_ENABLED, bool(value))


def save_wifi_passwords():
    return bool(settings_store.get(KEY_WIFI_PASSWORDS, False))


def set_save_wifi_passwords(value):
    settings_store.set(KEY_WIFI_PASSWORDS, bool(value))


def max_entries():
    value = settings_store.get(KEY_MAX, DEFAULT_MAX)
    if not isinstance(value, int) or isinstance(value, bool):
        return DEFAULT_MAX
    return max(MIN_MAX, min(MAX_MAX, value))


# ------------------------------------------------------------------ paths

def _history_dir():
    return os.path.join(settings_store.folder(), "history")


def _thumbs_dir():
    return os.path.join(_history_dir(), "thumbs")


def _list_path():
    return os.path.join(settings_store.folder(), "history.json")


def thumbnail_path(entry):
    """Path of the entry's preview picture, or None when it has none."""
    if not entry.get("thumb"):
        return None
    path = os.path.join(_thumbs_dir(), entry["id"] + ".png")
    return path if os.path.exists(path) else None


# ------------------------------------------------------------------ WiFi

def redact_wifi(raw):
    """``raw`` (a WIFI:... payload) without its password; other text is returned unchanged."""
    if not raw.upper().startswith("WIFI:"):
        return raw
    parts, current, i = [], [], 5
    while i < len(raw):
        ch = raw[i]
        if ch == "\\" and i + 1 < len(raw):
            current.append(raw[i:i + 2])
            i += 2
            continue
        if ch == ";":
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
        i += 1
    parts.append("".join(current))
    kept = [p for p in parts if not p.upper().startswith("P:")]
    return raw[:5] + ";".join(kept)


def is_wifi(text):
    return text.strip().upper().startswith("WIFI:")


# ------------------------------------------------------------------ the list

_VALID_KINDS = (GENERATED, SCANNED)


def _clean(entry):
    """The entry if it looks like one we wrote, else None."""
    if not isinstance(entry, dict):
        return None
    if not isinstance(entry.get("id"), str) or not entry["id"].isalnum():
        return None
    if entry.get("kind") not in _VALID_KINDS or not isinstance(entry.get("text"), str):
        return None
    if not isinstance(entry.get("type"), str) or not isinstance(entry.get("created"), str):
        return None
    for key in ("fields", "style"):
        if key in entry and not isinstance(entry[key], dict):
            entry.pop(key)
    entry["thumb"] = bool(entry.get("thumb"))
    return entry


def entries():
    """All entries, newest first. A damaged file is set aside and treated as empty."""
    path = _list_path()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as e:
        get_logger().error("History file could not be read (%s); it was set aside.", e)
        _set_aside(path)
        return []
    items = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(items, list):
        get_logger().error("History file has an unexpected shape; it was set aside.")
        _set_aside(path)
        return []
    return [e for e in (_clean(item) for item in items) if e is not None]


def _set_aside(path):
    try:
        os.replace(path, path + ".damaged")
    except OSError as e:
        get_logger().error("Could not set the damaged history file aside: %s", e)


def _write(items):
    path = _list_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"version": 1, "entries": items}, fh, indent=1, ensure_ascii=False)
    for attempt in range(6):          # a reader (antivirus, backup) can hold the file for a moment
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(0.05)


def _delete_thumb(entry_id):
    path = os.path.join(_thumbs_dir(), entry_id + ".png")
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def _same(a, b):
    """True when entry ``b`` (not yet stored) repeats the stored entry ``a``."""
    keys = ("kind", "type", "text", "style", "logo")
    return all(a.get(k) == b.get(k) for k in keys)


def _add(entry, thumbnail=None):
    items = entries()
    if items and _same(items[0], entry):
        return None                        # the same code twice in a row is one entry
    entry["id"] = uuid.uuid4().hex
    entry["created"] = datetime.datetime.now().isoformat(timespec="seconds")
    entry["thumb"] = False
    if thumbnail is not None:
        os.makedirs(_thumbs_dir(), exist_ok=True)
        thumb = thumbnail.convert("RGB")
        thumb.thumbnail((THUMB_SIZE, THUMB_SIZE), Image.Resampling.LANCZOS)
        thumb.save(os.path.join(_thumbs_dir(), entry["id"] + ".png"), "PNG")
        entry["thumb"] = True
    items.insert(0, entry)
    for old in items[max_entries():]:
        _delete_thumb(old["id"])
    _write(items[:max_entries()])
    return entry


def add_generated(type_name, text, fields, style, logo_path=None, image=None):
    """Remember a generated QR. Returns the entry, or None when history is off.

    ``text`` is the encoded payload, ``fields`` the form values (to refill the form), ``style``
    a QRStyle, ``image`` the picture to make the preview from.
    """
    if not enabled():
        return None
    wifi = is_wifi(text)
    keep_secret = save_wifi_passwords()
    entry = {
        "kind": GENERATED, "type": type_name,
        "text": text if (not wifi or keep_secret) else redact_wifi(text),
        "fields": dict(fields or {}),
        "style": style.to_dict(),
        "logo": logo_path or "",
    }
    if wifi and not keep_secret:
        entry["redacted"] = True
        entry["fields"].pop("password", None)
        image = None                       # the picture of a WiFi QR contains the password
    return _add(entry, image)


def add_scanned(text, type_name, thumbnail=None):
    """Remember a scanned QR. Returns the entry, or None when history is off."""
    if not enabled() or not text.strip():
        return None
    wifi = is_wifi(text)
    keep_secret = save_wifi_passwords()
    entry = {"kind": SCANNED, "type": type_name,
             "text": text if (not wifi or keep_secret) else redact_wifi(text)}
    if wifi and not keep_secret:
        entry["redacted"] = True
        thumbnail = None
    return _add(entry, thumbnail)


def get(entry_id):
    for entry in entries():
        if entry["id"] == entry_id:
            return entry
    return None


def delete(entry_id):
    items = entries()
    kept = [e for e in items if e["id"] != entry_id]
    if len(kept) != len(items):
        _delete_thumb(entry_id)
        _write(kept)


def clear():
    """Remove the whole history: the list and every preview file."""
    try:
        os.remove(_list_path())
    except FileNotFoundError:
        pass
    if os.path.isdir(_history_dir()):
        shutil.rmtree(_history_dir())       # previews included, whatever is left in there
    damaged = _list_path() + ".damaged"
    if os.path.exists(damaged):
        os.remove(damaged)


def count():
    return len(entries())


def stored_files():
    """Every file history keeps (list, previews): for tests and for the privacy statement."""
    found = []
    if os.path.exists(_list_path()):
        found.append(_list_path())
    for root, _dirs, files in os.walk(_history_dir()):
        found.extend(os.path.join(root, name) for name in files)
    return found
