'use strict';

const express = require('express');
const cors = require('cors');

const app = express();

app.use(cors());
app.use(express.json({ limit: '1mb' }));

const PORT = process.env.PORT || 8080;

// =============================
// Config
// =============================
const PRO_JSON_URL = process.env.PRO_JSON_URL || '';
const TOP10_JSON_URL = process.env.TOP10_JSON_URL || '';

// Cache simples (só para /api/pro e /api/top10)
const CACHE_TTL_MS = 10_000; // 10s
const cache = {
  pro: { at: 0, data: null },
  top10: { at: 0, data: null },
};

function nowIso() {
  return new Date().toISOString();
}

function normSymbol(par) {
  // Entrada aceita: "SUI" ou "SUIUSDT"
  const p = String(par || '').trim().toUpperCase();
  if (!p) return '';
  return p.endsWith('USDT') ? p : `${p}USDT`;
}

async function fetchJson(url, timeoutMs = 8000) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, { signal: ctrl.signal, headers: { 'accept': 'application/json' } });
    const text = await res.text();
    let json;
    try { json = JSON.parse(text); } catch { json = { raw: text }; }
    return { ok: res.ok, status: res.status, json };
  } finally {
    clearTimeout(t);
  }
}

async function getData(kind) {
  const slot = cache[kind];
  const age = Date.now() - slot.at;
  if (slot.data && age < CACHE_TTL_MS) {
    return { ok: true, source: 'cache', updated_at: new Date(slot.at).toISOString(), items: slot.data.items || slot.data };
  }

  const url = (kind === 'top10') ? TOP10_JSON_URL : PRO_JSON_URL;
  if (!url) {
    return { ok: false, error: `missing env ${(kind === 'top10') ? 'TOP10_JSON_URL' : 'PRO_JSON_URL'}` };
    }

  const r = await fetchJson(url);
  if (!r.ok) {
    return { ok: false, error: `fetch failed`, status: r.status, url };
  }

  slot.at = Date.now();
  slot.data = r.json;

  return {
    ok: true,
    source: 'live',
    updated_at: new Date(slot.at).toISOString(),
    items: r.json.items || r.json,
  };
}

// =============================
// Routes
// =============================
app.get('/api/version', (req, res) => {
  res.json({
    ok: true,
    service: 'entrada-pro-api',
    version: process.env.VERSION || 'unknown',
    now_utc: nowIso(),
    data_dir: process.env.DATA_DIR || '/workspace/data',
    pro_json_url: PRO_JSON_URL ? 'set' : 'missing',
    top10_json_url: TOP10_JSON_URL ? 'set' : 'missing',
  });
});

app.get('/api/pro', async (req, res) => {
  try {
    const out = await getData('pro');
    if (!out.ok) return res.status(500).json(out);
    return res.json(out);
  } catch (e) {
    return res.status(500).json({ ok: false, error: String(e?.message || e) });
  }
});

app.get('/api/top10', async (req, res) => {
  try {
    const out = await getData('top10');
    if (!out.ok) return res.status(500).json(out);
    return res.json(out);
  } catch (e) {
    return res.status(500).json({ ok: false, error: String(e?.message || e) });
  }
});

// AUDITORIA DE PREÇO (FUTUROS PERPÉTUO / LINEAR USDT)
// URL: /api/audit/price?par=SUI   (ou par=SUIUSDT)
app.get('/api/audit/price', async (req, res) => {
  try {
    const symbol = normSymbol(req.query.par);
    if (!symbol) return res.status(400).json({ ok: false, error: 'missing par (ex: ?par=SUI)' });

    // BYBIT PERP (linear)
    const bybitUrl = `https://api.bybit.com/v5/market/tickers?category=linear&symbol=${encodeURIComponent(symbol)}`;

    // BITGET PERP (USDT-FUTURES)
    const bitgetUrl = `https://api.bitget.com/api/v2/mix/market/symbol-price?productType=USDT-FUTURES&symbol=${encodeURIComponent(symbol)}`;

    const [bybitR, bitgetR] = await Promise.all([
      fetchJson(bybitUrl, 8000),
      fetchJson(bitgetUrl, 8000),
    ]);

    // Parse Bybit
    let bybit = { ok: false, note: 'no data' };
    if (bybitR.ok && bybitR.json && bybitR.json.result && Array.isArray(bybitR.json.result.list) && bybitR.json.result.list[0]) {
      const x = bybitR.json.result.list[0];
      bybit = {
        ok: true,
        symbol: x.symbol,
        lastPrice: Number(x.lastPrice),
        markPrice: Number(x.markPrice),
        indexPrice: Number(x.indexPrice),
        fundingRate: x.fundingRate != null ? Number(x.fundingRate) : null,
        nextFundingTime: x.nextFundingTime || null,
      };
    } else {
      bybit = { ok: false, status: bybitR.status, sample: bybitR.json };
    }

    // Parse Bitget
    let bitget = { ok: false, note: 'no data' };
    const bg = bitgetR.json;
    // Bitget pode vir como {data:[{symbol,price}]} ou {data:{...}} dependendo do endpoint/versão
    if (bitgetR.ok && bg) {
      const d = Array.isArray(bg.data) ? bg.data[0] : bg.data;
      if (d && (d.price != null || d.last != null)) {
        bitget = {
          ok: true,
          symbol: d.symbol || symbol,
          price: Number(d.price ?? d.last),
        };
      } else {
        bitget = { ok: false, status: bitgetR.status, sample: bg };
      }
    } else {
      bitget = { ok: false, status: bitgetR.status, sample: bg };
    }

    // Também mostramos o que está no painel (TOP10) agora, para comparar
    const top10 = await getData('top10');
    let painel = null;
    if (top10.ok && Array.isArray(top10.items)) {
      const row = top10.items.find(r => String(r.PAR || '').toUpperCase() === symbol.replace('USDT', ''));
      if (row) {
        painel = {
          PAR: row.PAR,
          ATUAL: row.ATUAL,
          ENTRADA: row.ENTRADA,
          ALVO: row.ALVO,
          updated_at: top10.updated_at,
          source: top10.source,
        };
      }
    }

    return res.json({
      ok: true,
      par: symbol.replace('USDT', ''),
      symbol,
      now_utc: nowIso(),
      bybit,
      bitget,
      painel,
      obs: 'Se BYBIT(mark/last) estiver perto da corretora e o painel estiver distante, o problema está no WORKER/ENGINE que gerou o JSON (não no site).',
    });
  } catch (e) {
    return res.status(500).json({ ok: false, error: String(e?.message || e) });
  }
});

app.get('/', (req, res) => res.send('ok'));

app.listen(PORT, () => {
  console.log(`entrada-pro-api listening on :${PORT}`);
});
