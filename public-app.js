// ComotVid — Public Reels, Videos & Stories Downloader Logic with Alpine.js
/* global window, document, fetch */

const DOC_ID_POST = '24368985919464652';

function extractInstagramTarget(url) {
  const cleanUrl = url.split('?')[0].replace(/\/$/, '');

  // 1. Stories: /stories/{username}/{optional_story_id}
  const storyMatch = cleanUrl.match(/instagram\.com\/stories\/([A-Za-z0-9._]+)(?:\/(\d+))?/);
  if (storyMatch) {
    return {
      type: 'story',
      username: storyMatch[1],
      storyId: storyMatch[2] || null
    };
  }

  // 2. Highlights: /stories/highlights/{id} atau /s/{id}
  const highlightMatch = cleanUrl.match(/instagram\.com\/(?:stories\/highlights|s)\/(\d+)/);
  if (highlightMatch) {
    return {
      type: 'highlight',
      highlightId: highlightMatch[1]
    };
  }

  // 3. Posts/Reels: /p/{shortcode}, /reel/{shortcode}, /reels/{shortcode}, /tv/{shortcode}
  const postMatch = cleanUrl.match(/instagram\.com\/(?:p|reel|reels|tv)\/([A-Za-z0-9_-]+)/);
  if (postMatch) {
    return {
      type: 'post',
      shortcode: postMatch[1]
    };
  }

  return { type: 'unknown', raw: cleanUrl };
}

function getBestResourceUrl(resources) {
  if (!Array.isArray(resources) || !resources.length) return null;
  let best = resources[0];
  let maxDim = (best.config_width || 0) * (best.config_height || 0);
  for (const r of resources) {
    const dim = (r.config_width || 0) * (r.config_height || 0);
    if (dim > maxDim) {
      best = r;
      maxDim = dim;
    }
  }
  return best.src || null;
}

function extractPostMedia(media) {
  const items = [];

  // Carousel (Multi photo / video)
  if (media.edge_sidecar_to_children?.edges) {
    media.edge_sidecar_to_children.edges.forEach(e => {
      const node = e.node;
      const isVideo = Boolean(node.is_video);
      const url = isVideo
        ? (node.video_url || node.video_resources?.[0]?.src)
        : (getBestResourceUrl(node.display_resources) || node.display_url);
      if (url) {
        items.push({
          url,
          thumb: node.display_url,
          isVideo,
          takenAt: node.taken_at_timestamp ? new Date(node.taken_at_timestamp * 1000).toLocaleString('id-ID') : ''
        });
      }
    });
    return items;
  }

  // Single Item (Reel atau Single Photo)
  const isVideo = Boolean(media.is_video || media.video_url);
  const url = isVideo
    ? (media.video_url || media.video_resources?.[0]?.src)
    : (getBestResourceUrl(media.display_resources) || media.display_url);

  if (url) {
    items.push({
      url,
      thumb: media.display_url,
      isVideo,
      takenAt: media.taken_at_timestamp ? new Date(media.taken_at_timestamp * 1000).toLocaleString('id-ID') : ''
    });
  }

  return items;
}

// Alpine.js component data definition
window.publicDownloader = () => ({
  url: '',
  loading: false,
  statusMsg: '',
  isError: false,
  items: [],

  async fetchMedia() {
    const trimmedUrl = this.url.trim();
    if (!trimmedUrl) {
      this.statusMsg = 'Masukkan link Instagram terlebih dahulu.';
      this.isError = true;
      return;
    }

    const target = extractInstagramTarget(trimmedUrl);
    if (target.type === 'unknown') {
      this.statusMsg = 'Link Instagram tidak valid. Masukkan link /stories/, /reel/, atau /p/';
      this.isError = true;
      return;
    }

    this.loading = true;
    this.statusMsg = 'Menghubungkan ke Instagram...';
    this.isError = false;
    this.items = [];

    // ==========================================
    // EKSTRAKSI MEDIA VIA BACKEND SERVER (yt-dlp)
    // ==========================================
    try {
      const apiRes = await fetch(`/api/extract?url=${encodeURIComponent(trimmedUrl)}`);
      if (apiRes.ok) {
        const json = await apiRes.json();
        if (json.status === 'ok' && Array.isArray(json.items) && json.items.length) {
          this.items = json.items.map(it => ({
            url: it.url,
            thumb: it.thumb || it.url,
            isVideo: it.isVideo,
            takenAt: it.duration ? `Durasi: ${Math.round(it.duration)} detik` : ''
          }));
        }
      }
    } catch (err) {
      console.warn('Backend extract error:', err);
    }

    this.loading = false;

    if (this.items.length > 0) {
      this.statusMsg = `Berhasil! ${this.items.length} media siap diunduh.`;
      this.isError = false;
    } else {
      this.statusMsg = 'Gagal mengambil media secara otomatis. Jika akun privat, silakan gunakan Private Downloader.';
      this.isError = true;
    }
  }
});
