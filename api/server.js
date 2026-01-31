"use strict";

const DEFAULT_SOURCE = process.env.PRICE_SOURCE || "MARK_PRICE";

const fs = require("fs");
const path = require("path");
const express = require("express");
const cors = require("cors");

const app = express();
app.use(cors());

const PORT = parseInt(process.env.PORT || "8090", 10);
const DATA_DIR = process.env.DATA_DIR || path.join(__dirname, "..", "data");

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

function healthPayload() {
  const now = new Date().toISOString();
  const audit = safeJsonRead(path.join(DATA_DIR, "audit.json"));
  return {
    ok: true,
    service: "entrada-pro-api",
    now_utc: now,
    data_dir: DATA_DIR,
    audit:
      audit && audit.ok === true
        ? { ok: true, updated_brt: audit.updated_brt, counts: audit.counts }
        : { ok: false },
  };
}

function readVersion() {
  const candidates = [
    path.join(__dirname, "..", "VERSION"),
    path.join(__dirname, "VERSION"),
    path.join(process.cwd(), "VERSION"),
  ];
  for (const fp of candidates) {
    try {
      if (fs.existsSync(fp)) {
        const v = String(fs.readFileSync(fp, "utf-8")).trim();
        if (v) return v;
      }
    } catch (e) {}
  }
  // fallback: package.json
  try {
    const pj = require("./package.json");
    return pj && pj.version ? String(pj.version) : "0.0.0";
  } catch (e) {
    return "0.0.0";
  }
}

function serveJsonFile(res, filename, notFoundError) {
  const fp = path.join(DATA_DIR, filename);
  const data = safeJsonRead(fp);
  if (!data) return res.status(404).json({ ok: false, error: notFoundError, data_dir: DATA_DIR });
  return res.json(data);
}

// compat (nginx pode reescrever /api/* -> /* dependendo do proxy_pass)
app.get("/health", (req, res) => res.json(healthPayload()));
app.get("/api/health", (req, res) => res.json(healthPayload()));

app.get("/version", (req, res) =>
  res.json({ ok: true, service: "entrada-pro-api", version: readVersion(), now_utc: new Date().toISOString() })
);
app.get("/api/version", (req, res) =>
  res.json({ ok: true, service: "entrada-pro-api", version: readVersion(), now_utc: new Date().toISOString() })
);

// PRO
app.get("/api/pro", (req, res) => serveJsonFile(res, "pro.json", "pro.json_not_found"));
app.get("/pro", (req, res) => serveJsonFile(res, "pro.json", "pro.json_not_found"));

// TOP10
app.get("/api/top10", (req, res) => serveJsonFile(res, "top10.json", "top10.json_not_found"));
app.get("/top10", (req, res) => serveJsonFile(res, "top10.json", "top10.json_not_found"));

// COMPAT (frontend antigo)
app.get("/api/pro/full", (req, res) => serveJsonFile(res, "pro.json", "pro.json_not_found"));
app.get("/api/pro/top10", (req, res) => serveJsonFile(res, "top10.json", "top10.json_not_found"));

// AUDIT
app.get("/api/audit", (req, res) => serveJsonFile(res, "audit.json", "audit.json_not_found"));
app.get("/audit", (req, res) => serveJsonFile(res, "audit.json", "audit.json_not_found"));

// static site (opcional) se quiser servir pelo node
const SITE_DIR = process.env.SITE_DIR || path.join(__dirname, "..", "site");
app.use("/", express.static(SITE_DIR));

app.listen(PORT, () => {
  console.log(`[ENTRADA-PRO] API on :${PORT} | DATA_DIR=${DATA_DIR} | SITE_DIR=${SITE_DIR}`);
});