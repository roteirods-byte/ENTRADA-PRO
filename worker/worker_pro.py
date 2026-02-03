# worker/worker_pro.py  (ATUAL AO VIVO - BYBIT PERP MARK)
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import urlopen, Request

from engine.config import COINS, DATA_DIR, now_brt_str

OUT_FILE = Path(os.getenv("PRO_JSON", str(Path(DATA_DIR) / "pro.json")))

# intervalo (segundos). Se não existir variável, usa 60s.
INTERVAL_S = int(os.getenv("WORKER_INTERVAL_S", "60"))

BYBIT_TICKERS_URL = "https://api.bybit.com/v5/market/tickers?category=linear"  # USDT Perp (linear)

def log(msg: str) -> None:
    print(f"[WORKER_PRO] {msg}", flush=True)

def http_get_json(url: str, timeout: int = 10) -> dict:
    req = Request(url, headers={"accept": "application/json", "user-agent": "entrada-pro-worker"})
    with urlopen(req, timeout=timeout) as r:
        data = r.read().decode("utf-8", errors="replace")
    return json.loads(data)

def fetch_bybit_mark_map() -> dict[str, float]:
    """
    Retorna dict: {"BATUSDT": 0.11757, ...} usando markPrice do PERP (linear).
    """
    out: dict[str, float] = {}
    j = http_get_json(BYBIT_TICKERS_URL, timeout=10)

    # resposta padrão do V5: { "retCode":0, "result": { "list":[...] } }
    result = (j or {}).get("result") or {}
    lst = result.get("list") or []

    for it in lst:
        sym = str(it.get("symbol", "")).upper().strip()
        mp = it.get("markPrice")
        try:
            if sym and mp is not None:
                out[sym] = float(mp)
        except:
            pass

    return out

def load_existing_payload() -> dict:
    """
    Carrega o pro.json existente, para NÃO quebrar o formato atual do painel.
    """
    if not OUT_FILE.exists():
        return {"ok": True, "items": []}

    try:
        txt = OUT_FILE.read_text(encoding="utf-8")
        return json.loads(txt) if txt else {"ok": True, "items": []}
    except Exception:
        return {"ok": True, "items": []}

def save_payload(payload: dict) -> None:
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

def symbol_usdt(par: str) -> str:
    # Ex: "BAT" -> "BATUSDT"
    p = (par or "").strip().upper()
    if p.endswith("USDT"):
        return p
    return f"{p}USDT"

def update_items_with_live_price(payload: dict, mark_map: dict[str, float]) -> tuple[int, int]:
    """
    Atualiza ATUAL pelo MARK do PERP (linear).
    Mantém todo o resto igual.
    """
    items = payload.get("items")
    if not isinstance(items, list):
        return (0, 0)

    ok_count = 0
    miss_count = 0

    for it in items:
        if not isinstance(it, dict):
            continue

        # aceita PAR (modelo atual) ou coin (modelo antigo)
        par = it.get("PAR") or it.get("par") or it.get("coin")
        if not par:
            continue

        sym = symbol_usdt(str(par))
        mp = mark_map.get(sym)

        if mp is None:
            miss_count += 1
            continue

        # grava ATUAL em float (sem formatar; o site formata)
        it["ATUAL"] = float(mp)

        # opcional: marca a fonte (não atrapalha)
        it["PRICE_SOURCE"] = "MARK"

        ok_count += 1

    return (ok_count, miss_count)

def main() -> None:
    log(f"START | OUT_FILE={OUT_FILE} | INTERVAL_S={INTERVAL_S} | COINS={len(COINS)}")

    while True:
        try:
            payload = load_existing_payload()

            # atualiza carimbos de tempo
            payload["ok"] = True
            payload["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
            payload["now_brt"] = now_brt_str()

            mark_map = fetch_bybit_mark_map()
            ok_count, miss_count = update_items_with_live_price(payload, mark_map)

            save_payload(payload)
            log(f"UPDATED | ATUAL(MARK) ok={ok_count} miss={miss_count}")

        except Exception as e:
            log(f"ERROR: {type(e).__name__}: {e}")

        time.sleep(INTERVAL_S)

if __name__ == "__main__":
    main()
