# Rules for AI agents working on this repo

These are standing rules from the owner. Read them before running anything.

## Processes
- **Never stop processes by name or in bulk.** No `taskkill /IM python.exe`, no `Stop-Process -Name ...`,
  no `pkill`, no "kill everything that matches". The PC also runs the owner's own programs (their copy of
  Mosaiq, editors, language servers) and a name match can end them.
- Only stop a process **you started yourself**, by its PID (keep the PID or the `Popen` handle when starting it).
- A process you did not start (for example the owner's open `MosaiqQRStudio.exe`) is never touched. If it is in
  the way (`build.ps1` and the exe tests refuse to run while one runs from `dist\`), ask the owner to close it.
- A test that must clean up uses its own handle (`proc.kill()`) or a path-scoped check (see
  `packaging/msix/install_test.ps1`: only the installed test package's own process).

## Screenshots and privacy
- Capture only the app's own window (PrintWindow of its handle), never the screen. If anything else was
  captured, delete it without looking at it. No screenshots of screens that can show an email or account.
- Never replace or remove a Store-installed copy of the app without asking the owner first.

## Commits
- No AI attribution (no `Co-Authored-By`, no "generated with" lines) in commits or pull requests.

## Product rules
- Version stays as set in `packaging/msix/identity.json` / `config.py` unless the owner says otherwise; the app logo is never changed.
- `QRSTUDIO_NO_SPLASH=1`, the lazy `cv2` import and the Windows N fallback must keep working.
- No silent exception swallowing: a caught error is logged to `mosaiq.log` or shown.
- A test only counts when it really ran and passed.
