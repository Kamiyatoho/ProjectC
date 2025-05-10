from datetime import datetime


def calculate_portfolio(data):
    """
    À partir des données brutes Binance (transactions, soldes, prix),
    calcule le portefeuille par crypto, les statistiques pour les graphiques,
    et l'estimation d'impôt.
    """
    transactions = data.get("transactions", [])
    balances = data.get("balances", {})
    prices = data.get("prices", {})

    # Structures intermédiaires
    portfolio = []
    portfolio_dict = {}
    profit_events = []  # Liste de (timestamp, profit réalisé) pour calcul mensuel

    # Parcourir les transactions
    for trade in transactions:
        symbol = trade["symbol"]           # ex : "BTCUSDC"
        asset = symbol.replace("USDC", "")
        is_buy = trade.get('isBuyer', False)
        qty = trade.get('qty', 0.0)
        quote_qty = trade.get('quoteQty', 0.0)

        # Initialiser si nouveau asset
        if asset not in portfolio_dict:
            portfolio_dict[asset] = {
                "quantity": 0.0,
                "total_cost": 0.0,
                "realized_profit": 0.0
            }
        entry = portfolio_dict[asset]

        if is_buy:
            # Achat : on augmente quantité et coût
            entry["quantity"] += qty
            entry["total_cost"] += quote_qty
        else:
            # Vente : calcul de la plus-value réalisée
            if entry["quantity"] <= 0:
                continue
            total_qty_before = entry["quantity"]
            total_cost_before = entry["total_cost"]
            # Portion de coût liée à qty vendue
            portion_cost = total_cost_before * (qty / total_qty_before)
            profit = quote_qty - portion_cost
            entry["realized_profit"] += profit
            # Mettre à jour position
            entry["quantity"] -= qty
            entry["total_cost"] -= portion_cost
            if abs(entry["quantity"]) < 1e-9:
                entry["quantity"] = 0.0
                entry["total_cost"] = 0.0
            # Enregistrer pour statistique mensuelle
            profit_events.append((trade.get('time', 0), profit))

    # Construction du portefeuille final
    total_value = 0.0
    distribution = []

    for asset, vals in portfolio_dict.items():
        qty = vals["quantity"]
        cost = vals["total_cost"]
        realized = vals["realized_profit"]
        # Prix moyen
        avg_price = cost / qty if qty > 0 else 0.0
        # Valorisation actuelle
        current_price = prices.get(asset, 0.0)
        current_value = current_price * qty
        total_value += current_value
        if qty > 0:
            distribution.append({"asset": asset, "value": round(current_value, 2)})

        # Plus-value latente
        unrealized = round(current_value - cost, 2)

        portfolio.append({
            "asset": asset,
            "quantite": round(qty, 8),
            "investissement_total": round(cost, 2),
            "prix_moyen": round(avg_price, 2) if avg_price >= 1 else round(avg_price, 5),
            "plus_value_realisee": round(realized, 2),
            "plus_value_latente": unrealized
        })

    # Ajouter cash si présent
    for cash_asset in ("USD", "EUR"):
        amt = balances.get(cash_asset, 0.0)
        if amt > 0:
            total_value += amt
            distribution.append({"asset": cash_asset, "value": round(amt, 2)})

    # Calcul des plus-values mensuelles
    monthly_profits = {}
    for ts, profit in profit_events:
        date = datetime.fromtimestamp(ts/1000)
        key = date.strftime("%Y-%m")
        monthly_profits[key] = monthly_profits.get(key, 0.0) + profit
    # Remplir mois manquants
    if monthly_profits:
        months = sorted(monthly_profits.keys())
        start = datetime.strptime(months[0], "%Y-%m")
        end = datetime.now()
        cur = start
        while cur <= end:
            key = cur.strftime("%Y-%m")
            monthly_profits.setdefault(key, 0.0)
            if cur.month == 12:
                cur = cur.replace(year=cur.year+1, month=1)
            else:
                cur = cur.replace(month=cur.month+1)
        monthly_list = [ {"month": m, "profit": round(monthly_profits[m], 2)} for m in sorted(monthly_profits) ]
    else:
        monthly_list = []

    # Calcul de l'impôt estimé (flat 30%) sur plus-values réalisées de l'année
    current_year = datetime.now().year
    pv_year = sum(p for ts,p in profit_events if datetime.fromtimestamp(ts/1000).year == current_year)
    pv_year = round(pv_year, 2)
    tax = round(pv_year * 0.30, 2) if pv_year > 0 else 0.0

    stats = {
        "historique_valeur": round(total_value, 2),
        "distribution": distribution,
        "plus_values_mensuelles": monthly_list
    }
    taxes = {"annee": current_year, "plus_values_annee": pv_year, "taxes_estimees": tax}

    return portfolio, stats, taxes