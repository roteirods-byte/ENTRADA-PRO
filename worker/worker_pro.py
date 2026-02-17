<<<<<<< Updated upstream
#!/usr/bin/env python3
# worker/worker_pro.py
# Gera data/pro.json e data/top10.json para o painel ENTRADA-PRO (FULL + TOP10)
=======
# worker/worker_pro.py  (GERADOR COMPLETO - SINAIS + FULL + TOP10)
from __future__ import annotations
>>>>>>> Stashed changes

import json
import os
<<<<<<< Updated upstream
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple
from zoneinfo import ZoneInfo

from engine.config import load_settings, get_thresholds, get_coins
from engine.exchanges import fetch_mark_price, fetch_klines
=======
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from engine.config import COINS, DATA_DIR, now_utc_iso, now_brt_str
from engine.exchanges import binance_mark_last, binance_klines, bybit_mark_last
>>>>>>> Stashed changes
from engine.compute import build_signal

<<<<<<< Updated upstream
DATA_DIR = os.getenv("DATA_DIR", "/opt/ENTRADA-PRO/data")
TZ_BRT = ZoneInfo("America/Sao_Paulo")

def _sym(par: str) -> str:
    # sem USDT na planilha; mas no exchange o símbolo é <PAR>USDT
    return f"{par}USDT"

def _now_brt():
    dt = datetime.now(TZ_BRT)
    return dt, dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")

def _ttl_iso(minutes: int = 6) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")

def _safe_mark(symbol: str) -> Tuple[float, str]:
    # tenta BYBIT primeiro, depois BINANCE
    for src in ("BYBIT", "BINANCE"):
        try:
            px = fetch_mark_price(symbol, source=src, timeout=5)
            if px is not None and px > 0:
                return float(px), src
        except Exception:
            pass
    return 0.0, "NONE"

def _safe_klines(symbol: str, interval: str, limit: int = 120):
    for src in ("BYBIT", "BINANCE"):
        try:
            kl = fetch_klines(symbol, interval=interval, limit=limit, source=src, timeout=8)
            if kl and len(kl) >= 20:
                return kl, src
        except Exception:
            pass
    return None, "NONE"

def _mk_item(par: str, side: str, atual: float, alvo: float, ganho_pct: float, assert_pct: float,
             data: str, hora: str, prazo: str, zona: str, risco: str, prioridade: str,
             price_source: str, nao_entrar_motivo: str, ttl_expira_em: str) -> Dict:
    # GARANTIA: chaves sempre existem e números nunca são None
    return {
        "par": par,
        "side": side,
        "atual": float(atual or 0.0),
        "alvo": float(alvo or 0.0),
        "ganho_pct": float(ganho_pct or 0.0),
        "assert_pct": float(assert_pct or 0.0),
        "data": data,
        "hora": hora,
        "prazo": prazo or "",
        "zona": zona or "",
        "risco": risco or "",
        "prioridade": prioridade or "",
        "price_source": price_source or "NONE",
        "nao_entrar_motivo": nao_entrar_motivo,
        "ttl_expira_em": ttl_expira_em,
    }

def build_payload() -> Dict:
    settings = load_settings()
    gain_min, assert_min = get_thresholds(settings)
    coins = get_coins(settings)

    dt_brt, date_brt, time_brt = _now_brt()
    ttl = _ttl_iso(6)
=======
# arquivos de saída (lidos pela API / painéis)
OUT_FILE  = Path(os.getenv("PRO_JSON",  str(Path(DATA_DIR) / "pro.json")))
TOP10_FILE = Path(os.getenv("TOP10_JSON", str(Path(DATA_DIR) / "top10.json")))

# intervalo (segundos). Padrão: 300 (5 min)
INTERVAL_S = int(os.getenv("WORKER_INTERVAL_S", "300"))

