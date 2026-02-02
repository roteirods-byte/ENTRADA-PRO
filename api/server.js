"use strict";

const DEFAULT_SOURCE = process.env.PRICE_SOURCE || "MARK_PRICE";

const fs = require("fs");
const path = require("path");
const express = require("express");
const cors = require("cors");

const app = express();
app.use(cors());

// DigitalOcean: use sempre process.env.PORT (e fallback 8080)
const PORT = parseInt(process.env.PORT || "8080", 10);

// Data dir padrão (fallback local)
const DATA_DIR = process.env.DATA_DIR || path.join(__dirname, "..", "data");

// Links (Spaces) – se existirem, a API lê direto de lá
const PRO_JSON_URL = process.env.PRO_JSON_URL || "";
const TOP10_JSON_URL = process.env.TOP10_JSON_URL || "";

// Cache simples em memória (evita buscar toda hora)
const CACHE_TTL_MS = parseInt(process.env.CACHE_TTL_MS || "60000", 10); // 60s
const cache = {
  "pro.json": { ts: 0, data: null },
  "top10.json": { ts: 0, data: null },
};

function safeJsonRead(fp) {
  try {
    if (!fs.existsSync(fp)) return null;
    const raw = fs.readFileSync(fp, "utf-8");
    return JSON.parse(raw);
  } catch (e) {
    return {
      ok: false,
      error: "invalid_json",
      file: fp,
      details: String(e && e.message ? e.message : e),
    };
  }
}

function readVersion() {
  try {
    const fp = path.join(__dirname, "..", "VERSION");
    if (fs.existsSync(fp)) return fs.readFileSync(fp, "utf-8").trim();
  } catch (e) {}
  return "unknown";
}

function healthPayload() {
  return {
    ok: true,
    service: "entrada-pro-api",
    version: readVersion(),
    now_utc: new Date().toISOString(),
    data_dir: DATA_DIR,
    pro_json_url: PRO_JSON_URL ? "set" : "not_set",
    top10_json_url: TOP10_JSON_URL ? "set" : "not_set",
  };
}

async function fetchJson(url) {
  // Node 18+ tem fetch nativo
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), 8000);

  try {
    const r = await fetch(url, { signal: controller.signal, headers: { "cache-control": "no-cache" } });
    if (!r.ok) throw new Error("http_" + r.status);
    const data = await r.json();
    return data;
  } finally {
    clearTimeout(t);
  }
}

async function serveJson(res, filename, notFoundError) {
  const now = Date.now();

  // 1) Se tiver URL (Spaces), usa ela (com cache)
  const url =
    filename === "pro.json" ? PRO_JSON_URL :
    filename === "top10.json" ? TOP10_JSON_URL :
    "";

  if (url) {
    const c = cache[filename];
    if (c && c.data && now - c.ts < CACHE_TTL_MS) {
      return res.json(c.data);
    }

    try {
      const data = await fetchJson(url);
      if (c) {
        c.ts = now;
        c.data = data;
      }
      return res.json(data);
    } catch (e) {
      // Se falhar, cai para o arquivo local (fallback)
    }
  }

  // 2) Fallback local (DATA_DIR)
  const fp = path.join(DATA_DIR, filename);
  const data = safeJsonRead(fp);

  if (!data) {
    if (filename === "top10.json")
      return res.json({ ok: false, error: notFoundError, data_dir: DATA_DIR, items: [], count: 0 });
    if (filename === "pro.json")
      return res.json({ ok: false, error: notFoundError, data_dir: DATA_DIR, items: [], count: 0 });
    return res.json({ ok: false, error: notFoundError, data_dir: DATA_DIR });
  }

  return res.json(data);
}

// ROOT
app.get("/", (req, res) => res.json({ ok: true, message: "entrada-pro-api", now_utc: new Date().toISOString() }));
app.get("/api/health", (req, res) => res.json(healthPayload()));
app.get("/api/version", (req, res) =>
  res.json({ ok: true, service: "entrada-pro-api", version: readVersion(), now_utc: new Date().toISOString() })
);

// PRO
app.get("/api/pro", async (req, res) => serveJson(res, "pro.json", "pro.json_not_found"));
app.get("/pro", async (req, res) => serveJson(res, "pro.json", "pro.json_not_found"));

// TOP10
app.get("/api/top10", async (req, res) => serveJson(res, "top10.json", "top10.json_not_found"));
app.get("/top10", async (req, res) => serveJson(res, "top10.json", "top10.json_not_found"));

// COMPAT (frontend antigo)
app.get("/api/pro/full", async (req, res) => serveJson(res, "pro.json", "pro.json_not_found"));
app.get("/api/pro/top10", async (req, res) => serveJson(res, "top10.json", "top10.json_not_found"));

// static site (opcional)
const SITE_DIR =
  process.env.SITE_DIR ||
  (() => {
    const dist = path.join(__dirname, "..", "dist");
    const site = path.join(__dirname, "..", "site");
    try {
      if (fs.existsSync(dist)) return dist;
    } catch (e) {}
    return site;
  })();

app.use("/", express.static(SITE_DIR));

app.listen(PORT, () => {
  console.log(
    `[ENTRADA-PRO] API on :${PORT} | DATA_DIR=${DATA_DIR} | PRO_JSON_URL=${PRO_JSON_URL ? "set" : "not_set"} | TOP10_JSON_URL=${TOP10_JSON_URL ? "set" : "not_set"}`
  );
});
