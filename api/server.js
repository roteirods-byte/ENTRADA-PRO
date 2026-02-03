// api/server.js
const express = require("express");
const cors = require("cors");
const http = require("http");
const https = require("https");

const app = express();
app.use(cors());

// ---- Config ----
const PORT = process.env.PORT || 8080;
const SERVICE = "entrada-pro-api";
const APP_VERSION = process.env.APP_VERSION || "unknown";

const PRO_JSON_URL = (process.env.PRO_JSON_URL || "").trim();
const TOP10_JSON_URL = (process.env.TOP10_JSON_URL || "").trim();

// Cache (último dado bom)
const cache = {
  pro: { items: [], count: 0, updated_at: null },
  top10: { items: [], count: 0, updated_at: null },
};

function nowUTC() {
  return new Date().toISOString();
}

function parseItems(data) {
  // Aceita: Array, {items:[...]}, ou qualquer objeto (vira 1 item)
  if (Array.isArray(data)) return { items: data, count: data.length };

  if (data && typeof data === "object" && Array.isArray(data.items)) {
    const items = data.items;
    const count = Number.isFinite(data.count) ? data.count : items.length;
    return { items, count };
  }

  if (data && typeof data === "object") return { items: [data], count: 1 };

  return { items: [], count: 0 };
}

function fetchJson(url, timeoutMs = 8000) {
  return new Promise((resolve, reject) => {
    if (!url) return reject(new Error("url_empty"));

    const lib = url.startsWith("https://") ? https : http;

    const req = lib.get(url, (res) => {
      const sc = res.statusCode || 0;

      if (sc < 200 || sc >= 300) {
        res.resume();
        return reject(new Error(`http_${sc}`));
      }

      let raw = "";
      res.setEncoding("utf8");
      res.on("data", (chunk) => (raw += chunk));
      res.on("end", () => {
        try {
          resolve(JSON.parse(raw));
        } catch {
          reject(new Error("json_parse_error"));
        }
      });
    });

    req.on("error", (err) => reject(err));
    req.setTimeout(timeoutMs, () => req.destroy(new Error("timeout")));
  });
}

// ---- Routes ----
app.get("/", (req, res) => res.status(200).send("ok"));

app.get("/api/version", (req, res) => {
  res.json({
    ok: true,
    service: SERVICE,
    version: APP_VERSION,
    now_utc: nowUTC(),
    pro_json_url: PRO_JSON_URL ? "set" : "missing",
    top10_json_url: TOP10_JSON_URL ? "set" : "missing",
  });
});

app.get("/api/pro", async (req, res) => {
  try {
    if (!PRO_JSON_URL) return res.status(500).json({ ok: false, error: "PRO_JSON_URL_missing" });

    const data = await fetchJson(PRO_JSON_URL, 8000);
    const { items, count } = parseItems(data);

    cache.pro = { items, count, updated_at: nowUTC() };

    return res.json({ ok: true, source: "spaces", updated_at: cache.pro.updated_at, items, count });
  } catch (e) {
    if (cache.pro.count > 0) {
      return res.json({
        ok: true,
        source: "cache",
        warning: String(e.message || e),
        updated_at: cache.pro.updated_at,
        items: cache.pro.items,
        count: cache.pro.count,
      });
    }
    return res.status(500).json({ ok: false, error: String(e.message || e) });
  }
});

app.get("/api/top10", async (req, res) => {
  try {
    if (!TOP10_JSON_URL) return res.status(500).json({ ok: false, error: "TOP10_JSON_URL_missing" });

    const data = await fetchJson(TOP10_JSON_URL, 8000);
    const { items, count } = parseItems(data);

    cache.top10 = { items, count, updated_at: nowUTC() };

    return res.json({ ok: true, source: "spaces", updated_at: cache.top10.updated_at, items, count });
  } catch (e) {
    if (cache.top10.count > 0) {
      return res.json({
        ok: true,
        source: "cache",
        warning: String(e.message || e),
        updated_at: cache.top10.updated_at,
        items: cache.top10.items,
        count: cache.top10.count,
      });
    }
    return res.status(500).json({ ok: false, error: String(e.message || e) });
  }
});

// ---- Start ----
app.listen(PORT, () => {
  console.log(`[${SERVICE}] listening on ${PORT} | now=${nowUTC()}`);
  console.log(`[${SERVICE}] PRO_JSON_URL=${PRO_JSON_URL ? "set" : "missing"}`);
  console.log(`[${SERVICE}] TOP10_JSON_URL=${TOP10_JSON_URL ? "set" : "missing"}`);
});
