// BUILD FIX: common.js v3 (2026-02-01)
// - Compatível com o HTML atual (FULL/TOP10 usa tbody#rows)
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

async function fetchJsonAny(urls, timeoutMs = 8000) {
  let lastErr = null;
  for (const url of urls) {
    try {
      return await fetchJson(url, timeoutMs);
    } catch (e) {
      lastErr = e;
    }
  }
  throw lastErr || new Error('fetch_error');
}

function apiUrls(path) {
  // tenta primeiro /api/... e depois sem /api (para evitar 404)
  const p = path.startsWith('/') ? path : `/${path}`;
  if (p.startsWith('/api/')) return [p, p.replace(/^\/api\//, '/')];
  return [`/api${p}`, p];
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

// ASSERT%: cor por qualidade (não por sinal)
function assertClass(v){
  const n = Number(v);
  if (!isFinite(n)) return "";
  if (n >= 65) return "pct-pos";     // verde
  if (n >= 50) return "pct-mid";     // amarelo
  return "pct-neg";                  // vermelho
}

function tagClass(v){
  const s = String(v||"").toUpperCase();
  if (s.includes("ALTA") || s === "HIGH") return "tag-high";
  if (s.includes("MEDIA") || s.includes("MÉDIA") || s === "MEDIUM") return "tag-mid";
  if (s.includes("BAIXA") || s === "LOW") return "tag-low";
  return "tag-unk";
}

const COLS_FULL = [
  ["PAR","PAR"],
  ["SIDE","SIDE"],
  ["ENTRADA","ENTRADA"],
  ["ATUAL","ATUAL"],
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

function renderRows(tbody, items, cols, meta){
  if(!items || !items.length){
    tbody.innerHTML = "";
    return;
  }

  // fallback DATA/HORA a partir do updated_brt (se vier)
  let fbDate = null, fbTime = null;
  const ub = meta && meta.updated_brt ? String(meta.updated_brt) : "";
  const m = ub.match(/^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})/);
  if (m){ fbDate = m[1]; fbTime = m[2]; }

  const rows = items.map(it=>{
    return "<tr>" + cols.map(([k])=>{
      let v = it[k];

      if ((k === "DATA" || k === "HORA") && (isNil(v))){
        v = (k === "DATA") ? fbDate : fbTime;
      }

      if(k === "SIDE") return `<td class="${sideClass(v)}">${esc(fmtTxt(v))}</td>`;

      if(k === "GANHO_PCT"){
        const cls = pctClass(v);
        return `<td class="${cls}">${esc(fmtPct(v))}</td>`;
      }

      if(k === "ASSERT_PCT"){
        const cls = assertClass(v);
        return `<td class="${cls}">${esc(fmtPct(v))}</td>`;
      }

      if(k === "ENTRADA" || k === "ATUAL" || k === "ALVO"){
        return `<td>${esc(fmtPrice(v))}</td>`;
      }

      if(k === "ZONA" || k === "RISCO" || k === "PRIORIDADE"){
        const cls = tagClass(v);
        return `<td class="${cls}">${esc(fmtTxt(v))}</td>`;
      }

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
  if (tbody) renderRows(tbody, j.items || [], COLS_FULL, j);
}

async function loadTop10(){
  const tbody = document.getElementById("rows");

  // tenta usar top10.json; se não existir, deriva do /api/pro (10 maiores GANHO_PCT)
  let j = await fetchJson("/api/top10");
  if(!j || !j.ok || !Array.isArray(j.items) || j.items.length === 0){
    const j2 = await fetchJson("/api/pro");
    if(j2 && j2.ok && Array.isArray(j2.items)){
      const items = [...j2.items].filter(it => !isNil(it.GANHO_PCT));
      items.sort((a,b)=> (num(b.GANHO_PCT) - num(a.GANHO_PCT)) || (num(b.ASSERT_PCT) - num(a.ASSERT_PCT)));
      const top = items.slice(0, 10);

      setBadges(Object.assign({}, j2, { count: top.length, source: "DERIVADO_PRO" }));
      hideErr();
      if (tbody) renderRows(tbody, top, COLS_TOP10, j2);
      return;
    }

    setBadges(j || j2 || {});
    const dir = (j && j.data_dir) ? j.data_dir : ((j2 && j2.data_dir) ? j2.data_dir : "-");
    const err = (j && j.error) ? j.error : ((j2 && j2.error) ? j2.error : "sem_dados");
    showErr(`Sem dados: ${err} (DATA_DIR: ${dir})`);
    if (tbody) tbody.innerHTML = "";
    return;
  }

  setBadges(j || {});
  hideErr();
  if (tbody) renderRows(tbody, j.items || [], COLS_TOP10, j);
}


async function boot(kind){
  try{
    if(kind === "full") await loadFull();
    else if(kind === "top10") await loadTop10();
    else await loadFull();
  }catch(e){
    const msg = (e && e.message) ? e.message : "erro";
    showErr("API indisponível. (" + msg + ")");
  }
}

// garante acesso global
window.boot = boot;
