import React from 'react';

function TaxInfo({ taxes }) {
    if (!taxes) return null;
    const year = taxes.annee;
    const profit = taxes.plus_values_annee;
    const taxesEstimees = taxes.taxes_estimees;
    const profitLabel = profit >= 0 ? "Plus-values réalisées" : "Moins-values réalisées";
    return (
        <div className="tax-info">
            <h3>Bilan Fiscal {year}</h3>
            <p>{profitLabel} en {year} : <strong>{profit.toFixed(2)} USD</strong></p>
            <p>Impôt estimé (30%) : <strong>{taxesEstimees.toFixed(2)} USD</strong></p>
        </div>
    );
}

export default TaxInfo;