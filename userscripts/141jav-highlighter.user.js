// ==UserScript==
// @name         141JAV Highlighter
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  Add search buttons for 141jav
// @author       You
// @match        https://www.141jav.com/*
// @grant        GM_xmlhttpRequest
// @connect      192.168.31.81
// @require      https://cdn.jsdelivr.net/npm/jquery@3.6.0/dist/jquery.min.js
// ==/UserScript==

(function() {
    'use strict';

    const API_URL = 'http://192.168.31.81:3333/jav';

    function addSearchButtons() {
        console.log('[141JAV] Adding search buttons');
        
        $('.card-content').each(function() {
            const idLink = $(this).find('h5 a');
            if (idLink.length) {
                const videoId = idLink.text().trim();
                console.log('[141JAV] Found video ID:', videoId);
                
                const tagsContainer = $(this).find('.tags').first();
                if (tagsContainer.length && !tagsContainer.find('.search-tag').length) {
                    const missavBtn = '<a class="tag is-dark search-tag" href="https://missav.ws/dm58/cn/' + videoId + '" target="_blank">missav</a>';
                    const javlibraryBtn = '<a class="tag is-dark search-tag" href="https://www.javlibrary.com/cn/vl_searchbyid.php?keyword=' + videoId + '" target="_blank">javlibrary</a>';
                    const javbusBtn = '<a class="tag is-dark search-tag" href="https://www.javbus.com/search/' + videoId + '" target="_blank">javbus</a>';
                    const btdigBtn = '<a class="tag is-dark search-tag" href="https://www.btdig.com/search?q=' + videoId + '" target="_blank">btdig</a>';
                    
                    tagsContainer.prepend(btdigBtn + javbusBtn + javlibraryBtn + missavBtn);
                }
            }
        });
    }

    function init() {
        console.log('[141JAV] Script starting...');
        
        GM_xmlhttpRequest({
            method: 'GET',
            url: API_URL,
            onload: function(response) {
                console.log('[141JAV] API response status:', response.status);
                try {
                    const data = JSON.parse(response.responseText);
                    const javIds = data.jav_id || [];
                    console.log('[141JAV] Parsed jav_id count:', javIds.length);
                    addSearchButtons();
                } catch (e) {
                    console.error('[141JAV] JSON parse error:', e);
                }
            },
            onerror: function(error) {
                console.error('[141JAV] Fetch error:', error);
            }
        });
    }

    if (window.jQuery) {
        init();
    } else {
        $(document).ready(init);
    }
})();