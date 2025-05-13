from .pricing import get_price_at, get_current_price
from .utils import to_timestamp, from_timestamp


class PortfolioService:
    """
    High-level portfolio operations: deposits, withdrawals, value, P/L.
    """

    def __init__(self, client):
        """
        Initialize with a BinanceClient instance.
        """
        self.client = client

    def calculate_invested(self, deposits: list, year: int = None) -> float:
        invested = 0.0
        for dep in deposits:
            ts = dep.get('time', 0)
            dep_year = from_timestamp(ts).year
            if year is not None and dep_year != year:
                continue
            asset = dep.get('asset')
            amt   = float(dep.get('amount', 0))
            if asset in ["USDC", "BUSD", "EUR", "USD"]:
                invested += amt
            else:
                invested += get_price_at(f"{asset}USDT", ts) * amt
        return invested

    def get_portfolio_value(self, balances: list) -> float:
        """
        Calculate current total portfolio value in USDT equivalent.

        :param balances: List of dicts with keys 'asset', 'free', 'locked'.
        :return: Total current value.
        """
        total = 0.0
        for bal in balances:
            symbol = bal.get('asset')
            free = float(bal.get('free', 0))
            locked = float(bal.get('locked', 0))
            amt = free + locked
            if symbol in ["USDC", "BUSD", "EUR", "USD"]:
                total += amt
            else:
                total += get_current_price(f"{symbol}USDT") * amt
        return total

    def calculate_pl(self, deposits: list, balances: list, year: int) -> float:
        """
        Calculate profit or loss: current value minus invested for a given year.

        :param deposits: List of deposit dicts.
        :param balances: List of balance dicts.
        :param year: Year for P/L calculation.
        :return: Profit (positive) or loss (negative).
        """
        invested = self.calculate_invested(deposits, year)
        current_value = self.get_portfolio_value(balances)
        return current_value - invested
