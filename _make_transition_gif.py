"""Make docs/design/theme-transition.gif: the Midnight -> Aqua Mint blob transition.

Frames come only from snapshots of the app's own window (PrintWindow, see
utils/theme_transition.capture_client) rendered with the same FrameRenderer the app uses. The window
is shown for a few seconds (Tk only paints windows that are on a monitor) with a throw-away APPDATA. Nothing from the screen is captured.

Run:  .venv\\Scripts\\python.exe _make_transition_gif.py [output.gif]
"""
import os
import sys
import tempfile

os.environ.setdefault("PYTHONUTF8", "1")
os.environ["QRSTUDIO_NO_SPLASH"] = "1"
os.environ["QRSTUDIO_NO_THEME_ANIMATION"] = "1"          # the app itself must not animate while we snapshot
os.environ["APPDATA"] = tempfile.mkdtemp()

FPS = 20
WIDTH = 800


def main():
    out = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join("docs", "design", "theme-transition.gif"))

    from PIL import Image

    from ui.app import QRCodeStudioApp
    from utils import settings_store, theme_transition as tt
    from utils.theme_manager import ThemeManager

    settings_store.update({"theme": "Midnight"})
    ThemeManager.load_saved()
    app = QRCodeStudioApp()
    root = app.root
    root.geometry("1280x800+20+20")                           # on screen for a few seconds: Tk only paints visible windows
    root.update()
    gp = app.generate_page
    gp.content_card.url_entry.insert(0, "https://example.com/mosaiq")
    gp.generate_qr()
    import time
    end = time.time() + 2.0
    while time.time() < end:
        root.update()
        time.sleep(0.02)

    before = tt.capture_client(root)
    ThemeManager.set_theme("Aqua Mint", persist=False)
    app.refresh_theme()
    root.update_idletasks()
    end = time.time() + 0.5
    while time.time() < end:
        root.update()
        time.sleep(0.02)
    after = tt.capture_client(root)
    accent = ThemeManager.get_theme()["primary"]
    scaling = root._get_window_scaling()
    app.close()

    renderer = tt.FrameRenderer(before, after, accent, scaling=scaling)
    frames = []
    count = int(tt.DURATION_SEC * FPS)
    hold = FPS // 2
    height = round(before.height * WIDTH / before.width)
    for i in range(count + 1):
        frame = renderer.render(i / count, quality=0.6)
        frames.append(frame.resize((WIDTH, height), Image.Resampling.LANCZOS))
    if os.environ.get('GIF_DEBUG'):
        frames[len(frames)//2].save(os.environ['GIF_DEBUG'])
    frames = [frames[0]] * hold + frames + [frames[-1]] * hold
    palette = frames[len(frames) // 2].quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    quantised = [f.quantize(palette=palette, dither=Image.Dither.FLOYDSTEINBERG) for f in frames]
    os.makedirs(os.path.dirname(out), exist_ok=True)
    quantised[0].save(out, save_all=True, append_images=quantised[1:], duration=int(1000 / FPS), loop=0,
                      optimize=False, disposal=1)
    print(f"wrote {out}: {len(frames)} frames, {os.path.getsize(out) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
