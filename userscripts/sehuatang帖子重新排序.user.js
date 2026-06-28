// ==UserScript==
// @name         sehuatang 帖子排序
// @namespace    http://tampermonkey.net/
// @version      1.1
// @description  对sehuatang页面的帖子进行排序：AI/裸舞优先蓝色加粗，其他按查看数排序；帖子页ed2k复制代码改为打开链接
// @match        https://www.sehuatang.net/*
// @grant        GM_xmlhttpRequest
// @grant        GM_registerMenuCommand
// @grant        GM_getValue
// @grant        GM_setValue
// @require      https://cdn.bootcdn.net/ajax/libs/jquery/3.6.0/jquery.min.js
// @run-at       document-idle
// ==/UserScript==

(function($) {
    'use strict';

    const aiKeywords = (GM_getValue('aiKeywords', '') || 'ai,裸舞').split(',').map(s => s.trim()).filter(Boolean);
    const notAiKeywords = (GM_getValue('notAiKeywords', '') || '').split(',').map(s => s.trim()).filter(Boolean);

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
        const matched = aiKeywords.some(k => title.includes(k.toLowerCase()));
        if (!matched) return false;
        if (notAiKeywords.length === 0) return true;
        return !notAiKeywords.some(k => title.includes(k.toLowerCase()));
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

    function convertCopyToOpen() {
        $('div.blockcode').each(function() {
            const $block = $(this);
            const $em = $block.find('em').first();
            if ($em.length === 0) return;

            const links = [];
            $block.find('li').each(function() {
                const text = $(this).text().trim();
                if (text.startsWith('ed2k://')) {
                    links.push(text);
                }
            });
            if (links.length === 0) return;

            const $newEm = $('<em>').text('打开链接').css('cursor', 'pointer');
            $newEm.on('click', function(e) {
                e.preventDefault();
                links.forEach(link => window.open(link));
            });
            $em.replaceWith($newEm);
        });
    }

    function promptKeywords(key, label, defaultValue) {
        const current = GM_getValue(key, '') || defaultValue;
        const input = prompt(`请输入${label}（多个关键词用英文逗号分隔）`, current);
        if (input !== null) {
            GM_setValue(key, input.trim());
            location.reload();
        }
    }

    GM_registerMenuCommand('设置 AI 优先关键词', () => promptKeywords('aiKeywords', 'AI优先关键词', 'ai,裸舞'));
    GM_registerMenuCommand('设置 AI 排除关键词', () => promptKeywords('notAiKeywords', 'AI排除关键词', ''));

    function initSort() {
        setTimeout(sortThreads, 500);
        setTimeout(convertCopyToOpen, 500);
    }

    $(document).ready(initSort);
})(jQuery);
