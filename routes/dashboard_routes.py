import flask
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from services import binance_service

bp = Blueprint('dashboard', __name__, template_folder='../templates')

@bp.route('/')
def dashboard():
    # Page principale affichant le tableau de bord du portefeuille
    data = binance_service.get_portfolio_data()
    if not data or "valeur_actuelle" not in data:
        # Si aucune donnée n'a encore été synchronisée, on invite à le faire
        return render_template('dashboard.html', data=None)
    return render_template('dashboard.html', data=data)

@bp.route('/sync')
def sync():
    # Route pour lancer la synchronisation des données depuis Binance
    try:
        binance_service.sync_data()
        flash("Synchronisation réussie !", "success")
    except Exception as e:
        flash(f"Erreur lors de la synchronisation : {e}", "danger")
    return redirect(url_for('dashboard.dashboard'))

@bp.route('/transactions')
def transactions():
    # Page de détail des transactions (dépôts, trades, conversions)
    data = binance_service.get_raw_data()
    if not data or (not data.get("deposits") and not data.get("trades") and not data.get("conversions")):
        flash("Aucune donnée de transaction disponible. Veuillez synchroniser le portefeuille.", "info")
        return redirect(url_for('dashboard.dashboard'))
    return render_template('transactions.html', data=data)

@bp.route('/impots', methods=['GET', 'POST'])
def impots():
    # Page de calcul des impôts
    data = binance_service.get_raw_data()
    if not data or not data.get("deposits"):
        flash("Aucune donnée disponible. Veuillez synchroniser le portefeuille.", "info")
        return redirect(url_for('dashboard.dashboard'))

    result = None
    year = None

    if request.method == 'POST':
        try:
            year = int(request.form.get('year', 0))
        except ValueError:
            flash("Année invalide fournie.", "warning")
            return redirect(url_for('dashboard.impots'))

        invested_year = 0.0
        for dep in data.get('deposits', []):
            ts = dep.get('time', 0)
            dep_year = datetime.fromtimestamp(ts / 1000).year
            if dep_year == year:
                asset = dep.get('asset')
                amount = float(dep.get('amount', 0))
                if asset in ["USDC", "BUSD", "EUR", "USD"]:
                    invested_year += amount
                else:
                    price = binance_service.get_price_at(asset, ts)
                    invested_year += price * amount

        pf = binance_service.get_portfolio_data()
        total_value = pf.get("valeur_actuelle", 0)
        excess = max(total_value - invested_year, 0)
        tax = excess * 0.30

        result = {
            "year": year,
            "invested": invested_year,
            "capital_non_imposable": invested_year,
            "total_value": total_value,
            "excess": excess,
            "tax": tax
        }

    return render_template('impots.html', result=result, year=year)