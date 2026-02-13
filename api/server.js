// api/server.js
'use strict';

const express = require('express');
const path = require('path');
const fs = require('fs/promises');

const app = express();
app.disable('x-powered-by');

// CORS simples
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
const DATA_DIR = (process.env.DATA_DIR || '/opt/ENTRADA-PRO/data').trim();

const PRO_JSON_URL = (process.env.PRO_JSON_URL || '').trim();
const TOP10_JSON_URL = (process.env.TOP10_JSON_URL || '').trim();

// cache simples para quando usar link
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
    const res = await fetch(url, { signal: controller.signal, headers: { accept: 'application/json' } });
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

async function readLocalJson(filename) {
  const file = path.join(DATA_DIR, filename);
  const txt = await fs.readFile(file, 'utf8');
  return JSON.parse(txt);
}

function normalizeOut(json, source) {
  return { ok: true, source, updated_at: nowUtc(), items: json.items ?? json, raw: json };
}

async function getData(key, url, localFile) {
  const slot = cache[key];
  const age = Date.now() - slot.at;

  // Se tem cache válido, devolve rápido
  if (slot.data && age < CACHE_TTL_MS) {
    return normalizeOut(slot.data, 'cache');
  }

  // 1) Se NÃO tem link, lê o arquivo local
  if (!url) {
    try {
      const local = await readLocalJson(localFile);
      return normalizeOut(local, 'local');
    } catch (e) {
      return { ok: false, error: 'local_read_error' };
    }
  }

  // 2) Se tem link, tenta buscar
  try {
    const json = await fetchJsonWithTimeout(url, 8000);
    slot.at = Date.now();
    slot.data = json;
    slot.err = null;
    return normalizeOut(json, 'spaces');
  } catch (e) {
    slot.at = Date.now();
    slot.err = e?.code || e?.message || 'fetch_error';

    // Se já tem cache antigo, devolve cache antigo
    if (slot.data) {
      return { ...normalizeOut(slot.data, 'stale_cache'), warning: slot.err };
    }

    // Sem cache: tenta o arquivo local como “salva-vidas”
    try {
      const local = await readLocalJson(localFile);
      return { ...normalizeOut(local, 'local_fallback'), warning: slot.err };
    } catch {
      return { ok: false, error: slot.err };
    }
  }
}

// ====== ROUTES ======
app.get(['/api/health', '/health'], (req, res) => res.status(200).json({ ok: true }));

app.get(['/api/version', '/version'], async (req, res) => {
  let localPro = 'unknown';
  let localTop10 = 'unknown';
  try { await fs.access(path.join(DATA_DIR, 'pro.json')); localPro = 'ok'; } catch { localPro = 'missing'; }
  try { await fs.access(path.join(DATA_DIR, 'top10.json')); localTop10 = 'ok'; } catch { localTop10 = 'missing'; }

  res.json({
    ok: true,
    service: SERVICE,
    version: process.env.APP_VERSION || 'unknown',
    now_utc: nowUtc(),
    data_dir: DATA_DIR,
    pro_json_url: PRO_JSON_URL ? 'set' : 'missing',
    top10_json_url: TOP10_JSON_URL ? 'set' : 'missing',
    local_pro: localPro,
    local_top10: localTop10,
  });
});

app.get(['/api/pro'], async (req, res) => {
  const out = await getData('pro', PRO_JSON_URL, 'pro.json');
  if (!out.ok) return res.status(500).json(out);
  return res.json(out);
});

app.get(['/api/top10'], async (req, res) => {
  const out = await getData('top10', TOP10_JSON_URL, 'top10.json');
  if (!out.ok) return res.status(500).json(out);
  return res.json(out);
});

// ====== START ======
app.listen(PORT, () => {
  console.log(`[${SERVICE}] listening on ${PORT} | now=${nowUtc()}`);
  console.log(`[${SERVICE}] DATA_DIR=${DATA_DIR}`);
  console.log(`[${SERVICE}] PRO_JSON_URL=${PRO_JSON_URL ? 'set' : 'missing'}`);
  console.log(`[${SERVICE}] TOP10_JSON_URL=${TOP10_JSON_URL ? 'set' : 'missing'}`);
});
