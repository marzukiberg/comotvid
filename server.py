#!/usr/bin/env python3
"""
ComotVid local server - static files + native IG GraphQL & yt-dlp resolver.
Rendered with Jinja2 template engine.
"""
import importlib
import json
import re
import subprocess
import sys
import urllib.parse as up
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

try:
    import jinja2
except ImportError:
    jinja2 = None

LEGACY_QUERY_HASH = "de8017ee0a7c9c45ec4260733d81ea31"
DOC_ID_POST = "24368985919464652"
DOC_ID_STORIES = "26659189347081290"

WEB_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
ANDROID_UA = (
    "Mozilla/5.0 (Linux; Android 9; GM1903 Build/PKQ1.190110.001; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/75.0.3770.143 "
    "Mobile Safari/537.36 Instagram 103.1.0.15.119 Android (28/9; 420dpi; "
    "1080x2260; OnePlus; GM1903; OnePlus7; qcom; sv_SE; 164094539)"
)

RE_HIGHLIGHT = re.compile(r"instagram\.com/(?:stories/highlights|s)/(\d+)")
RE_STORY = re.compile(r"instagram\.com/stories/([^/?#]+)")
RE_POST = re.compile(r"instagram\.com/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)")
RE_PROFILE = re.compile(r"instagram\.com/([A-Za-z0-9._]+)/?$")

BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"

if jinja2:
    jinja_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=jinja2.select_autoescape(["html", "xml"]),
    )
else:
    jinja_env = None


def render_template(template_name: str, context: dict[str, Any] | None = None) -> str:
    """Render template menggunakan Jinja2 dengan fallback file statis."""
    ctx = context or {}
    if jinja_env:
        tmpl = jinja_env.get_template(template_name)
        return tmpl.render(**ctx)
    fallback_path = BASE_DIR / template_name
    if fallback_path.exists():
        return fallback_path.read_text(encoding="utf-8")
    return f"Template {template_name} tidak ditemukan."


def http_get(url, headers=None, timeout=15):
    if not (isinstance(url, str) and url.startswith(("https://", "http://"))):
        raise ValueError("Scheme URL tidak valid")
    req_headers = {
        "User-Agent": WEB_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Fetch-Mode": "navigate",
    }
    if headers:
        req_headers.update(headers)

    req = urllib.request.Request(url, headers=req_headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
        return r.status, r.read().decode("utf-8", "replace")


def resolve_user_id_native(username):
    """Resolve username ke Instagram Numeric User ID secara native tanpa pihak ketiga."""
    # 1. Scraping direct HTML profil Instagram
    try:
        url = f"https://www.instagram.com/{username}/"
        status, body = http_get(url, timeout=10)
        if status == 200:
            match_id = re.search(r'"user_id":"(\d+)"', body) or re.search(r'"profile_id":"(\d+)"', body)
            if match_id:
                return match_id.group(1)
            match_owner = re.search(r'"owner":\{"id":"(\d+)"', body)
            if match_owner:
                return match_owner.group(1)
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"HTML profile scrape notice for @{username}: {e}\n")

    # 2. Endpoint resmi web_profile_info
    for host in ("i.instagram.com", "https://www.instagram.com"):
        url = (
            f"{host}/api/v1/users/web_profile_info/?username={username}"
            if host.startswith("http")
            else f"https://{host}/api/v1/users/web_profile_info/?username={username}"
        )
        try:
            status, body = http_get(
                url,
                headers={
                    "User-Agent": ANDROID_UA,
                    "x-ig-app-id": "936619743392459",
                    "Accept": "application/json, text/plain, */*",
                },
                timeout=10,
            )
            if status == 200:
                uid = ((json.loads(body).get("data") or {}).get("user") or {}).get("id")
                if uid:
                    return str(uid)
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"web_profile_info ({host}) notice for @{username}: {e}\n")

    raise RuntimeError(f"Gagal mengekstrak User ID untuk @{username}")


