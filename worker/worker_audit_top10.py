#!/usr/bin/env python3
import os
import time

from engine.audit_top10 import run_audit_top10

DATA_DIR = os.getenv("DATA_DIR", "/opt/ENTRADA-PRO/data")

def main():
    while True:
        try:
            run_audit_top10(data_dir=DATA_DIR, api_source="BYBIT")
        except Exception:
            # auditoria nunca pode derrubar o servidor
            pass
        time.sleep(300)

if __name__ == "__main__":
    main()
