cat > /opt/ENTRADA-PRO/worker/worker_pro.py <<'PY'
#!/usr/bin/env python3
import os, json, time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Optional

import requests
from zoneinfo import ZoneInfo

BRT = ZoneInfo("America/Sao_Paulo")
DATA_DIR = os.environ.get("DATA_DIR", "/opt/ENTRADA-PRO/data")

# ---------- Config ----------
BYBIT_BASE = "https://api.bybit.com"

def _now_brt() -> Tuple[datetime, str, str]:
    dt = datetime.now(tz=BRT)
    return dt, dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")

def _iso_utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")

def _ttl_iso(hours: float) -> str:
    return (datetime.now(tz=timezone.utc) + (hours * 3600) * (datetime.now(tz=timezone.utc) - datetime.now(tz=timezone.utc))).isoformat()  # placeholder, overwritten below

# fix ttl without extra imports
def _ttl_iso(hours: float) -> str:
    return (datetime.now(tz=timezone.utc) + (timezone.utc.utcoffset(datetime.now()) or (datetime.now(tz=timezone.utc)-datetime.now(tz=timezone.utc)))).isoformat().replace("+00:00","Z")

# simpler ttl: add seconds
def _ttl_iso(hours: float) -> str:
    return (datetime.now(tz=timezone.utc) + (hours * 3600) * (datetime.fromtimestamp(1, tz=timezone.utc) - datetime.fromtimestamp(0, tz=timezone.utc))).isoformat().replace("+00:00","Z")

# ---------- Settings ----------
def load_settings() -> dict:
    # mantemos thresholds fixos (você pode plugar settings depois)
    return {
        "gain_min_pct": 2.0,
        "assert_min_pct": 55.0,
        "coins": [
            "AAVE","ADA","APE","APT","AR","ARB","ATOM","AVAX","AXS","BAT","BCH","BLUR","BNB","BONK","BTC","COMP","CRV","DASH","DGB","DENT","DOGE","DOT","EGLD","EOS","ETC","ETH","FET","FIL","FLOKI","FLOW","FTM","GALA","GLM","GRT","HBAR","IMX","INJ","IOST","ICP","KAS","KAVA","KSM","LINK","LTC","MANA","MATIC","MKR","NEO","NEAR","OMG","ONT","OP","ORDI","PEPE","QNT","QTUM","RNDR","ROSE","RUNE","SAND","SEI","SHIB","SNX","SOL","STX","SUI","SUSHI","TIA","THETA","TRX","UNI","VET","XRP","XEM","XLM","XVS","ZEC","ZRX"
        ]
    }

def get_thresholds(s: dict) -> Tuple[float, float]:
    return float(s.get("gain_min_pct", 2.0)), float(s.get("assert_min_pct", 55.0))

def get_coins(s: dict) -> List[str]:
    return list(s.get("coins") or [])

def _sym(par: str) -> str:
    # Bybit USDT perp
    return f"{par}USDT"

# ---------- Exchange (Bybit) ----------
def _http_get(url: str, params: dict, timeout=10) -> dict:
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()

def _safe_mark(symbol: str) -> Tuple[float, str]:
    try:
        js = _http_get(f"{BYBIT_BASE}/v5/market/tickers", {"category":"linear","symbol":symbol})
        lst = (js.get("result") or {}).get("list") or []
        if not lst:
            return 0.0, "NONE"
        p = float(lst[0].get("lastPrice") or 0.0)
        return (p if p > 0 else 0.0), "BYBIT"
    except Exception:
        return 0.0, "NONE"

def _safe_klines(symbol: str, interval: str, limit: int) -> Tuple[List[List[float]], str]:
    """
    Retorna lista de candles: [ts, open, high, low, close] como float
    interval: "60" (1h) ou "240"(4h)
    """
    try:
        js = _http_get(
            f"{BYBIT_BASE}/v5/market/kline",
            {"category":"linear","symbol":symbol,"interval":interval,"limit":str(limit)}
        )
        rows = (js.get("result") or {}).get("list") or []
        out = []
        for it in reversed(rows):
            # it: [startTime, open, high, low, close, volume, turnover]
            out.append([float(it[0]), float(it[1]), float(it[2]), float(it[3]), float(it[4])])
        return out, "BYBIT"
    except Exception:
        return [], "NONE"

# ---------- Signal Logic (simples e coerente p/ 1-2 dias) ----------
@dataclass
class Sig:
    side: str
    atual: float
    alvo: float
    ganho_pct: float
    assert_pct: float
    prazo: str
    nao_entrar_motivo: str

def _trend_dir(closes: List[float]) -> int:
    # dir: +1 alta, -1 baixa, 0 indefinido
    if len(closes) < 30:
        return 0
    a = closes[-1]
    b = closes[-25]
    if b <= 0:
        return 0
    chg = (a - b) / b
    if chg > 0.003:
        return +1
    if chg < -0.003:
        return -1
    return 0

