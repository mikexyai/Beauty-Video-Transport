#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-9222}"
START_URL="${2:-https://www.douyin.com/jingxuan}"
CHROME_EXE='C:\Program Files\Google\Chrome\Application\chrome.exe'
# Use native Windows paths for cmd.exe/start; POSIX paths can be mangled by MSYS argument conversion.
PROFILE_DIR='C:\Project\Chrome\chrome_profile'

if curl -fsS "http://127.0.0.1:${PORT}/json/version" >/dev/null 2>&1; then
  echo "Chrome CDP is already listening on 127.0.0.1:${PORT}"
  curl -fsS "http://127.0.0.1:${PORT}/json/version"
  exit 0
fi

cmd.exe /c if not exist "$PROFILE_DIR" mkdir "$PROFILE_DIR"

# Use cmd.exe start so Chrome survives after this shell exits.
# MSYS2_ARG_CONV_EXCL prevents Git Bash from rewriting --user-data-dir and URL args.
MSYS2_ARG_CONV_EXCL='*' cmd.exe /c start "" "$CHROME_EXE" \
  --remote-debugging-port="$PORT" \
  --remote-allow-origins=* \
  --user-data-dir="$PROFILE_DIR" \
  --restore-last-session \
  "$START_URL"

echo "Started Chrome CDP on 127.0.0.1:${PORT} using profile: $PROFILE_DIR"
