import flask
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from services import binance_service

bp = Blueprint('dashboard', __name__, template_folder='../templates')

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
        flash("Synchronisation réussie !", "success")
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
    years = sorted({datetime.fromtimestamp(tx['time'] / 1000).year for tx in all_tx}, reverse=True)
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

    raw = binance_service.get_raw_data()
    raw_deposits = [tx for tx in raw.get('deposits', [])
                    if datetime.fromtimestamp(tx['time'] / 1000).year == year]
    raw_withdrawals = [tx for tx in raw.get('withdrawals', [])
                       if datetime.fromtimestamp(tx['time'] / 1000).year == year]

    # Conversion en USDC
    def to_usdc(tx):
        asset = tx.get('asset')
        amount = float(tx.get('amount', 0))
        ts = tx.get('time')
        if asset == 'USDC':
            return amount
        try:
            price = binance_service.get_price_at(asset, ts)
            return round(price * amount, 4)
        except:
            return 0.0

    # Total investis et retirés en USDC
    converted_deposits = [to_usdc(tx) for tx in raw_deposits]
    converted_withdrawals = [to_usdc(tx) for tx in raw_withdrawals]
    total_deposit = sum(converted_deposits)
    total_withdrawal = sum(converted_withdrawals)
    non_taxable = max(total_deposit - total_withdrawal, 0)
    current_value = binance_service.get_portfolio_data().get('valeur_actuelle', 0)
    tax_amount = round((total_withdrawal - total_deposit) * 0.30, 2) if total_withdrawal > total_deposit else 0

    # Data mensuelle
    months = [f"{m:02d}" for m in range(1, 13)]
    deposits_month = []
    withdrawals_month = []
    for m in range(1, 13):
        md = [to_usdc(tx) for tx in raw_deposits if datetime.fromtimestamp(tx['time'] / 1000).month == m]
        wd = [to_usdc(tx) for tx in raw_withdrawals if datetime.fromtimestamp(tx['time'] / 1000).month == m]
        deposits_month.append(sum(md))
        withdrawals_month.append(sum(wd))

    return flask.jsonify({
        'totalDeposit': round(total_deposit, 4),
        'nonTaxable': round(non_taxable, 4),
        'currentValue': round(current_value, 4),
        'tax': tax_amount,
        'months': months,
        'deposits': deposits_month,
        'withdrawals': withdrawals_month
    })