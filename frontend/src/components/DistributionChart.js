import React from 'react';
import { Pie } from 'react-chartjs-2';

function DistributionChart({ stats }) {
    if (!stats || !stats.distribution) {
        return <div className="chart"><h3>Répartition du portefeuille</h3><p>Aucune donnée</p></div>;
    }
    // Préparer les données pour le graphique en camembert
    const labels = stats.distribution.map(item => item.asset);
    const values = stats.distribution.map(item => item.value);
    const data = {
        labels: labels,
        datasets: [{
            data: values,
            backgroundColor: ['#36A2EB', '#FF6384', '#FFCE56', '#4BC0C0', '#9966FF', '#c9cbcf'], // couleurs distinctes
            hoverOffset: 4
        }]
    };
    const options = {
        plugins: {
            legend: { position: 'bottom' }
        }
    };
    return (
        <div className="chart">
            <h3>Répartition du portefeuille</h3>
            <Pie data={data} options={options} redraw />
        </div>
    );
}

export default DistributionChart;