def extract_media_with_ytdlp(target_url):
    """Ekstraksi metadata media menggunakan library open-source yt-dlp."""
    try:
        yt_dlp = importlib.import_module("yt_dlp")
    except ImportError:
        return None

    ydl_opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "dump_single_json": True,
        "skip_download": True,
    }

    try:
        ydl_cls = yt_dlp.YoutubeDL
        with ydl_cls(ydl_opts) as ydl:
            raw_info = ydl.extract_info(target_url, download=False)
            if not isinstance(raw_info, dict):
                return None
            info: dict[str, Any] = raw_info

            items = []
            raw_entries = info.get("entries")
            entries = raw_entries if isinstance(raw_entries, list) else [info]
            for e in entries:
                if not isinstance(e, dict):
                    continue
                url = e.get("url")
                formats = e.get("formats")
                if not url and isinstance(formats, list) and len(formats) > 0:
                    last_fmt = formats[-1]
                    if isinstance(last_fmt, dict):
                        url = last_fmt.get("url")

                thumb = e.get("thumbnail")
                thumbnails = e.get("thumbnails")
                if not thumb and isinstance(thumbnails, list) and len(thumbnails) > 0:
                    last_thumb = thumbnails[-1]
                    if isinstance(last_thumb, dict):
                        thumb = last_thumb.get("url")

                desc = str(e.get("description") or "")
                title = str(e.get("title") or desc[:60])

                if url:
                    items.append({
                        "url": url,
                        "thumb": thumb,
                        "isVideo": bool(e.get("vcodec") and e.get("vcodec") != "none") or bool(e.get("ext") == "mp4"),
                        "title": title,
                    })
            return items if items else None
    except Exception as e:
        sys.stderr.write(f"yt-dlp extract notice: {e}\n")
        return None


def num(x):
    s = str(x)
    try:
        return int(s) if s.isdigit() else s
    except Exception:
        return s


def build_graphql_url(raw_url):
    """Ubah URL Instagram menjadi GraphQL format (format sama seperti savevid)."""
    clean_url = raw_url.split("?")[0].rstrip("/")

    # 1. Highlights
    m = RE_HIGHLIGHT.search(clean_url)
    if m:
        variables = {
            "reel_ids": [],
            "highlight_reel_ids": [num(m.group(1))],
            "precomposed_overlay": False,
        }
        vars_enc = up.quote(json.dumps(variables, separators=(",", ":")))
        return f"https://www.instagram.com/graphql/query/?query_hash={LEGACY_QUERY_HASH}&variables={vars_enc}"

    # 2. Stories
    m = RE_STORY.search(clean_url)
    if m:
        part = m.group(1)
        uid = part if part.isdigit() else resolve_user_id_native(part)
        variables = {
            "reel_ids": [num(uid)],
            "highlight_reel_ids": [],
            "precomposed_overlay": False,
        }
        vars_enc = up.quote(json.dumps(variables, separators=(",", ":")))
        return f"https://www.instagram.com/graphql/query/?query_hash={LEGACY_QUERY_HASH}&variables={vars_enc}"

    # 3. Post / Reel / TV
    m = RE_POST.search(clean_url)
    if m:
        variables = {
            "shortcode": m.group(1),
            "fetch_tagged_user_count": None,
            "hoisted_comment_id": None,
            "hoisted_reply_id": None,
        }
        vars_enc = up.quote(json.dumps(variables, separators=(",", ":")))
        return f"https://www.instagram.com/graphql/query/?doc_id={DOC_ID_POST}&variables={vars_enc}"

    # 4. Profile
    m = RE_PROFILE.search(clean_url)
    if m and m.group(1) not in ("explore", "reels", "stories", "direct", "accounts"):
        uid = resolve_user_id_native(m.group(1))
        variables = {
            "reel_ids": [num(uid)],
            "highlight_reel_ids": [],
            "precomposed_overlay": False,
        }
        vars_enc = up.quote(json.dumps(variables, separators=(",", ":")))
        return f"https://www.instagram.com/graphql/query/?query_hash={LEGACY_QUERY_HASH}&variables={vars_enc}"

    raise ValueError(f"URL tidak dikenali sebagai format Instagram yang valid: {raw_url}")


