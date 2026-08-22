// ==UserScript==
// @name         Humble Bundle -> Steam Link
// @namespace    http://tampermonkey.net/
// @version      3.0
// @description  Redirect Humble Bundle game tiles to their Steam search page
// @author       You
// @match        https://zh.humblebundle.com/games/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    function updateLinks() {
        const tiles = document.querySelectorAll('.tier-item-view');
        tiles.forEach(tile => {
            if (tile.dataset.hbSteam) return;
            tile.dataset.hbSteam = '1';

            const link = tile.querySelector('a.item-details, a.js-item-details');
            const titleEl = tile.querySelector('.item-title');
            if (!link || !titleEl) return;

            const gameTitle = titleEl.textContent.trim();
            if (!gameTitle) return;

            const steamUrl = `https://store.steampowered.com/search/?term=${encodeURIComponent(gameTitle)}`;

            link.href = steamUrl;
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
            link.classList.remove('js-item-details');
            link.addEventListener('click', function(e) {
                e.stopPropagation();
            });
        });
    }

    updateLinks();
    const observer = new MutationObserver(updateLinks);
    observer.observe(document.body, { childList: true, subtree: true });
    setTimeout(() => observer.disconnect(), 30000);
})();