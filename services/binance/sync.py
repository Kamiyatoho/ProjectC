# services/binance/sync.py

import os
import json
from .client import BinanceClient
from .data_fetcher import (
    fetch_deposits, fetch_withdrawals,
    fetch_conversions, fetch_trades
)
from .portfolio import PortfolioService

def sync_data(base_currency: str = "USDC") -> dict:
    # 1) Fetch raw events
    deposits    = fetch_deposits()
    withdrawals = fetch_withdrawals()
    conversions = fetch_conversions()

    # 2) Fetch trades for all non-stable assets
    assets = {d["asset"] for d in deposits}
    assets |= {c["fromAsset"] for c in conversions}
    assets |= {c["toAsset"]   for c in conversions}
    trades = []
    for asset in assets:
        if asset not in ["USDC", "BUSD", "EUR", "USD"]:
            symbol = f"{asset}{base_currency}"
            trades.extend(fetch_trades(symbol))

    # 3) Get balances
    client   = BinanceClient()
    account  = client._signed_request("GET", "/api/v3/account")
    balances = account.get("balances", [])

    # 4) Calculate portfolio (no year filtering → tout l’historique)
    svc      = PortfolioService(client)
    invested = svc.calculate_invested(deposits, year=None)  # on modifiera la méthode pour accepter None
    value    = svc.get_portfolio_value(balances)
    pl       = value - invested

    portfolio_data = {
        "valeur_actuelle": value,
        "capital_investi": invested,
        "pl": pl
    }

    raw_data = {
        "deposits":    deposits,
        "withdrawals": withdrawals,
        "conversions": conversions,
        "trades":      trades
    }

    # 5) Persist JSON
    os.makedirs("data", exist_ok=True)
    with open("data/raw_data.json", "w") as f:
        json.dump(raw_data, f, indent=2)
    with open("data/portfolio_data.json", "w") as f:
        json.dump(portfolio_data, f, indent=2)

    return portfolio_data