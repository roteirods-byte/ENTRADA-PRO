// api/server.js
'use strict';

const express = require('express');
// --- NO CACHE (Spaces -> API) ---
function noStore(res) {
  res.setHeader("Cache-Control", "no-store, no-cache, must-revalidate, proxy-revalidate");
  res.setHeader("Pragma", "no-cache");
  res.setHeader("Expires", "0");
  res.setHeader("Surrogate-Control", "no-store");
}

async function fetchJsonNoCache(url) {
  // cache-bust para derrubar cache de CDN/proxy
  const u = new URL(url);
  u.searchParams.set("t", String(Date.now()));

  const r = await fetch(u.toString(), {
    method: "GET",
    // Node/undici respeita isso; e os headers ajudam em proxies
    cache: "no-store",
    headers: {
      "Cache-Control": "no-cache",
      "Pragma": "no-cache",
      "Accept": "application/json",
    },
  });

  if (!r.ok) {
    const txt = await r.text().catch(() => "");
    throw new Error(`fetch ${u} -> ${r.status} ${txt.slice(0, 200)}`);
  }
  return r.json();
}

const app = express();
app.get("/health", (req, res) => res.status(200).json({ ok: true }));
app.get("/api/health", (req, res) => res.status(200).json({ ok: true }));
app.get("/", (req, res) => res.status(200).send("ok"));
app.disable('x-powered-by');

// CORS simples (para o painel poder ler a API mesmo se estiver em outro endereço)
app.use((req, res, next) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.sendStatus(204);
  next();
});

// ====== CONFIG ======
const SERVICE = 'entrada-pro-api';
const PORT = Number(process.env.PORT || 8080);
const DATA_DIR = process.env.DATA_DIR || '/workspace/data';

const PRO_JSON_URL = (process.env.PRO_JSON_URL || '').trim();
const TOP10_JSON_URL = (process.env.TOP10_JSON_URL || '').trim();

// cache simples p/ evitar 504 e excesso de chamadas
const CACHE_TTL_MS = Number(process.env.CACHE_TTL_MS || 60_000);

const cache = {
  pro: { at: 0, data: null, err: null },
  top10: { at: 0, data: null, err: null },
};

function nowUtc() {
  return new Date().toISOString();
}

async function fetchJsonWithTimeout(url, timeoutMs = 8000) {
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(url, {
      signal: controller.signal,
      headers: { accept: 'application/json' },
    });

    if (!res.ok) {
      const err = new Error(`http_${res.status}`);
      err.code = `http_${res.status}`;
      throw err;
    }

    return await res.json();
  } finally {
    clearTimeout(t);
  }
}

async function getCached(key, url) {
  const slot = cache[key];
  const age = Date.now() - slot.at;

  if (slot.data && age < CACHE_TTL_MS) {
    return { ok: true, source: 'cache', updated_at: nowUtc(), items: slot.data.items ?? slot.data, raw: slot.data };
  }

  if (!url) {
    return { ok: false, error: 'url_not_set' };
  }

  try {
    const json = await fetchJsonWithTimeout(url, 8000);
    slot.at = Date.now();
    slot.data = json;
    slot.err = null;

    return { ok: true, source: 'spaces', updated_at: nowUtc(), items: json.items ?? json, raw: json };
  } catch (e) {
    slot.at = Date.now();
    slot.err = e?.code || e?.message || 'fetch_error';

    if (slot.data) {
      return { ok: true, source: 'stale_cache', warning: slot.err, updated_at: nowUtc(), items: slot.data.items ?? slot.data, raw: slot.data };
    }

    return { ok: false, error: slot.err };
  }
}

// ====== ROUTES ======
app.get('/', (req, res) => {
  res.status(200).send(
    `OK: ${SERVICE}\n` +
    `GET /api/version OR GET /version\n` +
    `GET /api/pro OR GET /pro\n` +
    `GET /api/top10 OR GET /top10\n` +
    `GET /api/health OR GET /health\n`
  );
});

function versionPayload() {
  return {
    ok: true,
    service: SERVICE,
    version: process.env.APP_VERSION || 'unknown',
    now_utc: nowUtc(),
    data_dir: DATA_DIR,
    pro_json_url: PRO_JSON_URL ? 'set' : 'missing',
    top10_json_url: TOP10_JSON_URL ? 'set' : 'missing',
  };
}

