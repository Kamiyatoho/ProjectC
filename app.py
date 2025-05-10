from flask import Flask
import os
from datetime import datetime
from routes.dashboard_routes import bp as dashboard_bp

app = Flask(__name__)
# Enregistrement du Blueprint définissant les routes du tableau de bord
app.register_blueprint(dashboard_bp)

# Configuration éventuelle (par exemple, clé secrète, etc.)
app.config['SECRET_KEY'] = os.getenv("BINANCE_API_SECRET")

@app.template_filter('datetimeformat')
def datetimeformat(value):
    """
    Filtre Jinja2 : transforme un timestamp (ms) en chaîne 'YYYY-MM-DD HH:MM:SS'
    """
    # Si la valeur est en millisecondes
    try:
        ts = int(value) / 1000.0
        dt = datetime.fromtimestamp(ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return value  # si erreur, renvoie la valeur brute


if __name__ == "__main__":
    # Lancement de l'application en mode développement (debug)
    app.run(debug=True)