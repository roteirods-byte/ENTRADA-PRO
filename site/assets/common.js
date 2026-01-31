// BUILD FIX: common.js v2 (2026-01-31) - endpoints corretos + colunas completas + null não vira 0

async function fetchJson(url, timeoutMs = 8000) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const r = await fetch(url, { cache: "no-store", signal: ctrl.signal });
    const ct = (r.headers.get("content-type") || "").toLowerCase();
    if (!r.ok) throw new Error(`HTTP_${r.status}`);
    if (!ct.includes("application/json")) throw new Error("NAO_JSON");
    return await r.json();
  } finally {
    clearTimeout(t);
  }
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"]/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;" }[c]));
}

function isNil(v){ return v === null || v === undefined || v === ""; }

function fmtPrice(v){
  if (isNil(v)) return "-";
  const n = Number(v);
  return isFinite(n) ? n.toFixed(3) : "-";
}
function fmtPct(v){
  if (isNil(v)) return "-";
  const n = Number(v);
  return isFinite(n) ? n.toFixed(2) + "%" : "-";
}
function fmtTxt(v){
  return isNil(v) ? "-" : String(v);
}

function sideClass(v){
  const s = String(v||"").toUpperCase();
  if (s === "LONG") return "side-long";
  if (s === "SHORT") return "side-short";
  return "side-nao";
}
function pctClass(v){
  const n = Number(v);
  if (!isFinite(n)) return "";
  return n >= 0 ? "pct-pos" : "pct-neg";
}

// Colunas completas (as que estavam faltando no seu print)
const COLS_FULL = [
  ["PAR","PAR"],
  ["SIDE","SIDE"],
  ["MODO","MODO"],
  ["ENTRADA","ENTRADA"],
  ["ALVO","ALVO"],
  ["GANHO_PCT","GANHO %"],
  ["ASSERT_PCT","ASSERT %"],
  ["PRAZO","PRAZO"],
  ["ZONA","ZONA"],
  ["RISCO","RISCO"],
  ["PRIORIDADE","PRIORIDADE"],
  ["DATA","DATA"],
  ["HORA","HORA"],
];

const COLS_TOP10 = COLS_FULL;

function renderTable(el, items, cols){
  if(!items || !items.length){
    el.innerHTML = "<p class='err'>Sem dados (API/Worker).</p>";
    return;
  }
  const thead = "<tr>" + cols.map(([k,label])=>`<th>${esc(label)}</th>`).join("") + "</tr>";
  const rows = items.map(it=>{
    return "<tr>" + cols.map(([k])=>{
      const v = it[k];

      if(k === "SIDE") return `<td class="${sideClass(v)}">${esc(fmtTxt(v))}</td>`;
      if(k === "GANHO_PCT" || k === "ASSERT_PCT"){
        const cls = pctClass(v);
        return `<td class="${cls}">${esc(fmtPct(v))}</td>`;
      }
      if(k === "ENTRADA" || k === "ALVO"){
        return `<td>${esc(fmtPrice(v))}</td>`;
      }
      return `<td>${esc(fmtTxt(v))}</td>`;
    }).join("") + "</tr>";
  }).join("");

  el.innerHTML = `<div class="tableWrap"><table><thead>${thead}</thead><tbody>${rows}</tbody></table></div>`;
}

function setBadges(meta){
  const upd = document.getElementById("upd");
  const cnt = document.getElementById("cnt");
  const src = document.getElementById("src");
  if(upd) upd.textContent = meta.updated_brt ? `Atualizado (BRT): ${meta.updated_brt}` : "Atualizado (BRT): -";
  if(cnt) cnt.textContent = `Itens: ${meta.count ?? 0}`;
  if(src) src.textContent = meta.source ? `Fonte: ${meta.source}` : "Fonte: -";
}

// ENDPOINTS CORRETOS (sem /api/pro/top10)
// FULL usa /api/pro
async function loadFull(){
  const tableEl = document.getElementById("table");
  const j = await fetchJson("/api/pro");
  if(!j.ok) throw new Error(j.error || "API ok=false");
  setBadges(j);
  renderTable(tableEl, j.items || [], COLS_FULL);
}

// TOP10 usa /api/top10 (esse existe e o audit também usa)
async function loadTop10(){
  const tableEl = document.getElementById("table");
  const j = await fetchJson("/api/top10");
  if(!j.ok) throw new Error(j.error || "API ok=false");
  setBadges(j);
  renderTable(tableEl, j.items || [], COLS_TOP10);
}

async function loadAudit(){
  const tableEl = document.getElementById("table");
  const j = await fetchJson("/api/audit");
  if(!j.ok) throw new Error(j.error || "AUDIT ok=false");
  setBadges(j);
  const cols = [["name","CHECK"],["ok","OK?"],["detail","DETALHE"]];
  renderTable(tableEl, j.checks || [], cols);
}

async function boot(kind){
  const errEl = document.getElementById("err");
  try{
    if(kind==="full") await loadFull();
    else if(kind==="top10") await loadTop10();
    else await loadAudit();
  }catch(e){
    if(errEl) errEl.textContent = "API indisponível. (" + (e && e.message ? e.message : "erro") + ")";
  }
}
