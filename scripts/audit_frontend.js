/**
 * Frontend Audit (AVP) - checks contract between HTML and JS
 * Run: node scripts/audit_frontend.js
 */
"use strict";
const fs = require("fs");
const path = require("path");

const SITE = path.join(__dirname, "..", "site");
const files = ["full.html","top10.html","audit.html"];
const mustCss = '/assets/style.css';
const mustJs = '/assets/common.js';

function read(p){ return fs.readFileSync(p, "utf-8"); }

let ok = true;
for (const f of files){
  const html = read(path.join(SITE, f));
  if(!html.includes(mustCss)){ console.error("FAIL", f, "missing", mustCss); ok=false; }
  if(!html.includes(mustJs)){ console.error("FAIL", f, "missing", mustJs); ok=false; }
}

const js = read(path.join(SITE, "assets", "common.js"));
if(js.includes("/api/pro/top10") || js.includes("/api/pro/full")){
  console.error("FAIL common.js: should call /api/top10 and /api/pro (not /api/pro/top10 or /api/pro/full)");
  ok=false;
}
const needCols = ["PAR","SIDE","ENTRADA","ALVO","GANHO_PCT","ASSERT_PCT","PRAZO","ZONA","RISCO","PRIORIDADE","DATA","HORA"];
for (const k of needCols){
  if(!js.includes(`["${k}"`)) { console.error("FAIL common.js: missing column", k); ok=false; }
}
if(js.includes('["MODO"')) { console.error("FAIL common.js: must not include MODO column in table"); ok=false; }

if(ok) console.log("OK: frontend contract looks correct.");
process.exit(ok?0:1);