# ===== FILTRO OFICIAL (ATUAL) =====
# FULL: se não bater os mínimos => "NÃO ENTRAR"
FULL_GAIN_MIN_PCT   = float(os.getenv("FULL_GAIN_MIN_PCT",  "2.0"))
FULL_ASSERT_MIN_PCT = float(os.getenv("FULL_ASSERT_MIN_PCT","55.0"))

def log(msg: str) -> None:
    print(f"[WORKER_PRO] {msg}", flush=True)

def _sym(par: str) -> str:
    return f"{par.upper()}USDT"

def _safe_mark(symbol: str) -> Tuple[Optional[float], str]:
    # tenta Binance primeiro, depois Bybit
    try:
        j = binance_mark_last(symbol)
        return float(j["mark"]), "BINANCE"
    except Exception:
        pass
    try:
        j = bybit_mark_last(symbol)
        return float(j["mark"]), "BYBIT"
    except Exception:
        return None, "NONE"

def _safe_ohlc(symbol: str, interval: str) -> Optional[List[List[float]]]:
    try:
        return binance_klines(symbol, interval=interval, limit=220)
    except Exception:
        return None

def _norm(x) -> str:
    return str(x or "").upper().replace("É","E").replace("Í","I").replace("Ó","O").replace("Á","A").replace("Ã","A").replace("Ç","C")

# ===== PONTUAÇÃO (CORES) =====
# VERDE=3, AMARELO/LARANJA=2, VERMELHO=1
def _pts_zona(z: str) -> int:
    z = _norm(z)
    if z == "ALTA":  return 3
    if z == "MEDIA": return 2
    return 1  # BAIXA/qualquer

def _pts_risco(r: str) -> int:
    r = _norm(r)
    if r == "BAIXO": return 3
    if r == "MEDIO": return 2
    return 1  # ALTO/qualquer

def _pts_prioridade(p: str) -> int:
    p = _norm(p)
    if p == "ALTA":  return 3
    if p == "MEDIA": return 2
    return 1  # BAIXA/qualquer

def build_payload() -> Tuple[Dict, Dict]:
    updated_at = now_utc_iso()
    now_brt = now_brt_str()
    _date, _time = (now_brt.split(" ")[0], now_brt.split(" ")[1] if " " in now_brt else "")

    def _mk_no(par: str, atual: float, src: str) -> Dict:
        # regra: NÃO ENTRAR preenche só PAR, SIDE, ATUAL, DATA, HORA
        return {
            "par": par,
            "side": "NÃO ENTRAR",
            "atual": (None if atual is None else float(atual)),
            "nao_entrar_motivo": None,
            "ttl_expira_em": None,
            "data": _date,
            "hora": _time,
            "alvo": None,
            "ganho_pct": None,
            "assert_pct": None,
            "prazo": None,
            "zona": None,
            "risco": None,
            "prioridade": None,
            "price_source": src,
        }

    items: List[Dict] = []
    ok_count = 0
    miss_count = 0
>>>>>>> Stashed changes

    items: List[Dict] = []
    miss_mark = 0
    miss_kl = 0

    for par in coins:
        symbol = _sym(par)

