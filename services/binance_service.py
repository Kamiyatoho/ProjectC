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
# 2. Calcul des positions et P/L
    portfolio = {}
    cost_basis = {}
    invested_capital = 0.0
    realized_profit = 0.0
    realized_by_asset = {}
    base_assets = ["USDC", "BUSD", "EUR", "USD"]

    def add_holding(asset, qty, cost):
        portfolio[asset] = portfolio.get(asset, 0.0) + qty
        cost_basis[asset] = cost_basis.get(asset, 0.0) + cost

    def remove_holding(asset, qty, cost):
        portfolio[asset] = portfolio.get(asset, 0.0) - qty
        cost_basis[asset] = cost_basis.get(asset, 0.0) - cost
        if portfolio[asset] <= 1e-9:
            portfolio[asset] = 0.0
        if cost_basis.get(asset) is not None and abs(cost_basis[asset]) < 1e-9:
            cost_basis[asset] = 0.0

    # Traitement des dépôts (capital investi)
    for dep in deposits:
        asset, amount, ts = dep["asset"], dep["amount"], dep["time"]
        if asset in ["USDC", "BUSD"]:
            # stables 1:1
            add_holding(asset, amount, amount)
            invested_capital += amount

        elif asset == "EUR":
            # récupérer le cours EURUSDC au timestamp
            price = get_price_at("EUR", ts, base_currency="USDC")
            cost = price * amount
            # on ajoute un solde USDC, pas un solde EUR
            add_holding("USDC", cost, cost)
            invested_capital += cost

        else:
            # crypto classique
            price = get_price_at(asset, ts)
            cost = price * amount
            add_holding(asset, amount, cost)
            invested_capital += cost
    # Traitement des retraits (capital investi)
    for w in withdrawals:
        asset, amount, ts = w["asset"], w["amount"], w["time"]

        if asset in ["USDC", "BUSD"]:
            # Stablecoins 1:1
            remove_holding(asset, amount, amount)
            invested_capital -= amount

        elif asset == "EUR":
            # On convertit d’abord l’EUR en USDC au taux historique
            price = get_price_at("EUR", ts, base_currency="USDC")
            cost = price * amount
            # On retire du solde USDC (pas de solde EUR conservé)
            remove_holding("USDC", cost, cost)
            invested_capital -= cost

        else:
            # Crypto classique : on récupère le prix spot au moment du retrait
            price = get_price_at(asset, ts)
            cost = price * amount
            remove_holding(asset, amount, cost)
            invested_capital -= cost

    # Combiner trades et conversions chronologiquement
    events = []
    for t in trade_list:
        events.append({
            "type": "trade",
            "symbol": t["symbol"],
            "price": t["price"],
            "qty": t["qty"],
            "quoteQty": t["quoteQty"],
            "commission": t.get("commission", 0.0),
            "commissionAsset": t.get("commissionAsset"),
            "time": t["time"],
            "isBuyer": t["isBuyer"]
        })
    for c in conversions:
        events.append({
            "type": "conversion",
            "fromAsset": c["fromAsset"],
            "toAsset": c["toAsset"],
            "fromAmount": c["fromAmount"],
            "toAmount": c["toAmount"],
            "time": c["time"]
        })
    events.sort(key=lambda x: x["time"])

    # Parcours des événements pour mettre à jour le portefeuille
    for ev in events:
        if ev["type"] == "trade":
            is_buy = ev["isBuyer"]
            qty = ev["qty"]
            quote_qty = ev["quoteQty"]
            fee = ev.get("commission", 0.0)
            fee_asset = ev.get("commissionAsset")
            if is_buy:
                # Achat: on achète base_asset en dépensant quote_asset
                base_asset, quote_asset = ev["symbol"][:-len(base_currency)], base_currency
                spent_asset = quote_asset
                received_asset = base_asset
                spent_amount = quote_qty
                received_amount = qty
            else:
                # Vente: on vend base_asset pour obtenir quote_asset
                base_asset, quote_asset = ev["symbol"][:-len(base_currency)], base_currency
                spent_asset = base_asset
                received_asset = quote_asset
                spent_amount = qty
                received_amount = quote_qty
            # Ajuster pour les frais
            if fee_asset == spent_asset:
                spent_amount += fee
            if fee_asset == received_asset:
                received_amount -= fee
            # Calcul du coût de l'actif dépensé
            if is_buy and spent_asset in base_assets:
                cost_spent_total = spent_amount
            else:
                avg_cost_spent = 0.0
                if portfolio.get(spent_asset, 0) > 0:
                    total_cost = cost_basis.get(spent_asset, 0.0)
                    total_qty = portfolio.get(spent_asset, 0.0)
                    if total_qty > 0:
                        avg_cost_spent = total_cost / total_qty
                cost_spent_total = avg_cost_spent * spent_amount
            # Mettre à jour le portefeuille
            remove_holding(spent_asset, spent_amount, cost_spent_total)
            if received_asset in base_assets:
                # On reçoit une stable : on réalise le profit
                net_received = received_amount
                profit = net_received - cost_spent_total
                realized_profit += profit
                realized_by_asset[spent_asset] = realized_by_asset.get(spent_asset, 0.0) + profit
                add_holding(received_asset, net_received, cost_spent_total)
            else:
                # On reçoit une crypto : reporter le coût
                add_holding(received_asset, received_amount, cost_spent_total)
            # Frais en BNB ou autre
            if fee_asset and fee_asset not in [spent_asset, received_asset]:
                fee_amount = fee
                avg_cost_fee = 0.0
                if portfolio.get(fee_asset, 0.0) > 0:
                    avg_cost_fee = cost_basis.get(fee_asset, 0.0) / portfolio.get(fee_asset, 0.0)
                cost_fee_total = avg_cost_fee * fee_amount
                remove_holding(fee_asset, fee_amount, cost_fee_total)
                realized_profit -= cost_fee_total
                realized_by_asset[fee_asset] = realized_by_asset.get(fee_asset, 0.0) - cost_fee_total

        elif ev["type"] == "conversion":
            from_asset = ev["fromAsset"]
            to_asset = ev["toAsset"]
            from_amount = ev["fromAmount"]
            to_amount = ev["toAmount"]
            # Calcul du coût moyen de l'actif source
            avg_cost_from = 0.0
            if from_asset in base_assets:
                # Stablecoins / fiat : coût 1:1
                cost_spent_total = from_amount
            else:
                # Crypto : on utilise le coût moyen historique
                avg_cost_from = 0.0
                total_qty_from = portfolio.get(from_asset, 0.0)
                if total_qty_from > 0:
                    total_cost_from = cost_basis.get(from_asset, 0.0)
                    avg_cost_from = total_cost_from / total_qty_from
                cost_spent_total = avg_cost_from * from_amount
            remove_holding(from_asset, from_amount, cost_spent_total)
            if to_asset in base_assets:
                net_received = to_amount
                profit = net_received - cost_spent_total
                realized_profit += profit
                realized_by_asset[from_asset] = realized_by_asset.get(from_asset, 0.0) + profit
                add_holding(to_asset, net_received, cost_spent_total)
            else:
                add_holding(to_asset, to_amount, cost_spent_total)
            # Pas de frais distincts pour Binance Convert généralement

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
        "capital_investi": invested_capital - usdc_balance,
        "pl_realise": realized_profit,
        "pl_latent": unrealized_profit,
        "open_positions": open_positions,
        "closed_positions": closed_positions
    }
    # Ajout du solde USDC réel
    portfolio_data["solde_usdc"] = usdc_balance

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