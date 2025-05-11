import os
import time
import hmac
import hashlib
import json
import requests
from urllib.parse import urlencode

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
BASE_URL = "https://api.binance.com"

raw_data = {}
portfolio_data = {}

base_assets = ["USDC", "BUSD", "EUR", "USD"]


def _signed_request(method: str, path: str, params: dict = None) -> dict:
    if params is None:
        params = {}
    params['timestamp'] = int(time.time() * 1000)
    query_string = urlencode(params)
    signature = hmac.new(
        BINANCE_API_SECRET.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    url = f"{BASE_URL}{path}?{query_string}&signature={signature}"
    headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
    resp = requests.request(method, url, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_price_at(asset: str, ts: int, base_currency: str = "USDC") -> float:
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
            return float(kline[0][4])
    except Exception:
        pass
    try:
        ticker = requests.get(f"{BASE_URL}/api/v3/ticker/price", params={"symbol": symbol}, timeout=5).json()
        return float(ticker.get("price", 0))
    except:
        return 0.0


def fetch_deposits() -> list:
    deposits = []
    try:
        crypto_data = _signed_request("GET", "/sapi/v1/capital/deposit/hisrec")
    except Exception:
        crypto_data = []
    for entry in crypto_data:
        deposits.append({
            "asset": entry.get("coin"),
            "amount": float(entry.get("amount", 0)),
            "time": entry.get("insertTime", 0),
            "category": "Crypto deposit"
        })
    try:
        fiat_data = _signed_request("GET", "/sapi/v1/fiat/orders", {"transactionType": "0"})
        fiat_list = fiat_data.get("data", [])
    except Exception:
        fiat_list = []
    for o in fiat_list:
        deposits.append({
            "asset": o.get("fiatCurrency"),
            "amount": float(o.get("amount", 0)),
            "time": o.get("createTime", 0),
            "category": o.get("method", "Ordre fiat")
        })
    deposits.sort(key=lambda x: x["time"])
    return deposits


def fetch_withdrawals() -> list:
    try:
        data = _signed_request("GET", "/sapi/v1/capital/withdraw/history")
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
    now = int(time.time() * 1000)
    try:
        data = _signed_request("GET", "/sapi/v1/convert/tradeFlow", {
            "startTime": now - 30 * 24 * 3600 * 1000,
            "endTime": now,
            "limit": 1000
        })
    except Exception:
        return []
    conv = data.get("list", []) if isinstance(data, dict) else []
    conversions = []
    for entry in conv:
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
    try:
        data = _signed_request("GET", "/api/v3/myTrades", {"symbol": symbol, "limit": 1000})
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
            "time": t.get("time"),
            "isBuyer": t.get("isBuyer", False)
        })
    trades.sort(key=lambda x: x["time"])
    return trades


def get_raw_data() -> dict:
    global raw_data
    if not raw_data:
        try:
            with open("data/raw_data.json", "r") as f:
                raw_data = json.load(f)
        except Exception:
            raw_data = {"deposits": [], "withdrawals": [], "trades": [], "conversions": []}
    return raw_data


def get_portfolio_data() -> dict:
    global portfolio_data
    if not portfolio_data:
        try:
            with open("data/portfolio_data.json", "r") as f:
                portfolio_data = json.load(f)
        except Exception:
            portfolio_data = {}
    return portfolio_data


