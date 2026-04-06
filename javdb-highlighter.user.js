// ==UserScript==
// @name         JAVDB Highlighter
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  Highlight videos that exist in the local database
// @author       You
// @match        https://javdb.com/*
// @grant        GM_xmlhttpRequest
// @connect      192.168.31.81
// @require      https://cdn.jsdelivr.net/npm/jquery@3.6.0/dist/jquery.min.js
// ==/UserScript==

(function() {
    'use strict';

    const API_URL = 'http://192.168.31.81:3333/jav';

    function highlightVideos(javIds) {
        console.log('[JAVDB] Total IDs from API:', javIds.length);
        
        $('.item').each(function() {
            const titleEl = $(this).find('.video-title strong');
            if (titleEl.length) {
                const videoId = titleEl.text().trim();
                console.log('[JAVDB] Found video ID:', videoId);
                if (javIds.includes(videoId)) {
                    console.log('[JAVDB] Matched, highlighting:', videoId);
                    titleEl.parent('.video-title').css('color', 'red');
                    const tagsEl = $(this).find('.tags');
                    if (tagsEl.length && !tagsEl.find('.tag.is-danger:contains("已收录")').length) {
                        tagsEl.append('<span class="tag is-danger">已收录</span>');
                    }
                }
            }
        });
    }

    function highlightActors(actorCount) {
        console.log('[JAVDB] Actor count data:', actorCount);
        
        $('.actor-box').each(function() {
            const linkEl = $(this).find('a');
            const title = linkEl.attr('title');
            const strongEl = $(this).find('strong');
            
            console.log('[JAVDB] Actor title:', title);
            
            const href = linkEl.attr('href');
            if (href) {
                const actorId = href.replace('/actors/', '');
                linkEl.attr('href', '/actors/' + actorId + '?t=d&sort_type=1');
            }
            
            if (title && actorCount) {
                const names = title.split(',').map(n => n.trim());
                let matchedCount = 0;
                for (const name of names) {
                    if (actorCount[name] !== undefined) {
                        matchedCount = actorCount[name];
                        break;
                    }
                }
                if (matchedCount > 0) {
                    console.log('[JAVDB] Matched count:', matchedCount);
                    if (!strongEl.find('.actor-count').length) {
                        strongEl.append('<br><span class="actor-count" style="color:red">已收录' + matchedCount + '部</span>');
                    }
                }
            }
        });
    }

    function init() {
        console.log('[JAVDB] Script starting...');
        console.log('[JAVDB] jQuery version:', $.fn.jquery);
        console.log('[JAVDB] Items found:', $('.item').length);
        console.log('[JAVDB] Actor boxes found:', $('.actor-box').length);
        
        GM_xmlhttpRequest({
            method: 'GET',
            url: API_URL,
            onload: function(response) {
                console.log('[JAVDB] API response status:', response.status);
                console.log('[JAVDB] API response:', response.responseText.substring(0, 500));
                try {
                    const data = JSON.parse(response.responseText);
                    const javIds = data.jav_id || [];
                    const actorCount = data.actor_count || {};
                    console.log('[JAVDB] Parsed jav_id count:', javIds.length);
                    console.log('[JAVDB] Parsed actor_count count:', Object.keys(actorCount).length);
                    
                    if ($('.item').length > 0) {
                        highlightVideos(javIds);
                    }
                    if ($('.actor-box').length > 0) {
                        highlightActors(actorCount);
                    }
                } catch (e) {
                    console.error('[JAVDB] JSON parse error:', e);
                }
            },
            onerror: function(error) {
                console.error('[JAVDB] Fetch error:', error);
            }
        });
    }

    if (window.jQuery) {
        init();
    } else {
        $(document).ready(init);
    }
})();