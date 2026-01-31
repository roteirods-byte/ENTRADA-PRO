async function fetchJson(url, timeoutMs = 6000) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const r = await fetch(url, { cache: "no-store", signal: ctrl.signal });
    if (!r.ok) throw new Error("HTTP_" + r.status);
    const ct = (r.headers.get("content-type") || "").toLowerCase();
    // aceita json mesmo sem header perfeito
    const txt = await r.text();
    try { return JSON.parse(txt); } catch { throw new Error("RESPOSTA_NAO_JSON"); }
  } finally {
    clearTimeout(t);
  }
}

function fmt3(n) { const x = Number(n); return isFinite(x) ? x.toFixed(3) : ""; }
function fmt2(n) { const x = Number(n); return isFinite(x) ? x.toFixed(2) : ""; }
function sideClass(s) {
  s = String(s || "").toUpperCase();
  if (s === "LONG") return "long";
  if (s === "SHORT") return "short";
  return "nao";
}
function pctClass(p) { const x = Number(p); if (!isFinite(x)) return ""; return x >= 0 ? "pos" : "neg"; }

function showOffline(msg) {
  const el = document.getElementById("offline") || document.getElementById("err");
  if (!el) return;
  el.style.display = "block";
  el.textContent = msg || "API indisponível. O HTML abriu (ok), mas não conseguiu buscar dados.";
}

function pick(it, keys) {
  for (const k of keys) {
    if (it && it[k] !== undefined && it[k] !== null) return it[k];
  }
  return null;
}

function setMetaText(txt) {
  const meta = document.getElementById("meta");
  if (meta) meta.textContent = txt;
  const upd = document.getElementById("upd");
  const cnt = document.getElementById("cnt");
  if (upd) upd.textContent = txt;
  if (cnt) cnt.textContent = "";
}

function renderRows(items) {
  const tbody = document.getElementById("rows");
  const cards = document.getElementById("cards");
  if (!tbody) return;

  tbody.innerHTML = "";
  if (cards) cards.innerHTML = "";

  // remove itens “vazios” (par nulo etc)
  const clean = (items || []).filter(it => {
    const par = pick(it, ["par", "PAR"]);
    return !!par;
  });

  if (!clean.length) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="8" class="small">Sem dados (ainda).</td>`;
    tbody.appendChild(tr);
    return;
  }

  for (const it of clean) {
    const par = pick(it, ["par", "PAR"]) || "";
    const side = (pick(it, ["side", "SIDE"]) || "").toUpperCase();
    const modo = pick(it, ["modo", "MODO"]) || "";
    const entrada = pick(it, ["entrada", "preco", "ENTRADA", "PREÇO"]);
    const alvo = pick(it, ["alvo", "ALVO"]);
    const ganho = pick(it, ["ganho_pct", "GANHO_PCT", "ganhoPct"]);
    const assertv = pick(it, ["assert_pct", "ASSERT_PCT", "assertPct"]);
    const prazoH = pick(it, ["prazo_h", "PRAZO_H", "prazo", "PRAZO"]);

    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td>${par}</td>` +
      `<td class="${sideClass(side)}">${side}</td>` +
      `<td>${modo}</td>` +
      `<td>${fmt3(entrada)}</td>` +
      `<td>${fmt3(alvo)}</td>` +
      `<td class="${pctClass(ganho)}">${fmt2(ganho)}%</td>` +
      `<td>${fmt2(assertv)}%</td>` +
      `<td>${fmt2(prazoH)}h</td>`;
    tbody.appendChild(tr);

    if (cards) {
      const div = document.createElement("div");
      div.className = "item";
      div.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
          <div class="pill"><b>${par}</b></div>
          <div class="pill ${sideClass(side)}">${side}</div>
        </div>
        <div class="grid">
          <div><div class="k">MODO</div><div class="v">${modo}</div></div>
          <div><div class="k">PRAZO</div><div class="v">${fmt2(prazoH)}h</div></div>
          <div><div class="k">ENTRADA</div><div class="v">${fmt3(entrada)}</div></div>
          <div><div class="k">ALVO</div><div class="v">${fmt3(alvo)}</div></div>
          <div><div class="k">GANHO</div><div class="v ${pctClass(ganho)}">${fmt2(ganho)}%</div></div>
          <div><div class="k">ASSERT</div><div class="v">${fmt2(assertv)}%</div></div>
        </div>`;
      cards.appendChild(div);
    }
  }
}

async function boot(kind) {
  try {
    if (kind === "full") {
      const j = await fetchJson("/api/pro");
      setMetaText(`atualizado ${j.updated_brt || "-"} • itens ${(j.items || []).length}`);
      renderRows(j.items || []);
      return;
    }
    if (kind === "top10") {
      const j = await fetchJson("/api/top10");
      setMetaText(`atualizado ${j.updated_brt || "-"} • itens ${(j.items || []).length}`);
      renderRows(j.items || []);
      return;
    }
    // audit
    const j = await fetchJson("/api/audit");
    const out = document.getElementById("audit_json");
    if (out) out.textContent = JSON.stringify(j, null, 2);
  } catch (e) {
    showOffline("API indisponível. (" + (e && e.message ? e.message : "erro") + ")");
  }
}
