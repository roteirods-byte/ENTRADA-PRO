from __future__ import annotations

"""
BLOCO AUDITORIA (TOP10) - ENTRADA-PRO
- NÃO altera cálculo do TOP10.
- Só lê data/top10.json, acompanha preço (BYBIT) e fecha cada sinal como:
  WIN (bateu ALVO) | LOSS (bateu INVALIDADO) | EXPIRED (TTL).
- Gera arquivos em data/audit/ para o painel audit.html (somente leitura).

Arquivos gerados:
- data/audit/top10_open.json
- data/audit/top10_closed.jsonl
- data/audit/top10_summary.json
"""

import json
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from .io import atomic_write_json
from .exchanges import fetch_mark_price

TZ_BRT = ZoneInfo("America/Sao_Paulo")


def _now_brt() -> datetime:
    return datetime.now(TZ_BRT)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso_z(s: str) -> Optional[datetime]:
    """Parse ISO 8601 com Z para datetime UTC."""
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


def _append_jsonl(path: Path, obj: Dict[str, Any]) -> None:
    line = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _sym(par: str) -> str:
    """Mesmo mapeamento do worker_pro.py (moedas muito baratas)."""
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
    """
    Regra: ALVO = ENTRADA ± 1.5*ATR  => ATR = |ALVO-ENTRADA|/1.5
    (permite auditar sem precisar ATR no JSON)
    """
    try:
        d = abs(float(alvo) - float(entrada))
        return float(d) / 1.5 if d > 0 else 0.0
    except Exception:
        return 0.0


def _invalidado(entrada: float, atr: float, side: str) -> float:
    """INVALIDADO (corte): 1.0*ATR contra a entrada."""
    if side == "LONG":
        return float(entrada) - float(atr)
    return float(entrada) + float(atr)


def _pnl_pct(side: str, entrada: float, preco: float) -> float:
    """PNL% real no ponto atual/fechamento."""
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
    hit: str      # ALVO | INVALIDADO | TTL
    result: str   # WIN | LOSS | EXPIRED
    close_price: float


def _check_close(side: str, preco: float, alvo: float, inv: float, ttl_utc: Optional[datetime]) -> Optional[CloseResult]:
    """
    Prioridade:
      1) ALVO / INVALIDADO
      2) TTL
    """
    p = float(preco)
    a = float(alvo)
    i = float(inv)

    if side == "LONG":
        if a > 0 and p >= a:
            return CloseResult("ALVO", "WIN", p)
        if i > 0 and p <= i:
            return CloseResult("INVALIDADO", "LOSS", p)
    else:  # SHORT
        if a > 0 and p <= a:
            return CloseResult("ALVO", "WIN", p)
        if i > 0 and p >= i:
            return CloseResult("INVALIDADO", "LOSS", p)

    if ttl_utc is not None and _now_utc() >= ttl_utc:
        return CloseResult("TTL", "EXPIRED", p)

    return None


def run_audit_top10(*, data_dir: str, api_source: str = "BYBIT", max_last_closed: int = 20) -> Dict[str, Any]:
    """
    - Lê data/top10.json
    - Abre novos sinais em data/audit/top10_open.json
    - Atualiza preço e fecha sinais em data/audit/top10_closed.jsonl
    - Gera resumo em data/audit/top10_summary.json
    """
    data_dir = data_dir or "/opt/ENTRADA-PRO/data"
    audit_dir = _audit_dir(data_dir)

    top10 = _read_json(Path(data_dir) / "top10.json", default={})
    items = list((top10 or {}).get("items") or [])

    open_path = audit_dir / "top10_open.json"
    closed_path = audit_dir / "top10_closed.jsonl"
    summary_path = audit_dir / "top10_summary.json"

    open_list: List[Dict[str, Any]] = _read_json(open_path, default=[])
    open_by_id = {str(x.get("audit_id")): x for x in open_list if x.get("audit_id")}

    # ---------- CAPTURA: abre novos ----------
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

            entrada = float(it.get("atual") or 0.0)  # entrada = atual no momento do sinal
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
                # métricas durante a vida
                "mfe_pct": 0.0,
                "mae_pct": 0.0,
            }
        except Exception:
            continue

    # ---------- ATUALIZA OPEN / FECHA ----------
    new_open: List[Dict[str, Any]] = []
    closed_cycle: List[Dict[str, Any]] = []
    win = loss = expired = 0

    for aid, s in list(open_by_id.items()):
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

    # grava open
    atomic_write_json(open_path, new_open)

    # ---------- RESUMO ----------
    total = win + loss + expired
    win_rate = (win / total * 100.0) if total > 0 else 0.0

    last_closed = closed_cycle[-max_last_closed:]

    def _avg(nums: List[float]) -> float:
        nums = [float(x) for x in nums if x is not None]
        return sum(nums) / len(nums) if nums else 0.0

    pnl_list = [float(x.get("pnl_pct_real") or 0.0) for x in last_closed]

