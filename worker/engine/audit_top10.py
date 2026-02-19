from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from .io import atomic_write_json
from .exchanges import fetch_mark_price

TZ_BRT = ZoneInfo("America/Sao_Paulo")


def _now_brt() -> datetime:
    return datetime.now(TZ_BRT)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso_z(s: str) -> Optional[datetime]:
    try:
        if not s:
            return None
        ss = s.strip()
        if ss.endswith("Z"):
            ss = ss[:-1] + "+00:00"
        return datetime.fromisoformat(ss).astimezone(timezone.utc)
    except Exception:
        return None


def _audit_dir(data_dir: str) -> Path:
    p = Path(data_dir) / "audit"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _read_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _read_jsonl(path: Path, max_lines: int = 5000) -> List[Dict[str, Any]]:
    """
    Lê JSONL com limite (seguro). Para seu caso (117 linhas), lê tudo.
    """
    out: List[Dict[str, Any]] = []
    try:
        if not path.exists():
            return out
        # lê do fim (simples e suficiente aqui)
        lines = path.read_text(encoding="utf-8").splitlines()
        for line in lines[-max_lines:]:
            line = (line or "").strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        return out
    return out


def _append_jsonl(path: Path, obj: Dict[str, Any]) -> None:
    line = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _sym(par: str) -> str:
    p = (par or "").upper().strip()
    mult = {
        "BONK": "1000BONK",
        "FLOKI": "1000FLOKI",
        "PEPE": "1000PEPE",
        "SHIB": "1000SHIB",
    }
    base = mult.get(p, p)
    return f"{base}USDT"


def _audit_id(par: str, side: str, entrada: float, alvo: float, ttl: str) -> str:
    raw = f"{par}|{side}|{entrada:.10f}|{alvo:.10f}|{ttl}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _atr_from_entry_target(entrada: float, alvo: float) -> float:
    try:
        d = abs(float(alvo) - float(entrada))
        return float(d) / 1.5 if d > 0 else 0.0
    except Exception:
        return 0.0


def _invalidado(entrada: float, atr: float, side: str) -> float:
    if side == "LONG":
        return float(entrada) - float(atr)
    return float(entrada) + float(atr)


def _pnl_pct(side: str, entrada: float, preco: float) -> float:
    try:
        e = float(entrada)
        p = float(preco)
        if e <= 0:
            return 0.0
        if side == "LONG":
            return (p - e) / e * 100.0
        return (e - p) / e * 100.0
    except Exception:
        return 0.0


@dataclass
class CloseResult:
    hit: str
    result: str
    close_price: float


def _check_close(side: str, preco: float, alvo: float, inv: float, ttl_utc: Optional[datetime]) -> Optional[CloseResult]:
    p = float(preco)
    a = float(alvo)
    i = float(inv)

    if side == "LONG":
        if a > 0 and p >= a:
            return CloseResult("ALVO", "WIN", p)
        if i > 0 and p <= i:
            return CloseResult("INVALIDADO", "LOSS", p)
    else:
        if a > 0 and p <= a:
            return CloseResult("ALVO", "WIN", p)
        if i > 0 and p >= i:
            return CloseResult("INVALIDADO", "LOSS", p)

    if ttl_utc is not None and _now_utc() >= ttl_utc:
        # TTL: fecha por PNL (TIMEOUT)
        # WIN se pnl>0, LOSS se pnl<0, FLAT se ==0
        pnl = _pnl_pct(side, entrada, p) if False else None
        # (pnl real será calculado fora; aqui só marca hit)
        return CloseResult("TTL", "TIMEOUT", p)

    return None


def _dow_name_pt(dow: int) -> str:
    # Monday=0
    names = ["SEG", "TER", "QUA", "QUI", "SEX", "SAB", "DOM"]
    return names[dow] if 0 <= dow <= 6 else "?"


def _parse_brt_ts(ts_brt: str) -> Optional[datetime]:
    try:
        # "YYYY-MM-DD HH:MM"
        return datetime.strptime(ts_brt, "%Y-%m-%d %H:%M").replace(tzinfo=TZ_BRT)
    except Exception:
        return None


