import os
import time
import hmac
import hashlib
from urllib.parse import urlencode
import requests


class BinanceClient:
    """
    Low-level Binance REST client for signed and unsigned requests.
    """
    BASE_URL = "https://api.binance.com"

    def __init__(self, api_key: str = None, api_secret: str = None, timeout: int = 10):
        """
        Initialize the client with API key/secret and request timeout.
        Keys default to environment variables BINANCE_API_KEY and BINANCE_API_SECRET.
        """
        self.api_key = api_key or os.getenv("BINANCE_API_KEY")
        self.api_secret = api_secret or os.getenv("BINANCE_API_SECRET")
        self.timeout = timeout

    def _signed_request(self, method: str, path: str, params: dict = None) -> dict:
        """
        Send a signed request to the Binance API (requires API key & secret).

        :param method: HTTP method ("GET", "POST", etc.)
        :param path: Endpoint path (e.g., "/api/v3/account").
        :param params: Query parameters.
        :return: Parsed JSON response.
        """
        if params is None:
            params = {}
        # Binance requires timestamp in ms
        params['timestamp'] = int(time.time() * 1000)
        # Build query string and sign it
        qs = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode('utf-8'), qs.encode('utf-8'), hashlib.sha256
        ).hexdigest()
        url = f"{self.BASE_URL}{path}?{qs}&signature={signature}"
        headers = {"X-MBX-APIKEY": self.api_key}
        response = requests.request(method, url, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _public_request(self, path: str, params: dict = None) -> dict:
        """
        Send a public (unsigned) request to the Binance API.

        :param path: Endpoint path (e.g., "/api/v3/ticker/price").
        :param params: Query parameters.
        :return: Parsed JSON response.
        """
        url = f"{self.BASE_URL}{path}"
        response = requests.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()