ttl_pos = 0
    ttl_neg = 0
    ttl_zero = 0
    for _x in last_closed:
        if str(_x.get("result")) == "EXPIRED":
            _v = float(_x.get("pnl_pct_real") or 0.0)
            if _v > 0:
                ttl_pos += 1
            elif _v < 0:
                ttl_neg += 1
            else:
                ttl_zero += 1
  
    overall = {
        "total": int(total),
        "win": int(win),
        "loss": int(loss),
        "expired": int(expired),
        "win_rate_pct": float(win_rate),
        "pnl_avg_pct": float(_avg(pnl_list)) if pnl_list else 0.0,
      "ttl_pos": int(ttl_pos),
        "ttl_neg": int(ttl_neg),
        "ttl_zero": int(ttl_zero),
    }

    by_dow: Dict[str, Dict[str, Any]] = {}
    by_hour: Dict[str, Dict[str, Any]] = {}
    combo: Dict[str, Dict[str, Any]] = {}

    dow_map = ["SEG", "TER", "QUA", "QUI", "SEX", "SAB", "DOM"]

    for x in last_closed:
        ts = str(x.get("ts_brt") or "")
        dow = "-"
        hour = "-"
        try:
            dt = datetime.strptime(ts, "%Y-%m-%d %H:%M").replace(tzinfo=TZ_BRT)
            dow = dow_map[dt.weekday()]
            hour = f"{dt.hour:02d}"
        except Exception:
            pass

        pnl = float(x.get("pnl_pct_real") or 0.0)

        by_dow.setdefault(dow, {"n": 0, "pnl_sum": 0.0})
        by_dow[dow]["n"] += 1
        by_dow[dow]["pnl_sum"] += pnl

        by_hour.setdefault(hour, {"n": 0, "pnl_sum": 0.0})
        by_hour[hour]["n"] += 1
        by_hour[hour]["pnl_sum"] += pnl

        key = f"{dow}|{hour}"
        combo.setdefault(key, {"dow": dow, "hour": hour, "n": 0, "pnl_sum": 0.0})
        combo[key]["n"] += 1
        combo[key]["pnl_sum"] += pnl

    by_dow_out = {k: {"n": v["n"], "pnl_avg_pct": (v["pnl_sum"]/v["n"]) if v["n"] else 0.0} for k, v in by_dow.items()}
    by_hour_out = {k: {"n": v["n"], "pnl_avg_pct": (v["pnl_sum"]/v["n"]) if v["n"] else 0.0} for k, v in by_hour.items()}

    best_windows = sorted(
        [
            {
                "dow": v["dow"],
                "hour": v["hour"],
                "n": v["n"],
                "pnl_avg_pct": (v["pnl_sum"]/v["n"]) if v["n"] else 0.0,
            }
            for v in combo.values()
        ],
        key=lambda r: (r["pnl_avg_pct"], r["n"]),
        reverse=True
    )[:8]

    summary = {
        "ok": True,
        "updated_at_brt": _now_brt().strftime("%Y-%m-%d %H:%M"),
        "open_count": len(new_open),

        # schema esperado pelo audit.html
        "overall": overall,
        "by_dow": by_dow_out,
        "by_hour": by_hour_out,
        "best_windows": best_windows,

        # mantém compatibilidade
        "closed_cycle": {
            "total": int(total),
            "win": int(win),
            "loss": int(loss),
            "expired": int(expired),
            "win_rate_pct": float(win_rate),
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
            } for x in last_closed
        ],
    }

    atomic_write_json(summary_path, summary)
    return summary
