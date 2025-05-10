import os, time, hmac, hashlib
import requests
from datetime import datetime
from urllib.parse import urlencode

# Lecture des clés d'API Binance depuis les variables d'environnement ou un fichier config.py
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")

# URL de base de l'API Binance
BASE_URL = "https://api.binance.com"

def get_price_at(asset: str, ts: int, base_currency: str = "USDC") -> float:
    """
    Récupère le prix de clôture de `asset` en base_currency au timestamp `ts` (ms).
    Utilise l'endpoint /api/v3/klines de Binance avec interval=1m.
    """
    symbol = f"{asset}{base_currency}"
    # On demande la bougie 1 minute démarrant à ts
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

# Stockage en mémoire des dernières données synchronisées
portfolio_data = {}  # Dictionnaire contenant le résumé du portefeuille et P/L
raw_data = {}        # Dictionnaire contenant les listes brutes: dépôts, trades, conversions

def _signed_request(method, path, params=None):
    """Helper interne pour effectuer une requête signée (HMAC SHA256) à l'API Binance."""
    if params is None:
        params = {}
    # Ajout du timestamp requis pour l'authentification
    params['timestamp'] = int(time.time() * 1000)
    query_string = urlencode(params)
    # Calcul de la signature HMAC SHA256
    signature = hmac.new(BINANCE_API_SECRET.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    # Construction de l’URL avec la signature
    url = f"{BASE_URL}{path}?{query_string}&signature={signature}"
    # En-tête d'authentification API
    headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
    # Envoi de la requête signée selon la méthode spécifiée
    resp = requests.request(method, url, headers=headers)
    resp.raise_for_status()
    return resp.json()

def fetch_deposits():
    """Récupère l'historique des dépôts Binance (tous coins)."""
    try:
        data = _signed_request("GET", "/sapi/v1/capital/deposit/hisrec")
    except Exception as e:
        print(f"Erreur lors de la récupération des dépôts: {e}")
        data = []
    # On normalise les données importantes (asset, amount, timestamp)
    deposits = []
    for entry in data:
        deposits.append({
            "asset": entry.get("coin"),
            "amount": float(entry.get("amount", 0)),
            "time": entry.get("insertTime") or entry.get("timestamp") or 0
        })
    # Trier par date croissante
    deposits.sort(key=lambda x: x["time"])
    return deposits

def fetch_conversions():
    """Récupère l'historique des conversions Binance sur les 30 derniers jours."""
    now = int(time.time() * 1000)
    # 30 jours en millisecondes
    thirty_days_ms = 30 * 24 * 60 * 60 * 1000
    params = {
        "startTime": now - thirty_days_ms,
        "endTime"  : now,
        "limit"    : 100
    }
    try:
        data = _signed_request("GET", "/sapi/v1/convert/tradeFlow", params)
    except Exception as e:
        print(f"Erreur lors de la récupération des conversions: {e}")
        data = {"list": []}

    conversions = []
    for entry in data.get("list", []):
        conversions.append({
            "fromAsset" : entry.get("fromAsset"),
            "toAsset"   : entry.get("toAsset"),
            "fromAmount": float(entry.get("fromAmount", 0)),
            "toAmount"  : float(entry.get("toAmount", 0)),
            "time"      : entry.get("createTime") or entry.get("timestamp") or 0
        })
    conversions.sort(key=lambda x: x["time"])
    return conversions


def fetch_trades(symbol):
    """Récupère les trades (transactions d'achat/vente) pour un symbole de trading donné."""
    # On utilise l’endpoint myTrades pour récupérer l'historique des trades sur le marché spécifié.
    try:
        data = _signed_request("GET", "/api/v3/myTrades", {"symbol": symbol, "limit": 1000})
    except Exception as e:
        # Si le symbole n'existe pas ou autre erreur, on renvoie une liste vide
        print(f"Erreur lors de la récupération des trades pour {symbol}: {e}")
        return []
    trades = []
    for t in data:
        trades.append({
            "symbol": symbol,
            "id": t.get("id"),
            "orderId": t.get("orderId"),
            "price": float(t.get("price", 0)),
            "qty": float(t.get("qty", 0)),
            "quoteQty": float(t.get("quoteQty", 0)),
            "commission": float(t.get("commission", 0)),
            "commissionAsset": t.get("commissionAsset"),
            "time": t.get("time"),
            # Indique le sens de la transaction du point de vue utilisateur
            "isBuyer": t.get("isBuyer")  # booléen, True si l'utilisateur est acheteur (donc trade d'achat)
        })
    trades.sort(key=lambda x: x["time"])
    return trades

def sync_data():
    """Synchronise les données du portefeuille en appelant les API Binance et calcule le portefeuille actuel et les P/L."""
    global portfolio_data, raw_data
    # 1. Récupération des données brutes depuis l'API
    deposits = fetch_deposits()
    conversions = fetch_conversions()
    # Préparer une liste des actifs concernés par les trades à récupérer.
    assets_to_check = set()
    # Inclure les actifs déposés
    for d in deposits:
        assets_to_check.add(d["asset"])
    # Inclure les actifs impliqués dans les conversions
    for conv in conversions:
        assets_to_check.add(conv["fromAsset"])
        assets_to_check.add(conv["toAsset"])
    # On peut également inclure les actifs actuellement en portefeuille via l'API account:
    try:
        account_data = _signed_request("GET", "/api/v3/account")
        for bal in account_data.get("balances", []):
            asset = bal.get("asset")
            qty = float(bal.get("free", 0)) + float(bal.get("locked", 0))
            if qty > 0:
                assets_to_check.add(asset)
    except Exception as e:
        print(f"Impossible de récupérer les soldes du compte: {e}")
        # Si l'appel /account échoue, on continue avec les données existantes
        pass

    # On va récupérer les trades pour chaque actif (en présumant une paire avec USDC ou stable de base)
    trade_list = []
    base_currency = "USDC"
    for asset in list(assets_to_check):
        # On ne récupère pas les trades pour les stablecoins ou fiat directement (capital investi vient des dépôts)
        if asset in ["USDC", "BUSD", "EUR", "USD"]:
            continue
        symbol = f"{asset}{base_currency}"
        trades = fetch_trades(symbol)
        # S'il n'y a pas de trades et que le symbole inversé existe (cas pair fiat par ex: EURUSDC)
        if not trades and asset == "EUR":
            # Exemple: si asset=EUR, symbol=EURUSDC peut ne pas exister sur Binance Spot (EUR peut être noté EURBUSD, etc.)
            # Ici pour simplifier, on essaie avec BUSD si USDC ne donne rien (peut être adapté selon les cas)
            symbol_alt = f"{asset}BUSD"
            trades = fetch_trades(symbol_alt)
        trade_list.extend(trades)

    # 2. Calculer les positions et les P/L à partir des données brutes
    portfolio = {}       # quantités détenues par actif
    cost_basis = {}      # coût total investi par actif détenu
    invested_capital = 0.0
    realized_profit = 0.0
    realized_by_asset = {}  # suivi des P/L réalisés par actif (pour positions fermées)
    # Liste des actifs considérés comme "monnaie de base" ou stable (pas de P/L latent car valeur stable)
    base_assets = ["USDC", "BUSD", "EUR", "USD"]

    # Fonctions utilitaires internes pour mettre à jour les portfolios
    def add_holding(asset, qty, cost):
        """Ajoute qty de l'actif au portfolio avec un coût total spécifié."""
        portfolio[asset] = portfolio.get(asset, 0.0) + qty
        cost_basis[asset] = cost_basis.get(asset, 0.0) + cost

    def remove_holding(asset, qty, cost):
        """Retire qty de l'actif du portfolio en déduisant le coût correspondant."""
        portfolio[asset] = portfolio.get(asset, 0.0) - qty
        cost_basis[asset] = cost_basis.get(asset, 0.0) - cost
        # Nettoyage si la quantité devient ~0
        if portfolio[asset] <= 1e-9:
            portfolio[asset] = 0.0
        if cost_basis.get(asset) is not None and abs(cost_basis[asset]) < 1e-9:
            cost_basis[asset] = 0.0

    # Traitement des dépôts (entrées de capital)
    # Traitement des dépôts (entrées de capital)
    for dep in deposits:
        asset     = dep["asset"]
        amount    = dep["amount"]
        timestamp = dep["time"]

        if asset in base_assets:
            # Stablecoin : coût 1:1
            add_holding(asset, amount, amount)
            invested_capital += amount
        else:
            # Crypto-dépôt : récupérer le prix au moment du dépôt
            price_at_deposit = get_price_at(asset, timestamp)
            cost = price_at_deposit * amount
            add_holding(asset, amount, cost)
            # On considère que ce dépôt n'affecte pas le capital investi (hors plateforme)

    # Combiner les trades et conversions dans l'ordre chronologique
    # On uniformise les conversions en les traitant comme des "trades" (vente de fromAsset contre toAsset sans frais)
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
    # Tri par date/heure
    events.sort(key=lambda x: x["time"])

    # Parcours de chaque événement (trade ou conversion) pour mettre à jour le portfolio et calculer les plus-values
    for ev in events:
        if ev["type"] == "trade":
            # Pour un trade, déterminer l'actif de base et l'actif coté ainsi que le sens (achat ou vente)
            is_buy = ev["isBuyer"]
            base_asset, quote_asset = None, None
            qty = ev["qty"]
            quote_qty = ev["quoteQty"]
            fee = ev.get("commission", 0.0)
            fee_asset = ev.get("commissionAsset")
            if is_buy:
                # Achat: on a acheté base_asset en dépensant quote_asset
                # Exemple: symbol BTCUSDC, on achète BTC (base) en dépensant USDC (quote)
                base_asset, quote_asset = ev["symbol"][:-4], ev["symbol"][-4:]  # base = symbol sans le suffixe "USDC", quote = "USDC" (approximation)
                # Astuce: ceci fonctionne pour paires finissant par 4 caractères de base ("USDC", "BUSD", etc.)
                # Pour une implémentation robuste, on pourrait utiliser l’API ExchangeInfo.
                spent_asset = quote_asset
                received_asset = base_asset
                spent_amount = quote_qty
                received_amount = qty
            else:
                # Vente: on a vendu base_asset pour obtenir quote_asset
                base_asset, quote_asset = ev["symbol"][:-4], ev["symbol"][-4:]
                spent_asset = base_asset
                received_asset = quote_asset
                spent_amount = qty
                received_amount = quote_qty
            # Ajustement des montants si des frais sont prélevés dans l'une des deux devises du trade
            if fee_asset == spent_asset:
                spent_amount += fee  # on a dépensé un peu plus de l'actif de départ pour payer les frais
            if fee_asset == received_asset:
                received_amount -= fee  # on a reçu un peu moins de l'actif cible à cause des frais
            # Calcul du coût moyen de l'actif dépensé
            if is_buy and spent_asset in base_assets:
                # si on achète en stablecoin (USDC, BUSD…), on sait que 1 unité = 1
                cost_spent_total = spent_amount
            else:
                # sinon on calcule le coût moyen comme avant
                avg_cost_spent = 0.0
                if portfolio.get(spent_asset, 0) > 0:
                    total_cost = cost_basis.get(spent_asset, 0.0)
                    total_qty  = portfolio.get(spent_asset, 0.0)
                    if total_qty > 0:
                        avg_cost_spent = total_cost / total_qty
                cost_spent_total = avg_cost_spent * spent_amount
            # Mise à jour du portfolio : retirer l'actif dépensé
            remove_holding(spent_asset, spent_amount, cost_spent_total)
            if received_asset in base_assets:
                # Si on a reçu une devise stable (on a vendu contre du stable), on réalise le profit maintenant
                net_received = received_amount
                # Profit réalisé = montant stable reçu - coût de revient de ce qui a été vendu
                profit = net_received - cost_spent_total
                realized_profit += profit
                # On enregistre le profit réalisé pour l'actif vendu (position fermée)
                realized_by_asset[spent_asset] = realized_by_asset.get(spent_asset, 0.0) + profit
                # On ajoute la devise stable au portfolio avec pour coût uniquement le coût de revient (le profit n'a pas de coût)
                add_holding(received_asset, net_received, cost_spent_total)
            else:
                # Sinon, on a reçu une crypto (on a échangé une crypto contre une autre sans encaisser en stable)
                # On transfère le coût de revient vers la nouvelle position (pas de réalisation immédiate de profit)
                add_holding(received_asset, received_amount, cost_spent_total)
            # Gestion des frais dans un actif tiers (ex: BNB utilisé pour les commissions)
            if fee_asset and fee_asset not in [spent_asset, received_asset]:
                # Si on a payé des frais en BNB (ou autre), on diminue la quantité de cet actif
                fee_amount = fee
                avg_cost_fee = 0.0
                if portfolio.get(fee_asset, 0.0) > 0:
                    avg_cost_fee = cost_basis.get(fee_asset, 0.0) / portfolio.get(fee_asset, 0.0) if portfolio.get(fee_asset, 0.0) else 0.0
                cost_fee_total = avg_cost_fee * fee_amount
                remove_holding(fee_asset, fee_amount, cost_fee_total)
                # Payer des frais est considéré comme une perte (diminution du profit réalisé)
                realized_profit -= cost_fee_total
                realized_by_asset[fee_asset] = realized_by_asset.get(fee_asset, 0.0) - cost_fee_total

        elif ev["type"] == "conversion":
            # Conversion instantanée (Binance Convert) traitée comme une vente de fromAsset contre toAsset (sans frais)
            from_asset = ev["fromAsset"]
            to_asset = ev["toAsset"]
            from_amount = ev["fromAmount"]
            to_amount = ev["toAmount"]
            # Calcul du coût moyen de l'actif source
            avg_cost_from = 0.0
            if portfolio.get(from_asset, 0.0) > 0:
                total_cost_from = cost_basis.get(from_asset, 0.0)
                total_qty_from = portfolio.get(from_asset, 0.0)
                if total_qty_from > 0:
                    avg_cost_from = total_cost_from / total_qty_from
            cost_spent_total = avg_cost_from * from_amount
            # Retirer l'actif source du portfolio
            remove_holding(from_asset, from_amount, cost_spent_total)
            if to_asset in base_assets:
                # Si on convertit en stable, on réalise la plus-value
                net_received = to_amount
                profit = net_received - cost_spent_total
                realized_profit += profit
                realized_by_asset[from_asset] = realized_by_asset.get(from_asset, 0.0) + profit
                add_holding(to_asset, net_received, cost_spent_total)
            else:
                # Conversion crypto->crypto, on reporte le coût sur le nouvel actif
                add_holding(to_asset, to_amount, cost_spent_total)
            # (Pas de frais distincts dans Binance Convert généralement)

    # 3. Calcul du portefeuille actuel et des plus-values latentes
    current_value = 0.0
    prices = {}  # stocker les prix courants des actifs
    for asset, qty in portfolio.items():
        if qty == 0:
            continue
        if asset in base_assets:
            # Les devises stables ou fiat sont évaluées 1:1 (on suppose ici en USD ou équivalent stable)
            prices[asset] = 1.0
            current_value += qty  # valeur = quantité (puisque 1:1)
        else:
            # Récupérer le prix actuel de l'actif en base_currency (ex: BTCUSDC)
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
    # Calcul des plus-values latentes (non réalisées)
    # Formule : P/L latente = valeur actuelle - capital investi - P/L réalisées
    unrealized_profit = current_value - invested_capital - realized_profit

    # Préparer les listes de positions ouvertes et fermées pour affichage
    open_positions = []
    closed_positions = []
    for asset, qty in portfolio.items():
        if asset in base_assets or qty == 0:
            continue  # on ignore les devises stables et les actifs soldés
        avg_price = 0.0
        if qty > 0:
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
        # Si l'actif n'est plus détenu (position entièrement fermée) et ce n'est pas un stablecoin
        if portfolio.get(asset, 0.0) == 0 and asset not in base_assets:
            closed_positions.append({
                "asset": asset,
                "pl_realise": pl
            })

    # Stocker les résultats dans les variables globales
    portfolio_data = {
        "valeur_actuelle": current_value,
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
    return portfolio_data

def get_portfolio_data():
    """Retourne les dernières données de portefeuille calculées (après un sync)."""
    return portfolio_data

def get_raw_data():
    """Retourne les données brutes (dépôts, trades, conversions) de la dernière synchronisation."""
    return raw_data