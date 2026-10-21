#!/usr/bin/env bash
# Start the SnapFetch server.
#   PORT       port to listen on (default 8901; hosts like Render set this)
#   YTDLP_BIN  path to the yt-dlp binary (default ~/workspace/bin/yt-dlp)
set -e
cd "$(dirname "$0")"
export PORT="${PORT:-8901}"
exec python3 app.py
