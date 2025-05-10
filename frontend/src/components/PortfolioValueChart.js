import React from 'react';

function PortfolioValueChart({ stats }) {
    // Ici, stats.historique_valeur contient la valeur totale actuelle du portefeuille.
    // On peut étendre pour un historique temporel si disponible.
    const totalValue = stats && stats.historique_valeur ? stats.historique_valeur : 0;
    return (
        <div className="chart">
            <h3>Valeur du portefeuille</h3>
            <p style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>
                {totalValue.toFixed(2)} USD
            </p>
        </div>
    );
}

export default PortfolioValueChart;