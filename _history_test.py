"""History store: limits, privacy (WiFi passwords, thumbnails), clearing, damaged files.

Run:  .venv\\Scripts\\python.exe _history_test.py
"""
import json
import os
import sys
import tempfile

os.environ.setdefault("PYTHONUTF8", "1")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
APPDATA = tempfile.mkdtemp()
os.environ["APPDATA"] = APPDATA          # the real history is never touched

problems = []
PASSWORD = "hunter2-pass"


def check(label, ok, detail=""):
    if not ok:
        problems.append(f"{label} {detail}".strip())


def fresh():
    """An empty history with default settings."""
    from utils import history_store as h, settings_store
    h.clear()
    settings_store.set(h.KEY_ENABLED, True)
    settings_store.set(h.KEY_WIFI_PASSWORDS, False)
    settings_store.set(h.KEY_MAX, h.DEFAULT_MAX)


def style_of(**kw):
    from utils.qr_render import QRStyle
    return QRStyle(**kw)


def picture(text, **kw):
    from utils.qr_generator import QRGenerator
    return QRGenerator().generate(text, style=style_of(**kw))


def decode_thumbnail(path):
    """What a scanner reads from a saved preview (enlarged first: previews are small)."""
    from PIL import Image
    from utils.qr_scanner import QRScanner
    image = Image.open(path).convert("RGB")
    image = image.resize((image.width * 4, image.height * 4), Image.Resampling.LANCZOS)
    return QRScanner.decode_image(image, thorough=True)


def test_basics():
    from utils import history_store as h
    from utils.qr_render import QRStyle

    fresh()
    check("starts empty", h.entries() == [] and h.count() == 0)
    a = h.add_generated("URL / Text", "https://example.com/a", {"url": "https://example.com/a"},
                        style_of(module_shape="dots", fg="#0E7490"), None, picture("https://example.com/a"))
    b = h.add_scanned("https://example.com/b", "URL", picture("https://example.com/b"))
    check("entries have ids and dates", a["id"] != b["id"] and "T" in a["created"])
    listed = h.entries()
    check("newest first", [e["id"] for e in listed] == [b["id"], a["id"]])
    check("kinds kept", [e["kind"] for e in listed] == ["scanned", "generated"])
    check("form fields kept", listed[1]["fields"] == {"url": "https://example.com/a"})
    check("style round trip", QRStyle.from_dict(listed[1]["style"]) == style_of(module_shape="dots", fg="#0E7490"))
    check("previews saved", all(h.thumbnail_path(e) for e in listed))
    check("preview decodes to the text", decode_thumbnail(h.thumbnail_path(listed[0])) == "https://example.com/b")
    check("get by id", h.get(a["id"])["text"] == "https://example.com/a" and h.get("nope") is None)

    h.delete(a["id"])
    check("delete removes the entry", [e["id"] for e in h.entries()] == [b["id"]])
    check("delete removes its preview", not os.path.exists(os.path.join(h._thumbs_dir(), a["id"] + ".png")))
    h.delete("does-not-exist")
    h.delete(a["id"])
    check("deleting twice / unknown is harmless", h.count() == 1)

    check("empty scan is not stored", h.add_scanned("   ", "Text") is None and h.count() == 1)


def test_switch_off():
    from utils import history_store as h

    fresh()
    h.set_enabled(False)
    check("switched off: generated not stored",
          h.add_generated("URL / Text", "x", {}, style_of(), None, picture("x")) is None)
    check("switched off: scanned not stored", h.add_scanned("x", "Text", picture("x")) is None)
    check("switched off: nothing written to disk", h.stored_files() == [], str(h.stored_files()))
    h.set_enabled(True)
    h.add_scanned("y", "Text")
    check("switched on again: stored", h.count() == 1)


