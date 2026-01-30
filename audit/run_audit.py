from __future__ import annotations
import json, os, sys
from pathlib import Path
from datetime import datetime
from dateutil import tz

BRT = tz.gettz("America/Sao_Paulo")
SCHEMA_VERSION = "r2"

def now_brt() -> str:
    return datetime.utcnow().replace(tzinfo=tz.UTC).astimezone(BRT).strftime("%Y-%m-%d %H:%M:%S")

def load_json(fp: Path):
    return json.loads(fp.read_text(encoding="utf-8"))

def atomic_write(fp: Path, obj: dict):
    tmp = fp.with_suffix(fp.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(fp)

def expected_count_from_config(data_dir: Path) -> int:
    # tenta achar config/coins.json (repo) e usar como fonte única
    repo_root = data_dir.parent  # .../AUTOTRADER-PRO
    coins_fp = Path(os.environ.get("COINS_FILE") or (repo_root / "current" / "config" / "coins.json"))
    if not coins_fp.exists():
        # fallback: /home/roteiro_ds/ENTRADA-PRO/config/coins.json
        alt = Path("/home/roteiro_ds/ENTRADA-PRO/config/coins.json")
        coins_fp = alt if alt.exists() else coins_fp
    try:
        d = json.loads(coins_fp.read_text(encoding="utf-8"))
        return int(len(d.get("coins", [])))
    except Exception:
        return 0

def main() -> int:
    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "data"
    pro_fp = data_dir / "pro.json"
    top_fp = data_dir / "top10.json"
    aud_fp = data_dir / "audit.json"

    errors=[]
    ok=True

    expected = expected_count_from_config(data_dir)

    # PRO checks
    try:
        p = load_json(pro_fp)
        if p.get("ok") is not True:
            ok=False; errors.append("pro_ok_false")
        c = int(p.get("count", 0))
        items = p.get("items") or []
        if c != len(items):
            ok=False; errors.append(f"pro_count_mismatch_items:{c}!={len(items)}")
        if expected and c != expected:
            ok=False; errors.append(f"pro_count_expected_{expected}_got_{c}")
        if not p.get("updated_brt"):
            ok=False; errors.append("pro_missing_updated_brt")
        if not p.get("schema_version"):
            ok=False; errors.append("pro_missing_schema_version")
    except Exception as e:
        ok=False
        errors.append(f"pro_read_error:{e}")

    # TOP10 checks
    try:
        t = load_json(top_fp)
        if t.get("ok") is not True:
            ok=False; errors.append("top10_ok_false")
        c = int(t.get("count", 0))
        items = t.get("items") or []
        if c != len(items):
            ok=False; errors.append(f"top10_count_mismatch_items:{c}!={len(items)}")
        if c > 10:
            ok=False; errors.append(f"top10_count_gt_10:{c}")
        if not t.get("updated_brt"):
            ok=False; errors.append("top10_missing_updated_brt")
        if not t.get("schema_version"):
            ok=False; errors.append("top10_missing_schema_version")
    except Exception as e:
        ok=False
        errors.append(f"top10_read_error:{e}")

    out = {
        "ok": ok,
        "schema_version": SCHEMA_VERSION,
        "updated_brt": now_brt(),
        "counts": {"expected": expected, "pro": None, "top10": None},
        "data_dir": str(data_dir),
        "errors": errors[:50],
    }

    # fill counts safely
    try:
        out["counts"]["pro"] = int(load_json(pro_fp).get("count", 0))
    except Exception:
        out["counts"]["pro"] = 0
    try:
        out["counts"]["top10"] = int(load_json(top_fp).get("count", 0))
    except Exception:
        out["counts"]["top10"] = 0

    atomic_write(aud_fp, out)
    return 0 if ok else 2

if __name__ == "__main__":
    raise SystemExit(main())
