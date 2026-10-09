// ==UserScript==
// @name         ComotVid Auto-Bridge
// @namespace    https://github.com/marzukiberg/comotvid
// @version      1.0
// @description  Otomatis fetch Instagram Story/Post GraphQL dan kirim ke ComotVid lokal
// @match        https://www.instagram.com/*
// @match        http://localhost:8787/*
// @match        http://127.0.0.1:8787/*
// @grant        GM_xmlhttpRequest
// @grant        unsafeWindow
// @connect      localhost
// @connect      127.0.0.1
// @connect      instagram.com
// @connect      www.instagram.com
// ==/UserScript==

(function() {
    'use strict';

    // 1. Jika berjalan di tab ComotVid (localhost)
    if (location.hostname === 'localhost' || location.hostname === '127.0.0.1') {
        window.hasComotVidBridge = true;
        window.addEventListener('message', async (event) => {
            if (event.data && event.data.type === 'COMOTVID_FETCH_REQUEST') {
                console.log('[ComotVid Bridge] Menerima request fetch...');
                // Kirim request ke background GM_xmlhttpRequest
                GM_xmlhttpRequest({
                    method: 'POST',
                    url: 'https://www.instagram.com/api/graphql',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-IG-App-ID': '936619743392459',
                        'X-ASBD-ID': '359341',
                        'X-FB-LSD': event.data.lsd || 'AVrX7h5b_bA',
                        'Origin': 'https://www.instagram.com',
                        'Referer': 'https://www.instagram.com/'
                    },
                    data: new URLSearchParams(event.data.payload).toString(),
                    onload: function(response) {
                        try {
                            const json = JSON.parse(response.responseText);
                            window.postMessage({ type: 'COMOTVID_FETCH_RESPONSE', success: true, data: json }, '*');
                        } catch (e) {
                            window.postMessage({ type: 'COMOTVID_FETCH_RESPONSE', success: false, error: response.responseText }, '*');
                        }
                    },
                    onerror: function(err) {
                        window.postMessage({ type: 'COMOTVID_FETCH_RESPONSE', success: false, error: 'Network Error' }, '*');
                    }
                });
            }
        });
        return;
    }

    // 2. Jika berjalan di tab instagram.com
    console.log('[ComotVid Bridge] Aktif di tab Instagram.');
})();
