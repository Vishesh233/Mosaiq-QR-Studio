"""Colour maths, recent colours and the in-app colour picker.

Run:  .venv\\Scripts\\python.exe _color_picker_test.py
"""
import json
import os
import sys
import tempfile

os.environ.setdefault("PYTHONUTF8", "1")
os.environ["QRSTUDIO_NO_SPLASH"] = "1"
APPDATA = tempfile.mkdtemp()
os.environ["APPDATA"] = APPDATA          # settings (recent colours) never touch the real ones

problems = []


def check(label, ok, detail=""):
    if not ok:
        problems.append(f"{label} {detail}".strip())


def test_maths():
    from utils import colors

    for raw, expected in (("#abc", "#AABBCC"), ("abc", "#AABBCC"), ("#aabbcc", "#AABBCC"),
                          ("  0e7490 ", "#0E7490"), ("#0E7490", "#0E7490")):
        check(f"parse {raw!r}", colors.parse_color(raw) == expected, repr(colors.parse_color(raw)))
    for bad in ("", None, "#12", "#1234", "#12345", "#1234567", "#GGGGGG", "red", "# 123456",
                "#12345g", "rgb(1,2,3)"):
        check(f"reject {bad!r}", colors.parse_color(bad) is None, repr(colors.parse_color(bad)))

    # hex <-> rgb <-> hsv round trips for a spread of colours (including edges)
    for color in ("#000000", "#FFFFFF", "#FF0000", "#00FF00", "#0000FF", "#0E7490", "#1E3A8A",
                  "#808080", "#010203", "#FEFDFC", "#7C6CFF"):
        r, g, b = colors.hex_to_rgb(color)
        check(f"rgb round trip {color}", colors.rgb_to_hex(r, g, b) == color)
        h, s, v = colors.rgb_to_hsv(r, g, b)
        check(f"hsv round trip {color}", colors.rgb_to_hex(*colors.hsv_to_rgb(h, s, v)) == color)
    check("rgb_to_hex clamps", colors.rgb_to_hex(-5, 300, 12.4) == "#00FF0C")

    check("black on white contrast is 21", abs(colors.contrast_ratio("#000000", "#FFFFFF") - 21) < 0.01)
    check("identical colours contrast 1", abs(colors.contrast_ratio("#123456", "#123456") - 1) < 1e-9)
    check("contrast is symmetric",
          colors.contrast_ratio("#0E7490", "#FFFFFF") == colors.contrast_ratio("#FFFFFF", "#0E7490"))
    check("known value", abs(colors.contrast_ratio("#777777", "#FFFFFF") - 4.48) < 0.02,
          str(colors.contrast_ratio("#777777", "#FFFFFF")))
    check("presets are valid and unique",
          all(colors.parse_color(c) == c for c in colors.PRESET_COLORS)
          and len(set(colors.PRESET_COLORS)) == len(colors.PRESET_COLORS))


def test_recent():
    from utils import colors, settings_store

    check("recent starts empty", colors.load_recent() == [])
    colors.remember("#0e7490")
    colors.remember("#ffffff")
    colors.remember("#0E7490")                         # moves to the front, no duplicate
    check("newest first, no duplicates", colors.load_recent() == ["#0E7490", "#FFFFFF"],
          repr(colors.load_recent()))
    colors.remember("not a colour")
    check("invalid colour ignored", colors.load_recent() == ["#0E7490", "#FFFFFF"])
    for index in range(20):
        colors.remember("#%06X" % (index * 1000 + 1))
    check("at most 10 kept", len(colors.load_recent()) == colors.MAX_RECENT)
    check("newest of the 20 is first", colors.load_recent()[0] == "#%06X" % (19 * 1000 + 1))
    # damaged settings never break the picker
    for broken in ("oops", 5, None, {"a": 1}, ["#12", 7, None, "#abcdef", "#ABCDEF"]):
        settings_store.set(colors.RECENT_KEY, broken)
        loaded = colors.load_recent()
        check(f"damaged recent list {broken!r} handled", isinstance(loaded, list)
              and all(colors.parse_color(c) == c for c in loaded), repr(loaded))
    check("partly valid list keeps the valid colours, once",
          colors.load_recent() == ["#ABCDEF"], repr(colors.load_recent()))
    settings_store.set(colors.RECENT_KEY, [])