def sync_data() -> dict:
    global raw_data, portfolio_data

    deposits = fetch_deposits()
    withdrawals = fetch_withdrawals()
    conversions = fetch_conversions()

    # Collecte des actifs à vérifier
    assets_to_check = set()
    for d in deposits:
        assets_to_check.add(d["asset"])
    for conv in conversions:
        assets_to_check.add(conv["fromAsset"])
        assets_to_check.add(conv["toAsset"])

    # Récupération du solde USDC réel
    usdc_balance = 0.0
    try:
        account_data = _signed_request("GET", "/api/v3/account")
        for bal in account_data.get("balances", []):
            asset = bal.get("asset")
            qty = float(bal.get("free", 0)) + float(bal.get("locked", 0))
            if asset == "USDC":
                usdc_balance = qty
            if qty > 0:
                assets_to_check.add(asset)
    except Exception as e:
        print(f"Impossible de récupérer les soldes du compte: {e}")

    # Récupération des trades pour chaque actif (supposé contre USDC ou stable)
    trade_list = []
    base_currency = "USDC"
    for asset in list(assets_to_check):
        if asset in ["USDC", "BUSD", "EUR", "USD"]:
            continue
        symbol = f"{asset}{base_currency}"
        trades = fetch_trades(symbol)
        if not trades and asset == "EUR":
            symbol_alt = f"{asset}BUSD"
            trades = fetch_trades(symbol_alt)
        trade_list.extend(trades)

    # Enregistrement brut
    raw_data = {
        "deposits": deposits,
        "withdrawals": withdrawals,
        "trades": trade_list,
        "conversions": conversions
    }
    # 2. Initialisation des structures et compteurs
    portfolio       = {}
    cost_basis      = {}
    invested_capital= 0.0
    realized_profit = 0.0
    realized_by_asset = {}
    base_assets     = ["USDC", "BUSD", "EUR", "USD"]

    # 3. Fonctions utilitaires
    def add_holding(asset, quantity, cost):
        portfolio[asset]   = portfolio.get(asset, 0.0) + quantity
        cost_basis[asset]  = cost_basis.get(asset, 0.0) + cost

    def remove_holding(asset, quantity, cost):
        if portfolio.get(asset, 0.0) < quantity:
            print(f"⚠️ Alerte : pas assez de {asset} pour retirer {quantity}. Disponible : {portfolio.get(asset, 0.0)}")
        portfolio[asset]  = max(portfolio.get(asset, 0.0) - quantity, 0.0)
        cost_basis[asset] = max(cost_basis.get(asset, 0.0) - cost, 0.0)

    # 4. Traitement des dépôts (capital investi)
    for dep in deposits:
        asset     = dep["asset"]
        amount    = dep["amount"]
        timestamp = dep["time"]
        if asset in base_assets:
            add_holding(asset, amount, amount)
            invested_capital += amount
        else:
            price = get_price_at(asset, timestamp)
            cost  = price * amount
            add_holding(asset, amount, cost)
            invested_capital += cost

    # 5. Fusion des trades + conversions en events
    events = []
    for t in trade_list:
        is_buy      = t["isBuyer"]
        base_asset  = t["symbol"][:-len(base_currency)]
        quote_asset = base_currency
        if is_buy:
            frm_amt, to_amt = t["quoteQty"], t["qty"]
            frm_asset, to_asset = quote_asset, base_asset
        else:
            frm_amt, to_amt = t["qty"], t["quoteQty"]
            frm_asset, to_asset = base_asset, quote_asset

        events.append({
            "time": t["time"],
            "from": {"asset": frm_asset, "amount": frm_amt},
            "to":   {"asset": to_asset,   "amount": to_amt},
            "fee":  {"asset": t.get("commissionAsset"), "amount": float(t.get("commission", 0.0))}
                   if t.get("commissionAsset") else None
        })

    for c in conversions:
        events.append({
            "time": c["time"],
            "from": {"asset": c["fromAsset"], "amount": c["fromAmount"]},
            "to":   {"asset": c["toAsset"],   "amount": c["toAmount"]},
            "fee":  None
        })

    events.sort(key=lambda ev: ev["time"])

    # 6. Boucle unifiée d'application des échanges
    for ev in events:
        frm_a = ev["from"]["asset"]
        frm_q = ev["from"]["amount"]
        to_a  = ev["to"]["asset"]
        to_q  = ev["to"]["amount"]
        fee   = ev["fee"]

        # 🔸 Calcul du coût du from_asset
        if frm_a in base_assets:
            cost_spent = frm_q
        else:
            total_q = portfolio.get(frm_a, 0.0)
            total_c = cost_basis.get(frm_a, 0.0)
            avg     = (total_c / total_q) if total_q > 0 else 0.0
            cost_spent = avg * frm_q

        # 🔸 Retrait de l'actif dépensé
        remove_holding(frm_a, frm_q, cost_spent)

        # 🔸 Réception de to_asset
        if to_a in base_assets:
            profit = to_q - cost_spent
            realized_profit += profit
            realized_by_asset[frm_a] = realized_by_asset.get(frm_a, 0.0) + profit
            add_holding(to_a, to_q, cost_spent)
        else:
            add_holding(to_a, to_q, cost_spent)

        # 🔸 Gestion des frais, si un fee asset différent
        if fee and fee["asset"] not in [frm_a, to_a]:
            f_a = fee["asset"]
            f_q = float(fee["amount"])
            total_q = portfolio.get(f_a, 0.0)
            total_c = cost_basis.get(f_a, 0.0)
            avg_f   = (total_c / total_q) if total_q > 0 else 0.0
            cost_fee = avg_f * f_q

            remove_holding(f_a, f_q, cost_fee)
            realized_profit -= cost_fee
            realized_by_asset[f_a] = realized_by_asset.get(f_a, 0.0) - cost_fee

    # 3. Calcul de la valeur actuelle et P/L latent
    current_value = 0.0
    prices = {}
    for asset, qty in portfolio.items():
        if qty == 0:
            continue
        if asset in base_assets:
            prices[asset] = 1.0
            current_value += qty
        else:
            symbol = f"{asset}{base_currency}"
            try:
                resp = requests.get(f"{BASE_URL}/api/v3/ticker/price", params={"symbol": symbol})
                resp.raise_for_status()
                price = float(resp.json().get("price", 0.0))
            except Exception as e:
                print(f"Erreur en récupérant le prix de {asset}: {e}")
                price = 0.0
            prices[asset] = price
            current_value += qty * price

    unrealized_profit = current_value - invested_capital - realized_profit

    # Positions ouvertes et fermées
    open_positions = []
    closed_positions = []
    for asset, qty in portfolio.items():
        if asset in base_assets or qty == 0:
            continue
        avg_price = cost_basis.get(asset, 0.0) / qty if qty != 0 else 0.0
        curr_price = prices.get(asset, 0.0)
        pl_latent = qty * curr_price - cost_basis.get(asset, 0.0)
        open_positions.append({
            "asset": asset,
            "quantity": qty,
            "avg_price": avg_price,
            "current_price": curr_price,
            "pl_latent": pl_latent
        })
    for asset, pl in realized_by_asset.items():
        if portfolio.get(asset, 0.0) == 0 and asset not in base_assets:
            closed_positions.append({
                "asset": asset,
                "pl_realise": pl
            })

    # Rassemblement des résultats
    portfolio_data = {
        "valeur_actuelle": current_value,
        "solde_usdc": usdc_balance,
        "capital_investi": invested_capital,
        "pl_realise": realized_profit,
        "pl_latent": unrealized_profit,
        "open_positions": open_positions,
        "closed_positions": closed_positions
    }

    raw_data = {
        "deposits": deposits,
        "trades": trade_list,
        "conversions": conversions
    }

    # Persistance locale en JSON
    os.makedirs("data", exist_ok=True)
    with open("data/raw_data.json", "w") as f:
        json.dump(raw_data, f)
    with open("data/portfolio_data.json", "w") as f:
        json.dump(portfolio_data, f)

    return portfolio_data