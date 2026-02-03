# worker/worker_pro.py
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from datetime import datetime, timezone

from engine.config import COINS, DATA_DIR, GAIN_MIN_PCT, now_utc_iso, now_brt_str


OUT_FILE = Path(os.getenv("PRO_JSON", str(Path(DATA_DIR) / "pro.json")))

# intervalo (segundos). Se não existir variável, usa 60s.
INTERVAL_S = int(os.getenv("WORKER_INTERVAL_S", "60"))

# só para log simples
def log(msg: str) -> None:
    print(f"[WORKER] {msg}", flush=True)


def write_pro_json(items: list[dict], ok: bool = True, error: str | None = None) -> None:
    payload = {
        "ok": ok,
        "service": "entrada-pro-worker",
        "now_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "now_brt": now_brt_str(),
        "data_dir": str(DATA_DIR),
        "gain_min_pct": float(GAIN_MIN_PCT),
        "coins_count": len(COINS),
        "items": items,
        "count": len(items),
    }
    if not ok:
        payload["error"] = error or "unknown"

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    log(f"START | DATA_DIR={DATA_DIR} | OUT_FILE={OUT_FILE} | INTERVAL_S={INTERVAL_S} | COINS={len(COINS)}")

    # Garante um pro.json inicial (para o API não reclamar de “not_found”)
    write_pro_json(items=[], ok=True)

    while True:
        try:
            # ✅ Por enquanto: publica “heartbeat” com as moedas.
            # Depois a gente liga os cálculos reais, sem quebrar deploy.
            items = [{"coin": c, "ts_utc": now_utc_iso()} for c in COINS]

            write_pro_json(items=items, ok=True)
            log(f"UPDATED pro.json | items={len(items)}")
        except Exception as e:
            # nunca pode derrubar o container
            write_pro_json(items=[], ok=False, error=f"worker_exception:{type(e).__name__}")
            log(f"ERROR: {type(e).__name__}: {e}")

        time.sleep(INTERVAL_S)


if __name__ == "__main__":
    main()