def test_wifi_privacy():
    from utils import history_store as h, qr_payloads

    wifi = qr_payloads.build_wifi("Guest Net", PASSWORD, "WPA")
    fields = {"ssid": "Guest Net", "password": PASSWORD, "security": "WPA", "hidden": False}

    # ---- password saving OFF (default) ----
    fresh()
    g = h.add_generated("WiFi", wifi, fields, style_of(), None, picture(wifi))
    s = h.add_scanned(wifi, "WiFi", picture(wifi))
    ok_entry = h.add_generated("URL / Text", "https://example.com/ok", {"url": "https://example.com/ok"},
                               style_of(), None, picture("https://example.com/ok"))
    check("wifi generated: marked redacted", g.get("redacted") is True)
    check("wifi generated: network name kept", "Guest Net" in g["text"] and g["type"] == "WiFi")
    check("wifi generated: password not in the text", PASSWORD not in g["text"], g["text"])
    check("wifi generated: password not in the fields", PASSWORD not in json.dumps(g["fields"]))
    check("wifi generated: NO preview saved", not g["thumb"] and h.thumbnail_path(g) is None)
    check("wifi scanned: password not in the text", PASSWORD not in s["text"] and "Guest Net" in s["text"])
    check("wifi scanned: NO preview saved", not s["thumb"] and h.thumbnail_path(s) is None)
    check("other types still get a preview", ok_entry["thumb"] and h.thumbnail_path(ok_entry))

    # nothing on disk may contain the password: not the list, not any preview
    for path in h.stored_files():
        if path.endswith(".json"):
            check("password absent from history.json", PASSWORD not in open(path, encoding="utf-8").read())
        elif path.endswith(".png"):
            check(f"password absent from the picture bytes ({os.path.basename(path)})",
                  PASSWORD.encode() not in open(path, "rb").read())
            decoded = decode_thumbnail(path)
            check(f"decoding {os.path.basename(path)} gives no password",
                  decoded is None or PASSWORD not in decoded, repr(decoded))
    previews = [p for p in h.stored_files() if p.endswith(".png")]
    check("exactly one preview exists (the non-WiFi one)", len(previews) == 1, str(previews))
    check("the saved preview is readable (so the check above means something)",
          decode_thumbnail(previews[0]) == "https://example.com/ok")
    check("redacted text is still a WiFi payload", g["text"].startswith("WIFI:T:WPA;S:Guest Net;"))
    parsed = qr_payloads.parse(g["text"])
    check("redacted text parses as WiFi without a password",
          parsed.kind == "wifi" and not any(label == "Password" for label, _ in parsed.fields))

    # ---- password saving ON ----
    fresh()
    h.set_save_wifi_passwords(True)
    g = h.add_generated("WiFi", wifi, fields, style_of(), None, picture(wifi))
    check("on: password kept", g["text"] == wifi and not g.get("redacted"))
    check("on: preview saved", g["thumb"] and h.thumbnail_path(g) is not None)
    check("on: preview decodes to the full payload", decode_thumbnail(h.thumbnail_path(g)) == wifi)

    # ---- redaction details ----
    check("redact: escaped separators", h.redact_wifi("WIFI:T:WPA;S:a\\;b;P:pa\\;ss;H:true;;")
          == "WIFI:T:WPA;S:a\\;b;H:true;;")
    check("redact: open network unchanged", h.redact_wifi("WIFI:T:nopass;S:Cafe;;") == "WIFI:T:nopass;S:Cafe;;")
    check("redact: lower-case key", "secret" not in h.redact_wifi("WIFI:T:WPA;S:x;p:secret;;"))
    check("redact: password first", "secret" not in h.redact_wifi("WIFI:P:secret;T:WPA;S:x;;"))
    check("redact: non-wifi unchanged", h.redact_wifi("https://p:secret") == "https://p:secret")
    parsed = qr_payloads.parse(h.redact_wifi("WIFI:T:WPA;S:a\\;b;P:pa\\;ss;H:true;;"))
    check("redact: parses with the right name", parsed.kind == "wifi" and ("Network", "a;b") in parsed.fields)


