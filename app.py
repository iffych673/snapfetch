#!/usr/bin/env python3
"""
SnapFetch — free online video downloader (TikTok, Facebook, Instagram, YouTube, X).

A small Flask app. The download engine is the yt-dlp binary; this app only
exposes a friendly web UI + a thin JSON API around it.

Environment:
  YTDLP_BIN   path to yt-dlp binary (default: ~/workspace/bin/yt-dlp)
  PORT        set by run.sh / the host platform
"""
import io
import json
import os
import re
import subprocess
import tempfile
import threading
import time
import urllib.parse

from flask import (
    Flask, Response, abort, jsonify, render_template, request,
    send_file, send_from_directory, url_for,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
import shutil as _shutil
YTDLP_BIN = os.environ.get(
    "YTDLP_BIN",
    _shutil.which("yt-dlp") or os.path.expanduser("~/workspace/bin/yt-dlp"))

app = Flask(__name__, static_folder="static", template_folder="templates")

SITE_NAME = "SnapFetch"
CONTACT_EMAIL = "irfanzafar021@gmail.com"

# Only two downloads at a time — protects a small server from being swamped.
_download_slots = threading.BoundedSemaphore(2)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def valid_url(url):
    """Basic sanity check: http/https URL with a real host."""
    if not url or len(url) > 2048:
        return False
    try:
        p = urllib.parse.urlparse(url)
    except ValueError:
        return False
    return p.scheme in ("http", "https") and bool(p.hostname) and "." in p.hostname


def run_ytdlp(args, timeout):
    """Run yt-dlp, return (returncode, stdout, stderr)."""
    proc = subprocess.run(
        [YTDLP_BIN] + args,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout.decode("utf-8", "replace"), \
        proc.stderr.decode("utf-8", "replace")


def friendly_error(stderr):
    """Turn yt-dlp stderr into a short, human message."""
    s = (stderr or "").lower()
    if "private" in s:
        return "This video looks private. Only public videos can be downloaded."
    if "login" in s or "sign in" in s or "cookies" in s:
        return ("This link needs a login to view, so it can't be fetched. "
                "Try a public link instead.")
    if "unsupported url" in s:
        return "That link isn't supported. Paste a link from TikTok, Facebook, Instagram, YouTube or X."
    if "video unavailable" in s or "not available" in s or "removed" in s \
            or "404" in s or "deleted" in s:
        return "This video seems to be unavailable or has been removed."
    if "timed out" in s or "timeout" in s:
        return "The site took too long to answer. Please try again in a moment."
    return "Sorry, we couldn't fetch that link. Check the URL and try again."


def fmt_size(n):
    if not n:
        return None
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def format_label(f):
    ext = (f.get("ext") or "").upper()
    res = f.get("resolution") or ""
    h = f.get("height")
    if not res and h:
        res = f"{h}p"
    parts = [ext] if ext else []
    if res:
        parts.append(res)
    return " · ".join(parts) if parts else (ext or "File")


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

LANGS = {
    "id": "Bahasa Indonesia",
    "pt": "Português",
    "es": "Español",
    "vi": "Tiếng Việt",
    "tr": "Türkçe",
    "ar": "العربية",
}


@app.context_processor
def _lang_ctx():
    return {"LANG_LIST": list(LANGS), "LANG_NAMES": LANGS}


def _lang_or_404(lang):
    if lang not in LANGS:
        abort(404)
    return lang


@app.route("/")
def home():
    return render_template("home.html", page_key="home")


@app.route("/<lang>/")
def home_lang(lang):
    _lang_or_404(lang)
    return render_template(f"i18n/{lang}/home.html",
                           page_key="home", lang=lang)


@app.route("/how-to-download-tiktok-videos")
def guide_tiktok():
    return render_template("guide_tiktok.html", page_key="guide")


@app.route("/<lang>/how-to-download-tiktok-videos")
def guide_tiktok_lang(lang):
    _lang_or_404(lang)
    return render_template(f"i18n/{lang}/guide_tiktok.html",
                           page_key="guide", lang=lang)


@app.route("/how-to-download-facebook-videos")
def guide_facebook():
    return render_template("guide_facebook.html")


@app.route("/about")
def about():
    return render_template("about.html", email=CONTACT_EMAIL)


@app.route("/privacy-policy")
def privacy():
    return render_template("privacy.html", email=CONTACT_EMAIL)


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/dmca")
def dmca():
    return render_template("dmca.html", email=CONTACT_EMAIL)


@app.route("/contact")
def contact():
    return render_template("contact.html", email=CONTACT_EMAIL)


@app.route("/gemini-watermark-remover")
def gemini_remover():
    return render_template("gemini_remover.html", page_key="gemini")


@app.route("/<lang>/gemini-watermark-remover")
def gemini_remover_lang(lang):
    _lang_or_404(lang)
    return render_template(f"i18n/{lang}/gemini_remover.html",
                           page_key="gemini", lang=lang)


@app.route("/soundcloud-downloader")
def soundcloud():
    return render_template("soundcloud.html")


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(os.path.join(BASE_DIR, "static"),
                               "favicon.svg", mimetype="image/svg+xml")


@app.route("/robots.txt")
def robots():
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "Disallow: /download\n"
        f"Sitemap: {request.url_root}sitemap.xml\n"
    )
    return Response(body, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap():
    pages = ["/", "/how-to-download-tiktok-videos",
             "/how-to-download-facebook-videos", "/gemini-watermark-remover",
             "/soundcloud-downloader",
             "/about", "/privacy-policy", "/terms", "/dmca", "/contact"]
    for lg in LANGS:
        pages += [f"/{lg}/", f"/{lg}/how-to-download-tiktok-videos",
                  f"/{lg}/gemini-watermark-remover"]
    urls = "".join(
        f"<url><loc>{request.url_root.rstrip('/')}{p}</loc></url>"
        for p in pages)
    body = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            f"{urls}</urlset>")
    return Response(body, mimetype="application/xml")


@app.route("/ads.txt")
def ads_txt():
    # Placeholder until the site is approved by Google AdSense.
    # After approval, replace with the line Google provides, e.g.:
    # google.com, pub-XXXXXXXXXXXXXXXX, DIRECT, f08c47fec0942fa0
    return Response("# ads.txt — AdSense publisher line will be added after approval.\n",
                    mimetype="text/plain")


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def _clean_gemini_image(raw):
    """Clean the visible Gemini sparkle logo from a photo's bottom-right
    corner. The corner is rebuilt by mirroring the areas directly above and
    beside it, then feather-blended so the repair is not obvious.
    Only the visible mark is touched — invisible provenance signals such as
    SynthID are part of the file and are not removed.
    Returns (bytes, extension, mimetype)."""
    from PIL import Image, ImageDraw, ImageFilter, ImageOps

    img = Image.open(io.BytesIO(raw))
    img = ImageOps.exif_transpose(img)
    fmt = (img.format or "JPEG").upper()
    img = img.convert("RGB")
    w, h = img.size
    max_edge = 2400
    if max(w, h) > max_edge:
        s = max_edge / max(w, h)
        img = img.resize((round(w * s), round(h * s)), Image.LANCZOS)
        w, h = img.size
    side = max(24, int(min(w, h) * 0.15))
    inset = max(2, int(min(w, h) * 0.008))
    x1, y1 = w - inset, h - inset
    x0, y0 = x1 - side, y1 - side
    above = img.crop((x0, max(0, y0 - side), x1, y0)).transpose(
        Image.FLIP_TOP_BOTTOM)
    left = img.crop((max(0, x0 - side), y0, x0, y1)).transpose(
        Image.FLIP_LEFT_RIGHT)
    if above.size != (side, side):
        above = above.resize((side, side))
    if left.size != (side, side):
        left = left.resize((side, side))
    fill = Image.blend(above, left, 0.5).filter(
        ImageFilter.GaussianBlur(1.2))
    # Feathered mask: soft on the two inner edges, full strength at the
    # image corner itself so no ghost of the logo survives there.
    f = max(4, int(side * 0.18))
    mask = Image.new("L", (side, side), 0)
    ImageDraw.Draw(mask).rectangle([f, f, side, side], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(f / 2))
    region = Image.composite(fill, img.crop((x0, y0, x1, y1)), mask)
    img.paste(region, (x0, y0))
    out = io.BytesIO()
    if fmt == "PNG":
        img.save(out, "PNG")
        return out.getvalue(), "png", "image/png"
    img.save(out, "JPEG", quality=92)
    return out.getvalue(), "jpg", "image/jpeg"


@app.route("/api/remove-watermark", methods=["POST"])
def api_remove_watermark():
    f = request.files.get("image")
    if f is None or not f.filename:
        return jsonify(error="Please choose an image first."), 400
    raw = f.read(16 * 1024 * 1024 + 1)
    if len(raw) > 16 * 1024 * 1024:
        return jsonify(error="That image is too large (16 MB max)."), 413
    try:
        data, ext, mime = _clean_gemini_image(raw)
    except Exception:
        return jsonify(error="That file could not be read as an image. "
                             "Please try a JPG, PNG or WebP photo."), 400
    return send_file(io.BytesIO(data), mimetype=mime, as_attachment=True,
                     download_name=f"snapfetch-clean.{ext}")


@app.route("/api/info", methods=["POST"])
def api_info():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not valid_url(url):
        return jsonify(error="Please paste a valid http/https video link."), 400
    try:
        rc, out, err = run_ytdlp(
            ["-J", "--no-playlist", "--socket-timeout", "30",
             "--no-warnings", url],
            timeout=90)
    except subprocess.TimeoutExpired:
        return jsonify(error="The site took too long to answer. Please try again."), 504
    except FileNotFoundError:
        return jsonify(error="Download engine is not available on this server."), 500
    if rc != 0:
        return jsonify(error=friendly_error(err)), 422
    try:
        info = json.loads(out)
    except json.JSONDecodeError:
        return jsonify(error="Couldn't read the video details. Please try again."), 502

    formats = []
    seen = set()
    for f in info.get("formats") or []:
        fid = f.get("format_id")
        if not fid or fid in seen:
            continue
        vcodec = f.get("vcodec") or "none"
        acodec = f.get("acodec") or "none"
        if vcodec == "none" and acodec == "none":
            continue  # storyboards / images
        proto = (f.get("protocol") or "")
        if "mhtml" in proto:
            continue
        seen.add(fid)
        size = f.get("filesize") or f.get("filesize_approx")
        kind = "video" if vcodec != "none" else "audio"
        # No per-format note: split video/audio streams are merged with
        # sound by the /download route, so buttons stay clean and honest.
        note = ""
        formats.append({
            "format_id": fid,
            "label": format_label(f),
            "ext": f.get("ext"),
            "kind": kind,
            "height": f.get("height") or 0,
            "tbr": f.get("tbr") or 0,
            "filesize": size,
            "filesize_label": fmt_size(size),
            "note": note,
        })

    # Dedupe video formats: best bitrate per resolution (e.g. Facebook
    # exposes several near-identical 720p streams).
    best_by_height = {}
    other = []
    for x in formats:
        if x["kind"] == "video" and x["height"]:
            cur = best_by_height.get(x["height"])
            if cur is None or (x["tbr"], x["filesize"] or 0) > \
                    (cur["tbr"], cur["filesize"] or 0):
                best_by_height[x["height"]] = x
        else:
            other.append(x)
    formats = list(best_by_height.values()) + other

    def sort_key(x):
        # Video with sound first, then by height desc; then audio by size.
        return (0 if x["kind"] == "video" else 1,
                0 if not x["note"] else 1,
                -(x["height"] or 0),
                -(x["filesize"] or 0))

    formats.sort(key=sort_key)
    # Keep the list tidy: best few per kind.
    videos = [x for x in formats if x["kind"] == "video"][:8]
    audios = [x for x in formats if x["kind"] == "audio"][:4]
    formats = videos + audios
    formats.append({
        "format_id": "mp3",
        "label": "MP3 · Audio only",
        "ext": "mp3",
        "kind": "audio",
        "height": 0,
        "filesize": None,
        "filesize_label": None,
        "note": "Converted to MP3 on download",
    })

    return jsonify(
        platform=info.get("extractor_key") or info.get("extractor") or "",
        title=info.get("title") or "Untitled video",
        thumbnail=info.get("thumbnail"),
        duration=info.get("duration"),
        webpage_url=info.get("webpage_url") or url,
        formats=formats,
    )


@app.route("/download")
def download():
    url = (request.args.get("url") or "").strip()
    format_id = (request.args.get("format_id") or "best").strip()
    if not valid_url(url):
        abort(400, "Invalid URL.")
    if not re.fullmatch(r"[A-Za-z0-9._+\-/ ]+", format_id):
        abort(400, "Invalid format.")

    if not _download_slots.acquire(blocking=False):
        return Response("The server is busy with other downloads. "
                        "Please try again in a minute.",
                        status=429, mimetype="text/plain")

    tmpdir = tempfile.mkdtemp(prefix="snapfetch-")
    try:
        if format_id == "mp3":
            fmt_args = ["-f", "bestaudio/best", "-x",
                        "--audio-format", "mp3", "--audio-quality", "0"]
        elif format_id == "best":
            fmt_args = ["-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"]
        else:
            # Merge the chosen stream with the best audio when the source
            # splits them (Facebook/YouTube DASH); fall back gracefully.
            fmt_args = ["-f", f"{format_id}+bestaudio/{format_id}/best",
                        "--merge-output-format", "mp4"]
        out_tmpl = os.path.join(tmpdir, "video.%(ext)s")
        try:
            rc, _out, err = run_ytdlp(
                fmt_args + ["--no-playlist", "--socket-timeout", "30",
                            "--no-warnings", "-o", out_tmpl, url],
                timeout=240)
        except subprocess.TimeoutExpired:
            return Response("This download took too long and was stopped. "
                            "Try a smaller quality option.",
                            status=504, mimetype="text/plain")
        if rc != 0:
            return Response(friendly_error(err), status=422,
                            mimetype="text/plain")
        files = [os.path.join(tmpdir, x) for x in os.listdir(tmpdir)]
        if not files:
            return Response("Download failed. Please try again.",
                            status=502, mimetype="text/plain")
        path = max(files, key=os.path.getsize)

        # Build a safe, friendly filename.
        safe = re.sub(r"[^A-Za-z0-9._ -]+", "", os.path.basename(path)).strip()
        if not safe:
            safe = "video.mp4"
        download_name = f"snapfetch-{safe}"

        # Read into memory, then clean up before responding (files are videos,
        # but v1 targets short clips; cap handled by yt-dlp timeout above).
        with open(path, "rb") as fh:
            payload = fh.read()
        resp = Response(payload, mimetype="application/octet-stream")
        resp.headers["Content-Disposition"] = \
            f'attachment; filename="{download_name}"'
        resp.headers["Content-Length"] = str(len(payload))
        return resp
    finally:
        _download_slots.release()
        # Best-effort cleanup of the temp dir.
        try:
            for name in os.listdir(tmpdir):
                os.remove(os.path.join(tmpdir, name))
            os.rmdir(tmpdir)
        except OSError:
            pass


@app.errorhandler(404)
def not_found(_e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8901"))
    app.run(host="0.0.0.0", port=port)
