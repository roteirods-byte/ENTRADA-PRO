from __future__ import annotations
import json, os
from pathlib import Path
from typing import Any, Dict

def atomic_write_json(fp: Path, obj: Any) -> None:
    fp.parent.mkdir(parents=True, exist_ok=True)
    tmp = fp.with_suffix(fp.suffix + ".tmp")
    data = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), indent=2)
    tmp.write_text(data, encoding="utf-8")
    os.replace(tmp, fp)