<<<<<<< Updated upstream
        mark, mark_src = _safe_mark(symbol)
        if mark <= 0:
            miss_mark += 1
            items.append(_mk_item(
                par=par, side="NÃO ENTRAR",
                atual=0.0, alvo=0.0, ganho_pct=0.0, assert_pct=0.0,
                data=date_brt, hora=time_brt,
                prazo="", zona="", risco="", prioridade="",
                price_source=mark_src, nao_entrar_motivo="sem_mark", ttl_expira_em=ttl
            ))
            continue

        k1, src1 = _safe_klines(symbol, "1h", 120)
        k4, src4 = _safe_klines(symbol, "4h", 120)
        if not k1 or not k4:
            miss_kl += 1
            items.append(_mk_item(
                par=par, side="NÃO ENTRAR",
                atual=mark, alvo=mark, ganho_pct=0.0, assert_pct=0.0,
                data=date_brt, hora=time_brt,
                prazo="", zona="", risco="", prioridade="",
                price_source=mark_src, nao_entrar_motivo="sem_klines", ttl_expira_em=ttl
            ))
            continue

        # Compute signal (always returns numeric alvo/ganho/assert even if NÃO ENTRAR)
        sig = build_signal(
            par=par,
            ohlc_1h=k1,
            ohlc_4h=k4,
            mark_price=mark,
            gain_min_pct=gain_min,
            assert_min_pct=assert_min,
        )

        # Decide motivo quando NÃO ENTRAR
        motivo = None
        if sig.side == "NÃO ENTRAR":
            g = float(getattr(sig, "ganho_pct", 0.0) or 0.0)
            a = float(getattr(sig, "assert_pct", 0.0) or 0.0)
            if g < float(gain_min):
                motivo = "gain_min"
            elif a < float(assert_min):
                motivo = "assert_min"
            else:
                motivo = "sem_sinal"

        items.append(_mk_item(
            par=par,
            side=sig.side,
            atual=sig.atual,
            alvo=sig.alvo,
            ganho_pct=sig.ganho_pct,
            assert_pct=sig.assert_pct,
            data=date_brt,
            hora=time_brt,
            prazo=sig.prazo if sig.side != "NÃO ENTRAR" else "",
            zona=sig.zona if sig.side != "NÃO ENTRAR" else "",
            risco=sig.risco if sig.side != "NÃO ENTRAR" else "",
            prioridade=sig.prioridade if sig.side != "NÃO ENTRAR" else "",
            price_source=mark_src,
            nao_entrar_motivo=motivo,
            ttl_expira_em=ttl,
        ))

    # Ordenar por PAR (estável para FULL)
    items.sort(key=lambda x: x["par"])
=======
        mark, src = _safe_mark(symbol)
        if mark is None:
            miss_count += 1
            x=_mk_no(par, None, src)
            x["nao_entrar_motivo"]="sem_mark"
            items.append(x)
            continue

        ohlc_1h = _safe_ohlc(symbol, "1h")
        ohlc_4h = _safe_ohlc(symbol, "4h")
        if (not ohlc_1h) or (not ohlc_4h):
            miss_count += 1
            items.append(_mk_no(par, float(mark), src))
            continue

        # IMPORTANTÍSSIMO: roda o build_signal sem filtro interno
        sig = build_signal(par=par, ohlc_1h=ohlc_1h, ohlc_4h=ohlc_4h, mark_price=float(mark), gain_min_pct=0.0)

        ganho = float(getattr(sig, "ganho_pct", 0.0) or 0.0)
        ass   = float(getattr(sig, "assert_pct", 0.0) or 0.0)

        # FILTRO FULL (55% / 2%)
        if (ass < FULL_ASSERT_MIN_PCT) or (ganho < FULL_GAIN_MIN_PCT):
            sig.side = "NÃO ENTRAR"

        if sig.side not in ("LONG", "SHORT"):
            items.append(_mk_no(sig.par, float(sig.atual), src))
        else:
            items.append({
                "par": sig.par,
                "side": sig.side,
                "atual": float(sig.atual),
                "alvo": float(sig.alvo),
                "ganho_pct": float(sig.ganho_pct),
                "assert_pct": float(sig.assert_pct),
                "prazo": sig.prazo,
                "zona": sig.zona,
                "risco": sig.risco,
                "prioridade": sig.prioridade,
                "data": _date,
                "hora": _time,
                "price_source": src,
            })
        ok_count += 1

    # FULL ordenado por par
    items.sort(key=lambda x: (x.get("par") or ""))
>>>>>>> Stashed changes

    payload = {
        "source": "local",
        "updated_at": dt_brt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "updated_at_brt": dt_brt.strftime("%Y-%m-%d %H:%M"),
        "gain_min_pct": gain_min,
        "assert_min_pct": assert_min,
        "miss_mark": miss_mark,
        "miss_klines": miss_kl,
        "items": items,
    }
<<<<<<< Updated upstream
    return payload

