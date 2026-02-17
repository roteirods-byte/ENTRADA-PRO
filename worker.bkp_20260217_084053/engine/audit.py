from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from .config import DATA_DIR, now_brt_str, GAIN_MIN_PCT


def _audit_dir() -> Path:
    d = Path(DATA_DIR) / "audit"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _append_jsonl(path: Path, obj: Dict[str, Any]) -> None:
    # JSONL: 1 objeto por linha
    line = json.dumps(obj, ensure_ascii=False)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def log_prices(items: Iterable[Dict[str, Any]], *, updated_at: str) -> None:
    """
    Salva preços (ATUAL) para cada moeda a cada atualização.
    Usado para auditoria de acerto por janelas (30m/4h/24h).
    """
    now_brt = now_brt_str()  # "YYYY-MM-DD HH:MM"
    d, h = now_brt.split(" ", 1)
    out = _audit_dir() / f"prices_{d}.jsonl"

    for it in items:
        try:
            par = str(it.get("par") or "").strip()
            atual = float(it.get("atual") or 0.0)
            if not par or atual <= 0:
                continue
            _append_jsonl(out, {
                "date": d,
                "hora": h,
                "ts_brt": now_brt,
                "updated_at": updated_at,
                "par": par,
                "atual": atual,
                "price_source": it.get("price_source") or "",
            })
        except Exception:
            # auditoria nunca pode derrubar o worker
            continue


def log_signals(items: Iterable[Dict[str, Any]], *, updated_at: str, gain_min_pct: Optional[float] = None) -> None:
    """
    Salva apenas sinais válidos (LONG/SHORT e ganho >= mínimo).
    """
    now_brt = now_brt_str()
    d, h = now_brt.split(" ", 1)
    out = _audit_dir() / f"signals_{d}.jsonl"

    gmin = float(GAIN_MIN_PCT if gain_min_pct is None else gain_min_pct)

    for it in items:
        try:
            side = str(it.get("side") or "").upper()
            if side not in ("LONG", "SHORT"):
                continue
            ganho = float(it.get("ganho_pct") or 0.0)
            if ganho < gmin:
                continue

            _append_jsonl(out, {
                "date": d,
                "hora": h,
                "ts_brt": now_brt,
                "updated_at": updated_at,
                "par": it.get("par"),
                "side": side,
                "atual": float(it.get("atual") or 0.0),
                "alvo": float(it.get("alvo") or 0.0),
                "ganho_pct": ganho,
                "assert_pct": float(it.get("assert_pct") or 0.0),
                "prazo": it.get("prazo") or "",
                "zona": it.get("zona") or "",
                "risco": it.get("risco") or "",
                "prioridade": it.get("prioridade") or "",
                "price_source": it.get("price_source") or "",
            })
        except Exception:
            continue
