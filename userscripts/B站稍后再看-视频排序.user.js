// ==UserScript==
// @name         B站稍后再看-视频排序
// @namespace    https://www.bilibili.com/
// @version      1.6.0
// @description  在稍后再看页面的筛选区添加“视频排序”一行（样式同“全部时长”行，随“更多筛选”显隐）：作者 / 时长 / 已播放时间；刷新页面后恢复默认顺序
// @author       you
// @match        https://www.bilibili.com/watchlater/*
// @run-at       document-end
// @grant        none
// ==/UserScript==

(function () {
  'use strict';

  const CARD_SEL = '.video-card';
  const GRID_SEL = '.watchlater-list-grid, .watchlater-list-container';
  const ROW_ID = 'wl-sort-row';
  const COALESCE_MS = 250;

  const MODES = [
    { value: 'author', label: '作者' },
    { value: 'duration', label: '时长' },
    { value: 'played', label: '观看进度' },
    { value: 'pubdate', label: '发布日期' },
  ];

  let currentMode = 'default';

  const CSS = `
#${ROW_ID}{align-items:center;gap:8px;width:100%;display:flex;margin-top:12px}
#${ROW_ID} .wl-btn{box-sizing:border-box;text-align:center;cursor:pointer;user-select:none;flex:none;width:100px;height:34px;color:var(--text2,#61666d);border-radius:6px;padding:10px 0;font-size:15px;font-weight:500;line-height:normal;transition:background-color .3s}
#${ROW_ID} .wl-btn:hover{background-color:var(--bg2,#f1f2f3)}
#${ROW_ID} .wl-btn.active{color:var(--brand_blue,#00aeec);background-color:var(--brand_blue_thin,rgba(0,174,236,.1))}
`;

  let cssInjected = false;
  function injectCSS() {
    if (cssInjected) return;
    cssInjected = true;
    const style = document.createElement('style');
    style.textContent = CSS;
    document.head.appendChild(style);
  }

  function parseTimeToSec(s) {
    if (!s || !/^\d{1,3}(:\d{2}){1,2}$/.test(s)) return NaN;
    return s.split(':').reduce((acc, v) => acc * 60 + Number(v), 0);
  }

  function getProgressPct(card) {
    const el = card.querySelector('.bili-cover-card__progress');
    if (!el) return NaN;
    const raw = el.style.getPropertyValue('--bili-cover-card-progress-value');
    const n = parseFloat(raw);
    return isNaN(n) ? NaN : n;
  }

  function extractCardData(card) {
    const authorEl = card.querySelector('.video-card__right a.stat.author');
    const author = authorEl ? authorEl.textContent.trim() : '';

    let duration = NaN;
    let played = NaN;

    const statEls = card.querySelectorAll('.bili-cover-card__stat');
    for (const el of statEls) {
      const text = (el.textContent || '').trim();
      if (!text) continue;
      if (text === '已看完') {
        played = Infinity;
        continue;
      }
      const m = text.match(/^(?:([\d:]+)\s*\/\s*)?([\d:]+)$/);
      if (!m) continue;
      duration = parseTimeToSec(m[2]);
      if (m[1]) {
        played = parseTimeToSec(m[1]);
      } else {
        const pct = getProgressPct(card);
        played = isNaN(pct) || isNaN(duration) ? NaN : Math.round((duration * pct) / 100);
      }
      break;
    }

    return { author, duration, played };
  }

  const dataCache = new Map();

  function getCardKey(card) {
    const a = card.querySelector('a[href*="bvid="]');
    const href = a ? a.getAttribute('href') || '' : '';
    const m = href.match(/[?&]bvid=([A-Za-z0-9]+)/);
    return m ? m[1] : null;
  }

  function getData(card, key) {
    if (key) {
      const hit = dataCache.get(key);
      if (hit) return hit;
      const d = extractCardData(card);
      dataCache.set(key, d);
      return d;
    }
    return extractCardData(card);
  }

  const apiData = new Map();
  let apiFetchPromise = null;

  async function fetchPage(pn, ps) {
    const u = new URL('https://api.bilibili.com/x/v2/history/toview/web');
    u.searchParams.set('pn', String(pn));
    u.searchParams.set('ps', String(ps));
    u.searchParams.set('asc', '0');
    u.searchParams.set('need_split', '1');
    const res = await fetch(u.href, { credentials: 'include' });
    return res.json();
  }

  function fetchAllWatchlater(force) {
    if (apiFetchPromise && !force) return apiFetchPromise;
    apiFetchPromise = (async () => {
      const out = new Map();
      try {
        let ps = 100;
        for (let pn = 1; pn <= 100; pn++) {
          let j = null;
          try {
            j = await fetchPage(pn, ps);
          } catch (e) {
            break;
          }
          if (!j || j.code !== 0) {
            if (pn === 1 && ps === 100 && j && j.code !== 0) {
              ps = 20;
              try {
                j = await fetchPage(1, ps);
              } catch (e2) {
                break;
              }
              if (!j || j.code !== 0) break;
            } else {
              break;
            }
          }
          const list = (j.data && j.data.list) || [];
          for (const it of list) {
            if (it && it.bvid) {
              out.set(it.bvid, {
                author: (it.owner && it.owner.name) || '',
                duration: +it.duration || NaN,
                progress: it.progress,
                pubdate: +it.pubdate || 0,
              });
            }
          }
          const total = (j.data && j.data.count) || 0;
          if (!list.length || out.size >= total) break;
        }
      } catch (e) {}
      if (out.size) {
        apiData.clear();
        for (const [k, v] of out) apiData.set(k, v);
      }
      return apiData;
    })();
    return apiFetchPromise;
  }

  function getMerged(card, key) {
    const dom = getData(card, key);
    const api = key ? apiData.get(key) : null;
    if (!api) return { author: dom.author, duration: dom.duration, played: dom.played, pubdate: 0 };
    const duration = api.duration > 0 ? api.duration : dom.duration;
    let played = dom.played;
    if (api.progress === -1) {
      played = duration;
    } else if (api.progress > 0) {
      played = Math.min(api.progress, duration || api.progress);
    } else if (api.progress === 0) {
      played = 0;
    }
    return {
      author: api.author || dom.author,
      duration,
      played,
      pubdate: api.pubdate || 0,
    };
  }

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  let suspendSorting = false;

  let loadAllPromise = null;
  function ensureAllLoaded() {
    if (loadAllPromise) return loadAllPromise;
    suspendSorting = true;
    loadAllPromise = (async () => {
      const startTop = window.scrollY;
      let lastN = -1;
      let stable = 0;
      try {
        for (let i = 0; i < 300; i++) {
          const n = getCards().length;
          stable = n === lastN ? stable + 1 : 0;
          lastN = n;
          if (stable >= 6) break;
          window.scrollTo(0, document.documentElement.scrollHeight);
          await sleep(350);
        }
      } finally {
        window.scrollTo(0, startTop);
        suspendSorting = false;
        loadAllPromise = null;
      }
      return lastN;
    })();
    return loadAllPromise;
  }

  function getCards() {
    const out = [];
    const all = document.querySelectorAll(CARD_SEL);
    for (const c of all) {
      const p = c.parentElement;
      if (p && p.matches(GRID_SEL) && !c.classList.contains('video-skeleton-card')) {
        out.push(c);
      }
    }
    return out;
  }

  let lastSig = null;
  let ordersApplied = false;

  function numCmp(a, b, desc) {
    const ax = isNaN(a) ? (desc ? -Infinity : Infinity) : a;
    const bx = isNaN(b) ? (desc ? -Infinity : Infinity) : b;
    if (ax === bx) return 0;
    const r = ax < bx ? -1 : 1;
    return desc ? -r : r;
  }

  function applySort(force) {
    const cards = getCards();

    if (currentMode === 'default') {
      if (ordersApplied) {
        for (const c of cards) c.style.removeProperty('order');
        ordersApplied = false;
        lastSig = null;
      }
      return;
    }

    const n = cards.length;
    if (!n) return;

    const keys = new Array(n);
    const datas = new Array(n);
    for (let i = 0; i < n; i++) {
      const k = getCardKey(cards[i]);
      keys[i] = k;
      datas[i] = getMerged(cards[i], k);
    }

    const sig = currentMode + '|' + keys.join(',');

    if (!force && sig === lastSig) {
      let arranged = true;
      for (let i = 0; i < n; i++) {
        if (cards[i].style.getPropertyValue('order') === '') {
          arranged = false;
          break;
        }
      }
      if (arranged) return;
    }

    const idx = new Array(n);
    for (let i = 0; i < n; i++) idx[i] = i;

    if (currentMode === 'author') {
      const count = Object.create(null);
      if (apiData.size) {
        for (const v of apiData.values()) {
          if (v.author) count[v.author] = (count[v.author] || 0) + 1;
        }
      } else {
        for (let i = 0; i < n; i++) {
          const a = datas[i].author;
          if (a) count[a] = (count[a] || 0) + 1;
        }
      }
      idx.sort((a, b) => {
        const ca = count[datas[a].author] || 0;
        const cb = count[datas[b].author] || 0;
        if (ca !== cb) return cb - ca;
        const an = datas[a].author || '';
        const bn = datas[b].author || '';
        if (an !== bn) return an < bn ? -1 : 1;
        return a - b;
      });
    } else if (currentMode === 'duration') {
      idx.sort((a, b) => numCmp(datas[a].duration, datas[b].duration, false) || a - b);
    } else if (currentMode === 'played') {
      idx.sort((a, b) => numCmp(datas[a].played, datas[b].played, true) || a - b);
    } else if (currentMode === 'pubdate') {
      idx.sort((a, b) => numCmp(datas[a].pubdate, datas[b].pubdate, true) || a - b);
    }

    const rank = new Array(n);
    for (let r = 0; r < n; r++) rank[idx[r]] = r;

    const groups = new Map();
    for (const c of cards) {
      const p = c.parentElement;
      if (p && !groups.has(p)) groups.set(p, true);
    }

    const cardIndexMap = new Map();
    cards.forEach((c, i) => cardIndexMap.set(c, i));

    for (const p of groups.keys()) {
      let tail = 100000;
      for (const child of p.children) {
        const ci = cardIndexMap.get(child);
        if (ci !== undefined) {
          child.style.order = rank[ci];
        } else {
          child.style.order = ++tail;
        }
      }
    }

    ordersApplied = true;
    lastSig = sig;
  }

  function setMode(mode) {
    const repeat = mode === currentMode;
    currentMode = mode;
    refreshActiveState();
    if (mode === 'default') {
      applySort(false);
      return;
    }
    if (repeat) {
      dataCache.clear();
      lastSig = null;
    }
    applySort(repeat);
    (async () => {
      try {
        await fetchAllWatchlater(true);
      } catch (e) {}
      if (!apiData.size) {
        try {
          await ensureAllLoaded();
        } catch (e) {}
      }
      lastSig = null;
      applySort(true);
    })();
  }

  function refreshActiveState() {
    const row = document.getElementById(ROW_ID);
    if (!row) return;
    const labelBtn = row.querySelector('.wl-label');
    if (labelBtn) labelBtn.classList.toggle('active', currentMode === 'default');
    row.querySelectorAll('.wl-opt').forEach((b) => {
      b.classList.toggle('active', b.dataset.mode === currentMode);
    });
  }

  function buildRow() {
    const row = document.createElement('div');
    row.id = ROW_ID;

    const label = document.createElement('div');
    label.className = 'wl-btn wl-label';
    label.textContent = '视频排序';
    label.title = '点击恢复默认排序';
    label.addEventListener('click', () => setMode('default'));
    row.appendChild(label);

    for (const m of MODES) {
      const btn = document.createElement('div');
      btn.className = 'wl-btn wl-opt';
      btn.dataset.mode = m.value;
      btn.textContent = m.label;
      btn.addEventListener('click', () => setMode(m.value));
      row.appendChild(btn);
    }

    refreshActiveState();
    return row;
  }

  function findExtraPanel() {
    const extra = document.querySelector('.list-header-extra');
    if (!extra || !extra.querySelector('.list-header-filter')) return null;
    return extra;
  }

  function findAnchor(extra) {
    const filters = extra.querySelectorAll('.list-header-filter');
    let target = null;
    for (const f of filters) {
      let isDuration = false;
      for (const c of f.children) {
        if ((c.textContent || '').trim() === '全部时长') {
          isDuration = true;
          break;
        }
      }
      if (isDuration) {
        target = f;
        break;
      }
    }
    return target || filters[filters.length - 1];
  }

  function ensureUI() {
    const extra = findExtraPanel();
    let row = document.getElementById(ROW_ID);
    if (!extra) {
      if (row && row.isConnected) row.remove();
      return;
    }
    const anchor = findAnchor(extra);
    injectCSS();
    if (!row) row = buildRow();
    if (anchor.nextElementSibling !== row) {
      anchor.insertAdjacentElement('afterend', row);
    }
    refreshActiveState();
  }

  let coalesceTimer = null;
  function coalesce() {
    if (coalesceTimer) return;
    coalesceTimer = setTimeout(() => {
      coalesceTimer = null;
      if (suspendSorting) return;
      ensureUI();
      if (currentMode !== 'default') applySort(false);
    }, COALESCE_MS);
  }

  const mo = new MutationObserver(coalesce);
  mo.observe(document.body, { childList: true, subtree: true });

  injectCSS();
  ensureUI();

  (async () => {
    let waited = 0;
    while (getCards().length === 0 && waited < 15000) {
      await sleep(300);
      waited += 300;
    }
    if (getCards().length === 0) return;
    await sleep(500);
    try {
      await ensureAllLoaded();
    } catch (e) {}
    lastSig = null;
    applySort(false);
    ensureUI();
  })();
})();
