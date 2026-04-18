// ==UserScript==
// @name         Missav Highlighter
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  Highlight videos that exist in the local database
// @author       You
// @match        https://missav.ws/*
// @grant        GM_xmlhttpRequest
// @connect      192.168.31.81
// @require      https://cdn.jsdelivr.net/npm/jquery@3.6.0/dist/jquery.min.js
// ==/UserScript==

(function() {
    'use strict';

    const API_URL = 'http://192.168.31.81:3333/jav';

    function highlightVideos(javIds) {
        console.log('[Missav] Total IDs from API:', javIds.length);
        console.log('[Missav] Items found:', $('div.thumbnail').length);

        $('div.thumbnail').each(function() {
            const linkEl = $(this).find('.text-nord4 a');
            if (linkEl.length) {
                const text = linkEl.text().trim();
                const href = linkEl.attr('href') || '';
                console.log('[Missav] href:', href);
                let videoId = '';
                const pathMatch = href.match(/\/([^\/]+)$/);
                if (pathMatch) {
                    videoId = pathMatch[1].toUpperCase();
                    console.log('[Missav] Extracted ID:', videoId);
                }
                if (!videoId) {
                    const match = text.match(/^([A-Z0-9]+[-]\d+)/i);
                    if (match) {
                        videoId = match[1].toUpperCase();
                    }
                }
                if (videoId) {
                    console.log('[Missav] Found video ID:', videoId);
                    if (javIds.includes(videoId)) {
                        console.log('[Missav] Matched, highlighting:', videoId);
                        linkEl.css('color', 'blue');
                        const newText = '【已收录】' + text;
                        linkEl.text(newText);
                    }
                }
            }
        });
    }

    function init() {
        console.log('[Missav] Script starting...');
        
        GM_xmlhttpRequest({
            method: 'GET',
            url: API_URL,
            onload: function(response) {
                console.log('[Missav] API response status:', response.status);
                try {
                    const data = JSON.parse(response.responseText);
                    const javIds = data.jav_id || [];
                    console.log('[Missav] Parsed jav_id count:', javIds.length);
                    highlightVideos(javIds);
                } catch (e) {
                    console.error('[Missav] JSON parse error:', e);
                }
            },
            onerror: function(error) {
                console.error('[Missav] Fetch error:', error);
            }
        });
    }

    if (window.jQuery) {
        init();
    } else {
        $(document).ready(init);
    }
})();