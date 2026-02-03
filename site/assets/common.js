/* ENTRADA PRO - common.js (revisado)
   Regras principais:
   - FULL: base (77 moedas)
   - TOP10: copia do FULL (top 10)
   - Cores:
     * GANHO %: >= 3% verde, < 3% vermelho
     * ASSERT %: >= 65% verde, < 65% vermelho
     * SIDE: LONG verde, SHORT vermelho, NAO ENTRAR amarelo
     * ZONA / PRIORIDADE: BAIXA verde, MEDIA laranja, ALTA vermelho
   - Sem pagina extra
*/

'use strict';

const CACHE_BUST = Date.now();

function q(sel) { return document.querySelector(sel); }

// ===== Colunas =====
const COLS_FULL = [
  ['PAR', 'par'],
  ['SIDE', 'side'],
  ['ENTRADA', 'entrada'],
  ['ATUAL', 'atual'],
  ['ALVO', 'alvo'],
  ['GANHO %', 'ganho_pct'],
  ['ASSERT %', 'assert_pct'],
  ['PRAZO', 'prazo'],
  ['ZONA', 'zona'],
  ['RISCO', 'risco'],
  ['PRIORIDADE', 'prioridade'],
  ['DATA', 'data'],
  ['HORA', 'hora'],
];

const COLS_TOP10 = [
  ['PAR', 'par'],
  ['SIDE', 'side'],
  ['ENTRADA', 'entrada'],
  ['ATUAL', 'atual'],
  ['ALVO', 'alvo'],
  ['GANHO %', 'ganho_pct'],
  ['ASSERT %', 'assert_pct'],
  ['PRAZO', 'prazo'],
  ['ZONA', 'zona'],
  ['RISCO', 'risco'],
  ['PRIORIDADE', 'prioridade'],
  ['DATA', 'data'],
  ['HORA', 'hora'],
];

// ===== Formatacao =====
function toNum(v) {
  if (v === null || v === undefined) return NaN;
  const s = String(v).replace(',', '.').trim();
  const n = Number(s);
  return Number.isFinite(n) ? n : NaN;
}

function fmtPrice(v) {
  const n = toNum(v);
  if (!Number.isFinite(n)) return v == null ? '-' : String(v);
  const abs = Math.abs(n);
  if (abs > 0 && abs < 1) return n.toFixed(8); // moedas pequenas
  return n.toFixed(3);
}

function fmtPct(v) {
  const n = toNum(v);
  if (!Number.isFinite(n)) return v == null ? '-' : String(v);
  return n.toFixed(2) + '%';
}

function fmtText(v) {
  if (v === null || v === undefined) return '-';
  const s = String(v).trim();
  return s === '' ? '-' : s;
}

function nowBrt() {
  const d = new Date();
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const yyyy = d.getFullYear();
  const hh = String(d.getHours()).padStart(2, '0');
  const mi = String(d.getMinutes()).padStart(2, '0');
  return `${dd}/${mm}/${yyyy} ${hh}:${mi}`;
}

function brtFromIso(iso) {
  if (!iso) return nowBrt();
  try {
    const d = new Date(iso);
    const date = d.toLocaleDateString('pt-BR', { timeZone: 'America/Sao_Paulo' });
    const time = d.toLocaleTimeString('pt-BR', { timeZone: 'America/Sao_Paulo', hour: '2-digit', minute: '2-digit' });
    return `${date} ${time}`;
  } catch {
    return nowBrt();
  }
}

function brtDateFromIso(iso) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleDateString('pt-BR', { timeZone: 'America/Sao_Paulo' });
  } catch {
    return '';
  }
}

