// ComotVid — Public Reels, Videos & Stories Downloader Logic with Alpine.js
/* global window, document, fetch, history */

function detectPlatformFromUrl(url) {
  const u = (url || '').toLowerCase();
  if (u.includes('instagram.com')) return 'Instagram';
  if (u.includes('youtube.com') || u.includes('youtu.be')) return 'YouTube';
  if (u.includes('tiktok.com')) return 'TikTok';
  if (u.includes('pinterest.') || u.includes('pin.it')) return 'Pinterest';
  return '';
}

window.publicDownloader = () => ({
  url: '',
  platform: 'auto',
  loading: false,
  statusMsg: '',
  isError: false,
  items: [],
  detectedPlatform: '',

  initPlatform(p) {
    this.platform = p || 'auto';
    this.applyTheme(this.platform);
  },

  applyTheme(platformKey) {
    const body = document.body;
    body.className = body.className.replace(/theme-[a-z0-9_-]+/g, '').trim();
    body.classList.add(`theme-${platformKey || 'auto'}`);
  },

  setPlatform(p) {
    this.platform = p;
    this.applyTheme(p);
    const path = p === 'auto' ? '/' : `/${p}`;
    if (window.location.pathname !== path) {
      history.pushState({ platform: p }, '', path);
    }
  },

  platformLabel() {
    const map = {
      auto: 'Tempel Link Video atau Media (Otomatis):',
      instagram: 'Tempel Link Reels, Video, atau Post Instagram:',
      youtube: 'Tempel Link Video atau Shorts YouTube:',
      tiktok: 'Tempel Link Video TikTok:',
      pinterest: 'Tempel Link Pin / Video Pinterest:'
    };
    return map[this.platform] || map.auto;
  },

  platformPlaceholder() {
    const map = {
      auto: 'https://www.instagram.com/... / https://youtu.be/... / https://vt.tiktok.com/...',
      instagram: 'https://www.instagram.com/reel/... atau /p/...',
      youtube: 'https://www.youtube.com/watch?v=... atau https://youtu.be/...',
      tiktok: 'https://www.tiktok.com/@user/video/... atau https://vt.tiktok.com/...',
      pinterest: 'https://pin.it/... atau https://www.pinterest.com/pin/...'
    };
    return map[this.platform] || map.auto;
  },

  platformHint() {
    const map = {
      auto: 'Didukung: Instagram (Reel/Post/Story), YouTube (Video/Shorts), TikTok (Video no WM), Pinterest (Pin/Video)',
      instagram: 'Mendukung: /reel/ · /p/ · /stories/ · /tv/ · single photo/video & carousel',
      youtube: 'Mendukung: youtube.com/watch · youtu.be · youtube.com/shorts',
      tiktok: 'Mendukung: tiktok.com/@user/video/ · vt.tiktok.com · vm.tiktok.com (Tanpa Watermark)',
      pinterest: 'Mendukung: pin.it · pinterest.com/pin/'
    };
    return map[this.platform] || map.auto;
  },

  async fetchMedia() {
    const trimmedUrl = this.url.trim();
    if (!trimmedUrl) {
      this.statusMsg = 'Masukkan link media terlebih dahulu.';
      this.isError = true;
      return;
    }

    this.loading = true;
    this.statusMsg = 'Menghubungkan & memproses media...';
    this.isError = false;
    this.items = [];
    this.detectedPlatform = detectPlatformFromUrl(trimmedUrl);

    try {
      const apiRes = await fetch(`/api/extract?url=${encodeURIComponent(trimmedUrl)}`);
      if (apiRes.ok) {
        const json = await apiRes.json();
        if (json.status === 'ok' && Array.isArray(json.items) && json.items.length) {
          this.items = json.items.map(it => ({
            url: it.url,
            thumb: it.thumb || it.url,
            isVideo: it.isVideo,
            isAudio: it.isAudio || false,
            title: it.title || '',
            takenAt: it.duration ? `Durasi: ${Math.round(it.duration)}s` : ''
          }));
        } else if (json.error) {
          this.statusMsg = json.error;
          this.isError = true;
        }
      } else {
        this.statusMsg = 'Gagal menghubungi server ekstraksi.';
        this.isError = true;
      }
    } catch (err) {
      console.warn('Backend extract error:', err);
      this.statusMsg = 'Terjadi kesalahan jaringan saat mengekstrak media.';
      this.isError = true;
    }

    this.loading = false;

    if (this.items.length > 0) {
      this.statusMsg = `Berhasil! ${this.items.length} media siap diunduh.`;
      this.isError = false;
    } else if (!this.isError) {
      this.statusMsg = 'Gagal mengambil media secara otomatis. Jika ini Story IG privat, silakan gunakan Private Downloader.';
      this.isError = true;
    }
  }
});
