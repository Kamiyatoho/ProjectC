import os
from flask import Flask, jsonify
from binance_client import client, fetch_binance_data
from portfolio import calculate_portfolio

app = Flask(__name__)

# Stockage en mémoire des données du portefeuille et transactions
cached_portfolio = None
cached_stats = None
cached_taxes = None
cached_transactions = None

@app.route('/api/sync', methods=['POST'])
def sync_data():
    """Endpoint pour synchroniser les données depuis l'API Binance."""
    global cached_portfolio, cached_stats, cached_taxes, cached_transactions
    # Récupérer les données brutes de Binance (transactions, soldes, prix)
    data = fetch_binance_data()
    # Calculer le portefeuille à jour et les statistiques associées
    portfolio, stats, taxes = calculate_portfolio(data)
    # Mettre en cache les résultats
    cached_portfolio = portfolio
    cached_stats = stats
    cached_taxes = taxes
    cached_transactions = data['transactions']
    return jsonify({"status": "Synchronisation réussie", "portfolioCount": len(portfolio)}), 200

@app.route('/api/portfolio', methods=['GET'])
def get_portfolio():
    """Retourne le tableau de suivi par crypto."""
    if cached_portfolio is None:
        # Si pas encore synchronisé, on peut soit retourner vide, soit déclencher une sync auto
        return jsonify({"error": "Données non synchronisées. Veuillez utiliser /api/sync."}), 400
    return jsonify(cached_portfolio), 200

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Retourne les données pour les graphiques de performance."""
    if cached_stats is None:
        return jsonify({"error": "Données non synchronisées."}), 400
    return jsonify(cached_stats), 200

@app.route('/api/taxes', methods=['GET'])
def get_taxes():
    """Retourne les plus-values de l'année en cours et l'impôt estimé."""
    if cached_taxes is None:
        return jsonify({"error": "Données non synchronisées."}), 400
    return jsonify(cached_taxes), 200

@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    """Retourne la liste brute des transactions importées (fiat/crypto)."""
    if cached_transactions is None:
        return jsonify({"error": "Données non synchronisées."}), 400
    return jsonify(cached_transactions), 200

if __name__ == '__main__':
    # Lancer le serveur Flask en local (port 5000 par défaut)
    # Assurez-vous d'avoir configuré BINANCE_API_KEY et BINANCE_API_SECRET dans les variables d’environnement.
    app.run(debug=True)