def write_json(path: str, data: Dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)

def main():
    payload = build_payload()
    write_json(os.path.join(DATA_DIR, "pro.json"), payload)

    # TOP10 (conforme PROMPT BLOCO 1):
    # 1) filtra somente LONG/SHORT válidos (passaram 55/2)
    # 2) ordena por: maior PRIORIDADE (ALTA>MÉDIA>BAIXA) -> maior ASSERT% -> maior GANHO%
    #    -> menor RISCO (BAIXO melhor) -> menor PRAZO (menor melhor)
    def _pts_prioridade(v: str) -> int:
        v = (v or "").upper()
        if v == "ALTA":
            return 3
        if v in ("MÉDIA", "MEDIA"):
            return 2
        if v == "BAIXA":
            return 1
        return 0

    def _pts_risco(v: str) -> int:
        v = (v or "").upper()
        if v == "BAIXO":
            return 3
        if v in ("MÉDIO", "MEDIO"):
            return 2
        if v == "ALTO":
            return 1
        return 0

    def _prazo_min(p: str) -> float:
        # aceita "4.2h" ou "50m"; se vazio, joga p/ fim
        try:
            s = (p or "").strip().lower()
            if not s:
                return 1e9
            if s.endswith('h'):
                return float(s[:-1].strip()) * 60.0
            if s.endswith('m'):
                return float(s[:-1].strip())
        except Exception:
            pass
        return 1e9

    ls = [x for x in payload["items"] if x.get("side") in ("LONG", "SHORT")]
    ls.sort(
        key=lambda x: (
            _pts_prioridade(x.get("prioridade")),
            float(x.get("assert_pct") or 0.0),
            float(x.get("ganho_pct") or 0.0),
            _pts_risco(x.get("risco")),
            -_prazo_min(x.get("prazo")),
        ),
        reverse=True,
    )
    top10 = dict(payload)
    top10["items"] = ls[:10]
    write_json(os.path.join(DATA_DIR, "top10.json"), top10)
=======

    # TOP10 = recorte do FULL já filtrado (LONG/SHORT) e ordenado por pontos
    cand = []
    for it in items:
        if it.get("side") not in ("LONG", "SHORT"):
            continue
        pts = _pts_zona(it.get("zona")) + _pts_risco(it.get("risco")) + _pts_prioridade(it.get("prioridade"))
        it2 = dict(it)
        it2["rank_pts"] = int(pts)
        cand.append(it2)

    cand.sort(key=lambda x: (
        -int(x.get("rank_pts") or 0),
        -float(x.get("assert_pct") or 0.0),
        -float(x.get("ganho_pct") or 0.0),
        str(x.get("par") or "")
    ))

    top10 = {
        "ok": True,
        "source": "local",
        "updated_at": updated_at,
        "now_brt": now_brt,
        "items": cand[:10],
    }

    # auditoria (não pode derrubar o worker)
    try:
        log_prices(top10["items"], updated_at=updated_at)
        log_signals(top10["items"], updated_at=updated_at, gain_min_pct=FULL_GAIN_MIN_PCT)
    except Exception:
        pass

    log(f"OK | coins={len(COINS)} ok={ok_count} missing={miss_count} | FULL(min_gain={FULL_GAIN_MIN_PCT} min_assert={FULL_ASSERT_MIN_PCT}) | TOP10={len(top10['items'])}")
    return payload, top10

def main():
    log(f"START | OUT_FILE={OUT_FILE} | TOP10_FILE={TOP10_FILE} | INTERVAL_S={INTERVAL_S} | COINS={len(COINS)}")
    while True:
        try:
            p, t = build_payload()
            atomic_write_json(OUT_FILE, p)
            atomic_write_json(TOP10_FILE, t)
            log("WROTE pro.json + top10.json")
        except Exception as e:
            log(f"ERROR: {e!r}")
        time.sleep(INTERVAL_S)
>>>>>>> Stashed changes

if __name__ == "__main__":
    main()
