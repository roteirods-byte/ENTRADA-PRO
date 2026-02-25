from __future__ import annotations
import os, json
from datetime import datetime, timedelta, timezone, date
from collections import defaultdict

DATA_DIR = os.environ.get("DATA_DIR", "/opt/ENTRADA-PRO/data")
AUDIT_DIR = os.path.join(DATA_DIR, "audit")

CLOSED = os.path.join(AUDIT_DIR, "top10_closed.jsonl")
OUT_JSON = os.path.join(AUDIT_DIR, "top10_metrics_30d.json")
OUT_CSV  = os.path.join(AUDIT_DIR, "top10_metrics_30d.csv")

PERIOD_DAYS = 30
MIN_N = 20  # regra: só confiar quando N >= 20

def _safe_float(x):
    try:
        if x is None: return None
        return float(x)
    except Exception:
        return None

def _parse_date_yyyy_mm_dd(s: str) -> date | None:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None

def _dow_pt(d: date) -> str:
    # 0=Mon ... 6=Sun
    names = ["SEG","TER","QUA","QUI","SEX","SAB","DOM"]
    return names[d.weekday()]

def _hour_from_ts_brt(s: str) -> str | None:
    # "YYYY-MM-DD HH:MM"
    try:
        return s.split(" ")[1][:2]
    except Exception:
        return None

