// ==UserScript==
// @name         Humble Bundle -> Steam Link
// @namespace    http://tampermonkey.net/
// @version      2.0
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

            const newLink = document.createElement('a');
            for (const attr of link.attributes) {
                if (attr.name !== 'href') {
                    newLink.setAttribute(attr.name, attr.value);
                }
            }
            newLink.href = steamUrl;
            newLink.target = '_blank';
            newLink.rel = 'noopener noreferrer';
            newLink.classList.add('hb-steam-link');
            while (link.firstChild) {
                newLink.appendChild(link.firstChild);
            }
            link.parentNode.replaceChild(newLink, link);
        });
    }

    updateLinks();
    const observer = new MutationObserver(updateLinks);
    observer.observe(document.body, { childList: true, subtree: true });
    setTimeout(() => observer.disconnect(), 30000);
})();