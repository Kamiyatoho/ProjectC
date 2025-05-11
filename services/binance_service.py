import os
import time
import hmac
import hashlib
import json
import requests
from datetime import datetime
from urllib.parse import urlencode

# Clés d'API Binance (via env variables)
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
BASE_URL = "https://api.binance.com"

def get_price_at(asset: str, ts: int, base_currency: str = "USDC") -> float:
    """
    Récupère le prix de clôture de `asset` en `base_currency` au timestamp `ts` (ms).
    """
    symbol = f"{asset}{base_currency}"
    params = {
        "symbol": symbol,
        "interval": "1m",
        "startTime": ts,
        "endTime": ts + 60 * 1000,
        "limit": 1
    }
    try:
        resp = requests.get(f"{BASE_URL}/api/v3/klines", params=params, timeout=5)
        resp.raise_for_status()
        kline = resp.json()
        if kline and len(kline) > 0:
            # Le close price est à l’index [0][4]
            return float(kline[0][4])
    except Exception as e:
        print(f"get_price_at erreur pour {symbol} à {ts}: {e}")
    # Fallback : prix courant
    try:
        ticker = requests.get(f"{BASE_URL}/api/v3/ticker/price", params={"symbol": symbol}, timeout=5).json()
        return float(ticker.get("price", 0))
    except:
        return 0.0

# Stockage en mémoire (chargé/sauvegardé dans JSON)
portfolio_data = {}
raw_data = {}

def _signed_request(method: str, path: str, params: dict = None) -> dict:
    """Envoie une requête signée à l'API Binance."""
    if params is None:
        params = {}
    params['timestamp'] = int(time.time() * 1000)
    query = urlencode(params)
    signature = hmac.new(
        BINANCE_API_SECRET.encode('utf-8'),
        query.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    url = f"{BASE_URL}{path}?{query}&signature={signature}"
    headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
    resp = requests.request(method, url, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()

def fetch_deposits() -> list:
    """
    Récupère l'historique des dépôts :
     - Crypto : /sapi/v1/capital/deposit/hisrec
     - Fiat  : /sapi/v1/fiat/orders (transactionType=0)
    Retourne une liste d'items avec asset, amount, time et category.
    """
    deposits = []
    # 1) Dépôts crypto
    try:
        crypto_data = _signed_request("GET", "/sapi/v1/capital/deposit/hisrec")
    except Exception as e:
        print(f"fetch_deposits (crypto) error: {e}")
        crypto_data = []
    for entry in crypto_data:
        ts    = entry.get("insertTime") or entry.get("timestamp") or 0
        amount= float(entry.get("amount", 0))
        asset = entry.get("coin")
        deposits.append({
            "asset":    asset,
            "amount":   amount,
            "time":     ts,
            "category": "Crypto deposit"
        })

    # 2) Dépôts fiat
    try:
        fiat_resp = _signed_request(
            "GET",
            "/sapi/v1/fiat/orders",
            {"transactionType": "0"}  # 0 = deposit
        )
        fiat_list = fiat_resp.get("data", [])
    except Exception as e:
        print(f"fetch_deposits (fiat) error: {e}")
        fiat_list = []

    for o in fiat_list:
        ts      = o.get("createTime") or 0
        amount  = float(o.get("amount", 0))
        asset   = o.get("fiatCurrency")
        method  = o.get("method", "Ordre fiat")
        deposits.append({
            "asset":    asset,
            "amount":   amount,
            "time":     ts,
            "category": method  # ex: "BankAccount", "GooglePay", etc.
        })

    # Tri chronologique
    deposits.sort(key=lambda x: x["time"])
    return deposits


def fetch_withdrawals() -> list:
    """Récupère l'historique des retraits."""
    try:
        data = _signed_request("GET", "/sapi/v1/capital/withdraw/history")
    except Exception as e:
        print(f"fetch_withdrawals error: {e}")
        return []
    withdrawals = []
    for entry in data:
        withdrawals.append({
            "asset": entry.get("coin"),
            "amount": float(entry.get("amount", 0)),
            "time": entry.get("applyTime") or entry.get("timestamp") or 0
        })
    withdrawals.sort(key=lambda x: x["time"])
    return withdrawals


def fetch_conversions() -> list:
    """Récupère l'historique des conversions (30 derniers jours)."""
    now = int(time.time() * 1000)
    params = {"startTime": now - 30*24*3600*1000, "endTime": now, "limit": 1000}
    try:
        data = _signed_request("GET", "/sapi/v1/convert/tradeFlow", params)
    except Exception as e:
        print(f"fetch_conversions error: {e}")
        return []
    conv = data.get("list", []) if isinstance(data, dict) else []
    conversions = []
    for entry in conv:
        conversions.append({
            "fromAsset": entry.get("fromAsset"),
            "toAsset": entry.get("toAsset"),
            "fromAmount": float(entry.get("fromAmount", 0)),
            "toAmount": float(entry.get("toAmount", 0)),
            "time": entry.get("createTime") or entry.get("timestamp") or 0
        })
    conversions.sort(key=lambda x: x["time"])
    return conversions


def fetch_trades(symbol: str) -> list:
    """Récupère les trades pour un symbole (ACHAT/VENTE)."""
    try:
        data = _signed_request("GET", "/api/v3/myTrades", {"symbol": symbol, "limit": 1000})
    except Exception as e:
        print(f"fetch_trades({symbol}) error: {e}")
        return []
    trades = []
    for t in data:
        trades.append({
            "symbol": symbol,
            "qty": float(t.get("qty", 0)),
            "price": float(t.get("price", 0)),
            "quoteQty": float(t.get("quoteQty", 0)),
            "commission": float(t.get("commission", 0)),
            "commissionAsset": t.get("commissionAsset"),
            "time": t.get("time"),
            "isBuyer": t.get("isBuyer", False)
        })
    trades.sort(key=lambda x: x["time"])
    return trades


def sync_data() -> dict:
    """Synchronise les données (dépôts, retraits, trades, conversions)."""
    global raw_data, portfolio_data
    deposits = fetch_deposits()
    withdrawals = fetch_withdrawals()
    conversions = fetch_conversions()
    symbols = {d['asset'] for d in deposits} | {c['fromAsset'] for c in conversions} | {c['toAsset'] for c in conversions}
    # Récupère trades par symbole contre USDC
    trade_list = []
    for asset in symbols:
        if asset.upper() in ("USDC","BUSD","USDT","EUR","USD"): continue
        sym = f"{asset}USDC"
        trade_list.extend(fetch_trades(sym))
    # Stockage raw_data
    raw_data = {
        "deposits": deposits,
        "withdrawals": withdrawals,
        "trades": trade_list,
        "conversions": conversions
    }
    # Sauvegarde JSON
    os.makedirs("data", exist_ok=True)
    with open("data/raw_data.json", "w") as f:
        json.dump(raw_data, f)
    return raw_data


def get_raw_data() -> dict:
    """Retourne les données brutes (chargées du JSON)."""
    global raw_data
    if not raw_data:
        try:
            with open("data/raw_data.json", "r") as f:
                raw_data = json.load(f)
        except Exception:
            raw_data = {"deposits":[],"withdrawals":[],"trades":[],"conversions":[]}
    return raw_data


def get_portfolio_data() -> dict:
    """Retourne les dernières données de portefeuille (chargées du JSON si nécessaire)."""
    global portfolio_data
    if not portfolio_data:
        try:
            with open("data/portfolio_data.json", "r") as f:
                portfolio_data = json.load(f)
        except Exception:
            portfolio_data = {}
    return portfolio_data
