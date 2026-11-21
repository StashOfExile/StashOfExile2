#!/usr/bin/env bash
# The Linux build (preview) - see linux/README.md. Makes dist/StashOfExile2-<version>-linux.tar.gz + dist/SHA256SUMS.
#
#   ./build_linux.sh              build, smoke-run the binary (Xvfb if there's no display), package
#   SMOKE=0 ./build_linux.sh      no smoke run
#   PYTHON=python3.12 ./build_linux.sh
#
# Tested setup: Arch + Hyprland (a player builds every release with this script). Run time (not bundled):
#   sudo pacman -S tesseract tesseract-data-eng grim socat xdotool
# Needs: python3 (3.11+) with Tk built with Xft (Debian / Ubuntu: python3-tk), pip install -r linux/requirements-linux.txt,
# for the smoke run xvfb-run (Debian / Ubuntu: xvfb) or a desktop session. The data files are the same as the Windows
# build's --add-data list (build_uioverhaul.bat / release.yml) plus crafthelper.json.
set -euo pipefail
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
VER=$("$PY" -c "import re; print(re.search(r'^APP_VERSION = \"([^\"]+)\"', open('stashofexile2.py').read(), re.M).group(1))")
echo "StashOfExile2 $VER - Linux build with $("$PY" --version)"

"$PY" - <<'EOF'
import sys, tkinter, _tkinter
if tkinter.TkVersion < 8.6:
    sys.exit(f"Tk {tkinter.TkVersion} is too old (8.6 is needed)")
print("Tk", tkinter.TkVersion, "-", _tkinter.__file__)
EOF

for t in tesseract grim socat xdotool; do command -v "$t" >/dev/null || echo "note: $t not found - needed at run time on Hyprland (linux/README.md)"; done

"$PY" -m PyInstaller --noconfirm --clean --onefile --name StashOfExile2 --collect-submodules soe2 \
  --add-data "modlists.json:." --add-data "gamedata.json:." --add-data "regexdata.json:." \
  --add-data "default_rules.json:." --add-data "searchdata.json:." --add-data "anointdata.json:." \
  --add-data "cxnames.json:." --add-data "gamedb.json:." --add-data "gamedb_hide.json:." --add-data "atlasmasters.json:." --add-data "moneymakers.json:." --add-data "mapdata.json:." --add-data "campaign.json:." \
  --add-data "crafthelper.json:." --add-data "tierdata.json:." --add-data "themes:themes" \
  --add-data "stashofexile2.ico:." \
  --add-data "soe2/sekhemas.json:soe2" --add-data "soe2/fonts:soe2/fonts" --add-data "linux/fonts.conf:linux" \
  --hidden-import PIL._tkinter_finder --hidden-import cv2 --hidden-import mss --hidden-import numpy \
  --collect-submodules Xlib --hidden-import pystray._xorg --hidden-import pystray._base \
  --exclude-module pystray._win32 --exclude-module pystray._darwin --exclude-module pystray._appindicator \
  --exclude-module pystray._gtk --exclude-module gi --exclude-module winrt \
  stashofexile2.py

BIN=dist/StashOfExile2
ls -l "$BIN"

if [ "${SMOKE:-1}" = "1" ]; then
  echo "Smoke run: $BIN --selftest (a throwaway home folder)"
  SMOKE_HOME=$(mktemp -d)
  run() { HOME="$SMOKE_HOME" XDG_RUNTIME_DIR="$SMOKE_HOME" timeout 120 "$@"; }
  if [ -n "${DISPLAY:-}" ]; then
    OUT=$(run "$BIN" --selftest 2>&1) || { echo "$OUT"; echo "Smoke run failed"; exit 1; }
  elif command -v xvfb-run >/dev/null; then
    OUT=$(run xvfb-run -a -s "-screen 0 1920x1080x24" "$BIN" --selftest 2>&1) || { echo "$OUT"; echo "Smoke run failed"; exit 1; }
  else
    echo "No display and no xvfb-run - install xvfb or run with SMOKE=0"; exit 1
  fi
  echo "$OUT" | grep -E "^selftest:" || { echo "$OUT"; echo "Smoke run: no window"; exit 1; }
  echo "$OUT" | grep -q "mapped=True" || { echo "Smoke run: the window didn't show"; exit 1; }
  run "$BIN" --check-linux || true
  rm -rf "$SMOKE_HOME"
fi

PKG="StashOfExile2-$VER-linux"
rm -rf "dist/$PKG" "dist/$PKG.tar.gz" dist/SHA256SUMS
mkdir -p "dist/$PKG"
cp "$BIN" "dist/$PKG/StashOfExile2"
cp linux/README.md "dist/$PKG/README.md"
cp linux/hyprland.conf linux/hyprland.lua linux/fonts.conf "dist/$PKG/"
cp LICENSE THIRD_PARTY_NOTICES.txt TOS.md "dist/$PKG/"
chmod +x "dist/$PKG/StashOfExile2"
tar -C dist -czf "dist/$PKG.tar.gz" "$PKG"
(cd dist && sha256sum "$PKG.tar.gz" > SHA256SUMS)
echo "Built dist/$PKG.tar.gz ($(du -h "dist/$PKG.tar.gz" | cut -f1))"
cat dist/SHA256SUMS
