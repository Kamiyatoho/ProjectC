import os
import json
import flask
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file
from services import binance_service

bp = Blueprint('dashboard', __name__, template_folder='../templates')
CACHE_DIR = os.path.join('data', 'taxes_cache')

# utilitaire de calcul des données fiscales
def compute_tax_data(year, raw_data):
    # filtres
    raw_deposits = [tx for tx in raw_data.get('deposits', []) if datetime.fromtimestamp(tx['time']/1000).year == year]
    raw_withdrawals = [tx for tx in raw_data.get('withdrawals', []) if datetime.fromtimestamp(tx['time']/1000).year == year]
    # conversion en USDC
    def to_usdc(tx):
        asset = tx.get('asset')
        amount = float(tx.get('amount', 0))
        ts = tx.get('time')
        if asset == 'USDC': return amount
        try:
            price = binance_service.get_price_at(asset, ts)
            return round(price * amount, 4)
        except:
            return 0.0
    deposits_usdc = [to_usdc(tx) for tx in raw_deposits]
    withdrawals_usdc = [to_usdc(tx) for tx in raw_withdrawals]
    total_deposit = sum(deposits_usdc)
    total_withdrawal = sum(withdrawals_usdc)
    non_taxable = max(total_deposit - total_withdrawal, 0)
    current_value = binance_service.get_portfolio_data().get('valeur_actuelle', 0)
    tax_amount = round((total_withdrawal - total_deposit) * 0.30, 2) if total_withdrawal > total_deposit else 0
    months = [f"{m:02d}" for m in range(1,13)]
    deposits_month = [sum(to_usdc(tx) for tx in raw_deposits if datetime.fromtimestamp(tx['time']/1000).month == m) for m in range(1,13)]
    withdrawals_month = [sum(to_usdc(tx) for tx in raw_withdrawals if datetime.fromtimestamp(tx['time']/1000).month == m) for m in range(1,13)]
    return {
        'totalDeposit': round(total_deposit,4),
        'nonTaxable': round(non_taxable,4),
        'currentValue': round(current_value,4),
        'tax': tax_amount,
        'months': months,
        'deposits': deposits_month,
        'withdrawals': withdrawals_month
    }

@bp.route('/')
def dashboard():
    data = binance_service.get_portfolio_data()
    if not data or "valeur_actuelle" not in data:
        return render_template('dashboard.html', data=None)
    return render_template('dashboard.html', data=data)

@bp.route('/sync')
def sync():
    try:
        binance_service.sync_data()
        # Pré-génération du cache fiscal pour chaque année trouvée
        raw = binance_service.get_raw_data()
        years = sorted({datetime.fromtimestamp(tx['time']/1000).year for tx in raw.get('deposits', []) + raw.get('withdrawals', [])}, reverse=True)
        os.makedirs(CACHE_DIR, exist_ok=True)
        for year in years:
            data = compute_tax_data(year, raw)
            path = os.path.join(CACHE_DIR, f"{year}.json")
            with open(path, 'w') as f:
                json.dump(data, f)
        flash("Synchronisation et pré-calcul fiscal réussis !", "success")
    except Exception as e:
        flash(f"Erreur lors de la synchronisation : {e}", "danger")
    return redirect(url_for('dashboard.dashboard'))

@bp.route('/transactions')
def transactions():
    data = binance_service.get_raw_data()
    if not data or (not data.get("deposits") and not data.get("trades") and not data.get("conversions")):
        flash("Aucune donnée de transaction disponible. Veuillez synchroniser le portefeuille.", "info")
        return redirect(url_for('dashboard.dashboard'))
    return render_template('transactions.html', data=data)

@bp.route('/impots', methods=['GET', 'POST'])
def impots():
    raw = binance_service.get_raw_data()
    depots = raw.get('deposits', [])
    retraits = raw.get('withdrawals', [])
    all_tx = depots + retraits
    years = sorted({datetime.fromtimestamp(tx['time']/1000).year for tx in all_tx}, reverse=True)
    current_year = datetime.now().year
    if request.method == 'POST':
        try:
            current_year = int(request.form.get('year', current_year))
        except (TypeError, ValueError):
            pass
    if current_year not in years:
        years.insert(0, current_year)
    return render_template('taxes.html', years=years, current_year=current_year)

@bp.route('/api/taxes')
def api_taxes():
    try:
        year = int(request.args.get('year', datetime.now().year))
    except ValueError:
        year = datetime.now().year
    cache_file = os.path.join(CACHE_DIR, f"{year}.json")
    if os.path.exists(cache_file):
        return send_file(cache_file, mimetype='application/json')
    raw = binance_service.get_raw_data()
    return flask.jsonify(compute_tax_data(year, raw))

#route de test en avec des données en dur
@bp.route('/api/taxes-test')
def api_taxes_test():
    year = datetime.now().year
    cache_file = os.path.join(CACHE_DIR, f"{year}.json")
    if os.path.exists(cache_file):
        return send_file(cache_file, mimetype='application/json')
    data = {
        'totalDeposit': 1000.0,
        'nonTaxable': 500.0,
        'currentValue': 2000.0,
        'tax': 150.0,
        'months': ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12'],
        'deposits': [100, 200, 150, 50, 300, 100, 50, 200, 150, 100, 50, 200],
        'withdrawals': [50, 100, 150, 200, 250, 300, 350, 400, 450, 500, 550, 600]
    }
    with open(cache_file, 'w') as f:
        json.dump(data, f)
    return flask.jsonify(data)
