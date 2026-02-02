"use strict";

const fs = require("fs");
const path = require("path");
const express = require("express");
const cors = require("cors");

const app = express();
app.use(cors());

const PORT = parseInt(process.env.PORT || "8080", 10);
const DATA_DIR = process.env.DATA_DIR || path.join(__dirname, "..", "data");

const PRO_JSON_URL = process.env.PRO_JSON_URL || "";
const TOP10_JSON_URL = process.env.TOP10_JSON_URL || "";

const CACHE_TTL_MS = parseInt(process.env.CACHE_TTL_MS || "60000", 10);
const cache = {
  "pro.json": { ts: 0, data: null },
  "top10.json": { ts: 0, data: null },
};

function readVersion() {
  try {
    const fp = path.join(__dirname, "..", "VERSION");
    if (fs.existsSync(fp)) return fs.readFileSync(fp, "utf-8").trim();
  } catch (e) {}
  return "unknown";
}

function safeJsonRead(fp) {
  try {
    if (!fs.existsSync(fp)) return null;
    const raw = fs.readFileSync(fp, "utf-8");
    return JSON.parse(raw);
  } catch (e) {
    return null;
  }
}

async function fetchJson(url) {
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), 8000);
  try {
    const r = await fetch(url, { signal: controller.signal, headers: { "cache-control": "no-cache" } });
    if (!r.ok) throw new Error("http_" + r.status);
    return await r.json();
  } finally {
    clearTimeout(t);
  }
}

async function serveJson(res, filename, notFoundError) {
  const now = Date.now();
  const url =
    filename === "pro.json" ? PRO_JSON_URL :
    filename === "top10.json" ? TOP10_JSON_URL :
    "";

  if (url) {
    const c = cache[filename];
    if (c && c.data && now - c.ts < CACHE_TTL_MS) return res.json(c.data);

    try {
      const data = await fetchJson(url);
      if (c) { c.ts = now; c.data = data; }
      return res.json(data);
    } catch (e) {
      // cai para o arquivo local
    }
  }

  const fp = path.join(DATA_DIR, filename);
  const data = safeJsonRead(fp);

  if (!data) return res.json({ ok: false, error: notFoundError, data_dir: DATA_DIR, items: [], count: 0 });
  return res.json(data);
}

app.get("/", (req, res) => res.json({ ok: true, message: "entrada-pro-api", now_utc: new Date().toISOString() }));

app.get("/api/health", (req, res) =>
  res.json({
    ok: true,
    service: "entrada-pro-api",
    version: readVersion(),
    now_utc: new Date().toISOString(),
    data_dir: DATA_DIR,
    pro_json_url: PRO_JSON_URL ? "set" : "not_set",
    top10_json_url: TOP10_JSON_URL ? "set" : "not_set",
  })
);

app.get("/api/version", (req, res) =>
  res.json({ ok: true, service: "entrada-pro-api", version: readVersion(), now_utc: new Date().toISOString() })
);

app.get("/api/pro", async (req, res) => serveJson(res, "pro.json", "pro.json_not_found"));
app.get("/api/top10", async (req, res) => serveJson(res, "top10.json", "top10.json_not_found"));

app.listen(PORT, () => {
  console.log(`[ENTRADA-PRO] API on :${PORT}`);
});
