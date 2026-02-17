// api/server.js
'use strict';

const express = require('express');
const fs = require('fs/promises');
const path = require('path');

const app = express();
app.disable('x-powered-by');

// ====== CONFIG ======
const SERVICE = 'entrada-pro-api';
const PORT = Number(process.env.PORT || 8080);

// Por padrão, usa ../data (repo/data). Em produção, configure DATA_DIR.
const DATA_DIR = (process.env.DATA_DIR && process.env.DATA_DIR.trim())
  ? process.env.DATA_DIR.trim()
  : path.join(__dirname, '..', 'data');

// ====== HELPERS ======
function nowUtc() {
  return new Date().toISOString();
}

// Sem cache (browser/proxy/CDN)
function noStore(res) {
  res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate, proxy-revalidate');
  res.setHeader('Pragma', 'no-cache');
  res.setHeader('Expires', '0');
  res.setHeader('Surrogate-Control', 'no-store');
}

// CORS simples (painel pode estar em outro host)
app.use((req, res, next) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.sendStatus(204);
  next();
});

async function readJsonFile(filename) {
  const full = path.join(DATA_DIR, filename);
  const raw = await fs.readFile(full, 'utf8');
  return JSON.parse(raw);
}

async function sendJsonFromFile(res, filename) {
  try {
    const json = await readJsonFile(filename);
    noStore(res);
    return res.status(200).json(json); // IMPORTANTE: retorna o JSON "puro" do data/
  } catch (e) {
    const msg = (e && e.message) ? e.message : String(e);
    return res.status(500).json({
      ok: false,
      service: SERVICE,
      now_utc: nowUtc(),
      data_dir: DATA_DIR,
      file: filename,
      error: msg,
    });
  }
}

// ====== ROUTES ======
app.get(['/health', '/api/health'], (req, res) => res.status(200).json({ ok: true }));

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
  };
}

app.get(['/api/version', '/version'], (req, res) => res.status(200).json(versionPayload()));

// BLOCO 2 (blindado): NÃO CALCULA NADA. SÓ LÊ ARQUIVO.
app.get(['/api/pro', '/pro'], async (req, res) => sendJsonFromFile(res, 'pro.json'));
app.get(['/api/top10', '/top10'], async (req, res) => sendJsonFromFile(res, 'top10.json'));

// ====== START ======
app.listen(PORT, () => {
  console.log(`[${SERVICE}] listening on ${PORT} | now=${nowUtc()}`);
  console.log(`[${SERVICE}] DATA_DIR=${DATA_DIR}`);
});
