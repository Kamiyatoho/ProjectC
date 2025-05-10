import React from 'react';
import { Bar } from 'react-chartjs-2';

function MonthlyProfitChart({ stats }) {
    if (!stats || !stats.plus_values_mensuelles) {
        return <div className="chart"><h3>Plus-values mensuelles</h3><p>Aucune donnée</p></div>;
    }
    const labels = stats.plus_values_mensuelles.map(item => item.month);
    const values = stats.plus_values_mensuelles.map(item => item.profit.toFixed(2));
    const data = {
        labels: labels,
        datasets: [{
            label: 'Profit mensuel (USD)',
            data: values,
            backgroundColor: '#4caf50'
        }]
    };
    const options = {
        plugins: {
            legend: { display: false }
        },
        scales: {
            x: { title: { display: true, text: 'Mois' } },
            y: { title: { display: true, text: 'Plus-value (USD)' } }
        }
    };
    return (
        <div className="chart">
            <h3>Plus-values mensuelles</h3>
            <Bar data={data} options={options} redraw />
        </div>
    );
}

export default MonthlyProfitChart;