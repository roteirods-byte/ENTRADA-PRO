// api/server.js
"use strict";

const express = require("express");
const cors = require("cors");

const app = express();
app.use(cors());
app.use(express.json({ limit: "1mb" }));

// =======================
// NO-CACHE helpers
// =======================
function noStore(res) {
  res.setHeader("Cache-Control", "no-store, no-cache, must-revalidate, proxy-revalidate");
  res.setHeader("Pragma", "no-cache");
  res.setHeader("Expires", "0");
  res.setHeader("Surrogate-Control", "no-store");
}

async function fetchJsonNoCache(url) {
  const u = new URL(url);

  // cache-bust para quebrar CDN/proxy/edge
  u.searchParams.set("t", String(Date.now()));

  const r = await fetch(u.toString(), {
    method: "GET",
    cache: "no-store",
    headers: {
      "Accept": "application/json",
      "Cache-Control": "no-cache",
      "Pragma": "no-cache",
    },
  });

  if (!r.ok) {
    const txt = await r.text().catch(() => "");
    throw new Error(`fetch ${u.toString()} -> ${r.status} ${txt.slice(0, 200)}`);
  }

  // Spaces pode vir como JSON puro (array/obj) ou wrapper {items,...}
  return r.json();
}

function unwrapItems(data) {
  if (!data) return { items: [] };
  if (Array.isArray(data)) return { items: data };
  if (typeof data === "object" && Array.isArray(data.items)) return { ...data, items: data.items };
  // fallback: objeto único vira "items: [obj]"
  return { items: [data] };
}

// =======================
// Routes
// =======================
app.get("/api/health", (req, res) => {
  noStore(res);
  res.json({ ok: true });
});

app.get("/api/version", (req, res) => {
  noStore(res);
  res.json({
    ok: true,
    service: "entrada-pro-api",
    version: process.env.APP_VERSION || process.env.VERSION || "unknown",
    now_utc: new Date().toISOString(),
    data_dir: process.env.DATA_DIR || "/workspace/data",
    pro_json_url: process.env.PRO_JSON_URL ? "set" : "not_set",
    top10_json_url: process.env.TOP10_JSON_URL ? "set" : "not_set",
  });
});

app.get("/api/pro", async (req, res) => {
  try {
    noStore(res);

    const url = process.env.PRO_JSON_URL;
    if (!url) return res.status(500).json({ ok: false, error: "PRO_JSON_URL not set" });

    const raw = await fetchJsonNoCache(url);
    const data = unwrapItems(raw);

    res.json({
      ok: true,
      source: "spaces",
      updated_at: data.updated_at || data.generated_at || new Date().toISOString(),
      items: data.items,
    });
  } catch (e) {
    noStore(res);
    res.status(500).json({ ok: false, error: String(e?.message || e) });
  }
});

app.get("/api/top10", async (req, res) => {
  try {
    noStore(res);

    const url = process.env.TOP10_JSON_URL;
    if (!url) return res.status(500).json({ ok: false, error: "TOP10_JSON_URL not set" });

    const raw = await fetchJsonNoCache(url);
    const data = unwrapItems(raw);

    res.json({
      ok: true,
      source: "spaces",
      updated_at: data.updated_at || data.generated_at || new Date().toISOString(),
      items: data.items,
    });
  } catch (e) {
    noStore(res);
    res.status(500).json({ ok: false, error: String(e?.message || e) });
  }
});

// =======================
// Start
// =======================
const PORT = process.env.PORT || 8080;
app.listen(PORT, () => {
  console.log(`entrada-pro-api listening on ${PORT}`);
});
