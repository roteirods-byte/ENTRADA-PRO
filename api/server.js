/* ENTRADA-PRO API (Node)
   - Serve /api/pro e /api/top10
   - Se PRO_JSON_URL/TOP10_JSON_URL não existirem ou falharem, lê do DATA_DIR: pro.json/top10.json
*/
require('dotenv').config({ path: require('path').join(__dirname, '.env') });

const fs = require('fs');
const path = require('path');
const express = require('express');
<<<<<<< Updated upstream
const fs = require('fs/promises');
const path = require('path');
=======
>>>>>>> Stashed changes

const app = express();
app.disable('x-powered-by');

<<<<<<< Updated upstream
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
=======
const PORT = Number(process.env.PORT || 8080);
const DATA_DIR = process.env.DATA_DIR || path.join(__dirname, '..', 'data');

const PRO_JSON_URL  = process.env.PRO_JSON_URL  || '';
const TOP10_JSON_URL = process.env.TOP10_JSON_URL || '';

const CACHE = {
  pro:  { ts: 0, data: null },
  top10:{ ts: 0, data: null },
};

function noStore(res){
>>>>>>> Stashed changes
  res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate, proxy-revalidate');
  res.setHeader('Pragma', 'no-cache');
  res.setHeader('Expires', '0');
  res.setHeader('Surrogate-Control', 'no-store');
<<<<<<< Updated upstream
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
=======
}

async function fetchJsonWithTimeout(url, ms){
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), ms);
  try{
    const r = await fetch(url, { signal: controller.signal, headers: { 'accept': 'application/json' } });
    if(!r.ok) throw new Error(`HTTP_${r.status}`);
    return await r.json();
  } finally {
    clearTimeout(t);
  }
}

function readLocalJson(fileName){
  try{
    const fp = path.join(DATA_DIR, fileName);
    const s = fs.readFileSync(fp, 'utf-8');
    const obj = JSON.parse(s);
    if(obj && typeof obj === 'object'){
      if(!obj.source) obj.source = 'local';
      return obj;
    }
  }catch(e){}
  return null;
}

async function getCached(name, url, maxAgeMs, localFile){
  const now = Date.now();
  const ent = CACHE[name];

  if(ent.data && (now - ent.ts) < maxAgeMs) return ent.data;

  let data = null;

  // tenta URL se existir
  if(url){
    try{
      data = await fetchJsonWithTimeout(url, 4000);
      if(data && typeof data === 'object' && !data.source) data.source = 'remote';
    }catch(e){
      console.error(`[api] ${name} remote fail:`, e?.message || e);
    }
>>>>>>> Stashed changes
  }

  // fallback local
  if(!data){
    const local = readLocalJson(localFile);
    if(local) data = local;
  }

  // se ainda não tem data, retorna erro claro
  if(!data){
    return { ok:false, error: url ? 'fetch_failed_and_no_local' : 'url_not_set_and_no_local', name };
  }

  ent.ts = now;
  ent.data = data;
  return data;
}

<<<<<<< Updated upstream
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
=======
function respondWithFallback(res, name, data){
  // se veio erro ({ok:false}) ou nulo, devolve o último cache bom
  if(!data || (data && data.ok === false)){
    const cached = CACHE[name] && CACHE[name].data;
    if(cached){
      res.setHeader('X-Fallback','1');
      return res.json(cached);
    }
    // sem cache ainda: devolve objeto vazio, mas válido (não quebra front)
    res.setHeader('X-Fallback','2');
    return res.json({ ok:true, source:'fallback', items:[], updated_at:null, now_brt:null });
  }
  return res.json(data);
}

app.get('/health', (req,res)=>{ noStore(res); res.json({ ok:true }); });
app.get('/api/version', (req,res)=>{ noStore(res); res.json({ ok:true, version: require('fs').existsSync(path.join(__dirname,'..','VERSION')) ? fs.readFileSync(path.join(__dirname,'..','VERSION'),'utf-8').trim() : 'unknown' }); });

app.get('/api/pro', async (req,res)=>{
  noStore(res);
  const data = await getCached('pro', PRO_JSON_URL, 6000, 'pro.json');
  respondWithFallback(res, 'pro', data);
});

app.get('/api/top10', async (req,res)=>{
  noStore(res);
  const data = await getCached('top10', TOP10_JSON_URL, 6000, 'top10.json');
  respondWithFallback(res, 'top10', data);
});

app.listen(PORT, '0.0.0.0', ()=>{
  console.log(`[entrada-pro-api] listening on ${PORT}`);
  console.log(`[entrada-pro-api] DATA_DIR=${DATA_DIR}`);
  console.log(`[entrada-pro-api] PRO_JSON_URL=${PRO_JSON_URL ? 'set' : 'missing'}`);
  console.log(`[entrada-pro-api] TOP10_JSON_URL=${TOP10_JSON_URL ? 'set' : 'missing'}`);
>>>>>>> Stashed changes
});
