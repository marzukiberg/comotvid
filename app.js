// ComotVid — Private Instagram Downloader Logic with Alpine.js
/* global window, document, URL, fetch, navigator, alert */

const DEFAULT_QUERY_HASH = 'de8017ee0a7c9c45ec4260733d81ea31';
const DEFAULT_DOC_ID_POST = '24368985919464652';

function extractInstagramInfo(url) {
  const cleanUrl = url.split('?')[0].replace(/\/$/, '');

  // Highlights: /stories/highlights/{id} atau /s/{id}
  const highlightMatch = cleanUrl.match(/instagram\.com\/(?:stories\/highlights|s)\/(\d+)/);
  if (highlightMatch) {
    return {
      type: 'highlight',
      highlightId: highlightMatch[1]
    };
  }

  // Stories: /stories/{username}/{story_id}
  const storyMatch = cleanUrl.match(/instagram\.com\/stories\/([A-Za-z0-9._]+)(?:\/(\d+))?/);
  if (storyMatch) {
    return {
      type: 'story',
      username: storyMatch[1],
      storyId: storyMatch[2] || null
    };
  }

  // Posts/Reels: /p/{shortcode}, /reel/{shortcode}, /reels/{shortcode}, /tv/{shortcode}
  const postMatch = cleanUrl.match(/instagram\.com\/(?:p|reel|reels|tv)\/([A-Za-z0-9_-]+)/);
  if (postMatch) {
    return {
      type: 'post',
      shortcode: postMatch[1]
    };
  }

  // Profile: instagram.com/{username}
  const profileMatch = cleanUrl.match(/instagram\.com\/([A-Za-z0-9._]+)$/);
  if (profileMatch && !['explore', 'reels', 'stories', 'direct', 'accounts'].includes(profileMatch[1])) {
    return {
      type: 'profile',
      username: profileMatch[1]
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

function bestCandidateUrl(cands) {
  if (!Array.isArray(cands) || !cands.length) return null;
  let best = cands[0];
  for (const c of cands) {
    if ((c.width || 0) * (c.height || 0) > (best.width || 0) * (best.height || 0)) {
      best = c;
    }
  }
  return best.url;
}

function normStoryItem(it) {
  if (!it) return null;
  const isVideo = Boolean(it.is_video || it.__typename === 'GraphStoryVideo');
  let url = null;
  const thumb = it.display_url || getBestResourceUrl(it.display_resources) || null;

  if (isVideo) {
    url = it.video_resources?.[0]?.src || it.video_url || null;
  } else {
    url = it.display_url || getBestResourceUrl(it.display_resources) || null;
  }
  if (!url) return null;

  return {
    url,
    thumb,
    isVideo,
    takenAt: it.taken_at_timestamp ? new Date(it.taken_at_timestamp * 1000).toLocaleString('id-ID') : ''
  };
}

function normV1Item(it) {
  if (!it) return null;
  const isVideo = it.media_type === 2;
  let url = null;
  let thumb = null;
  if (isVideo) {
    url = it.video_versions?.[0]?.url || null;
    thumb = bestCandidateUrl(it.image_versions2?.candidates);
  } else {
    url = bestCandidateUrl(it.image_versions2?.candidates) || it.display_url || null;
  }
  if (!url) return null;
  return {
    url,
    thumb,
    isVideo,
    takenAt: it.taken_at ? new Date(it.taken_at * 1000).toLocaleString('id-ID') : ''
  };
}

function normShortcodeItem(node) {
  if (!node) return null;
  const isVideo = Boolean(node.is_video);
  const url = isVideo
    ? (node.video_url || node.video_resources?.[0]?.src)
    : (node.display_url || getBestResourceUrl(node.display_resources));
  if (!url) return null;
  return {
    url,
    thumb: node.display_url,
    isVideo,
    takenAt: node.taken_at_timestamp ? new Date(node.taken_at_timestamp * 1000).toLocaleString('id-ID') : ''
  };
}

// Alpine.js Component for Private Downloader
window.privateDownloader = () => ({
  inputUrl: '',
  converting: false,
  statusMsg: '',
  isStatusError: false,
  gqlUrl: '',
  copiedText: 'Salin',
  jsonInput: '',
  parseError: '',
  showManualFallback: false,
  manualUserId: '',
  queryHash: DEFAULT_QUERY_HASH,
  currentUserId: null,
  currentHighlightId: null,
  items: [],
  banner: {
    show: false,
    type: 'info',
    icon: 'ph ph-info',
    title: '',
    desc: ''
  },

  init() {
    // Cek parameter ?url= dari redirect halaman utama
    const params = new URLSearchParams(window.location.search);
    const initialUrl = params.get('url');
    if (initialUrl) {
      this.inputUrl = initialUrl;
      this.convertLink();
    }
  },

  showBanner(icon, title, desc, type = 'info') {
    this.banner = { show: true, icon, title, desc, type };
  },

  hideBanner() {
    this.banner.show = false;
  },

  buildLegacyGraphqlUrl(userId, highlightId = null) {
    const qHash = this.queryHash.trim() || DEFAULT_QUERY_HASH;
    let vars;
    if (highlightId) {
      vars = {
        reel_ids: [],
        highlight_reel_ids: [Number(highlightId)],
        precomposed_overlay: false
      };
    } else {
      vars = {
        reel_ids: [Number(userId)],
        highlight_reel_ids: [],
        precomposed_overlay: false
      };
    }
    return `https://www.instagram.com/graphql/query/?query_hash=${qHash}&variables=${encodeURIComponent(JSON.stringify(vars))}`;
  },

  async convertLink() {
    const input = this.inputUrl.trim();
    if (!input) return;

    this.converting = true;
    this.statusMsg = 'Memeriksa & menghubungkan ke Instagram...';
    this.isStatusError = false;
    this.hideBanner();
    this.showManualFallback = false;
    this.currentHighlightId = null;

    const info = extractInstagramInfo(input);
    let resolvedTargetUrl = '';

    if (info.type === 'post') {
      const vars = {
        shortcode: info.shortcode,
        fetch_tagged_user_count: null,
        hoisted_comment_id: null,
        hoisted_reply_id: null
      };
      resolvedTargetUrl = `https://www.instagram.com/graphql/query/?doc_id=${DEFAULT_DOC_ID_POST}&variables=${encodeURIComponent(JSON.stringify(vars))}`;
    } else if (info.type === 'highlight') {
      this.currentHighlightId = info.highlightId;
      this.manualUserId = '';
      resolvedTargetUrl = this.buildLegacyGraphqlUrl(null, this.currentHighlightId);
    } else {
      try {
        const resp = await fetch('/api/get-url', {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: 'l=' + encodeURIComponent(input)
        });

        if (resp.ok) {
          const json = await resp.json();
          if (json.status === 'ok' && json.data) {
            const matchId = json.data.match(/reel_ids%22%3A%5B%22?(\d+)%22?%5D/);
            if (matchId) {
              this.currentUserId = matchId[1];
              this.manualUserId = this.currentUserId;
            }
            resolvedTargetUrl = json.data;
          }
        }
      } catch {
        /* fallback */
      }

      if (!resolvedTargetUrl) {
        resolvedTargetUrl = this.buildLegacyGraphqlUrl(this.currentUserId || '0');
      }
    }

    this.gqlUrl = resolvedTargetUrl;

    // Coba direct browser fetch
    try {
      const res = await fetch(resolvedTargetUrl, {
        method: 'GET',
        credentials: 'include',
        headers: { 'Accept': 'application/json, text/plain, */*' }
      });

      if (res.ok) {
        const data = await res.json();
        if (data && (data.data || data.items || data.graphql)) {
          this.statusMsg = 'Berhasil mengambil data otomatis!';
          this.showBanner(
            'ph ph-check-circle',
            'Sesi Login Terdeteksi',
            'Data story otomatis berhasil diambil dan diproses tanpa perlu membuka link manual.',
            'success'
          );
          this.processData(data);
          this.converting = false;
          return;
        }
      }
    } catch {
      /* continue to manual fallback */
    }

    this.statusMsg = 'Tindakan 1-klik diperlukan';
    this.showBanner(
      'ph ph-info',
      'Tindakan 1-Klik Diperlukan',
      'Browser membatasi direct request antar domain (CORS). Silakan klik Buka Link di Step 2, lalu salin JSON-nya ke Step 3.',
      'warn'
    );
    this.showManualFallback = true;
    this.converting = false;
  },

  genFromManualId() {
    const uid = this.manualUserId.trim();
    if (!uid || !/^\d+$/.test(uid)) {
      alert('Masukkan User ID (PK) numerik yang valid.');
      return;
    }
    this.currentUserId = uid;
    this.currentHighlightId = null;
    this.gqlUrl = this.buildLegacyGraphqlUrl(this.currentUserId);
    this.statusMsg = `Link GraphQL siap untuk User ID: ${this.currentUserId}`;
  },

  copyGql() {
    if (!this.gqlUrl) return;
    navigator.clipboard.writeText(this.gqlUrl).then(() => {
      this.copiedText = 'Tersalin!';
      setTimeout(() => { this.copiedText = 'Salin'; }, 1500);
    });
  },

  parseJson() {
    const raw = this.jsonInput.trim();
    this.parseError = '';

    if (!raw) {
      this.parseError = 'Tempelkan isi JSON atau Page Source terlebih dahulu.';
      return;
    }

    let data;
    try {
      data = JSON.parse(raw);
    } catch (e) {
      const jsonMatch = raw.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        try { data = JSON.parse(jsonMatch[0]); } catch { /* ignore */ }
      }
      if (!data) {
        this.parseError = 'Format data bukan JSON valid: ' + e.message;
        return;
      }
    }

    this.processData(data);
  },

  processData(data) {
    this.parseError = '';

    if (data.status === 'fail' || data.message) {
      if (data.require_login) {
        this.parseError = 'Instagram meminta login. Pastikan kamu membuka link Step 2 pada browser yang sudah login akun Instagram.';
        return;
      }
    }

    // Auto-detect User ID jika user menempel profile JSON
    if (data?.data?.user?.id) {
      const foundId = data.data.user.id;
      this.currentUserId = foundId;
      this.manualUserId = foundId;
      this.gqlUrl = this.buildLegacyGraphqlUrl(this.currentUserId);
      this.parseError = `User ID ${foundId} (@${data.data.user.username || 'user'}) berhasil didapat! Link GraphQL sudah diperbarui di Step 2. Silakan klik 'Buka Link', salin hasilnya, dan tempel di sini lagi.`;
      return;
    }

    const items = [];

    // Format 1: data.reels_media (query_hash legacy)
    const reelsMedia = data?.data?.reels_media || data?.reels_media;
    if (Array.isArray(reelsMedia)) {
      reelsMedia.forEach(reel => {
        (reel.items || []).forEach(it => items.push(normStoryItem(it)));
      });
    }

    // Format 2: xdt_api__v1__feed__reels_media
    const xdtReels = data?.data?.xdt_api__v1__feed__reels_media?.reels;
    if (xdtReels) {
      Object.keys(xdtReels).forEach(k => {
        (xdtReels[k].items || []).forEach(it => items.push(normV1Item(it)));
      });
    }

    // Format 3: direct reels dict
    const rawReels = data?.reels;
    if (rawReels && !xdtReels) {
      Object.keys(rawReels).forEach(k => {
        (rawReels[k].items || []).forEach(it => items.push(normV1Item(it)));
      });
    }

    // Format 4: Shortcode Media (Post / Reel)
    const shortcodeMedia = data?.graphql?.shortcode_media || data?.data?.xdt_shortcode_media;
    if (shortcodeMedia) {
      if (shortcodeMedia.edge_sidecar_to_children?.edges) {
        shortcodeMedia.edge_sidecar_to_children.edges.forEach(e => items.push(normShortcodeItem(e.node)));
      } else {
        items.push(normShortcodeItem(shortcodeMedia));
      }
    }

    // Format 5: raw items list
    if (Array.isArray(data?.items)) {
      data.items.forEach(it => items.push(normV1Item(it)));
    }

    this.items = items.filter(Boolean);

    if (!this.items.length) {
      this.parseError = 'Tidak ditemukan media video/foto dari data ini. Pastikan link di Step 2 dibuka saat story masih aktif.';
    }
  }
});
