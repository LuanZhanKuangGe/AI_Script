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

    function highlightVideos(javIds, actorCount) {
        console.log('[JAVDB] Total IDs from API:', javIds.length);
        console.log('[JAVDB] Current path:', window.location.pathname);
        
        if (window.location.pathname.startsWith('/actors/') && window.location.pathname !== '/actors' && window.location.pathname !== '/actors/censored' && !window.location.pathname.endsWith('/actors')) {
            console.log('[JAVDB] Actor detail page with items');
            
            console.log('[JAVDB] Actor-tags found:', $('.actor-tags a.tag').length);
            
            const boldTags = [];
            $('.actor-tags a.tag').each(function() {
                const tagText = $(this).text();
                console.log('[JAVDB] Tag text:', tagText);
                const keywords = ['中出', '多P', '凌辱', '強姦', '輪姦', '性騷擾', '魔鬼系'];
                for (const keyword of keywords) {
                    if (tagText.includes(keyword)) {
                        console.log('[JAVDB] Matched keyword:', keyword);
                        $(this).css('font-weight', 'bold').css('color', 'blue');
                        boldTags.push($(this));
                        break;
                    }
                }
            });
            
            const subtitleTag = $('.actor-tags a.tag:contains("含字幕")');
            if (subtitleTag.length && boldTags.length > 0) {
                boldTags.forEach(function(tag) {
                    subtitleTag.after(tag);
                });
            }
            
            const grid = $('.movie-list, .grid, .grid-view, .columns.grid, .video-grid');
            console.log('[JAVDB] Grid found:', grid.length);
            if (grid.length) {
                console.log('[JAVDB] Item grid found, will sort after highlighting');
                console.log('[JAVDB] Grid class:', grid.attr('class'));
            }
        } else if (window.location.pathname === '/actors/censored' || window.location.pathname === '/actors' || window.location.pathname.match(/\/actors\?/)) {
            console.log('[JAVDB] Actor list page');
            
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
        
        const grid = $('.movie-list, .grid, .grid-view, .columns.grid, .video-grid');
        if (grid.length && window.location.pathname.startsWith('/actors/') && window.location.pathname !== '/actors' && window.location.pathname !== '/actors/censored' && !window.location.pathname.endsWith('/actors')) {
            const items = grid.find('.item');
            console.log('[JAVDB] Items count after highlight:', items.length);
            const sortedItems = items.sort(function(a, b) {
                const aHasTag = $(a).find('.tag.is-danger:contains("已收录")').length > 0;
                const bHasTag = $(b).find('.tag.is-danger:contains("已收录")').length > 0;
                console.log('[JAVDB] aHasTag:', aHasTag, 'bHasTag:', bHasTag);
                if (aHasTag && !bHasTag) return -1;
                if (!aHasTag && bHasTag) return 1;
                return 0;
            });
            grid.append(sortedItems);
        }
        
        if (window.location.pathname.startsWith('/v/')) {
            const idEl = $('h2 strong').first();
            const videoId = idEl.text().trim();
            console.log('[JAVDB] Video detail page, ID:', videoId);
            
            const reviewButtons = $('.review-buttons');
            if (reviewButtons.length && videoId) {
                const missavBtn = '<a class="button is-info is-outlined" href="https://missav.ws/dm58/cn/' + videoId + '" target="_blank"><span class="icon is-small"><i class="icon-search"></i></span><span>missav</span></a>';
                const javlibraryBtn = '<a class="button is-info is-outlined" href="https://www.javlibrary.com/cn/vl_searchbyid.php?keyword=' + videoId + '" target="_blank"><span class="icon is-small"><i class="icon-search"></i></span><span>javlibrary</span></a>';
                const javbusBtn = '<a class="button is-info is-outlined" href="https://www.javbus.com/search/' + videoId + '" target="_blank"><span class="icon is-small"><i class="icon-search"></i></span><span>javbus</span></a>';
                const btdigBtn = '<a class="button is-info is-outlined" href="https://www.btdig.com/search?q=' + videoId + '" target="_blank"><span class="icon is-small"><i class="icon-search"></i></span><span>btdig</span></a>';
                reviewButtons.find('.buttons').first().prepend(btdigBtn + javbusBtn + javlibraryBtn + missavBtn);
            }
        }
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
                    
                    if ($('.item').length > 0 || $('.actor-box').length > 0) {
                        highlightVideos(javIds, actorCount);
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