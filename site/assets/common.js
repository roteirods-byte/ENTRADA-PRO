// site/assets/common.js
(() => {
  'use strict';

  const REFRESH_MS = 15 * 60 * 1000;

  const API = {
    version: '/api/version',
    pro: '/api/pro',
    top10: '/api/top10',
  };

  function $(id) { return document.getElementById(id); }

  const COLS_FULL = [
    'PAR', 'SIDE', 'ENTRADA', 'ATUAL', 'ALVO', 'GANHO_PCT', 'ASSERT_PCT', 'PRAZO', 'ZONA', 'RISCO', 'PRIORIDADE', 'DATA', 'HORA', 'PRICE_SOURCE'
  ];

  const COLS_TOP10 = [
    'PAR', 'SIDE', 'ENTRADA', 'ATUAL', 'ALVO', 'GANHO_PCT', 'ASSERT_PCT', 'PRAZO', 'ZONA', 'RISCO', 'PRIORIDADE', 'DATA', 'HORA'
  ];

  function detectKind() {
    // 1) pelo <body data-kind="...">
    const dk = document.body?.dataset?.kind;
    if (dk === 'top10' || dk === 'full') return dk;

    // 2) pelo nome do arquivo (full.html / top10.html)
    const p = (location.pathname || '').toLowerCase();
    if (p.endsWith('/top10.html') || p.endsWith('top10.html')) return 'top10';
    if (p.endsWith('/full.html') || p.endsWith('full.html')) return 'full';

    // 3) pelo hash do index.html (#top10.html / #full.html)
    const h = (location.hash || '').toLowerCase();
    if (h.includes('top10')) return 'top10';
    return 'full';
  }

  function fmtBrt(isoOrNull) {
    if (!isoOrNull) return '-';
    try {
      const d = new Date(isoOrNull);
      const parts = new Intl.DateTimeFormat('pt-BR', {
        timeZone: 'America/Sao_Paulo',
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit',
      }).formatToParts(d);
      const map = Object.fromEntries(parts.map(p => [p.type, p.value]));
      return `${map.day}/${map.month}/${map.year} ${map.hour}:${map.minute}`;
    } catch {
      return '-';
    }
  }

  function splitDataHora(brtStr) {
    if (!brtStr || brtStr === '-') return { data: '-', hora: '-' };
    const [data, hora] = brtStr.split(' ');
    return { data: data || '-', hora: hora || '-' };
  }

  function fmtPct(n) {
    const v = Number(n);
    if (!Number.isFinite(v)) return '-';
    return `${v.toFixed(2)}%`;
  }

  function fmtPrice(n) {
    const v = Number(n);
    if (!Number.isFinite(v)) return '-';
    const a = Math.abs(v);
    if (a > 0 && a < 1) return v.toFixed(8);
    return v.toFixed(3);
  }

  function classSide(v) {
    const s = String(v || '').toUpperCase();
    if (s === 'LONG') return 'side-long';
    if (s === 'SHORT') return 'side-short';
    return '';
  }

  function classPct(v) {
    const n = Number(v);
    if (!Number.isFinite(n)) return '';
    return n >= 0 ? 'pct-pos' : 'pct-neg';
  }

  function classRisco(v) {
    const s = String(v || '').toUpperCase();
    if (s.includes('ALTO')) return 'risco-alto';
    if (s.includes('MÉDIO') || s.includes('MEDIO')) return 'risco-medio';
    if (s.includes('BAIXO')) return 'risco-baixo';
    return '';
  }

  async function fetchJson(url) {
    const res = await fetch(url, { headers: { accept: 'application/json' }, cache: 'no-store' });
    if (!res.ok) throw new Error(`http_${res.status}`);
    return res.json();
  }

  function setMeta(meta, itemsLen) {
    const el = $('meta');
    if (!el) return;

    const updatedBrt = fmtBrt(meta?.updated_at || meta?.raw?.updated_at || meta?.raw?.updated_utc);
    const source = meta?.source || '-';
    el.textContent = `Atualizado (BRT): ${updatedBrt} • Itens: ${itemsLen} • Fonte: ${source}`;
  }

  function renderTable(kind, items, meta) {
    const cols = kind === 'top10' ? COLS_TOP10 : COLS_FULL;
    const brt = fmtBrt(meta?.updated_at || meta?.raw?.updated_at || meta?.raw?.updated_utc);
    const { data, hora } = splitDataHora(brt);

    const label = (c) => c
      .replace('_PCT', ' %')
      .replace('PRICE_SOURCE', 'PRICE');

    const thead = cols.map(c => `<th>${label(c)}</th>`).join('');
    const rows = (items || []).map(it => {
      return '<tr>' + cols.map(c => {
        const raw = it?.[c];
        if (c === 'DATA') return `<td>${it?.DATA || data}</td>`;
        if (c === 'HORA') return `<td>${it?.HORA || hora}</td>`;

        if (c === 'PAR') return `<td class="mono">${raw ?? '-'}</td>`;
        if (c === 'SIDE') return `<td class="${classSide(raw)}">${raw ?? '-'}</td>`;
        if (c === 'GANHO_PCT') return `<td class="${classPct(raw)}">${fmtPct(raw)}</td>`;
        if (c === 'ASSERT_PCT') return `<td class="pct">${fmtPct(raw)}</td>`;
        if (c === 'ENTRADA' || c === 'ATUAL' || c === 'ALVO') return `<td class="mono">${fmtPrice(raw)}</td>`;
        if (c === 'RISCO') return `<td class="${classRisco(raw)}">${raw ?? '-'}</td>`;
        return `<td>${raw ?? '-'}</td>`;
      }).join('') + '</tr>';
    }).join('');

    return `<table class="t"><thead><tr>${thead}</tr></thead><tbody>${rows}</tbody></table>`;
  }

  async function loadKind(kind) {
    try {
      const url = (kind === 'top10') ? API.top10 : API.pro;
      const json = await fetchJson(url);
      const items = Array.isArray(json.items) ? json.items : (json.items ? [json.items] : []);
      setMeta(json, items.length);

      const target = $('table');
      if (target) target.innerHTML = renderTable(kind, items, json);
    } catch (e) {
      const target = $('table');
      if (target) target.innerHTML = `<div class="err">API indisponível.</div>`;
      const meta = $('meta');
      if (meta) meta.textContent = 'Atualizado (BRT): - • Itens: 0 • Fonte: -';
      console.error(e);
    }
  }

  function boot() {
    const kind = detectKind();
    loadKind(kind);

    clearInterval(window.__entradaProTimer);
    window.__entradaProTimer = setInterval(() => loadKind(kind), REFRESH_MS);
  }

  window.addEventListener('load', boot);
})();
