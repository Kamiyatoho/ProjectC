from flask import Blueprint, render_template, redirect, url_for, flash
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
        flash(f"Erreur lors de la synchronisation : {e}", "error")
    return redirect(url_for('dashboard.dashboard'))

@bp.route('/transactions')
def transactions():
    # Page de détail des transactions (dépôts, trades, conversions)
    data = binance_service.get_raw_data()
    if not data or (not data.get("deposits") and not data.get("trades") and not data.get("conversions")):
        flash("Aucune donnée de transaction disponible. Veuillez synchroniser le portefeuille.", "info")
        return redirect(url_for('dashboard.dashboard'))
    return render_template('transactions.html', data=data)
