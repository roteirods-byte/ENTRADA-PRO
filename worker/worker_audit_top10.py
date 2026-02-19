#!/usr/bin/env python3
import os
import time

from engine.audit_top10 import run_audit_top10

def main() -> None:
    data_dir = os.environ.get("DATA_DIR", "/opt/ENTRADA-PRO/data").strip()
    while True:
        try:
            run_audit_top10(data_dir=data_dir)
        except Exception:
            pass
        time.sleep(900)

if __name__ == "__main__":
    main()
