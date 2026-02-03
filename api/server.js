/**
 * ENTRADA-PRO API
 * - Lê PRO e TOP10 direto do Spaces (URLs via ENV)
 * - Fallback opcional: lê arquivos locais em DATA_DIR
 * - Expõe endpoints /api/pro, /api/top10, /api/health, /api/version
 */

const express = require("express");
const cors = require("cors");
const fs = require("fs");
const path = require("path");
const https = require("https");

const app = express();
app.use(cors());
app.use(express.json({ limit: "1mb" }));

const PORT = process.env.PORT || 8080;
const SERVICE = "entrada-pro-api";

const DATA_DIR = process.env.DATA_DIR || "/workspace/data";
const PRO_JSON_URL = (process.env.PRO_JSON_URL || "").trim();
const TOP10_JSON_URL = (process.env.TOP10_JSON_URL || "").trim();

// Site está em ../site (só funciona se o deploy incluir a pasta "site")
const SITE_DIR = path.resolve(__dirname, "../site");
if (fs.existsSync(SITE_DIR)) {
  app.use(express.static(SITE_DIR));
}

// cache simples para evitar bater no Spaces a todo request
const CACHE_TTL_MS = 30 * 1000; // 30s
let cachePro = { ts: 0, data: null };
let cacheTop10 = { ts: 0, data: null };

function nowIso() {
  return new Date().toISOString();
}

function safeJsonParse(txt) {
  try {
    return { ok: true, json: JSON.parse(txt) };
  } catch (e) {
    return { ok: false, error: "invalid_json" };
  }
}

function httpsGetText(url) {
  return new Promise((resolve, reject) => {
    https
      .get(
        url,
        {
          headers: {
            "User-Agent": "entrada-pro-api",
            Accept: "application/json",
          },
        },
        (res) => {
          let body = "";
          res.on("data", (c) => (body += c));
          res.on("end", () => {
            const code = res.statusCode || 0;
            if (code < 200 || code >= 300) {
              return reject(new Error(`HTTP_${code}`));
            }
            resolve(body);
          });
        }
      )
      .on("error", reject);
  });
}

async function fetchJsonFromUrl(url) {
  const txt = await httpsGetText(url);
  const parsed = safeJsonParse(txt);
  if (!parsed.ok) throw new Error(parsed.error);
  return parsed.json;
}

function readLocalJson(fileName) {
  const filePath = path.join(DATA_DIR, fileName);
  if (!fs.existsSync(filePath)) return null;
  const raw = fs.readFileSync(filePath, "utf8");
  const parsed = safeJsonParse(raw);
  if (!parsed.ok) return null;
  return parsed.json;
}

async function getProJson() {
  const t = Date.now();
  if (cachePro.data && t - cachePro.ts < CACHE_TTL_MS) return cachePro.data;

  // 1) tenta URL (Spaces)
  if (PRO_JSON_URL) {
    const j = await fetchJsonFromUrl(PRO_JSON_URL);
    cachePro = { ts: t, data: j };
    return j;
  }

  // 2) fallback local
  const local = readLocalJson("pro.json");
  if (local) {
    cachePro = { ts: t, data: local };
    return local;
  }

  return null;
}

async function getTop10Json() {
  const t = Date.now();
  if (cacheTop10.data && t - cacheTop10.ts < CACHE_TTL_MS) return cacheTop10.data;

  // 1) tenta URL (Spaces)
  if (TOP10_JSON_URL) {
    const j = await fetchJsonFromUrl(TOP10_JSON_URL);
    cacheTop10 = { ts: t, data: j };
    return j;
  }

  // 2) fallback local
  const local = readLocalJson("top10.json");
  if (local) {
    cacheTop10 = { ts: t, data: local };
    return local;
  }

  return null;
}

app.get("/api/health", (req, res) => {
  res.json({
    ok: true,
    service: SERVICE,
    now_utc: nowIso(),
    data_dir: DATA_DIR,
  });
});

app.get("/api/version", (req, res) => {
  res.json({
    ok: true,
    service: SERVICE,
    version: process.env.APP_VERSION || "unknown",
    now_utc: nowIso(),
    data_dir: DATA_DIR,
    pro_json_url: PRO_JSON_URL ? "set" : "missing",
    top10_json_url: TOP10_JSON_URL ? "set" : "missing",
  });
});

// atende os 2 formatos, para não quebrar nada
app.get(["/api/pro", "/pro"], async (req, res) => {
  try {
    const data = await getProJson();
    if (!data) {
      return res.status(404).json({
        ok: false,
        error: "pro.json_not_found",
        data_dir: DATA_DIR,
        items: [],
        count: 0,
      });
    }

    // mantém compatível com o front (items/count)
    const items = Array.isArray(data.items) ? data.items : Array.isArray(data) ? data : [];
    res.json({
      ok: true,
      source: PRO_JSON_URL ? "url" : "local",
      data_dir: DATA_DIR,
      items,
      count: items.length,
    });
  } catch (e) {
    res.status(502).json({
      ok: false,
      error: "pro.json_fetch_failed",
      message: String(e && e.message ? e.message : e),
    });
  }
});

app.get(["/api/top10", "/top10"], async (req, res) => {
  try {
    const data = await getTop10Json();
    if (!data) {
      return res.status(404).json({
        ok: false,
        error: "top10.json_not_found",
        data_dir: DATA_DIR,
        items: [],
        count: 0,
      });
    }

    const items = Array.isArray(data.items) ? data.items : Array.isArray(data) ? data : [];
    res.json({
      ok: true,
      source: TOP10_JSON_URL ? "url" : "local",
      data_dir: DATA_DIR,
      items,
      count: items.length,
    });
  } catch (e) {
    res.status(502).json({
      ok: false,
      error: "top10.json_fetch_failed",
      message: String(e && e.message ? e.message : e),
    });
  }
});

app.listen(PORT, () => {
  console.log(`[${SERVICE}] listening on ${PORT} | now=${nowIso()}`);
  console.log(`[${SERVICE}] DATA_DIR=${DATA_DIR}`);
  console.log(`[${SERVICE}] PRO_JSON_URL=${PRO_JSON_URL ? "set" : "missing"}`);
  console.log(`[${SERVICE}] TOP10_JSON_URL=${TOP10_JSON_URL ? "set" : "missing"}`);
});
