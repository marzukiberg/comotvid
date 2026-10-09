# ComotVid — Private Instagram Downloader

Downloader video, foto, reels, dan story Instagram (flow ala savevid.net / saveig).

## ⚠️ Update penting (kenapa dulu error)

Kalau kamu pernah salin URL dari savevid lalu buka dan dapat:

```json
{"errors":[{"message":"execution error","severity":"CRITICAL"}],"data":null,"status":"ok"}
```

Itu **bukan bug ComotVid**. Instagram sudah menonaktifkan akses GraphQL anonim:

| Endpoint | Status |
|---|---|
| `GET graphql/query/?query_hash=de8017ee...` | ❌ 400 `Incorrect Query` (query_hash retired) |
| `GET graphql/query/?doc_id=...` | ❌ 400 `Incorrect Query` — **IG menonaktifkan `doc_id` di endpoint GET** |
| `GET api/v1/feed/reels_media/?reel_ids=...` | ❌ `{"reels":{}}` anonim / `useragent mismatch` di browser |
| **`POST api/graphql` + `doc_id` + sesi login** | ✅ **satu-satunya yang jalan** |

Catatan: savevid.net **masih** menghasilkan URL `query_hash` lama itu sampai sekarang — jadi
metode "salin URL → buka tab" memang sudah usang, bukan salah setelanmu.

`doc_id` yang benar juga bukan yang lama. Yang **valid** (terverifikasi dari Relay artifact Instagram):

| Query | doc_id |
|---|---|
| Story / Highlight (`PolarisStoriesV3ReelPageStandaloneQuery`) | `29184890191114309` |
| Post / Reel (`shortcode media`) | `24368985919464652` |

Variabelnya juga bukan `reel_ids`, tapi:

```json
{"media_id": null, "reel_ids_arr": ["<user_id>"]}
```

## Alur Kerja

1. **Step 1 — Masukkan Link Instagram**
   - `https://www.instagram.com/stories/<username>/<story_id>/`
   - `https://www.instagram.com/stories/highlights/<highlight_id>/`
   - `https://www.instagram.com/p/<shortcode>/` (atau `/reel/`, `/reels/`, `/tv/`)
   - ComotVid otomatis resolve `username → user_id` (lewat `server.py`).

2. **Step 2 — Cara Utama: Console**
   - ComotVid membuat perintah siap-tempel yang menembak `POST /api/graphql` dengan
     `doc_id` + header (LSD, CSRF, X-IG-App-ID) yang benar.
   - Buka `instagram.com` di tab yang **sudah login** → `F12` → tab **Console** → tempel → Enter.
   - JSON hasilnya otomatis tercopy ke clipboard.

3. **Step 3 — Tempel JSON & Ekstrak**
   - `Ctrl+V` ke Step 3 → **Ekstrak & Download Media**.

### Tab lain di Step 2 (opsional)

| Tab | Isi | Catatan |
|---|---|---|
| **Cara Utama: Console** | perintah `POST /api/graphql` | ✅ jalan (butuh login) |
| **URL API (anonim)** | `api/v1/feed/reels_media/?reel_ids=<id>` | butuh sesi login; sering `useragent mismatch` |
| **Legacy Hash** | `query_hash=de8017ee...` | ❌ retired — referensi saja |

## Cara Resolve User ID (username → numeric id)

1. **Resolver lokal** — `server.py` (`/api/resolve`), bebas CORS/Cloudflare. Ini yang dipakai.
2. **Manual** — buka `https://www.instagram.com/api/v1/users/web_profile_info/?username=<u>`
   di tab yang sudah login, ambil `data.user.id`, tempel di "Pengaturan Manual".

> Resolver lama lewat `v3.savevid.net/api/get-url` **sudah dibuang** karena selalu kena
> Cloudflare 403 saat dipanggil dari origin lain.

## Dev / Menjalankan

```bash
make dev              # start server + buka browser (port 8787)
make dev PORT=9000    # port lain
make start            # server saja (tanpa buka browser)
make check            # syntax check app.js + server.py
```

Atau tanpa `make`:

```bash
./dev.sh              # PORT=9000 ./dev.sh   NO_OPEN=1 ./dev.sh
npm run dev           # kalau lebih suka npm
python3 server.py     # paling dasar
```

Server menyajikan static (`index.html`, `app.js`) **dan** endpoint `/api/*` dari satu port.

### Endpoint server

| Method | Path | Fungsi |
|--------|------|--------|
| `GET` | `/api/resolve?username=<u>` | `username → user_id` |
| `POST` | `/api/get-url` (form `l=<url>`) | URL Instagram → info target: `kind`, `doc_id`, `endpoint`, `variables`, `console`, `data` (URL) |

## Kompatibilitas Parser

Parser di `app.js` (`parseJson`) menangani:

- **Polaris** (`data.xdt_api__v1__feed__reels_media.reels` / `.reels_media[]`) ← format utama sekarang
- Reels Feed API (`reels.<id>.items`)
- GraphQL Reels Media legacy (`data.reels_media`)
- Shortcode Post/Carousel (`shortcode_media` / `xdt_shortcode_media` / `edge_sidecar_to_children`)
- Web Profile Info (`data.user.id`) — auto-isi User ID
- Error Instagram: `Unauthorized logged out query`, `missing_required_variable_value`,
  `Incorrect Query`, `useragent mismatch`, `require_login`

## Catatan Teknis

- `reel_ids`/`reel_ids_arr` = **user_id pemilik story**, bukan story_id (story ID di-ignore).
- Header yang dipakai Console: `X-IG-App-ID: 936619743392459`, `X-ASBD-ID: 359341`,
  `X-FB-LSD` (dari HTML), `X-CSRFToken` (dari cookie `csrftoken`).
- Perintah Console **wajib** dijalankan di origin `instagram.com` (biar cookie + LSD valid).
- Pengambilan media butuh sesi login Instagram → karena itu Step 2/3 manual.

## Disclaimer

Untuk mengunduh konten milik sendiri / yang kamu punya hak aksesnya. Hormati privasi & ToS Instagram.
