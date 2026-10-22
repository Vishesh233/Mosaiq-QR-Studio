"""Run every _*_test.py in turn and print one result line per test.

Run:  .venv\\Scripts\\python.exe _run_all_tests.py [--exe] [--skip-desktop]

--exe           also run _frozen_exe_test.py (needs a build first)
--skip-desktop  skip the tests that use the real webcam, grab the screen or move the mouse
                (_camera_test, _region_test, _dnd_test)

_dnd_test drives the real mouse and is focus/timing sensitive (it also fails now and then on
the unchanged code): a failing run is retried up to twice and every failed attempt is printed.
Exit code 0 = every test passed.
"""
import glob
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DESKTOP = {"_camera_test.py", "_region_test.py", "_dnd_test.py"}
RETRY = {"_dnd_test.py"}
SLOW_TIMEOUT = 600


def run(script):
    env = dict(os.environ, PYTHONUTF8="1", QRSTUDIO_NO_SPLASH="1")
    started = time.time()
    try:
        proc = subprocess.run([sys.executable, script], cwd=HERE, env=env, text=True,
                              encoding="utf-8", errors="replace", capture_output=True,
                              timeout=SLOW_TIMEOUT)
        code, output = proc.returncode, proc.stdout + proc.stderr
    except subprocess.TimeoutExpired as e:
        code, output = -1, f"TIMEOUT after {SLOW_TIMEOUT}s\n{e.stdout or ''}"
    lines = [ln for ln in output.splitlines() if ln.strip()]
    ok_line = next((ln for ln in reversed(lines) if "_OK" in ln or "PASSED" in ln), "")
    return code, ok_line, lines[-3:], time.time() - started


def main():
    args = set(sys.argv[1:])
    scripts = sorted(os.path.basename(p) for p in glob.glob(os.path.join(HERE, "_*_test.py")))
    if "--exe" not in args:
        scripts = [s for s in scripts if s != "_frozen_exe_test.py"]
    if "--skip-desktop" in args:
        scripts = [s for s in scripts if s not in DESKTOP]

    failed = []
    for script in scripts:
        code, ok_line, tail, seconds = run(script)
        attempts = 1
        while code != 0 and script in RETRY and attempts < 3:
            print(f"  {script}: attempt {attempts} failed (exit {code}), retrying")
            code, ok_line, tail, seconds = run(script)
            attempts += 1
        if code == 0:
            print(f"PASS {script:28s} {seconds:5.0f}s  {ok_line}")
        else:
            failed.append(script)
            print(f"FAIL {script:28s} {seconds:5.0f}s  exit {code}")
            for ln in tail:
                print("       " + ln)
    print(f"\n{len(scripts) - len(failed)}/{len(scripts)} test scripts passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
