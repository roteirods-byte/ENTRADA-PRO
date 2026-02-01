// common.js v3 (2026-02-01) - compatível com HTML antigo (rows/offline/meta) e novo (table/err/upd)

async function fetchJson(url, timeoutMs = 8000) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const r = await fetch(url, { cache: "no-store", signal: ctrl.signal });
    const ct = (r.headers.get("content-type") || "").toLowerCase();
    if (!ct.includes("application/json")) throw new Error("NAO_JSON");
    const j = await r.json();
    return { http_ok: r.ok, status: r.status, json: j };
  } finally {
    clearTimeout(t);
  }
}

function $(...ids){
  for (const id of ids){
    const el = document.getElementById(id);
    if (el) return el;
  }
  return null;
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
function fmtTxt(v){ return isNil(v) ? "-" : String(v); }

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

// colunas oficiais completas (não trava se HTML tiver menos colunas)
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

function setBadges(meta){
  const upd = $("upd","meta");
  const cnt = $("cnt");
  const src = $("src");
  if (upd) upd.textContent = meta.updated_brt ? `Atualizado (BRT): ${meta.updated_brt}` : "Atualizado (BRT): -";
  if (cnt) cnt.textContent = `Itens: ${meta.count ?? 0}`;
  if (src) src.textContent = meta.source ? `Fonte: ${meta.source}` : "Fonte: -";
}

function showErr(msg){
  const errEl = $("err","offline");
  if (errEl){
    errEl.style.display = "block";
    errEl.textContent = msg;
  }
}

function renderIntoTableDiv(tableEl, items, cols){
  if(!tableEl) return;
  if(!items || !items.length){
    tableEl.innerHTML = "<p class='err'>Sem dados (API/Worker).</p>";
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
  tableEl.innerHTML = `<div class="tableWrap"><table><thead>${thead}</thead><tbody>${rows}</tbody></table></div>`;
}

function renderIntoTbody(rowsEl, items, cols){
  if(!rowsEl) return;
  if(!items || !items.length){
    rowsEl.innerHTML = "";
    return;
  }
  rowsEl.innerHTML = items.map(it=>{
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
}

async function loadFull(){
  const tableEl = $("table");
  const rowsEl = $("rows");
  const out = await fetchJson("/api/pro");
  const j = out.json || {};
  if(!j.ok) { showErr(j.error ? String(j.error) : `Erro /api/pro`); return; }
  setBadges(j);
  // preferir HTML antigo (tbody#rows), senão usa div#table
  if (rowsEl) renderIntoTbody(rowsEl, j.items || [], COLS_FULL);
  else renderIntoTableDiv(tableEl, j.items || [], COLS_FULL);
}

async function loadTop10(){
  const tableEl = $("table");
  const rowsEl = $("rows");
  const out = await fetchJson("/api/top10");
  const j = out.json || {};
  if(!j.ok) { showErr(j.error ? String(j.error) : `Erro /api/top10`); return; }
  setBadges(j);
  if (rowsEl) renderIntoTbody(rowsEl, j.items || [], COLS_FULL);
  else renderIntoTableDiv(tableEl, j.items || [], COLS_FULL);
}

async function loadAudit(){
  const pre = $("audit_json");
  const tableEl = $("table");
  const out = await fetchJson("/api/audit");
  const j = out.json || {};
  // se audit.json não existir, mostra mensagem sem travar
  if(!j.ok){
    showErr(j.error ? String(j.error) : "AUDIT indisponível");
    if (pre) pre.textContent = JSON.stringify(j, null, 2);
    return;
  }
  setBadges(j);
  const cols = [["name","CHECK"],["ok","OK?"],["detail","DETALHE"]];
  // audit pode aparecer como tabela OU como JSON no <pre>
  if (pre) pre.textContent = JSON.stringify(j, null, 2);
  renderIntoTableDiv(tableEl, j.checks || [], cols);
}

async function boot(kind){
  try{
    if(kind==="full") await loadFull();
    else if(kind==="top10") await loadTop10();
    else await loadAudit();
  }catch(e){
    showErr("Erro no painel. (" + (e && e.message ? e.message : "erro") + ")");
  }
}
