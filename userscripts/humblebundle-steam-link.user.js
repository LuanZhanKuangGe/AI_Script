// ==UserScript==
// @name         Humble Bundle -> Steam Link
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  Redirect Humble Bundle game tiles to their Steam search page
// @author       You
// @match        https://zh.humblebundle.com/games/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    function getGameData() {
        const script = document.querySelector('script#webpack-bundle-page-data[type="application/json"]');
        if (!script) {
            console.log('[HB->Steam] No webpack data found, retrying...');
            return null;
        }
        try {
            const data = JSON.parse(script.textContent);
            if (!data.bundleData) return null;
            const games = new Map();
            for (const [key, game] of Object.entries(data.bundleData)) {
                if (game.human_name) {
                    games.set(key, game.human_name);
                }
            }
            console.log(`[HB->Steam] Loaded ${games.size} games`);
            return games;
        } catch (e) {
            console.error('[HB->Steam] Parse error:', e);
            return null;
        }
    }

    function updateLinks(games) {
        const links = document.querySelectorAll('a[href*="/store/"]');
        let updated = 0;
        links.forEach(link => {
            const match = link.getAttribute('href').match(/\/store\/([^/?]+)/);
            if (!match) return;
            const machineName = match[1];
            const gameTitle = games.get(machineName);
            if (gameTitle && !link.dataset.hbSteam) {
                link.dataset.hbSteam = '1';
                link.href = `https://store.steampowered.com/search/?term=${encodeURIComponent(gameTitle)}`;
                link.target = '_blank';
                updated++;
            }
        });
        if (updated > 0) console.log(`[HB->Steam] Updated ${updated} links`);
    }

    const games = getGameData();
    if (games) {
        setTimeout(() => updateLinks(games), 1500);
        const observer = new MutationObserver(() => updateLinks(games));
        observer.observe(document.body, { childList: true, subtree: true });
        setTimeout(() => observer.disconnect(), 30000);
    }
})();