def main():
    now_utc = datetime.now(timezone.utc)
    cutoff = (now_utc - timedelta(days=PERIOD_DAYS)).date()

    if not os.path.exists(CLOSED):
        out = {
            "ok": True,
            "generated_at_utc": now_utc.isoformat().replace("+00:00","Z"),
            "period_days": PERIOD_DAYS,
            "cutoff_date": str(cutoff),
            "note": "SEM_ARQUIVO top10_closed.jsonl",
            "totals": {"n": 0, "wins": 0, "loss": 0, "expired": 0, "pnl_avg_pct": 0.0},
            "by_par": [],
            "by_hour_brt": [],
            "by_dow": [],
            "recommended": {"min_n": MIN_N, "best_par": [], "best_hours": []}
        }
        os.makedirs(AUDIT_DIR, exist_ok=True)
        with open(OUT_JSON, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        return

    rows = []
    with open(CLOSED, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: 
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            d = _parse_date_yyyy_mm_dd(str(r.get("date") or ""))
            if not d:
                continue
            if d < cutoff:
                continue
            rows.append(r)

    # agregadores
    by_par = defaultdict(lambda: {"n":0,"wins":0,"loss":0,"expired":0,"pnl_sum":0.0,"pnl_n":0,"pnl_min":None,"pnl_max":None,"timeout_n":0})
    by_hour = defaultdict(lambda: {"n":0,"wins":0,"loss":0,"expired":0,"pnl_sum":0.0,"pnl_n":0})
    by_dow  = defaultdict(lambda: {"n":0,"wins":0,"loss":0,"expired":0,"pnl_sum":0.0,"pnl_n":0})

    def classify(r):
        pnl = _safe_float(r.get("pnl_pct_real"))
        result = (r.get("result") or "").upper()
        hit = (r.get("hit") or "").upper()

        expired = False
        if pnl is None:
            expired = True
        if result in ("EXPIRED","TIMEOUT"):
            expired = True
        if hit in ("TTL",):
            expired = True

        win = (pnl is not None and pnl > 0)
        loss = (pnl is not None and pnl < 0)
        return pnl, win, loss, expired, (result == "TIMEOUT" or hit == "TTL")

    for r in rows:
        par = str(r.get("par") or "-")
        d = _parse_date_yyyy_mm_dd(str(r.get("date") or "")) or cutoff
        dow = _dow_pt(d)

        hour = None
        # prefer close_ts_brt; senão usa "hora"
        if r.get("close_ts_brt"):
            hour = _hour_from_ts_brt(str(r.get("close_ts_brt")))
        if hour is None and r.get("hora"):
            hour = str(r.get("hora"))[:2]

        pnl, win, loss, expired, is_timeout = classify(r)

        A = by_par[par]
        A["n"] += 1
        if win: A["wins"] += 1
        if loss: A["loss"] += 1
        if expired: A["expired"] += 1
        if is_timeout: A["timeout_n"] += 1

        if pnl is not None:
            A["pnl_sum"] += pnl
            A["pnl_n"] += 1
            A["pnl_min"] = pnl if A["pnl_min"] is None else min(A["pnl_min"], pnl)
            A["pnl_max"] = pnl if A["pnl_max"] is None else max(A["pnl_max"], pnl)

        if hour is not None:
            H = by_hour[hour]
            H["n"] += 1
            if win: H["wins"] += 1
            if loss: H["loss"] += 1
            if expired: H["expired"] += 1
            if pnl is not None:
                H["pnl_sum"] += pnl
                H["pnl_n"] += 1

        D = by_dow[dow]
        D["n"] += 1
        if win: D["wins"] += 1
        if loss: D["loss"] += 1
        if expired: D["expired"] += 1
        if pnl is not None:
            D["pnl_sum"] += pnl
            D["pnl_n"] += 1

    def finalize_item(k, v):
        n = v["n"]
        wins = v["wins"]
        pnl_avg = (v["pnl_sum"]/v["pnl_n"]) if v.get("pnl_n",0) else 0.0
        win_rate = (wins/n*100.0) if n else 0.0
        out = {
            "key": k,
            "n": n,
            "wins": wins,
            "loss": v["loss"],
            "expired": v["expired"],
            "win_rate_pct": round(win_rate, 2),
            "pnl_avg_pct": round(pnl_avg, 4),
        }
        if "pnl_min" in v:
            out["pnl_min_pct"] = None if v["pnl_min"] is None else round(v["pnl_min"], 4)
            out["pnl_max_pct"] = None if v["pnl_max"] is None else round(v["pnl_max"], 4)
        if "timeout_n" in v:
            out["timeout_pct"] = round((v["timeout_n"]/n*100.0), 2) if n else 0.0
        return out

    par_list  = [finalize_item(k,v) for k,v in by_par.items()]
    hour_list = [finalize_item(k,v) for k,v in by_hour.items()]
    dow_list  = [finalize_item(k,v) for k,v in by_dow.items()]

    par_list.sort(key=lambda x: (x["pnl_avg_pct"], x["win_rate_pct"], x["n"]), reverse=True)
    hour_list.sort(key=lambda x: (x["pnl_avg_pct"], x["win_rate_pct"], x["n"]), reverse=True)

    totals = {
        "n": sum(x["n"] for x in par_list),
        "wins": sum(x["wins"] for x in par_list),
        "loss": sum(x["loss"] for x in par_list),
        "expired": sum(x["expired"] for x in par_list),
        "win_rate_pct": 0.0,
        "pnl_avg_pct": 0.0,
    }
    if totals["n"]:
        totals["win_rate_pct"] = round(totals["wins"]/totals["n"]*100.0, 2)

    # recomendações só com N >= MIN_N
    best_par = [x for x in par_list if x["n"] >= MIN_N and x["pnl_avg_pct"] > 0][:15]
    best_hours = [x for x in hour_list if x["n"] >= MIN_N and x["pnl_avg_pct"] > 0][:10]

    out = {
        "ok": True,
        "generated_at_utc": now_utc.isoformat().replace("+00:00","Z"),
        "period_days": PERIOD_DAYS,
        "cutoff_date": str(cutoff),
        "totals": totals,
        "by_par": par_list,
        "by_hour_brt": hour_list,
        "by_dow": dow_list,
        "recommended": {"min_n": MIN_N, "best_par": best_par, "best_hours": best_hours}
    }

    os.makedirs(AUDIT_DIR, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # CSV simples (por moeda)
    with open(OUT_CSV, "w", encoding="utf-8") as f:
        f.write("par,n,win_rate_pct,pnl_avg_pct,pnl_min_pct,pnl_max_pct,expired,timeout_pct\n")
        for x in par_list:
            f.write(
                f"{x['key']},{x['n']},{x['win_rate_pct']},{x['pnl_avg_pct']},"
                f"{x.get('pnl_min_pct')},{x.get('pnl_max_pct')},{x['expired']},{x.get('timeout_pct',0.0)}\n"
            )

if __name__ == "__main__":
    main()
