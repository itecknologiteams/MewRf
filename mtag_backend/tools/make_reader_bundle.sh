#!/usr/bin/env bash
# Build the self-contained tag-reader bundle for a registration desk.
#
#     ./tools/make_reader_bundle.sh
#     → mtag-tag-reader.tar.gz  (~90 KB)
#
# Copy that one file to the registration PC and run its install.sh.
#
# Why a bundle rather than the repo: the agent needs only itself and the
# vendored com.rfid SDK. It imports no Django and touches no database. Putting
# the whole backend on a registration desk would also put master's .env — the
# database password every booth uses — on a machine that has no use for it.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$(dirname "$HERE")"
OUT="$BACKEND/mtag-tag-reader.tar.gz"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

PKG="$STAGE/mtag-tag-reader"
mkdir -p "$PKG/tools" "$PKG/vendor"

# Layout mirrors the repo so the agent's SDK lookup works unchanged.
cp "$HERE/tag_reader_agent.py" "$PKG/tools/"
cp -r "$BACKEND/vendor/rfid_sdk" "$PKG/vendor/"
cp "$BACKEND/deploy/99-hopeland-uhf-reader.rules" "$PKG/"

# Strip caches so the bundle is reproducible and small.
find "$PKG" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
find "$PKG" -name '*.pyc' -delete 2>/dev/null || true

cat > "$PKG/requirements.txt" <<'REQ'
pyserial==3.5
# The SDK imports `usb` at module level (com/rfid/RFIDReader.py, UsbConnect.py),
# so without pyusb it fails to load at all — even on the HID path, which never
# calls into it. Pure Python: importing it needs no libusb.
pyusb==1.3.1
# cython-hidapi. NOT the `hid` package: it has a different API and its `hid/`
# directory shadows this one's module, which makes every reader fail with
# "module 'hid' has no attribute 'device'".
hidapi==0.15.0
REQ

cat > "$PKG/install.sh" <<'INSTALL'
#!/usr/bin/env bash
# Set up the tag reader on this registration PC. Safe to re-run.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== 1/3  Python dependencies ==="
PY="${PYTHON:-python3}"
if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)'; then
  echo "!!! Python 3.8+ required. Set PYTHON=/path/to/python3 and re-run." >&2
  exit 1
fi
# The `hid` package shadows hidapi's module; remove it if a previous install
# pulled it in, or the reader will never open.
"$PY" -m pip uninstall -y hid >/dev/null 2>&1 || true
"$PY" -m pip install --quiet --upgrade -r "$HERE/requirements.txt"
"$PY" - <<'CHK'
import hid, serial, usb
assert hasattr(hid, 'device'), "wrong hid package: pip uninstall hid && pip install hidapi"
print("    pyserial + hidapi + pyusb OK")
CHK

echo "=== 2/3  udev rule (needs sudo) ==="
if [ -f /etc/udev/rules.d/99-hopeland-uhf-reader.rules ]; then
  echo "    already installed"
else
  sudo cp "$HERE/99-hopeland-uhf-reader.rules" /etc/udev/rules.d/
  sudo udevadm control --reload-rules && sudo udevadm trigger
  echo "    installed — UNPLUG AND REPLUG the reader now"
fi

echo "=== 3/3  Reader check ==="
if lsusb -d 2121:8633 >/dev/null 2>&1; then
  echo "    HopeLand UHF Reader detected"
else
  echo "    !!! reader not detected on USB — plug it in, then re-run this script"
fi

echo ""
echo "Done. Start it with:"
echo "    python3 $HERE/tools/tag_reader_agent.py --serve"
INSTALL
chmod +x "$PKG/install.sh"

cat > "$PKG/install.bat" <<'BAT'
@echo off
REM Set up the tag reader on this Windows registration PC. Safe to re-run.
setlocal

echo === 1/3  Python ===
where python >nul 2>&1
if errorlevel 1 (
  echo !!! Python is not on PATH. Install Python 3 from python.org and tick
  echo     "Add python.exe to PATH", then run this again.
  pause
  exit /b 1
)
python -c "import sys; sys.exit(0 if sys.version_info>=(3,8) else 1)"
if errorlevel 1 (
  echo !!! Python 3.8 or newer is required.
  pause
  exit /b 1
)
python --version