def _agg_best(closed_rows: List[Dict[str, Any]], min_n: int = 8) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]:
    """
    Retorna:
      by_dow: {SEG:{n,win,loss,expired,win_rate,pnl_avg}, ...}
      by_hour: {"00":{...}, ... "23":{...}}
      best_windows: top 5 de (DIA+HORA) por win_rate (>=min_n)
    """
    by_dow: Dict[str, Dict[str, float]] = {}
    by_hour: Dict[str, Dict[str, float]] = {}
    by_win: Dict[str, Dict[str, float]] = {}

    def upd(bucket: Dict[str, Dict[str, float]], key: str, r: Dict[str, Any]):
        b = bucket.setdefault(key, {"n": 0, "win": 0, "loss": 0, "expired": 0, "pnl_sum": 0.0})
        b["n"] += 1
        res = str(r.get("result") or "")
        if res == "WIN":
            b["win"] += 1
        elif res == "LOSS":
            b["loss"] += 1
        else:
            b["expired"] += 1
        b["pnl_sum"] += float(r.get("pnl_pct_real") or 0.0)

    for r in closed_rows:
        ts = _parse_brt_ts(str(r.get("ts_brt") or ""))
        if not ts:
            continue
        dow = _dow_name_pt(ts.weekday())
        hh = f"{ts.hour:02d}"
        upd(by_dow, dow, r)
        upd(by_hour, hh, r)
        upd(by_win, f"{dow}_{hh}", r)

    def finalize(bucket: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for k, b in bucket.items():
            n = int(b["n"])
            win = int(b["win"])
            loss = int(b["loss"])
            exp = int(b["expired"])
            win_rate = (win / n * 100.0) if n > 0 else 0.0
            pnl_avg = (b["pnl_sum"] / n) if n > 0 else 0.0
            out[k] = {
                "n": n,
                "win": win,
                "loss": loss,
                "expired": exp,
                "win_rate_pct": win_rate,
                "pnl_avg_pct": pnl_avg,
            }
        return out

    by_dow_f = finalize(by_dow)
    by_hour_f = finalize(by_hour)

    best: List[Dict[str, Any]] = []
    for k, b in by_win.items():
        n = int(b["n"])
        if n < min_n:
            continue
        win = int(b["win"])
        win_rate = (win / n * 100.0) if n > 0 else 0.0
        pnl_avg = (b["pnl_sum"] / n) if n > 0 else 0.0
        dow, hh = k.split("_", 1)
        best.append({
            "dow": dow,
            "hour": hh,
            "n": n,
            "win_rate_pct": win_rate,
            "pnl_avg_pct": pnl_avg,
        })

    best.sort(key=lambda x: (x["win_rate_pct"], x["n"]), reverse=True)
    return by_dow_f, by_hour_f, best[:5]


def run_audit_top10(*, data_dir: str, api_source: str = "BYBIT", max_last_closed: int = 20) -> Dict[str, Any]:
    data_dir = data_dir or "/opt/ENTRADA-PRO/data"
    audit_dir = _audit_dir(data_dir)

    top10 = _read_json(Path(data_dir) / "top10.json", default={})
    items = list((top10 or {}).get("items") or [])

    open_path = audit_dir / "top10_open.json"
    closed_path = audit_dir / "top10_closed.jsonl"
    summary_path = audit_dir / "top10_summary.json"

    open_list: List[Dict[str, Any]] = _read_json(open_path, default=[])
    open_by_id = {str(x.get("audit_id")): x for x in open_list if x.get("audit_id")}

    # ---------- CAPTURA ----------
    now_brt = _now_brt()
    now_brt_str = now_brt.strftime("%Y-%m-%d %H:%M")
    date_brt = now_brt.strftime("%Y-%m-%d")
    hora_brt = now_brt.strftime("%H:%M")

    for it in items:
        try:
            par = str(it.get("par") or "").strip()
            side = str(it.get("side") or "").upper().strip()
            if not par or side not in ("LONG", "SHORT"):
                continue

            entrada = float(it.get("atual") or 0.0)
            alvo = float(it.get("alvo") or 0.0)
            ttl = str(it.get("ttl_expira_em") or "").strip()
            if entrada <= 0 or alvo <= 0 or not ttl:
                continue

            aid = _audit_id(par, side, entrada, alvo, ttl)
            if aid in open_by_id:
                continue

            atr = _atr_from_entry_target(entrada, alvo)
            inv = _invalidado(entrada, atr, side)

            open_by_id[aid] = {
                "audit_id": aid,
                "ts_brt": now_brt_str,
                "date": date_brt,
                "hora": hora_brt,
                "par": par,
                "side": side,
                "entrada": float(entrada),
                "alvo": float(alvo),
                "invalidado": float(inv),
                "ganho_pct": float(it.get("ganho_pct") or 0.0),
                "assert_pct": float(it.get("assert_pct") or 0.0),
                "prazo": str(it.get("prazo") or "-"),
                "price_source": str(it.get("price_source") or "NONE"),
                "ttl_expira_em": ttl,
                "mfe_pct": 0.0,
                "mae_pct": 0.0,
            }
        except Exception:
            continue

    # ---------- FECHAMENTO ----------
    new_open: List[Dict[str, Any]] = []
    closed_cycle: List[Dict[str, Any]] = []
    win = loss = expired = 0

    for _aid, s in list(open_by_id.items()):
        try:
            par = str(s.get("par"))
            side = str(s.get("side"))
            entrada = float(s.get("entrada") or 0.0)
            alvo = float(s.get("alvo") or 0.0)
            inv = float(s.get("invalidado") or 0.0)
            ttl_utc = _parse_iso_z(str(s.get("ttl_expira_em") or ""))

            symbol = _sym(par)
            px = float(fetch_mark_price(symbol, source=api_source, timeout=8) or 0.0)
            if px <= 0:
                new_open.append(s)
                continue

            pnl = _pnl_pct(side, entrada, px)
            s["mfe_pct"] = max(float(s.get("mfe_pct") or 0.0), pnl)
            s["mae_pct"] = min(float(s.get("mae_pct") or 0.0), pnl)

            cr = _check_close(side, px, alvo, inv, ttl_utc)
            if cr is None:
                new_open.append(s)
                continue

            close_ts_brt = _now_brt().strftime("%Y-%m-%d %H:%M")
            obj = dict(s)
            obj.update({
                "close_ts_brt": close_ts_brt,
                "hit": cr.hit,
                "result": cr.result,
                "close_price": float(cr.close_price),
                "pnl_pct_real": float(_pnl_pct(side, entrada, cr.close_price)),
            })
            _append_jsonl(closed_path, obj)

            if cr.result == "WIN":
                win += 1
            elif cr.result == "LOSS":
                loss += 1
            else:
                expired += 1

            closed_cycle.append(obj)

        except Exception:
            new_open.append(s)

    atomic_write_json(open_path, new_open)

    # ---------- HISTÓRICO + MELHORES DIAS/HORAS ----------
    closed_hist = _read_jsonl(closed_path, max_lines=20000)
    # último N
    last_closed_hist = closed_hist[-max_last_closed:]

    # overall
    total_all = len(closed_hist)
    w_all = sum(1 for r in closed_hist if str(r.get("result")) == "WIN")
    l_all = sum(1 for r in closed_hist if str(r.get("result")) == "LOSS")
    e_all = sum(1 for r in closed_hist if str(r.get("result")) == "EXPIRED")
    win_rate_all = (w_all / total_all * 100.0) if total_all > 0 else 0.0
    pnl_avg_all = (sum(float(r.get("pnl_pct_real") or 0.0) for r in closed_hist) / total_all) if total_all > 0 else 0.0

    by_dow, by_hour, best_windows = _agg_best(closed_hist, min_n=8)

    # resumo por ciclo (para debug)
    total_cycle = win + loss + expired
    win_rate_cycle = (win / total_cycle * 100.0) if total_cycle > 0 else 0.0

    summary = {
        "ok": True,
        "updated_at_brt": _now_brt().strftime("%Y-%m-%d %H:%M"),
        "open_count": len(new_open),

        "overall": {
            "total": total_all,
            "win": w_all,
            "loss": l_all,
            "expired": e_all,
            "win_rate_pct": win_rate_all,
            "pnl_avg_pct": pnl_avg_all,
        },

        "by_dow": by_dow,
        "by_hour": by_hour,
        "best_windows": best_windows,

        "closed_cycle": {
            "total": total_cycle,
            "win": win,
            "loss": loss,
            "expired": expired,
            "win_rate_pct": win_rate_cycle,
        },

        "last_closed": [
            {
                "par": x.get("par"),
                "side": x.get("side"),
                "entrada": x.get("entrada"),
                "alvo": x.get("alvo"),
                "invalidado": x.get("invalidado"),
                "result": x.get("result"),
                "hit": x.get("hit"),
                "pnl_pct_real": x.get("pnl_pct_real"),
                "ts_brt": x.get("ts_brt"),
                "close_ts_brt": x.get("close_ts_brt"),
            } for x in last_closed_hist
        ],
    }

    atomic_write_json(summary_path, summary)
    return summary
