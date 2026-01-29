from __future__ import annotations
import json, sys
from pathlib import Path
from datetime import datetime
from dateutil import tz

BRT = tz.gettz("America/Sao_Paulo")

def now_brt():
    return datetime.utcnow().replace(tzinfo=tz.UTC).astimezone(BRT).strftime("%Y-%m-%d %H:%M:%S")

def load(fp: Path):
    return json.loads(fp.read_text(encoding="utf-8"))

def main() -> int:
    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "data"
    pro = data_dir / "pro.json"
    top = data_dir / "top10.json"
    aud = data_dir / "audit.json"

    errors=[]
    ok=True

    try:
        p = load(pro)
        c = int(p.get("count", 0))
        if c != 77:
            ok=False
            errors.append(f"pro_count_expected_77_got_{c}")
    except Exception as e:
        ok=False
        errors.append(f"pro_read_error:{e}")

    try:
        t = load(top)
        c = int(t.get("count", 0))
        if c > 10:
            ok=False
            errors.append(f"top10_count_gt_10:{c}")
    except Exception as e:
        ok=False
        errors.append(f"top10_read_error:{e}")

    out = {
        "ok": ok,
        "checked_brt": now_brt(),
        "data_dir": str(data_dir),
        "errors": errors
    }
    aud.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if ok else 2

if __name__ == "__main__":
    raise SystemExit(main())
