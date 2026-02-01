// BUILD FIX: common.js v3 (2026-02-01)
// - Compatível com o HTML atual (FULL/TOP10 usa tbody#rows; AUDIT usa pre#audit_json)
// - Se a API responder ok=false, mostra motivo (sem tratar como "API caiu")

async function fetchJson(url, timeoutMs = 8000) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const r = await fetch(url, { cache: "no-store", signal: ctrl.signal });
    const ct = (r.headers.get("content-type") || "").toLowerCase();
    if (!ct.includes("application/json")) {
      throw new Error(r.ok ? "NAO_JSON" : `HTTP_${r.status}`);
    }
    const j = await r.json();
    // Mesmo se HTTP != 200, se veio JSON devolvemos para a UI mostrar o erro.
    if (!r.ok && j && typeof j === "object" && !("_http" in j)) j._http = r.status;
    return j;
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

function getErrEl(){
  return document.getElementById("err") || document.getElementById("offline");
}
function showErr(msg){
  const el = getErrEl();
  if(!el) return;
  el.textContent = msg;
  // HTML atual usa display via classe; então só garante que aparece.
  el.style.display = "block";
}
function hideErr(){
  const el = getErrEl();
  if(!el) return;
  el.textContent = "";
  el.style.display = "none";
}

function setBadges(meta){
  const upd = document.getElementById("upd");
  const cnt = document.getElementById("cnt");
  const src = document.getElementById("src");
  const badge = document.getElementById("meta");

  const updText = meta && meta.updated_brt ? `Atualizado (BRT): ${meta.updated_brt}` : "Atualizado (BRT): -";
  const cntText = `Itens: ${meta && meta.count !== undefined ? meta.count : 0}`;
  const srcText = meta && meta.source ? `Fonte: ${meta.source}` : "Fonte: -";

  if (upd) upd.textContent = updText;
  if (cnt) cnt.textContent = cntText;
  if (src) src.textContent = srcText;
  if (badge) badge.textContent = `${updText} • ${cntText} • ${srcText}`;
}

function renderRows(tbody, items, cols){
  if(!items || !items.length){
    tbody.innerHTML = "";
    return;
  }
  const rows = items.map(it=>{
    return "<tr>" + cols.map(([k])=>{
      const v = it[k];
      if(k === "SIDE") return `<td class="${sideClass(v)}">${esc(fmtTxt(v))}</td>`;
      if(k === "GANHO_PCT" || k === "ASSERT_PCT"){
        const cls = pctClass(v);
        return `<td class="${cls}">${esc(fmtPct(v))}</td>`;
      }
      if(k === "ENTRADA" || k === "ALVO") return `<td>${esc(fmtPrice(v))}</td>`;
      return `<td>${esc(fmtTxt(v))}</td>`;
    }).join("") + "</tr>";
  }).join("");
  tbody.innerHTML = rows;
}

async function loadFull(){
  const tbody = document.getElementById("rows");
  const j = await fetchJson("/api/pro");
  setBadges(j || {});

  if(!j || !j.ok){
    const dir = j && j.data_dir ? j.data_dir : "-";
    const err = j && j.error ? j.error : "sem_dados";
    showErr(`Sem dados: ${err} (DATA_DIR: ${dir})`);
    if (tbody) tbody.innerHTML = "";
    return;
  }

  hideErr();
  if (tbody) renderRows(tbody, j.items || [], COLS_FULL);
}

async function loadTop10(){
  const tbody = document.getElementById("rows");
  const j = await fetchJson("/api/top10");
  setBadges(j || {});

  if(!j || !j.ok){
    const dir = j && j.data_dir ? j.data_dir : "-";
    const err = j && j.error ? j.error : "sem_dados";
    showErr(`Sem dados: ${err} (DATA_DIR: ${dir})`);
    if (tbody) tbody.innerHTML = "";
    return;
  }

  hideErr();
  if (tbody) renderRows(tbody, j.items || [], COLS_TOP10);
}

async function loadAudit(){
  const pre = document.getElementById("audit_json");
  const j = await fetchJson("/api/audit");
  setBadges(j || {});

  if(!j || !j.ok){
    const dir = j && j.data_dir ? j.data_dir : "-";
    const err = j && j.error ? j.error : "sem_dados";
    showErr(`Sem dados: ${err} (DATA_DIR: ${dir})`);
    if (pre) pre.textContent = "";
    return;
  }

  hideErr();
  if (pre) pre.textContent = JSON.stringify(j, null, 2);
}

async function boot(kind){
  try{
    if(kind === "full") await loadFull();
    else if(kind === "top10") await loadTop10();
    else await loadAudit();
  }catch(e){
    const msg = (e && e.message) ? e.message : "erro";
    showErr("API indisponível. (" + msg + ")");
  }
}