PLATFORMS = {
    "auto": {
        "title": "Universal Video & Media Downloader",
        "heading": "Universal Media Downloader",
        "desc": "Download video & foto dari Instagram, YouTube, TikTok, dan Pinterest secara instan",
        "icon": "ph-download-simple",
        "hint": "",
    },
    "instagram": {
        "title": "Instagram Video, Reels & Story Downloader",
        "heading": "Instagram Media & Story Downloader",
        "desc": "Download Reels, Story Publik, Video Post, Carousel, dan Foto Instagram secara instan",
        "icon": "ph-instagram-logo",
        "hint": "/reel/ · /p/ · /stories/ · username",
    },
    "youtube": {
        "title": "YouTube Video & Shorts Downloader",
        "heading": "YouTube Video & Shorts Downloader",
        "desc": "Download video YouTube, Shorts, dan ekstrak audio MP3 secara instan",
        "icon": "ph-youtube-logo",
        "hint": "youtube.com/watch · youtu.be · /shorts/",
    },
    "tiktok": {
        "title": "TikTok Video Downloader Tanpa Watermark",
        "heading": "TikTok Video Downloader",
        "desc": "Download video TikTok tanpa watermark + ekstrak audio secara instan",
        "icon": "ph-tiktok-logo",
        "hint": "tiktok.com/@user/video/ · vt.tiktok.com · vm.tiktok.com",
    },
    "pinterest": {
        "title": "Pinterest Video & Image Downloader",
        "heading": "Pinterest Video & Image Downloader",
        "desc": "Download video dan gambar Pinterest (Pin) kualitas penuh secara instan",
        "icon": "ph-pinterest-logo",
        "hint": "pin.it · pinterest.com/pin/",
    },
}


def detect_platform(url):
    """Deteksi platform dari URL. Return key PLATFORMS atau 'unknown'."""
    u = (url or "").lower()
    if "instagram.com" in u:
        return "instagram"
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    if "tiktok.com" in u:
        return "tiktok"
    if "pinterest." in u or "pin.it" in u:
        return "pinterest"
    return "unknown"


def extract_public_with_ytdlp(url):
    """Ekstrak media publik via yt-dlp — universal: IG, YouTube, TikTok, Pinterest."""
    try:
        platform = detect_platform(url)
        is_ig_story = platform == "instagram" and ("/stories/" in url or "/highlights/" in url)
        if is_ig_story:
            browsers_to_try = ["chrome", "firefox", "safari", "edge", ""]
        elif platform == "instagram":
            browsers_to_try = ["", "chrome", "firefox", "safari"]
        else:
            # YT / TikTok / Pinterest: direct dulu, cookie browser sbg fallback
            browsers_to_try = ["", "chrome", "firefox"]

        last_error = ""
        for b in browsers_to_try:
            cmd = ["yt-dlp", "-J", "--no-warnings", "--no-playlist"]
            if b:
                cmd.extend(["--cookies-from-browser", b])
            cmd.append(url)

            p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)  # noqa: S603
            if p.returncode == 0 and p.stdout.strip():
                try:
                    data = json.loads(p.stdout)
                    entries = data.get("entries") or [data]
                    items = []
                    for entry in entries:
                        if not entry:
                            continue
                        formats = entry.get("formats") or []
                        best_video = formats[-1].get("url") if formats else entry.get("url")
                        vcodec = entry.get("vcodec")
                        acodec = entry.get("acodec")
                        ext = (entry.get("ext") or "").lower()
                        is_video = vcodec != "none" or ext in ("mp4", "mov", "webm")
                        is_audio = vcodec == "none" and acodec not in (None, "none")
                        title = entry.get("title") or (entry.get("description", "") or "")[:80]
                        items.append({
                            "url": best_video or entry.get("url"),
                            "thumb": entry.get("thumbnail"),
                            "isVideo": is_video,
                            "isAudio": is_audio,
                            "platform": entry.get("extractor_key") or entry.get("extractor") or platform,
                            "title": title,
                            "duration": entry.get("duration"),
                        })
                    if items:
                        return {"status": "ok", "items": items,
                                "platform": platform,
                                "method": f"yt-dlp ({b or 'direct'})"}
                except Exception as ex:  # noqa: BLE001
                    last_error = str(ex)
            else:
                last_error = p.stderr.strip()[:300]

        return {"status": "fail", "platform": platform,
                "error": last_error or "Gagal mengekstrak media via yt-dlp"}
    except Exception as e:
        return {"status": "fail", "error": str(e)}


