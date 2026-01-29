from __future__ import annotations
import os, json
from pathlib import Path
from datetime import datetime
from dateutil import tz

BRT = tz.gettz("America/Sao_Paulo")

DATA_DIR = os.environ.get("DATA_DIR") or str(Path(__file__).resolve().parents[2] / "data")
CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"

COINS_FILE = os.environ.get("COINS_FILE") or str(CONFIG_DIR / "coins.json")
SETTINGS_FILE = os.environ.get("SETTINGS_FILE") or str(CONFIG_DIR / "settings.json")

def load_json(fp: str) -> dict:
    return json.loads(Path(fp).read_text(encoding="utf-8"))

COINS = load_json(COINS_FILE)["coins"]
SETTINGS = load_json(SETTINGS_FILE)

GAIN_MIN_PCT = float(SETTINGS.get("gain_min_pct", 3.0))
UPDATE_INTERVAL_SECONDS = int(SETTINGS.get("update_interval_seconds", 300))

def now_utc_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def now_brt_str() -> str:
    dt = datetime.utcnow().replace(tzinfo=tz.UTC).astimezone(BRT)
    return dt.strftime("%Y-%m-%d %H:%M:%S")
