// ==UserScript==
// @name         AnalVids BTDig Search
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  在 analvids 视频页添加 BTDig 搜索按钮
// @match        https://www.analvids.com/*/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    function getTitle() {
        const h1 = document.querySelector('h1.watch__title');
        if (!h1) return null;
        const clone = h1.cloneNode(true);
        const span = clone.querySelector('.watch__featuring_models');
        if (span) span.remove();
        return clone.textContent.trim();
    }

    function getDate() {
        const el = document.querySelector('i.bi.bi-calendar3');
        console.log('[debug] calendar element:', el);
        if (!el) return '';
        const raw = el.textContent.trim();
        console.log('[debug] calendar text:', raw);
        const m = raw.match(/\[(\d{4}-\d{2}-\d{2})\]/);
        if (m) return m[0];
        const n = raw.match(/(\d{4}-\d{2}-\d{2})/);
        return n ? '[' + n[1] + ']' : '';
    }

    function addButtons() {
        const title = getTitle();
        const date = getDate();
        if (!title) return;

        const container = document.querySelector('.watch__title')?.closest('.container-fluid');
        if (!container) return;

        const wrapper = document.createElement('div');
        wrapper.className = 'mt-15';
        wrapper.style.display = 'flex';
        wrapper.style.gap = '10px';

        const btdigBtn = document.createElement('a');
        btdigBtn.href = 'https://www.btdig.com/search?q=' + encodeURIComponent(title);
        btdigBtn.target = '_blank';
        btdigBtn.rel = 'noopener noreferrer';
        btdigBtn.textContent = 'BTDig Search';
        btdigBtn.className = 'btn btn-primary';

        const copyBtn = document.createElement('button');
        copyBtn.textContent = 'Copy Title';
        copyBtn.className = 'btn btn-primary';
        copyBtn.addEventListener('click', function() {
            const text = (date ? date + ' ' : '') + title;
            console.log('[debug] date:', JSON.stringify(date), 'title:', JSON.stringify(title), 'final:', JSON.stringify(text));
            navigator.clipboard.writeText(text).then(function() {
                copyBtn.textContent = 'Copied!';
                setTimeout(function() { copyBtn.textContent = 'Copy Title'; }, 2000);
            });
        });

        wrapper.appendChild(btdigBtn);
        wrapper.appendChild(copyBtn);
        container.appendChild(wrapper);
    }

    function init() {
        const h1 = document.querySelector('h1.watch__title');
        if (!h1) {
            console.log('[debug] h1.watch__title not found, retrying in 1s');
            setTimeout(init, 1000);
            return;
        }
        addButtons();
    }

    if (document.readyState === 'complete') {
        init();
    } else {
        window.addEventListener('load', init);
    }
})();
