# ComotVid

Private Instagram story downloader — ala savevid.net/instagram-private-downloader.

## Cara pakai
1. Deploy `index.html` ke web server apapun (jalan full client-side).
2. Buka halamannya, tempel link story Instagram.
3. Ikuti langkah 1-2-3 di halaman.

## Cara kerja
- Step 1: extract username dari URL story.
- Step 2a: buka `api/v1/users/web_profile_info/?username=X` (login IG) → dapat numeric user ID.
- Step 2b: generate GraphQL URL (`PolarisStoriesV3ReelPageGalleryQuery`, doc_id configurable).
- Step 3: paste JSON response → extract `image_versions2` / `video_versions` → tombol download.

## Catatan
- `doc_id` bisa rotate saat Instagram deploy ulang — update di Pengaturan Lanjutan.
- Hanya untuk story dari akun yang kamu follow / bisa lihat.