def test_dialog():
    from ui.app import QRCodeStudioApp
    from ui.dialogs.color_picker import ColorPickerDialog
    from utils import colors

    app = QRCodeStudioApp()
    root = app.root
    root.geometry("1280x820+-30000+-30000")
    root.update()

    def settle():
        for _ in range(3):
            root.update()

    dlg = ColorPickerDialog(app.header, "#0E7490", "Test")
    settle()
    check("opens on the initial colour", dlg.color == "#0E7490" and dlg.hex_entry.get() == "#0E7490")
    check("rgb fields match", [e.get() for e in dlg.rgb_entries] == ["14", "116", "144"],
          repr([e.get() for e in dlg.rgb_entries]))

    # HEX typing
    dlg.hex_entry.delete(0, "end")
    dlg.hex_entry.insert(0, "#FF8800")
    dlg._hex_typed()
    check("hex typing sets the colour", dlg.color == "#FF8800")
    check("rgb follows hex", [e.get() for e in dlg.rgb_entries] == ["255", "136", "0"])
    check("typing is not rewritten under the cursor", dlg.hex_entry.get() == "#FF8800")
    dlg.hex_entry.delete(0, "end")
    dlg.hex_entry.insert(0, "#0e7")
    dlg._hex_typed()
    check("short hex accepted", dlg.color == "#00EE77", dlg.color)
    check("short hex text left as typed", dlg.hex_entry.get() == "#0e7", dlg.hex_entry.get())
    dlg.hex_entry.delete(0, "end")
    dlg.hex_entry.insert(0, "#12")
    dlg._hex_typed()
    check("invalid hex keeps the last colour", dlg.color == "#00EE77")
    check("invalid hex shows a message", dlg.error_label.cget("text") != "")
    check("invalid hex marks the field", dlg.hex_entry.cget("border_color") ==
          __import__("utils.theme_manager", fromlist=["x"]).ThemeManager.get_theme()["danger"])

    # RGB typing
    for entry, value in zip(dlg.rgb_entries, ("10", "20", "30")):
        entry.delete(0, "end")
        entry.insert(0, value)
    dlg._rgb_typed()
    check("rgb typing sets the colour", dlg.color == "#0A141E", dlg.color)
    check("hex follows rgb", dlg.hex_entry.get() == "#0A141E")
    check("valid input clears the message", dlg.error_label.cget("text") == "")
    for bad in ("256", "-1", "x", "", "1.5"):
        dlg.rgb_entries[1].delete(0, "end")
        dlg.rgb_entries[1].insert(0, bad)
        dlg._rgb_typed()
        check(f"rgb {bad!r} rejected", dlg.color == "#0A141E" and dlg.error_label.cget("text") != "")
    dlg.set_color("#0A141E")

    # the square: corners and the hue bar
    class Pos:
        def __init__(self, x, y):
            self.x, self.y = x, y

    dlg._hue_drag(Pos(0, 0))                          # hue 0 = red
    dlg._sv_drag(Pos(dlg._sv_w - 1, 0))               # top right: full saturation, full value
    check("top right of the square is the pure hue", dlg.color == "#FF0000", dlg.color)
    dlg._sv_drag(Pos(0, 0))
    check("top left is white", dlg.color == "#FFFFFF", dlg.color)
    dlg._sv_drag(Pos(0, dlg._sv_h - 1))
    check("bottom is black", dlg.color == "#000000", dlg.color)
    dlg._sv_drag(Pos(dlg._sv_w + 500, -500))          # dragging outside is clamped
    check("outside the square is clamped", dlg.color == "#FF0000", dlg.color)
    dlg._hue_drag(Pos((dlg._sv_w - 1) // 3, 0))       # one third = green
    r, g, b = colors.hex_to_rgb(dlg.color)
    check("hue bar picks green", g == 255 and r <= 3 and b == 0, dlg.color)
    dlg._hue_drag(Pos(10 ** 6, 0))                    # far right clamps to 1.0 = red again
    check("hue bar clamps at the end", dlg.color == "#FF0000", dlg.color)

    # greys keep the hue where it was
    dlg.set_color("#FF0000")
    dlg.set_color("#808080")
    check("grey shown exactly", dlg.color == "#808080")
    check("hue kept for greys", abs(dlg._h - 0.0) < 1e-6)
    dlg.set_color("#000000")
    dlg.set_color("#00FF00")
    check("hue follows a real colour again", abs(dlg._h - 1 / 3) < 1e-3, str(dlg._h))

    # presets, recent, old swatch
    dlg.set_color("#112233")
    check("set_color rejects junk", dlg.set_color("zzz") is False and dlg.color == "#112233")
    for _ in range(2):      # the first synthetic click of a fresh window can be swallowed by Tk
        dlg.old_swatch._canvas.event_generate("<ButtonPress-1>", x=5, y=5, when="now")
        settle()
    check("clicking the old swatch goes back", dlg.color == "#0E7490", dlg.color)

    # Apply stores the colour in the recent list; Cancel does not
    dlg.set_color("#13579B")
    dlg.apply()
    settle()
    check("apply returns the colour", dlg.result == "#13579B")
    check("apply remembers it", colors.load_recent()[0] == "#13579B", repr(colors.load_recent()))
    check("dialog closed", not dlg.winfo_exists())

    before = colors.load_recent()
    dlg2 = ColorPickerDialog(app.header, "#000000", "Test")
    settle()
    check("recent colours listed", len(dlg2.recent_row.winfo_children()) == len(before),
          f"{len(dlg2.recent_row.winfo_children())} vs {len(before)}")
    dlg2.set_color("#FEDCBA")
    dlg2.cancel()
    settle()
    check("cancel returns None", dlg2.result is None)
    check("cancel remembers nothing", colors.load_recent() == before)

    # Escape and the window's X also cancel
    dlg3 = ColorPickerDialog(app.header, "#000000", "Test")
    settle()
    check("Escape and Enter are bound", bool(dlg3.bind("<Escape>")) and bool(dlg3.bind("<Return>")))
    dlg3.cancel()                                     # what Escape and the window's X call
    settle()
    check("cancel closes the dialog", not dlg3.winfo_exists())

    # the colour card uses this picker for both colours
    from ui.components import color_card as card_module
    gp = app.generate_page
    seen = []
    original = card_module.pick_color
    card_module.pick_color = lambda parent, initial, title: (seen.append((initial, title)), "#AB12CD")[1]
    try:
        gp.color_card.choose_color("qr")
        gp.color_card.choose_color("bg")
    finally:
        card_module.pick_color = original
    check("card asks for both colours with the current ones",
          seen == [("#000000", "QR colour"), ("#FFFFFF", "Background colour")], repr(seen))
    check("card shows and uses the picked colours",
          gp.color_card.get_qr_color() == "#AB12CD" and gp.color_card.get_bg_color() == "#AB12CD"
          and gp.color_card.qr_hex.cget("text") == "#AB12CD")
    card_module.pick_color = lambda parent, initial, title: None
    try:
        gp.color_card.choose_color("qr")
    finally:
        card_module.pick_color = original
    check("cancelled pick changes nothing", gp.color_card.get_qr_color() == "#AB12CD")
    gp.color_card.reset_colors()
    check("reset restores black on white",
          (gp.color_card.get_qr_color(), gp.color_card.get_bg_color()) == ("#000000", "#FFFFFF"))

    app.close()


def main():
    test_maths()
    test_recent()
    test_dialog()
    if problems:
        print("COLOR_PICKER_FAIL")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print("COLOR_PICKER_OK: colour maths, recent colours, picker dialog, colour card")


if __name__ == "__main__":
    main()