function brtTimeFromIso(iso) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleTimeString('pt-BR', { timeZone: 'America/Sao_Paulo', hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

// ====== normalize keys from worker JSON ======
function pick(obj, keys) {
  for (const k of keys) {
    if (obj && Object.prototype.hasOwnProperty.call(obj, k)) return obj[k];
  }
  return undefined;
}

function normalizeItem(it, fallbackIso) {
  const out = {
    par: pick(it, ['par', 'PAR', 'Par']),
    side: pick(it, ['side', 'SIDE', 'Side']),
    entrada: pick(it, ['entrada', 'ENTRADA', 'Entrada']),
    atual: pick(it, ['atual', 'ATUAL', 'Atual', 'price', 'PRICE']),
    alvo: pick(it, ['alvo', 'ALVO', 'Alvo']),
    ganho_pct: pick(it, ['ganho_pct', 'GANHO_PCT', 'GANHO %', 'GANHO%', 'Ganho %', 'GANHO']),
    assert_pct: pick(it, ['assert_pct', 'ASSERT_PCT', 'ASSERT %', 'ASSERT%', 'Assert %', 'ASSERT']),
    prazo: pick(it, ['prazo', 'PRAZO', 'Prazo']),
    zona: pick(it, ['zona', 'ZONA', 'Zona']),
    risco: pick(it, ['risco', 'RISCO', 'Risco']),
    prioridade: pick(it, ['prioridade', 'PRIORIDADE', 'Prioridade']),
    data: pick(it, ['data', 'DATA', 'Data']),
    hora: pick(it, ['hora', 'HORA', 'Hora']),
  };

  // Se DATA/HORA vierem vazios, usa a data/hora do "updated_at" (fallbackIso)
  if ((!out.data || out.data === '-') && fallbackIso) out.data = brtDateFromIso(fallbackIso);
  if ((!out.hora || out.hora === '-') && fallbackIso) out.hora = brtTimeFromIso(fallbackIso);

  return out;
}

function normalizeItems(items, fallbackIso) {
  if (!Array.isArray(items)) return [];
  return items.map(it => normalizeItem(it || {}, fallbackIso));
}

// ===== Cores =====
const GAIN_OK = 3.0;
const ASSERT_OK = 65.0;

function gainClass(v) {
  const n = toNum(v);
  if (!Number.isFinite(n)) return '';
  return n >= GAIN_OK ? 'pct-pos' : 'pct-neg';
}

function assertClass(v) {
  const n = toNum(v);
  if (!Number.isFinite(n)) return '';
  return n >= ASSERT_OK ? 'pct-pos' : 'pct-neg';
}

function normTag(s) {
  return String(s || '')
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .trim().toLowerCase();
}

function tagClass(v) {
  const t = normTag(v);
  if (t === 'baixa' || t === 'baixo' || t === 'low') return 'tag-low';
  if (t === 'media' || t === 'medio' || t === 'mid' || t === 'medium') return 'tag-mid';
  if (t === 'alta' || t === 'alto' || t === 'high') return 'tag-high';
  return '';
}

function sideClass(v) {
  const t = normTag(v);
  if (t === 'long') return 'side-long';
  if (t === 'short') return 'side-short';
  if (t === 'nao entrar' || t === 'não entrar' || t === 'no trade' || t === 'no') return 'side-nao';
  return '';
}

// ===== Fetch com cache =====
async function fetchJson(url, timeoutMs = 8000) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      signal: ctrl.signal,
      headers: { 'accept': 'application/json' },
      cache: 'no-store',
    });
    if (!res.ok) {
      const err = new Error(`http_${res.status}`);
      err.status = res.status;
      throw err;
    }
    return await res.json();
  } finally {
    clearTimeout(t);
  }
}

async function fetchWithFallback(paths) {
  let lastErr = null;
  for (const p of paths) {
    try {
      return await fetchJson(`${p}?_=${CACHE_BUST}`);
    } catch (e) {
      lastErr = e;
    }
  }
  throw lastErr || new Error('fetch_error');
}

const mem = {
  full: { at: 0, data: null },
  top10: { at: 0, data: null },
};

const CACHE_TTL_MS = 60_000;

