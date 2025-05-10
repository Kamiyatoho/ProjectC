import React, { useState } from 'react';
import CryptoTable from './components/CryptoTable';
import PortfolioValueChart from './components/PortfolioValueChart';
import DistributionChart from './components/DistributionChart';
import MonthlyProfitChart from './components/MonthlyProfitChart';
import TaxInfo from './components/TaxInfo';

function App() {
  const [portfolio, setPortfolio] = useState([]);
  const [stats, setStats] = useState(null);
  const [taxes, setTaxes] = useState(null);
  const [dataLoaded, setDataLoaded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  // Fonction de synchronisation des données depuis le backend
  const handleSync = async () => {
    setLoading(true);
    setErrorMsg('');
    try {
      // Appel à l’endpoint de synchronisation
      const syncResp = await fetch('/api/sync', { method: 'POST' });
      if (!syncResp.ok) {
        throw new Error('Erreur lors de la synchronisation');
      }
      // Une fois la sync effectuée, récupérer les données pour mise à jour du state
      const [portfolioResp, statsResp, taxesResp] = await Promise.all([
        fetch('/api/portfolio'),
        fetch('/api/stats'),
        fetch('/api/taxes')
      ]);
      if (!portfolioResp.ok || !statsResp.ok || !taxesResp.ok) {
        throw new Error('Erreur lors de la récupération des données');
      }
      const portfolioData = await portfolioResp.json();
      const statsData = await statsResp.json();
      const taxesData = await taxesResp.json();
      setPortfolio(portfolioData);
      setStats(statsData);
      setTaxes(taxesData);
      setDataLoaded(true);
    } catch (error) {
      console.error('Sync error:', error);
      setErrorMsg("La synchronisation a échoué. Vérifiez la connexion API.");
    } finally {
      setLoading(false);
    }
  };

  return (
      <div className="App">
        <header>
          <h1>Suivi d’investissement Crypto</h1>
        </header>

        <div className="sync-section">
          <button onClick={handleSync} disabled={loading} className="sync-button">
            {loading ? 'Synchronisation...' : '🔄 Synchroniser'}
          </button>
          {errorMsg && <p className="error-msg">{errorMsg}</p>}
        </div>

        {dataLoaded ? (
            <>
              {/* Tableau du portefeuille par crypto */}
              <CryptoTable portfolio={portfolio} />

              {/* Section des graphiques */}
              <div className="charts-container">
                <PortfolioValueChart stats={stats} />
                <DistributionChart stats={stats} />
                <MonthlyProfitChart stats={stats} />
              </div>

              {/* Section information impôt */}
              <TaxInfo taxes={taxes} />
            </>
        ) : (
            <p className="hint">Cliquez sur « Synchroniser » pour charger les données de Binance.</p>
        )}
      </div>
  );
}

export default App;