// version (com e sem /api)
app.get(['/api/version', '/version'], (req, res) => res.json(versionPayload()));

// health (com e sem /api)
app.get(['/api/health', '/health'], (req, res) => res.json({ ok: true }));

// pro (com e sem /api)
app.get(['/api/pro', '/pro'], async (req, res) => {
  const out = await getCached('pro', PRO_JSON_URL);
  if (!out.ok) return res.status(500).json(out);
  return res.json(out);
});

// top10 (com e sem /api)
app.get(['/api/top10', '/top10'], async (req, res) => {
  const out = await getCached('top10', TOP10_JSON_URL);
  if (!out.ok) return res.status(500).json(out);
  return res.json(out);
});

// ===== AUDITORIA PREÇO FUTUROS (BYBIT LINEAR) =====
async function fetchJson(url, timeoutMs = 8000) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const r = await fetch(url, { signal: ctrl.signal, headers: { "accept": "application/json" } });
    const txt = await r.text();
    let j = null;
    try { j = JSON.parse(txt); } catch {}
    return { ok: r.ok, status: r.status, json: j, text: txt };
  } finally {
    clearTimeout(t);
  }
}

// Bybit v5: category=linear (USDT Perp). Retorna lastPrice/markPrice/indexPrice
async function bybitLinearTicker(symbol) {
  const url = `https://api.bybit.com/v5/market/tickers?category=linear&symbol=${encodeURIComponent(symbol)}`;
  const out = await fetchJson(url);
  if (!out.ok || !out.json) return { ok:false, url, raw: out };
  const j = out.json;
  const row = j?.result?.list?.[0];
  return {
    ok: true,
    url,
    ts_utc: new Date().toISOString(),
    symbol,
    last: row?.lastPrice ? Number(row.lastPrice) : null,
    mark: row?.markPrice ? Number(row.markPrice) : null,
    index: row?.indexPrice ? Number(row.indexPrice) : null,
    raw: j
  };
}

// Compara com o valor do painel (top10/pro) no MESMO instante
app.get("/api/audit/price", async (req, res) => {
  try {
    const par = String(req.query.par || "SUI").toUpperCase().replace(/[^A-Z0-9]/g, "");
    const symbol = `${par}USDT`;

    // 1) Bybit Perp ao vivo
    const bybit = await bybitLinearTicker(symbol);

    // 2) Valor atual que a SUA API está servindo (top10 e pro)
    //    (usa suas rotas locais já existentes)
    const base = `${req.protocol}://${req.get("host")}`;
    const top10Live = await fetchJson(`${base}/api/top10`);
    const proLive  = await fetchJson(`${base}/api/pro`);

    function pickPrice(payload) {
      const items = payload?.json?.items || [];
      const row = items.find(x => String(x.PAR).toUpperCase() === par);
      return row ? Number(row.ATUAL) : null;
    }

    const atualTop10 = pickPrice(top10Live);
    const atualPro   = pickPrice(proLive);

    function diffPct(a, b) {
      if (!a || !b) return null;
      return ((a - b) / b) * 100;
    }

    const ref = bybit?.mark ?? bybit?.last ?? null;

    return res.json({
      ok: true,
      par,
      symbol,
      now_utc: new Date().toISOString(),
      bybit,
      painel: {
        top10_atual: atualTop10,
        pro_atual: atualPro,
        diff_top10_pct: ref && atualTop10 ? diffPct(atualTop10, ref) : null,
        diff_pro_pct: ref && atualPro ? diffPct(atualPro, ref) : null
      }
    });
  } catch (e) {
    return res.status(500).json({ ok:false, error: String(e?.message || e) });
  }
});

// ====== START ======
app.listen(PORT, () => {
  console.log(`[${SERVICE}] listening on ${PORT} | now=${nowUtc()}`);
  console.log(`[${SERVICE}] DATA_DIR=${DATA_DIR}`);
  console.log(`[${SERVICE}] PRO_JSON_URL=${PRO_JSON_URL ? 'set' : 'missing'}`);
  console.log(`[${SERVICE}] TOP10_JSON_URL=${TOP10_JSON_URL ? 'set' : 'missing'}`);
});
