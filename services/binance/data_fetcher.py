import time
from .client import BinanceClient

# Shared BinanceClient instance
client = BinanceClient()


def fetch_deposits() -> list:
    """
    Fetch crypto and fiat deposit history, combine and sort by time.
    """
    deposits = []
    # Crypto deposits
    try:
        crypto_data = client._signed_request("GET", "/sapi/v1/capital/deposit/hisrec")
    except Exception:
        crypto_data = []
    for entry in crypto_data:
        deposits.append({
            "asset": entry.get("coin"),
            "amount": float(entry.get("amount", 0)),
            "time": entry.get("insertTime", 0),
            "category": "Crypto deposit"
        })
    # Fiat deposits
    try:
        fiat_resp = client._signed_request(
            "GET", "/sapi/v1/fiat/orders", {"transactionType": "0"}
        )
        fiat_list = fiat_resp.get("data", [])
    except Exception:
        fiat_list = []
    for o in fiat_list:
        deposits.append({
            "asset": o.get("fiatCurrency"),
            "amount": float(o.get("amount", 0)),
            "time": o.get("createTime", 0),
            "category": o.get("method", "Fiat deposit")
        })
    # Sort by timestamp
    deposits.sort(key=lambda x: x["time"])
    return deposits


def fetch_withdrawals() -> list:
    """
    Fetch crypto withdrawal history and sort by time.
    """
    try:
        data = client._signed_request("GET", "/sapi/v1/capital/withdraw/history")
    except Exception:
        return []
    withdrawals = []
    for entry in data:
        withdrawals.append({
            "asset": entry.get("coin"),
            "amount": float(entry.get("amount", 0)),
            "time": entry.get("applyTime", 0)
        })
    withdrawals.sort(key=lambda x: x["time"])
    return withdrawals


def fetch_conversions() -> list:
    """
    Fetch convert trade flow (convert orders) for the last 30 days and sort by time.
    """
    now = int(time.time() * 1000)
    try:
        data = client._signed_request(
            "GET", "/sapi/v1/convert/tradeFlow", {
                "startTime": now - 30 * 24 * 3600 * 1000,
                "endTime": now,
                "limit": 1000
            }
        )
    except Exception:
        return []
    conv_list = data.get("list", []) if isinstance(data, dict) else []
    conversions = []
    for entry in conv_list:
        conversions.append({
            "fromAsset": entry.get("fromAsset"),
            "toAsset": entry.get("toAsset"),
            "fromAmount": float(entry.get("fromAmount", 0)),
            "toAmount": float(entry.get("toAmount", 0)),
            "time": entry.get("createTime", 0)
        })
    conversions.sort(key=lambda x: x["time"])
    return conversions


def fetch_trades(symbol: str) -> list:
    """
    Fetch user trades for a given symbol (max 1000) and sort by time.
    """
    try:
        data = client._signed_request("GET", "/api/v3/myTrades", {"symbol": symbol, "limit": 1000})
    except Exception:
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
            "time": t.get("time", 0),
            "isBuyer": t.get("isBuyer", False)
        })
    trades.sort(key=lambda x: x["time"])
    return trades