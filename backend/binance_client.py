import os
import time
from binance.client import Client
from binance.enums import KLINE_INTERVAL_1MINUTE

# Clés d'API Binance sécurisées via variables d'environnement
API_KEY = os.environ.get("BINANCE_API_KEY")
API_SECRET = os.environ.get("BINANCE_API_SECRET")
if not API_KEY or not API_SECRET:
    raise RuntimeError("Définissez BINANCE_API_KEY et BINANCE_API_SECRET dans vos variables d'environnement.")

# Initialisation du client Spot Binance
client = Client(API_KEY, API_SECRET)

# Récupérer et lister toutes les paires USDC disponibles
try:
    exchange_info = client.get_exchange_info()
    usdc_pairs = [s['symbol'] for s in exchange_info['symbols'] if 'USDC' in s['symbol']]
    print(f"[INFO] Paires USDC disponibles : {usdc_pairs}")
except Exception as e:
    print(f"[WARN] Échec récupération paires USDC : {e}")
    usdc_pairs = []

# Récupérer les soldes pour déterminer dynamiquement les paires à suivre
try:
    account_info = client.get_account()
    balances = {b['asset']: float(b['free']) for b in account_info.get('balances', []) if float(b['free']) > 0}
except Exception as e:
    print(f"[ERROR] Impossible de récupérer les soldes : {e}")
    balances = {}

# Construire la liste TRACKED_SYMBOLS = XXXUSDC pour chaque asset détenu dont la paire existe
TRACKED_SYMBOLS = []
for asset in balances:
    if asset in ('USDC', 'EUR', 'USD'):
        continue
    pair = f"{asset}USDC"
    if pair in usdc_pairs:
        TRACKED_SYMBOLS.append(pair)
print(f"[INFO] Paires suivies dynamiquement : {TRACKED_SYMBOLS}")


def fetch_binance_data():
    """
    Récupère :
    - Soldes actuels de chaque asset
    - Historique des dépôts crypto (coin deposits)
    - Historique des trades (achats/ventes) pour chaque paire suivie
    - Historique des conversions (Convert)
    - Prix historiques au moment des dépôts et prix actuels
    """
    data = {'balances': {}, 'transactions': [], 'prices': {}}

    # 1) Soldes du compte
    try:
        account = client.get_account()
        for b in account.get('balances', []):
            free = float(b.get('free', 0))
            if free > 0:
                data['balances'][b['asset']] = free
    except Exception as e:
        print(f"[ERROR] Récupération balances échouée : {e}")

    # 2) Historique des dépôts crypto (coin deposits)
    try:
        deposits = client.get_deposit_history()
        for d in deposits:
            asset = d.get('coin') or d.get('asset')
            amount = float(d.get('amount', 0))
            ts = d.get('insertTime') or d.get('time')
            pair = f"{asset}USDC"
            if amount > 0 and pair in TRACKED_SYMBOLS and d.get('status') == 1:
                try:
                    klines = client.get_historical_klines(
                        pair,
                        KLINE_INTERVAL_1MINUTE,
                        start_str=ts,
                        limit=1
                    )
                    price = float(klines[0][4]) if klines else 0.0
                except Exception as err:
                    print(f"[WARN] Prix historique non disponible pour {pair} : {err}")
                    price = 0.0
                data['transactions'].append({
                    'symbol': pair,
                    'isBuyer': True,
                    'qty': amount,
                    'price': price,
                    'quoteQty': round(price * amount, 8),
                    'commission': 0.0,
                    'commissionAsset': asset,
                    'time': ts,
                    'fromDeposit': True
                })
    except Exception as e:
        print(f"[WARN] Récupération dépôt échouée : {e}")

    # 3) Historique des trades pour chaque paire suivie
    for symbol in TRACKED_SYMBOLS:
        try:
            trades = client.get_my_trades(symbol=symbol)
        except Exception as e:
            print(f"[ERROR] get_my_trades({symbol}) : {e}")
            trades = []
        for t in trades:
            data['transactions'].append({
                'symbol': symbol,
                'isBuyer': t.get('isBuyer'),
                'qty': float(t.get('qty', 0)),
                'price': float(t.get('price', 0)),
                'quoteQty': float(t.get('quoteQty', 0)),
                'commission': float(t.get('commission', 0)),
                'commissionAsset': t.get('commissionAsset'),
                'time': t.get('time')
            })

    # 4) Historique des conversions (Convert)
    client = Client(API_KEY, API_SECRET)
now = int(time.time() * 1000)
params = {
    'startTime': now - 30 * 24 * 60 * 60 * 1000,
    'endTime':   now,
    'limit':     1000,
    'timestamp': now
}
resp = client.get_convert_trade_history(**params)

    client = Client(API_KEY, API_SECRET)

    now = int(time.time() * 1000)
    start_time = now - 30 * 24 * 60 * 60 * 1000  # 30 jours en ms

    # Appel à la méthode dédiée
    resp = client.get_convert_trade_flow(
        startTime=start_time,
        endTime=now,
        limit=1000
    )

    # Récupérer la liste et traiter les champs corrects
    trades_list = resp.get('list', [])

    for t in trades_list:
        to_asset      = t['toAsset']
        from_asset    = t['fromAsset']
        pair          = f"{to_asset}{from_asset}"
        if pair in TRACKED_SYMBOLS:
            to_amount    = float(t['toAmount'])
            from_amount  = float(t['fromAmount'])
            price        = float(t['ratio'])        # ratio = toAmount / fromAmount
            ts           = t['createTime']          # timestamp en ms
            data['transactions'].append({
                'symbol':           pair,
                'isBuyer':          True,
                'qty':              to_amount,
                'price':            price,
                'quoteQty':         from_amount,
                'commission':       0.0,
                'commissionAsset':  from_asset,
                'time':             ts,
                'isConvert':        True
            })


    # 5) Prix actuels (ticker) pour chaque asset suivi
    for symbol in TRACKED_SYMBOLS:
        asset = symbol.replace('USDC', '')
        try:
            ticker = client.get_symbol_ticker(symbol=symbol)
            data['prices'][asset] = float(ticker.get('price', 0))
        except Exception as e:
            print(f"[WARN] Ticker non disponible pour {symbol} : {e}")
            data['prices'][asset] = 0.0

    # 6) Prix des devises de base
    data['prices']['USD'] = 1.0
    data['prices']['EUR'] = 1.0

    return data