def build_signal(ohlc_1h: List[List[float]], ohlc_4h: List[List[float]], mark: float,
                 gain_min_pct: float, assert_min_pct: float) -> Sig:
    if mark <= 0:
        return Sig("NÃO ENTRAR", 0.0, 0.0, 0.0, 0.0, "-", "SEM_PRECO_ATUAL")

    c1 = [c[4] for c in ohlc_1h] if ohlc_1h else []
    c4 = [c[4] for c in ohlc_4h] if ohlc_4h else []

    if len(c1) < 30 or len(c4) < 30:
        return Sig("NÃO ENTRAR", mark, mark, 0.0, 0.0, "-", "SEM_KLINES")

    d1 = _trend_dir(c1)   # 1h
    d4 = _trend_dir(c4)   # 4h

    if d1 == 0 or d4 == 0:
        return Sig("NÃO ENTRAR", mark, mark, 0.0, 0.0, "-", "TENDENCIA_INDECISA")

    if d1 != d4:
        return Sig("NÃO ENTRAR", mark, mark, 0.0, 0.0, "-", "1H_X_4H_CONFLITO")

    side = "LONG" if d1 > 0 else "SHORT"
    alvo = mark * (1.0 + gain_min_pct/100.0) if side == "LONG" else mark * (1.0 - gain_min_pct/100.0)
    if alvo <= 0:
        return Sig("NÃO ENTRAR", mark, mark, 0.0, 0.0, "-", "ALVO_INVALIDO")

    # ganho coerente com alvo
    ganho = ((alvo - mark)/mark)*100.0 if side=="LONG" else ((mark - alvo)/mark)*100.0
    if ganho < gain_min_pct * 0.95:
        return Sig("NÃO ENTRAR", mark, mark, 0.0, 0.0, "-", "GANHO_BAIXO")

    # assert simples: concordância 1h/4h => base 60; força do movimento ajusta
    strength = abs((c1[-1]-c1[-25])/c1[-25]) * 100.0
    assert_pct = min(85.0, max(55.0, 60.0 + strength*2.0))
    if assert_pct < assert_min_pct:
        return Sig("NÃO ENTRAR", mark, mark, 0.0, assert_pct, "-", "ASSERT_BAIXA")

    prazo = "1-2d"
    return Sig(side, mark, alvo, ganho, assert_pct, prazo, "")

# ---------- JSON ----------
def write_json(path: str, data: Dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)

def _mk_item(par: str, sig: Sig, date_brt: str, time_brt: str, price_source: str, ttl: str) -> Dict:
    return {
        "par": par,
        "side": sig.side,
        "price_source": price_source or "NONE",
        "atual": float(sig.atual or 0.0),
        "alvo": float(sig.alvo or 0.0),
        "ganho_pct": float(sig.ganho_pct or 0.0),
        "assert_pct": float(sig.assert_pct or 0.0),
        "prazo": sig.prazo or "-",
        "data": date_brt,
        "hora": time_brt,
        "nao_entrar_motivo": (sig.nao_entrar_motivo or ""),
        "ttl_expira_em": ttl
    }

def main():
    while True:
        s = load_settings()
        gain_min, assert_min = get_thresholds(s)
        coins = get_coins(s)

        dt_brt, date_brt, time_brt = _now_brt()
        updated_at = _iso_utc_now()
        ttl = _iso_utc_now()  # simples por enquanto (pode trocar depois)

        items = []
        miss_mark = 0
        miss_kl = 0

        for par in coins:
            symbol = _sym(par)
            mark, src = _safe_mark(symbol)
            if mark <= 0:
                miss_mark += 1

            k1, _ = _safe_klines(symbol, "60", 220)
            k4, _ = _safe_klines(symbol, "240", 220)
            if not k1 or not k4:
                miss_kl += 1

            sig = build_signal(k1, k4, float(mark or 0.0), gain_min, assert_min)
            items.append(_mk_item(par, sig, date_brt, time_brt, src, ttl))

        items.sort(key=lambda x: x.get("par") or "")

        payload = {
            "ok": True,
            "source": "local",
            "updated_at": updated_at,
            "now_brt": dt_brt.strftime("%Y-%m-%d %H:%M"),
            "gain_min_pct": gain_min,
            "assert_min_pct": assert_min,
            "miss_mark": int(miss_mark),
            "miss_klines": int(miss_kl),
            "items": items,
        }

        write_json(os.path.join(DATA_DIR, "pro.json"), payload)

        # TOP10: só LONG/SHORT (NÃO ENTRAR não entra)
        tradables = [x for x in items if x.get("side") in ("LONG","SHORT")]
        top10 = sorted(tradables, key=lambda x: (-float(x.get("ganho_pct") or 0.0), -float(x.get("assert_pct") or 0.0)))[:10]
        payload_top = dict(payload)
        payload_top["items"] = top10
        write_json(os.path.join(DATA_DIR, "top10.json"), payload_top)

        print(f"[WORKER_PRO] OK | coins={len(coins)} miss_mark={miss_mark} miss_klines={miss_kl} | TOP10={len(top10)}")
        time.sleep(300)

if __name__ == "__main__":
    main()
PY
