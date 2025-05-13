# services/binance/io.py
import json

def get_raw_data():
    with open("data/raw_data.json", "r") as f:
        return json.load(f)

def get_portfolio_data():
    with open("data/portfolio_data.json", "r") as f:
        return json.load(f)