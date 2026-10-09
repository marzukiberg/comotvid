#!/usr/bin/env python3
"""
ComotVid local server — static files + native IG GraphQL & yt-dlp resolver.
100% self-contained & open-source.
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

LEGACY_QUERY_HASH = "de8017ee0a7c9c45ec4260733d81ea31"
DOC_ID_POST = "24368985919464652"
DOC_ID_STORIES = "26659189347081290"

WEB_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
ANDROID_UA = ("Mozilla/5.0 (Linux; Android 9; GM1903 Build/PKQ1.190110.001; wv) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/75.0.3770.143 "
              "Mobile Safari/537.36 Instagram 103.1.0.15.119 Android (28/9; 420dpi; "
              "1080x2260; OnePlus; GM1903; OnePlus7; qcom; sv_SE; 164094539)")

RE_HIGHLIGHT = re.compile(r"instagram\.com/(?:stories/highlights|s)/(\d+)")
RE_STORY = re.compile(r"instagram\.com/stories/([^/?#]+)")
RE_POST = re.compile(r"instagram\.com/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)")
RE_PROFILE = re.compile(r"instagram\.com/([A-Za-z0-9._]+)/?$")


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
    # 1. Scraping direct HTML profil Instagram (mencari user_id / profile_id di script payload)
    try:
        st, html = http_get(f"https://www.instagram.com/{username}/")
        if st == 200:
            patterns = [
                r'"user_id":"(\d+)"',
                r'"id":"(\d+)"',
                r'"profile_id":"(\d+)"',
                r'"owner":\{"id":"(\d+)"',
                r'/api/v1/users/(\d+)/info',
            ]
            for pat in patterns:
                m = re.search(pat, html)
                if m:
                    return str(m.group(1))
    except Exception as e:
        sys.stderr.write(f"HTML profile scrape notice for @{username}: {e}\n")

    # 2. Native Web Profile Info API dengan App ID Instagram resmi
    for host in ("https://i.instagram.com", "https://www.instagram.com"):
        try:
            st, body = http_get(
                f"{host}/api/v1/users/web_profile_info/?username={username}",
                headers={
                    "User-Agent": ANDROID_UA if "i.instagram.com" in host else WEB_UA,
                    "x-ig-app-id": "936619743392459",
                    "x-asbd-id": "198387",
                    "x-ig-www-claim": "0",
                },
            )
            if st == 200:
                uid = ((json.loads(body).get("data") or {}).get("user") or {}).get("id")
                if uid:
                    return str(uid)
        except Exception as e:
            sys.stderr.write(f"{host} profile info notice: {e}\n")

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
    """Ubah URL Instagram -> URL GraphQL Legacy Query Hash."""
    clean_url = raw_url.split("?")[0]

    m = RE_HIGHLIGHT.search(clean_url)
    if m:
        variables = {
            "reel_ids": [],
            "highlight_reel_ids": [num(m.group(1))],
            "precomposed_overlay": False,
        }
        vars_enc = up.quote(json.dumps(variables, separators=(",", ":")))
        return f"https://www.instagram.com/graphql/query/?query_hash={LEGACY_QUERY_HASH}&variables={vars_enc}"

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

    m = RE_STORY.search(clean_url)
    if m:
        uid = resolve_user_id_native(m.group(1))
        variables = {
            "reel_ids": [num(uid)],
            "highlight_reel_ids": [],
            "precomposed_overlay": False,
        }
        vars_enc = up.quote(json.dumps(variables, separators=(",", ":")))
        return f"https://www.instagram.com/graphql/query/?query_hash={LEGACY_QUERY_HASH}&variables={vars_enc}"

    m = RE_PROFILE.search(clean_url)
    if m:
        uid = resolve_user_id_native(m.group(1))
        variables = {
            "reel_ids": [num(uid)],
            "highlight_reel_ids": [],
            "precomposed_overlay": False,
        }
        vars_enc = up.quote(json.dumps(variables, separators=(",", ":")))
        return f"https://www.instagram.com/graphql/query/?query_hash={LEGACY_QUERY_HASH}&variables={vars_enc}"

    return f"{clean_url}/?__a=1&__d=dis"


def get_browser_cookie_targets():
    """Deteksi otomatis profil browser lokal (Chrome/Brave/Edge) yang mungkin memiliki sesi login IG."""
    targets = []
    # Chrome
    base_c = Path.home() / "Library/Application Support/Google/Chrome"
    if base_c.exists():
        for d in sorted(base_c.iterdir()):
            if d.name == "Default" or d.name.startswith("Profile "):
                targets.append(f"chrome:{d.name}")
    # Brave
    base_b = Path.home() / "Library/Application Support/BraveSoftware/Brave-Browser"
    if base_b.exists():
        for d in sorted(base_b.iterdir()):
            if d.name == "Default" or d.name.startswith("Profile "):
                targets.append(f"brave:{d.name}")
    # Edge
    base_e = Path.home() / "Library/Application Support/Microsoft Edge"
    if base_e.exists():
        for d in sorted(base_e.iterdir()):
            if d.name == "Default" or d.name.startswith("Profile "):
                targets.append(f"edge:{d.name}")
    return targets or ["chrome", "brave", "edge"]


def extract_public_with_ytdlp(url):
    """Gunakan yt-dlp untuk ekstrak Reel/Post publik dan Story secara otomatis."""
    try:
        is_story = "/stories/" in url or "/highlights/" in url
        # Untuk story, langsung prioritaskan profil browser lokal yang login
        cookie_targets = get_browser_cookie_targets()
        browsers_to_try = cookie_targets if is_story else ([None] + cookie_targets)

        last_error = ""
        for b in browsers_to_try:
            cmd = ["yt-dlp", "-J", "--no-warnings"]
            if b:
                cmd.extend(["--cookies-from-browser", b])
            cmd.append(url)

            p = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
            if p.returncode == 0 and p.stdout.strip():
                try:
                    data = json.loads(p.stdout)
                    raw_entries = data.get("entries")
                    entries = [e for e in raw_entries if e] if raw_entries is not None else [data]
                    items = []
                    for entry in entries:
                        formats = entry.get("formats", [])
                        best_v = next((f for f in reversed(formats) if f.get("vcodec") != "none" and f.get("url")), None)
                        video_url = best_v.get("url") if best_v else entry.get("url")
                        thumb = entry.get("thumbnail") or (formats[0].get("url") if formats else None)
                        is_video = bool(best_v or (video_url and ".mp4" in video_url))

                        items.append({
                            "id": entry.get("id"),
                            "title": entry.get("title") or entry.get("description") or "Instagram Media",
                            "url": video_url or thumb,
                            "thumb": thumb,
                            "isVideo": is_video,
                            "duration": entry.get("duration")
                        })
                    if items:
                        return {"status": "ok", "items": items, "method": f"yt-dlp ({b or 'direct'})"}
                except Exception:
                    pass
            else:
                last_error = p.stderr.strip()[:200]

        return {"status": "fail", "error": last_error or "Gagal mengekstrak media via yt-dlp"}
    except Exception as e:
        return {"status": "fail", "error": str(e)}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(Path(__file__).parent), **kw)

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:3000")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/private" or self.path == "/private/":
            self.path = "/private.html"
            return super().do_GET()

        if self.path.startswith("/api/resolve"):
            q = up.parse_qs(up.urlparse(self.path).query)
            username = (q.get("username") or [""])[0].strip().lstrip("@")
            if not username:
                return self._json({"error": "username wajib"}, 400)
            try:
                return self._json({"username": username, "user_id": resolve_user_id_native(username)})
            except Exception as e:  # noqa: BLE001
                return self._json({"error": str(e)}, 502)

        if self.path.startswith("/api/extract"):
            q = up.parse_qs(up.urlparse(self.path).query)
            target = (q.get("url") or [""])[0].strip()
            if not target:
                return self._json({"error": "url parameter wajib"}, 400)
            res = extract_public_with_ytdlp(target)
            return self._json(res)

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