def extract_via_saveclip(url, timeout=45):
    """Fallback via SaveClip (v3.saveclip.app/api/ajaxSearch) memakai Patchright.

    Alur yang terbukti (recon 2026-10-09):
    buka https://saveclip.app/id8/instagram-story-download -> Turnstile
    auto-solve -> isi #s_input -> klik -> intercept ajaxSearch -> parse
    data HTML (dl.snapcdn.app + i.snapcdn.app) jadi items ComotVid.
    Return format sama seperti yt-dlp: {"status":"ok","items":[...],"method":...}
    """
    try:
        from patchright.sync_api import sync_playwright
    except Exception as e:
        return {"status": "fail", "error": f"patchright belum terinstall: {e}"}

    import time as _time
    items = []
    last_error = ""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            page = context.new_page()
            page.goto("https://saveclip.app/id8/instagram-story-download",
                       wait_until="networkidle", timeout=30000)
            # Tunggu Turnstile terisi (maks 15 dtk)
            for _ in range(15):
                try:
                    val = page.evaluate(
                        "() => document.querySelector('input[name=\"cf-turnstile-response\"]')?.value || ''")
                    if val:
                        break
                except Exception:
                    pass
                _time.sleep(1)
            try:
                page.fill("#s_input", url, timeout=10000)
            except Exception as e:
                last_error = f"fill gagal: {e}"
                browser.close()
                return {"status": "fail", "error": last_error}
            try:
                with page.expect_response(
                        lambda r: "ajaxSearch" in r.url, timeout=timeout * 1000) as resp_info:
                    try:
                        page.click("button.btn-red", timeout=8000)
                    except Exception:
                        page.evaluate("() => document.querySelector('form#search-form button')?.click()")
                resp = resp_info.value
                try:
                    data = resp.json()
                except Exception:
                    last_error = (resp.text() or "")[:300]
                    browser.close()
                    return {"status": "fail", "error": last_error or "respons bukan JSON"}
                if data.get("status") != "ok":
                    browser.close()
                    return {"status": "fail",
                            "error": str(data.get("mess") or data.get("message") or data)[:300]}
                html = data.get("data") or ""
                # Parse link download + thumb dari snippet HTML
                hrefs = re.findall(r'href="(https://dl\.snapcdn\.app/[^"]+)"', html)
                imgs = re.findall(r'<img[^>]+src="([^"]+)"', html)
                labels = re.findall(r'Unduh (Video|Foto|Photo)', html, re.IGNORECASE)
                for i, href in enumerate(hrefs):
                    thumb = imgs[i] if i < len(imgs) else (imgs[0] if imgs else None)
                    is_vid = True
                    if i < len(labels):
                        is_vid = labels[i].lower() == "video"
                    else:
                        is_vid = "/stories/" in url or ".mp4" in href or "video" in html.lower()
                    items.append({
                        "url": href,
                        "thumb": thumb,
                        "isVideo": is_vid,
                        "title": f"SaveClip item {i+1}",
                    })
                browser.close()
                if items:
                    return {"status": "ok", "items": items, "method": "saveclip-fallback"}
                return {"status": "fail", "error": "SaveClip merespons ok tapi tidak ada link dl.snapcdn.app"}
            except Exception as e:
                try:
                    browser.close()
                except Exception:
                    pass
                return {"status": "fail", "error": f"ajaxSearch timeout/gagal: {e}"}
    except Exception as e:  # noqa: BLE001
        return {"status": "fail", "error": str(e)[:300]}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(Path(__file__).parent), **kw)

    def _html(self, html_content: str, code=200):
        body = html_content.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:3000")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        # Route: Halaman Universal / per-platform (Public Downloader)
        _plat_paths = {
            "/": "auto",
            "/index.html": "auto",
            "/instagram": "instagram",
            "/instagram/": "instagram",
            "/youtube": "youtube",
            "/youtube/": "youtube",
            "/tiktok": "tiktok",
            "/tiktok/": "tiktok",
            "/pinterest": "pinterest",
            "/pinterest/": "pinterest",
        }
        _path_only = up.urlparse(self.path).path
        if _path_only in _plat_paths:
            key = _plat_paths[_path_only]
            meta = PLATFORMS[key]
            html = render_template("index.html", {
                "active_page": "public",
                "active_platform": key,
                "platform_title": meta["title"],
                "platform_heading": meta["heading"],
                "platform_desc": meta["desc"],
                "platform_icon": meta["icon"],
            })
            return self._html(html)

        # Route: Halaman Private Downloader
        if self.path in ("/private", "/private/", "/private.html") or self.path.startswith("/private.html?") or self.path.startswith("/private?"):
            html = render_template("private.html", {"active_page": "private"})
            return self._html(html)

        # API: Resolve User ID
        if self.path.startswith("/api/resolve"):
            q = up.parse_qs(up.urlparse(self.path).query)
            username = (q.get("username") or [""])[0].strip().lstrip("@")
            if not username:
                return self._json({"error": "username wajib"}, 400)
            try:
                return self._json({"username": username, "user_id": resolve_user_id_native(username)})
            except Exception as e:  # noqa: BLE001
                return self._json({"error": str(e)}, 502)

        # API: Extract Media (universal: IG, YouTube, TikTok, Pinterest via yt-dlp)
        if self.path.startswith("/api/extract"):
            q = up.parse_qs(up.urlparse(self.path).query)
            target = (q.get("url") or [""])[0].strip()
            hint = (q.get("platform") or [""])[0].strip().lower()
            if not target:
                return self._json({"error": "url parameter wajib"}, 400)
            res = extract_public_with_ytdlp(target)
            if hint in PLATFORMS and hint != "auto":
                res["platform_hint"] = hint
            return self._json(res)

        # API: daftar platform yang didukung (utk frontend / health check)
        if up.urlparse(self.path).path == "/api/platforms":
            return self._json({"platforms": list(PLATFORMS.keys())})

        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/get-url"):
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except Exception:
                n = 0
            form = up.parse_qs(self.rfile.read(n).decode("utf-8", "replace"))
            target_link = (form.get("l") or [""])[0].strip()
            if not target_link:
                return self._json({"status": "fail", "mess": "parameter l kosong"}, 400)
            try:
                return self._json({"status": "ok", "data": build_graphql_url(target_link)})
            except Exception as e:  # noqa: BLE001
                return self._json({"status": "fail", "mess": str(e)}, 502)
        self.send_error(404)

    def log_message(self, format, *args):
        sys.stderr.write("  %s\n" % (format % args))


if __name__ == "__main__":
    try:
        port = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    except Exception:
        port = 3000
    print(f"ComotVid server -> http://127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
