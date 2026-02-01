/**
 * ENTRADA-PRO API (Node/Express)
 * - Lê JSONs do DATA_DIR e expõe endpoints
 * - Regra anti-trava: nunca retornar 404/400 para o painel; sempre JSON ok:false
 */
"use strict";

const express = require("express");
const fs = require("fs");
const path = require("path");

const app = express();

const PORT = Number(process.env.PORT || 8095);
const DATA_DIR = process.env.DATA_DIR || "/home/roteiro_ds/AUTOTRADER-PRO/data";

function safeJsonRead(fp) {
  try {
    if (!fs.existsSync(fp)) return null;
    const raw = fs.readFileSync(fp, "utf-8");
    return JSON.parse(raw);
  } catch (e) {
    return null;
  }
}

function serveJsonFile(res, filename, notFoundError) {
  const fp = path.join(DATA_DIR, filename);
  const data = safeJsonRead(fp);
  // Regra anti-trava: NUNCA devolver 404 para o painel (senão o JS quebra)
  if (!data) return res.json({ ok: false, error: notFoundError, data_dir: DATA_DIR });
  return res.json(data);
}

// HEALTH
app.get("/health", (req, res) => {
  res.json({ ok: true, service: "entrada-pro-api", now_utc: new Date().toISOString(), data_dir: DATA_DIR });
});
app.get("/api/health", (req, res) => {
  res.json({ ok: true, service: "entrada-pro-api", now_utc: new Date().toISOString(), data_dir: DATA_DIR });
});

// VERSION
app.get("/version", (req, res) => {
  const fp = path.join(__dirname, "..", "VERSION");
  const v = fs.existsSync(fp) ? fs.readFileSync(fp, "utf-8").trim() : "0.0.0";
  res.json({ ok: true, service: "entrada-pro-api", version: v });
});
app.get("/api/version", (req, res) => {
  const fp = path.join(__dirname, "..", "VERSION");
  const v = fs.existsSync(fp) ? fs.readFileSync(fp, "utf-8").trim() : "0.0.0";
  res.json({ ok: true, service: "entrada-pro-api", version: v });
});

// PRO / TOP10
app.get("/api/pro", (req, res) => serveJsonFile(res, "pro.json", "pro.json_not_found"));
app.get("/pro", (req, res) => serveJsonFile(res, "pro.json", "pro.json_not_found"));

app.get("/api/top10", (req, res) => serveJsonFile(res, "top10.json", "top10.json_not_found"));
app.get("/top10", (req, res) => serveJsonFile(res, "top10.json", "top10.json_not_found"));

// extras compat
app.get("/api/pro/full", (req, res) => serveJsonFile(res, "pro.json", "pro.json_not_found"));
app.get("/api/pro/top10", (req, res) => serveJsonFile(res, "top10.json", "top10.json_not_found"));

// AUDIT
app.get("/api/audit", (req, res) => serveJsonFile(res, "audit.json", "audit.json_not_found"));
app.get("/audit", (req, res) => serveJsonFile(res, "audit.json", "audit.json_not_found"));

// static site (se quiser servir pelo node também)
const SITE_DIR = process.env.SITE_DIR || path.join(__dirname, "..", "site");
app.use("/", express.static(SITE_DIR));

app.listen(PORT, () => {
  console.log(`[ENTRADA-PRO] API on :${PORT} | DATA_DIR=${DATA_DIR} | SITE_DIR=${SITE_DIR}`);
});