echo.
echo === 2/3  Dependencies ===
REM The `hid` package shadows hidapi's module and makes every reader fail with
REM "module 'hid' has no attribute 'device'". Remove it before installing.
python -m pip uninstall -y hid >nul 2>&1
python -m pip install --quiet --upgrade -r "%~dp0requirements.txt"
if errorlevel 1 (
  echo !!! pip install failed. Check this PC's internet access.
  pause
  exit /b 1
)
python -c "import hid,serial,usb; assert hasattr(hid,'device'); print('    pyserial + hidapi + pyusb OK')"
if errorlevel 1 (
  echo !!! Wrong hid package installed. Run:
  echo       python -m pip uninstall -y hid
  echo       python -m pip install hidapi
  pause
  exit /b 1
)

echo.
echo === 3/3  Reader ===
REM No udev and no group membership on Windows: HID and COM are open to the
REM logged-in user, so there is nothing to configure. Just confirm it is seen.
python "%~dp0tools\tag_reader_agent.py" --list

echo.
echo Done. Start it with:
echo     python "%~dp0tools\tag_reader_agent.py" --serve
echo.
pause
BAT

cat > "$PKG/start-reader.bat" <<'BAT'
@echo off
REM Double-click this to start the reader agent. Leave the window open.
title M-Tag reader agent
python "%~dp0tools\tag_reader_agent.py" --serve
echo.
echo The agent stopped. Press any key to close.
pause >nul
BAT

cat > "$PKG/README.txt" <<'DOC'
M-Tag registration desk — USB tag reader
========================================

What this is
    A small agent that reads the HopeLand USB desk reader and publishes each
    tag on http://127.0.0.1:8765/tag. The registration page in your browser
    picks it up and looks the tag up against master.

    It holds no passwords and never talks to master itself. The lookup is made
    by your browser, as you, from the session you are already logged into.

Install (once per PC)
    Windows :  double-click  install.bat
    Linux   :  ./install.sh

Run (whenever the desk is in use)
    Windows :  double-click  start-reader.bat
    Linux   :  python3 tools/tag_reader_agent.py --serve

    Leave the window open. Each read prints a line.

Use
    Open the portal, go to M-Tag Registration, step 2.
    The "Scan the tag" field shows a green "Reader connected" dot.
    Place a tag on the reader — the serial fills in automatically.

    If the dot is grey the agent is not running; typing or pasting a
    tag's TID by hand still works exactly the same.

Troubleshooting
    python3 tools/tag_reader_agent.py --list    what is plugged in

    "open failed"
        Windows: another program is holding the reader - close any HopeLand
                 demo tool, then unplug and replug it.
        Linux:   udev rule not applied. Run ./install.sh and replug.
    "module 'hid' has no attribute 'device'"
        Wrong package:  pip uninstall hid && pip install hidapi
    "Reader not detected" in the page
        The agent must run on the SAME PC as the browser.
DOC

# The .bat files and README are written by heredocs, so they come out with Unix
# line endings. cmd.exe misparses LF-only batch files — parenthesised
# `if errorlevel 1 ( ... )` blocks, which install.bat relies on, can run the
# wrong lines or none — and older Notepad shows the README as one long line.
# Convert the Windows-facing files to CRLF; install.sh must stay LF for bash.
for f in "$PKG"/*.bat "$PKG/README.txt"; do
  sed -i 's/\r$//; s/$/\r/' "$f"
done

tar -czf "$OUT" -C "$STAGE" mtag-tag-reader
echo "Built $OUT  ($(du -h "$OUT" | cut -f1))"

# Windows Explorer opens a zip with a double-click; a .tar.gz needs the command
# line even on Windows 11. Ship both so the desk PC is never the blocker.
ZIP="${OUT%.tar.gz}.zip"
if command -v zip >/dev/null 2>&1; then
  (cd "$STAGE" && zip -qr "$ZIP" mtag-tag-reader)
  echo "Built $ZIP  ($(du -h "$ZIP" | cut -f1))"
else
  "${PYTHON:-python3}" - "$STAGE" "$ZIP" <<'ZIPPY'
import os, shutil, sys
stage, out = sys.argv[1], sys.argv[2]
shutil.make_archive(out[:-4], 'zip', stage, 'mtag-tag-reader')
print(f"Built {out}  ({os.path.getsize(out) // 1024} KB)")
ZIPPY
fi

LISTING="$(tar -tzf "$OUT")"
echo "$LISTING" | sed -n '1,5p'
echo "  ... $(echo "$LISTING" | wc -l) files total"
