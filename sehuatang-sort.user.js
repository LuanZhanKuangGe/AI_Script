// ==UserScript==
// @name         sehuatang 帖子排序
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  对sehuatang页面的帖子进行排序：AI/裸舞优先蓝色加粗，其他按查看数排序
// @match        https://www.sehuatang.net/*
// @grant        GM_xmlhttpRequest
// @require      https://cdn.bootcdn.net/ajax/libs/jquery/3.6.0/jquery.min.js
// @run-at       document-idle
// ==/UserScript==

(function($) {
    'use strict';

    const aiKeywords = ['ai', '裸舞'];

    function getTitle(element) {
        const titleLink = $(element).find('a.xst')[0];
        return titleLink ? $(titleLink).text().toLowerCase() : '';
    }

    function getViewCount(element) {
        const viewEm = $(element).find('td.num em')[0];
        if (viewEm) {
            return parseInt($(viewEm).text().replace(/,/g, ''), 10) || 0;
        }
        return 0;
    }

    function isPriority(title) {
        return aiKeywords.some(k => title.includes(k.toLowerCase()));
    }

    function sortThreads() {
        console.log('[Sort] === 开始排序 ===');
        
        const $threads = $('tbody[id^="normalthread_"]');
        console.log('[Sort] 找到帖子数量:', $threads.length);
        
        if ($threads.length === 0) {
            return;
        }

        const threads = $threads.map(function() {
            const title = getTitle(this);
            const viewCount = getViewCount(this);
            return {
                id: this.id,
                title: title.substring(0, 50),
                viewCount: viewCount,
                priority: isPriority(title)
            };
        }).get();

        console.log('[Sort] 帖子详情:', threads);

        const priorityThreads = threads.filter(t => t.priority);
        const normalThreads = threads.filter(t => !t.priority);

        normalThreads.sort((a, b) => b.viewCount - a.viewCount);

        console.log('[Sort] 分类: 优先=', priorityThreads.length, '普通=', normalThreads.length);

        const $table = $('#threadlisttableid');
        
        const firstBefore = $table.children('tbody[id^="normalthread_"]').first().attr('id');
        console.log('[Sort] 排序前第一个:', firstBefore);
        
        const $allThreads = $table.children('tbody[id^="normalthread_"]').detach();
        
        priorityThreads.forEach((t) => {
            const $el = $allThreads.filter('#' + t.id);
            if ($el.length > 0) {
                $table.append($el);
                $el.find('a.xst').css({'color': 'blue', 'font-weight': 'bold'});
            }
        });
        normalThreads.forEach((t) => {
            const $el = $allThreads.filter('#' + t.id);
            if ($el.length > 0) {
                $table.append($el);
            }
        });
        
        const firstAfter = $table.children('tbody[id^="normalthread_"]').first().attr('id');
        console.log('[Sort] 排序后第一个:', firstAfter);
        console.log('[Sort] 排序后帖子数量:', $table.children('tbody[id^="normalthread_"]').length);
        console.log('[Sort] === 排序结束 ===');
    }

    function initSort() {
        setTimeout(sortThreads, 500);
    }

    $(document).ready(initSort);
})(jQuery);
