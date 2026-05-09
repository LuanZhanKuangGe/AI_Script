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

    function addButton() {
        const title = getTitle();
        if (!title) return;

        const container = document.querySelector('.watch__title')?.closest('.container-fluid');
        if (!container) return;

        const btn = document.createElement('a');
        btn.href = 'https://www.btdig.com/search?q=' + encodeURIComponent(title);
        btn.target = '_blank';
        btn.rel = 'noopener noreferrer';
        btn.textContent = 'BTDig Search';
        btn.className = 'btn btn-primary mt-15';
        btn.style.marginLeft = '10px';
        container.appendChild(btn);
    }

    window.addEventListener('load', addButton);
})();