def test_limit():
    from utils import history_store as h, settings_store

    fresh()
    settings_store.set(h.KEY_MAX, 10)
    first_ids = []
    for index in range(25):
        entry = h.add_scanned(f"https://example.com/{index}", "URL", picture(f"https://example.com/{index}"))
        first_ids.append(entry["id"])
    listed = h.entries()
    check("limit keeps exactly the newest 10", [e["id"] for e in listed] == first_ids[::-1][:10])
    check("oldest dropped", first_ids[0] not in [e["id"] for e in listed])
    previews = {os.path.splitext(n)[0] for n in os.listdir(h._thumbs_dir())}
    check("previews of dropped entries are deleted", previews == {e["id"] for e in listed},
          f"{len(previews)} previews for {len(listed)} entries")

    # default and bounds
    for value, expected in ((None, 200), ("many", 200), (True, 200), (3, 10), (99999, 1000),
                            (50, 50), (-5, 10), (12.5, 200)):
        settings_store.set(h.KEY_MAX, value)
        check(f"max_entries({value!r}) = {expected}", h.max_entries() == expected, str(h.max_entries()))
    settings_store.set(h.KEY_MAX, h.DEFAULT_MAX)
    check("default limit is 200", h.max_entries() == 200 and h.DEFAULT_MAX == 200)


def test_clear():
    from utils import history_store as h

    fresh()
    for index in range(5):
        h.add_scanned(f"https://example.com/{index}", "URL", picture(f"https://example.com/{index}"))
    # stray files that are not ours must go too: the folder is history's own
    with open(os.path.join(h._thumbs_dir(), "leftover.png"), "wb") as fh:
        fh.write(b"x")
    with open(h._list_path() + ".damaged", "w") as fh:
        fh.write("x")
    check("something is stored before clearing", len(h.stored_files()) >= 6)
    h.clear()
    check("clear: list gone", h.entries() == [] and not os.path.exists(h._list_path()))
    check("clear: thumbs folder gone entirely", not os.path.exists(h._thumbs_dir()))
    check("clear: history folder gone", not os.path.exists(h._history_dir()))
    check("clear: nothing left on disk", h.stored_files() == [], str(h.stored_files()))
    check("clear: damaged copy gone", not os.path.exists(h._list_path() + ".damaged"))
    h.clear()
    check("clearing an empty history is harmless", h.count() == 0)
    h.add_scanned("again", "Text")
    check("works again after clearing", h.count() == 1)


def test_damaged_files():
    from utils import history_store as h

    for label, content in (("garbage", "{{{ not json"), ("empty file", ""), ("a list", "[1,2,3]"),
                           ("wrong shape", json.dumps({"entries": "nope"})),
                           ("binary", None)):
        fresh()
        os.makedirs(os.path.dirname(h._list_path()), exist_ok=True)
        with open(h._list_path(), "wb") as fh:
            fh.write(b"\xff\xfe\x00\x01" if content is None else content.encode())
        check(f"{label}: reads as empty", h.entries() == [])
        check(f"{label}: file set aside, not deleted", os.path.exists(h._list_path() + ".damaged"))
        h.add_scanned("recovered", "Text")
        check(f"{label}: usable afterwards", h.count() == 1)

    # entries that do not look right are skipped, the good ones stay
    fresh()
    good = {"id": "a1", "kind": "scanned", "type": "URL", "created": "2026-01-01T00:00:00", "text": "t"}
    bad = [{"id": 5}, {"id": "b2", "kind": "weird", "text": "t", "type": "x", "created": "c"},
           "string", None, {"id": "../evil", "kind": "scanned", "text": "t", "type": "x", "created": "c"},
           {"id": "c3", "kind": "scanned", "text": 5, "type": "x", "created": "c"},
           dict(good, id="d4", fields="not a dict", style=[1])]
    with open(h._list_path(), "w", encoding="utf-8") as fh:
        json.dump({"version": 1, "entries": [good] + bad}, fh)
    ids = [e["id"] for e in h.entries()]
    check("bad entries skipped", ids == ["a1", "d4"], str(ids))
    kept = h.get("d4")
    check("bad optional fields dropped", "fields" not in kept and "style" not in kept)


def main():
    for test in (test_basics, test_switch_off, test_wifi_privacy, test_limit, test_clear,
                 test_damaged_files):
        test()
    if problems:
        print("HISTORY_FAIL")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print("HISTORY_OK: store, switch off, WiFi redaction (text + previews, decoded), limit, clear, damaged files")


if __name__ == "__main__":
    main()
