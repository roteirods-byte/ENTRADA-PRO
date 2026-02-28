cat > /opt/ENTRADA-PRO/api/server.js <<'JS'
const fs = require("fs");
const path = require("path");
const express = require("express");

const app = express();
const DATA_DIR = process.env.DATA_DIR || "/opt/ENTRADA-PRO/data";

function readJson(file) {
  const p = path.join(DATA_DIR, file);
  if (!fs.existsSync(p)) return { ok:false, error:"FILE_NOT_FOUND", file };
  const raw = fs.readFileSync(p, "utf8");
  return JSON.parse(raw);
}

app.get("/api/pro", (req,res)=> {
  try { return res.json(readJson("pro.json")); }
  catch(e){ return res.status(500).json({ok:false,error:"READ_FAIL",msg:String(e)}); }
});

app.get("/api/top10", (req,res)=> {
  try { return res.json(readJson("top10.json")); }
  catch(e){ return res.status(500).json({ok:false,error:"READ_FAIL",msg:String(e)}); }
});

app.get("/api/health", (req,res)=> res.json({ok:true, service:"entrada-pro-api"}));

const PORT = process.env.PORT || 3000;
app.listen(PORT, ()=> console.log(`[API] listening ${PORT} DATA_DIR=${DATA_DIR}`));
JS
