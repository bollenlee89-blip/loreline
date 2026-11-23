#!/bin/sh
# loreline installer: uses pipx, uv or pip (user install), whichever is available.
set -e
SRC="git+https://github.com/bollenlee89-blip/loreline"
if command -v pipx >/dev/null 2>&1; then
  pipx install --force "$SRC"
elif command -v uv >/dev/null 2>&1; then
  uv tool install --force "$SRC"
elif command -v python3 >/dev/null 2>&1; then
  python3 -m pip install --user --upgrade "$SRC"
  echo "Installed with pip --user. Make sure ~/.local/bin is on your PATH."
else
  echo "loreline needs Python 3.9+ (and git). Install Python, then re-run this script." >&2
  exit 1
fi
echo
echo "✓ loreline installed. Try:  cd your-repo && loreline init"
