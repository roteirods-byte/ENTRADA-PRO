"use strict";

const fs = require("fs");
const path = require("path");
const http = require("http");
const https = require("https");
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

function getJsonFromUrl(url, timeoutMs = 8000) {
  return new Promise((resolve, reject) => {
    try {
      const u = new URL(url);
      const lib = u.protocol === "https:" ? https : http;

      const req = lib.request(
        {
          method: "GET",
          hostname: u.hostname,
          path: u.pathname + (u.search || ""),
          headers: { "cache-control": "no-cache" },
        },
        (res) => {
          // redirecionamento simples
          if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
            return resolve(getJsonFromUrl(res.headers.location, timeoutMs));
          }

          if (res.statusCode !== 200) {
            return reject(new Error("http_" + res.statusCode));
          }

          let data = "";
          res.on("data", (chunk) => (data += chunk));
          res.on("end", () => {
            try {
              resolve(JSON.parse(data));
            } catch (e) {
              reject(new Error("invalid_json"));
            }
          });
        }
      );

      req.setTimeout(timeoutMs, () => {
        req.destroy(new Error("timeout"));
      });

      req.on("error", reject);
      req.end();
    } catch (e) {
      reject(e);
    }
  });
}

async function serveJson(res, filename, notFoundError) {
  const now = Date.now();

  const url =
    filename === "pro.json" ? PRO_JSON_URL :
    filename === "top10.json" ? TOP10_JSON_URL :
    "";

  // 1) tenta pelo link (Spaces)
  if (url) {
    const c = cache[filename];
    if (c && c.data && now - c.ts < CACHE_TTL_MS) return res.json(c.data);

    try {
      const data = await getJsonFromUrl(url);
      if (c) { c.ts = now; c.data = data; }
      return res.json(data);
    } catch (e) {
      // se falhar, tenta local
    }
  }

  // 2) tenta local
  const fp = path.join(DATA_DIR, filename);
  const local = safeJsonRead(fp);

  if (!local) {
    return res.json({
      ok: false,
      error: notFoundError,
      data_dir: DATA_DIR,
      items: [],
      count: 0,
    });
  }

  return res.json(local);
}

app.get("/", (req, res) =>
  res.json({ ok: true, message: "entrada-pro-api", now_utc: new Date().toISOString() })
);

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

app.listen(PORT, () => console.log(`[ENTRADA-PRO] API on :${PORT}`));
