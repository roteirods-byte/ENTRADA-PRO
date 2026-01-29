async function fetchJson(url){
  const r = await fetch(url, {cache:"no-store"});
  if(!r.ok) throw new Error(`HTTP ${r.status}`);
  return await r.json();
}

function esc(s){ return String(s ?? "").replace(/[&<>"]/g, c=>({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;" }[c])); }

function renderTable(el, items){
  if(!items || !items.length){ el.innerHTML = "<p>Sem dados.</p>"; return; }
  const cols = Object.keys(items[0]);
  const thead = "<tr>" + cols.map(c=>`<th>${esc(c)}</th>`).join("") + "</tr>";
  const rows = items.map(it=>"<tr>"+cols.map(c=>`<td>${esc(it[c])}</td>`).join("")+"</tr>").join("");
  el.innerHTML = `<table><thead>${thead}</thead><tbody>${rows}</tbody></table>`;
}

async function loadFull(){
  const metaEl = document.getElementById("meta");
  const tableEl = document.getElementById("table");
  const j = await fetchJson("/api/pro");
  metaEl.textContent = `updated_brt: ${j.updated_brt} | count: ${j.count}`;
  renderTable(tableEl, j.items);
}

async function loadTop10(){
  const metaEl = document.getElementById("meta");
  const tableEl = document.getElementById("table");
  const j = await fetchJson("/api/top10");
  metaEl.textContent = `updated_brt: ${j.updated_brt} | count: ${j.count}`;
  renderTable(tableEl, j.items);
}

async function loadAudit(){
  const pre = document.getElementById("audit");
  const j = await fetchJson("/api/audit");
  pre.textContent = JSON.stringify(j, null, 2);
}
