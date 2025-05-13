from .client import BinanceClient

# Instantiate a shared client for pricing endpoints
_client = BinanceClient()


def get_current_price(symbol: str) -> float:
    """
    Fetch the current ticker price for the given symbol.

    :param symbol: Asset pair symbol, e.g., "BTCUSDT".
    :return: Latest price as float.
    """
    data = _client._public_request("/api/v3/ticker/price", {"symbol": symbol})
    try:
        return float(data.get("price", 0.0))
    except (TypeError, ValueError):
        raise ValueError(f"Invalid price data returned for symbol {symbol}: {data}")


def get_price_at(symbol: str, timestamp: int) -> float:
    """
    Retrieve the historical closing price for a symbol at a given timestamp.

    :param symbol: Asset pair symbol, e.g., "ETHUSDT".
    :param timestamp: Millisecond epoch time.
    :return: Closing price for the 1-minute interval containing timestamp.
    :raises ValueError: if no data is found.
    """
    params = {
        "symbol": symbol,
        "interval": "1m",
        "startTime": timestamp,
        "limit": 1
    }
    data = _client._public_request("/api/v3/klines", params)
    if not data:
        raise ValueError(f"No kline data for {symbol} at {timestamp}")
    # Kline format: [openTime, open, high, low, close, ...]
    try:
        return float(data[0][4])
    except (IndexError, TypeError, ValueError):
        raise ValueError(f"Unexpected kline structure for {symbol} at {timestamp}: {data[0]}")