async function load(kind) {
  const slot = mem[kind];
  const age = Date.now() - slot.at;
  if (slot.data && age < CACHE_TTL_MS) return { ok: true, source: 'cache', raw: slot.data };

  const urlList = (kind === 'top10')
    ? ['/api/top10', '/top10']
    : ['/api/pro', '/pro'];

  const json = await fetchWithFallback(urlList);
  slot.at = Date.now();
  slot.data = json;
  return { ok: true, source: 'live', raw: json };
}

// ===== UI =====
function setStatus(msg, isErr = false) {
  const el = q('#status');
  if (!el) return;
  el.textContent = msg;
  el.style.display = msg ? 'block' : 'none';
  el.classList.toggle('err', !!isErr);
}

function setBadges(info) {
  const el = q('#badges');
  if (!el) return;
  const { updatedBrt, count, source } = info;
  el.textContent = `Atualizado (BRT): ${updatedBrt} • Itens: ${count} • Fonte: ${source}`;
}

function renderTable(kind, items) {
  const cols = (kind === 'top10') ? COLS_TOP10 : COLS_FULL;
  const tbody = q('#tbl tbody');
  if (!tbody) return;

  const rows = Array.isArray(items) ? items : [];
  const html = rows.map(it => {
    return '<tr>' + cols.map(([_, key]) => {
      const raw = (it && typeof it === 'object') ? it[key] : undefined;
      let text = '-';
      let cls = '';

      if (key === 'entrada' || key === 'atual' || key === 'alvo') text = fmtPrice(raw);
      else if (key === 'ganho_pct') { text = fmtPct(raw); cls = gainClass(raw); }
      else if (key === 'assert_pct') { text = fmtPct(raw); cls = assertClass(raw); }
      else if (key === 'side') { text = fmtText(raw).toUpperCase(); cls = sideClass(raw); }
      else if (key === 'zona') { text = fmtText(raw).toUpperCase(); cls = tagClass(raw); }
      else if (key === 'risco') { text = fmtText(raw).toUpperCase(); cls = tagClass(raw); }
      else if (key === 'prioridade') { text = fmtText(raw).toUpperCase(); cls = tagClass(raw); }
      else if (key === 'data') text = fmtText(raw);
      else if (key === 'hora') text = fmtText(raw);
      else text = fmtText(raw);

      return `<td class="${cls}">${text}</td>`;
    }).join('') + '</tr>';
  }).join('');

  tbody.innerHTML = html || '<tr><td colspan="20" style="opacity:.7;padding:18px">Sem dados</td></tr>';
}

async function boot(kind) {
  try {
    setStatus('carregando...');
    const out = await load(kind);
    if (!out.ok) throw new Error('load_error');

    const raw = out.raw || {};
    const itemsRaw = raw.items || raw || [];
    const updatedIso = (raw && raw.updated_at) ? String(raw.updated_at) : null;

    // Fallback seguro: se não vier updated_at, usa agora
    const fallbackIso = updatedIso || new Date().toISOString();

    const updatedBrt = updatedIso ? brtFromIso(updatedIso) : nowBrt();
    const items = normalizeItems(itemsRaw, fallbackIso);

    // Auditoria simples: se vier lista mas sem PAR/SIDE, considera formato inesperado
    if (Array.isArray(itemsRaw) && itemsRaw.length > 0) {
      const hasPar = items.some(it => String(it?.par ?? '').trim() !== '');
      const hasSide = items.some(it => String(it?.side ?? '').trim() !== '');
      if (!hasPar || !hasSide) {
        throw new Error('Formato de dados inesperado (faltando PAR/SIDE)');
      }
    }

    const count = Array.isArray(items) ? items.length : 0;
    const source = raw.source || out.source;

    setBadges({ updatedBrt, count, source });
    renderTable(kind, items);
    setStatus('');
  } catch (e) {
    console.error(e);
    setStatus('API indisponivel.', true);
  }
}

// expor p/ paginas
window.boot = boot;
