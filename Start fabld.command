#!/bin/bash
# Double-click this file to start fabld. A browser window opens automatically.
# retro??
cd "$(dirname "$0")"
echo ""
echo "  Starting fabld ..."
echo ""
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "  fabld needs one free helper program (ffmpeg) that isn't installed yet."
  echo "  Copy-paste this line into this window and press Enter:"
  echo ""
  echo "      brew install ffmpeg"
  echo ""
  read -r -p "  (press Enter to close) "
  exit 1
fi
exec python3 server.py
