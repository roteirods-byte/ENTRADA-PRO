const fs = require("fs");
const path = require("path");
const express = require("express");

const app = express();
const DATA_DIR = process.env.DATA_DIR || "/opt/ENTRADA-PRO/data";
const PORT = Number(process.env.PORT || 3000);

function shortErr(err) {
  const msg = err && err.message ? String(err.message) : String(err || "UNKNOWN");
  return msg.length > 120 ? msg.slice(0, 120) + "..." : msg;
}

function safeReadJson(file) {
  const fullPath = path.join(DATA_DIR, file);
  try {
    const raw = fs.readFileSync(fullPath, "utf8");
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object") return parsed;
    return { ok: false, error: "INVALID_JSON_OBJECT", file };
  } catch (err) {
    if (err && err.code === "ENOENT") return { ok: false, error: "FILE_NOT_FOUND", file };
    if (err instanceof SyntaxError) return { ok: false, error: "INVALID_JSON", file };
    return { ok: false, error: "READ_FAIL", file, message: shortErr(err) };
  }
}

function sendJsonFromFile(res, file) {
  return res.json(safeReadJson(file));
}

app.get("/api/pro", (req, res) => sendJsonFromFile(res, "pro.json"));
app.get("/api/top10", (req, res) => sendJsonFromFile(res, "top10.json"));

app.get(["/api/audit/summary", "/audit/summary"], (req, res) =>
  sendJsonFromFile(res, path.join("audit", "top10_summary.json"))
);

app.get("/api/audit", (req, res) => {
  const summary = safeReadJson(path.join("audit", "top10_summary.json"));
  if (!summary || summary.ok === false) {
    return res.json({
      ok: false,
      source: "local",
      checks: [],
      error: summary && summary.error ? summary.error : "AUDIT_UNAVAILABLE",
    });
  }

  const overall = summary.overall || {};
  const checks = [
    { name: "SUMMARY_PRESENT", ok: true, detail: "top10_summary.json carregado" },
    { name: "OPEN_COUNT", ok: true, detail: String(summary.open_count ?? 0) },
    {
      name: "WIN_RATE",
      ok: true,
      detail: overall.win_rate_pct !== undefined ? String(overall.win_rate_pct) : "0",
    },
  ];

  return res.json({
    ok: true,
    source: "local",
    updated_brt: summary.updated_at_brt || null,
    checks,
  });
});

app.get("/api/health", (req, res) => res.json({ ok: true, service: "entrada-pro-api" }));

process.on("uncaughtException", (err) => {
  console.error("[API] uncaughtException", shortErr(err));
});

process.on("unhandledRejection", (err) => {
  console.error("[API] unhandledRejection", shortErr(err));
});

app.listen(PORT, () => {
  console.log(`[API] listening ${PORT} DATA_DIR=${DATA_DIR}`);
});
