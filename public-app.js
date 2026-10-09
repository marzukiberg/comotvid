// ComotVid — Universal Media Downloader Logic with Alpine.js
// Mendukung: Instagram, YouTube, TikTok, Pinterest via /api/extract (yt-dlp backend)
/* global window, fetch */

const PLATFORM_PATTERNS = {
  instagram: [/instagram\.com\//i],
  youtube: [/youtube\.com\//i, /youtu\.be\//i],
  tiktok: [/tiktok\.com\//i],
  pinterest: [/pinterest\./i, /pin\.it\//i],
};

const PLATFORM_LABEL = {
  auto: 'Tempel link Instagram, YouTube, TikTok, atau Pinterest:',
  instagram: 'Tempel Link Reels, Story Publik, atau Post Instagram:',
  youtube: 'Tempel Link Video, Shorts, atau Playlist YouTube:',
  tiktok: 'Tempel Link Video TikTok:',
  pinterest: 'Tempel Link Pin Pinterest (video / gambar):',
};

const PLATFORM_PLACEHOLDER = {
  auto: 'https://... (otomatis deteksi platform)',
  instagram: 'https://www.instagram.com/stories/... atau /reel/... atau /p/...',
  youtube: 'https://www.youtube.com/watch?v=... atau /shorts/... atau youtu.be/...',
  tiktok: 'https://www.tiktok.com/@user/video/... atau vt.tiktok.com/...',
  pinterest: 'https://www.pinterest.com/pin/... atau pin.it/...',
};

const PLATFORM_HINT = {
  auto: 'Otomatis: Reels/Story/Post IG · Video/Shorts YT · TikTok tanpa watermark · Pin Pinterest.',
  instagram: 'Mendukung /reel/ · /p/ · /stories/ publik (butuh login browser utk story) · carousel.',
  youtube: 'Mendukung video biasa, Shorts, embed youtu.be. Playlist dibatasi 1 item (--no-playlist).',
  tiktok: 'Mendukung tiktok.com, vt.tiktok.com, vm.tiktok.com — diambil versi tanpa watermark bila tersedia.',
  pinterest: 'Mendukung pin.it shortlink & pinterest.com/pin/ — video diambil kualitas penuh, gambar resolusi asli.',
};

function detectPlatform(url) {
  const u = (url || '').trim();
  for (const [key, patterns] of Object.entries(PLATFORM_PATTERNS)) {
    if (patterns.some((rx) => rx.test(u))) return key;
  }
  return 'unknown';
}

// Alpine.js component data definition
window.publicDownloader = () => ({
  url: '',
  loading: false,
  statusMsg: '',
  isError: false,
  items: [],
  platform: 'auto',
  detectedPlatform: '',

  initPlatform(defaultPlatform) {
    if (defaultPlatform && PLATFORM_LABEL[defaultPlatform]) {
      this.platform = defaultPlatform;
    }
    // Sinkron pill navbar: klik pill = navigasi path (server-side render),
    // tapi tombol quick-switch di halaman cukup ubah state lokal.
  },

  setPlatform(p) {
    this.platform = p;
    this.statusMsg = '';
    this.isError = false;
  },

  platformLabel() {
    return PLATFORM_LABEL[this.platform] || PLATFORM_LABEL.auto;
  },

  platformPlaceholder() {
    return PLATFORM_PLACEHOLDER[this.platform] || PLATFORM_PLACEHOLDER.auto;
  },

  platformHint() {
    return PLATFORM_HINT[this.platform] || PLATFORM_HINT.auto;
  },

  downloadName(m, i) {
    const plat = (this.detectedPlatform || this.platform || 'media').replace(/[^a-z0-9]+/gi, '-').toLowerCase();
    const ext = m.isVideo ? 'mp4' : (m.isAudio ? 'mp3' : 'jpg');
    return `comotvid-${plat}-${i + 1}.${ext}`;
  },

  async fetchMedia() {
    const trimmedUrl = this.url.trim();
    if (!trimmedUrl) {
      this.statusMsg = 'Masukkan link terlebih dahulu.';
      this.isError = true;
      return;
    }

    const detected = detectPlatform(trimmedUrl);
    if (detected === 'unknown') {
      this.statusMsg = 'Link tidak dikenali. Gunakan link Instagram, YouTube, TikTok, atau Pinterest.';
      this.isError = true;
      return;
    }

    // Peringatan mismatch: user di tab IG tapi paste link YT (atau sebaliknya)
    if (this.platform !== 'auto' && this.platform !== detected) {
      this.statusMsg = `Link terdeteksi sebagai ${detected}, tapi tab aktif ${this.platform}. Tetap diproses...`;
      this.isError = false;
    } else {
      this.statusMsg = `Menghubungkan ke ${detected}...`;
      this.isError = false;
    }

    this.loading = true;
    this.items = [];
    this.detectedPlatform = detected;

    // ==========================================
    // EKSTRAKSI MEDIA VIA BACKEND (yt-dlp universal)
    // ==========================================
    try {
      const apiRes = await fetch(`/api/extract?url=${encodeURIComponent(trimmedUrl)}&platform=${encodeURIComponent(this.platform)}`);
      if (apiRes.ok) {
        const json = await apiRes.json();
        if (json.status === 'ok' && Array.isArray(json.items) && json.items.length) {
          this.detectedPlatform = json.platform || detected;
          this.items = json.items.map((it) => ({
            url: it.url,
            thumb: it.thumb || it.url,
            isVideo: Boolean(it.isVideo),
            isAudio: Boolean(it.isAudio),
            title: it.title || '',
            takenAt: it.duration ? `Durasi: ${Math.round(it.duration)} detik` : '',
          }));
        } else if (json.error) {
          this.statusMsg = `Gagal: ${json.error}`;
          this.isError = true;
        }
      } else {
        this.statusMsg = `Server error (${apiRes.status}). Coba lagi.`;
        this.isError = true;
      }
    } catch (err) {
      console.warn('Backend extract error:', err);
      this.statusMsg = 'Tidak bisa menghubungi server lokal. Pastikan server jalan.';
      this.isError = true;
    }

    this.loading = false;

    if (this.items.length > 0) {
      this.statusMsg = `Berhasil! ${this.items.length} media (${this.detectedPlatform}) siap diunduh.`;
      this.isError = false;
    } else if (!this.isError || !this.statusMsg) {
      this.statusMsg = this.platform === 'instagram' || detected === 'instagram'
        ? 'Gagal mengambil media secara otomatis. Jika akun privat, silakan gunakan Private Downloader.'
        : `Gagal mengambil media ${detected} secara otomatis. Pastikan link publik & coba lagi.`;
      this.isError = true;
    }
  }
});
