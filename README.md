---
title: SnapFetch — Video Downloader
emoji: ⬇️
colorFrom: blue
colorTo: green
sdk: docker
license: mit
app_port: 7860
pinned: false
---

# SnapFetch — free video downloader tool site

A small Flask website with a video-downloader tool (ssstik-style) at its core,
built to live on a custom domain and earn from Google AdSense.

## What's inside

| Path | What it is |
|---|---|
| `/` | The tool: paste a link → fetch formats → download video or MP3 |
| `/how-to-download-tiktok-videos` | Guide article (SEO content) |
| `/how-to-download-facebook-videos` | Guide article (SEO content) |
| `/about`, `/contact` | Trust pages (needed for AdSense review) |
| `/privacy-policy`, `/terms`, `/dmca` | Legal pages (needed for AdSense review) |
| `/robots.txt`, `/sitemap.xml`, `/ads.txt` | Served by the app; `ads.txt` is a placeholder until AdSense approval |
| `POST /api/info` | JSON: video title/thumbnail/duration + format list |
| `GET /download` | Streams the chosen file through the server via yt-dlp |

The download engine is the **yt-dlp** binary. Every download goes through the
server route (never a hotlink), so formats are fetched fresh from the source.

## Requirements

- Python 3.10+
- `pip install -r requirements.txt` (just Flask)
- A `yt-dlp` binary; set `YTDLP_BIN` to its path (default `~/workspace/bin/yt-dlp`).
  To install one: `curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp && chmod +x /usr/local/bin/yt-dlp`
- `ffmpeg` on PATH (only needed for the MP3 option)

## Run locally

```bash
./run.sh            # listens on $PORT or 8901
```

## Deploy (a) — small VPS with systemd

1. Copy this folder to the server, e.g. `/opt/snapfetch`.
2. Create a virtualenv and install requirements:
   ```bash
   cd /opt/snapfetch
   python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
   ```
   Install yt-dlp to `/usr/local/bin/yt-dlp` and ffmpeg via your package manager.
3. For production traffic use gunicorn behind nginx (the built-in Flask server
   is fine for testing only):
   ```bash
   .venv/bin/pip install gunicorn
   ```
   Example systemd unit `/etc/systemd/system/snapfetch.service`:
   ```ini
   [Unit]
   Description=SnapFetch
   After=network.target

   [Service]
   WorkingDirectory=/opt/snapfetch
   Environment=YTDLP_BIN=/usr/local/bin/yt-dlp
   Environment=PORT=8901
   ExecStart=/opt/snapfetch/.venv/bin/gunicorn -w 2 --timeout 300 -b 127.0.0.1:8901 app:app
   Restart=always
   User=www-data

   [Install]
   WantedBy=multi-user.target
   ```
   ```bash
   systemctl daemon-reload && systemctl enable --now snapfetch
   ```
4. Point nginx (or Caddy) at `127.0.0.1:8901` as a reverse proxy, add your
   domain + HTTPS (Let's Encrypt via certbot), and you're live.
5. Note: downloads are capped at 2 concurrent (a semaphore in `app.py`) to
   protect a small VPS. Raise it there if the server is beefier.

## Deploy (b) — Render

1. Push this folder to a Git repo and create a **Web Service** on Render.
2. Build command: `pip install -r requirements.txt`
3. Start command:
   ```bash
   curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /tmp/yt-dlp && chmod +x /tmp/yt-dlp && YTDLP_BIN=/tmp/yt-dlp gunicorn -w 2 --timeout 300 -b 0.0.0.0:$PORT app:app
   ```
   (Render provides `$PORT` automatically. yt-dlp must be re-downloaded on each
   deploy because the filesystem is ephemeral — the command above does that.)
   Alternatively add a `render.yaml` or use a Docker deploy with yt-dlp +
   ffmpeg baked into the image (recommended if MP3 conversion is important,
   since Render's native environment may not include ffmpeg).
4. Add your custom domain in Render's dashboard; HTTPS is automatic.

## Going live with AdSense

1. Deploy on the real domain first, with all pages reachable.
2. Apply for AdSense; after approval, replace the placeholder in the
   `/ads.txt` route (in `app.py`) with the publisher line Google gives you.
3. The privacy policy already discloses AdSense cookies — keep it that way.
4. Rename the site: the name "SnapFetch" appears in `templates/base.html`,
   `app.py` (`SITE_NAME`), and the page templates — a find-and-replace does it.

## Limits of v1 (known)

- Max 2 concurrent downloads; a download is capped at 240 s and the whole file
  is buffered in memory before streaming — fine for short clips (Reels,
  TikToks, Shorts), not ideal for very long/large videos. For a bigger launch,
  switch `/download` to chunked streaming to disk-backed responses.
- Private/login-only videos can't be fetched (by design).
- Some platforms rate-limit datacenter IPs; if a big platform starts failing,
  the usual fix is a residential-proxy yt-dlp config — out of scope for v1.
