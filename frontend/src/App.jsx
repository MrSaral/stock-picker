import { useState, useEffect } from 'react'

const API_BASE = 'http://127.0.0.1:8000/api';

function App() {
  // Monitored Stocks State
  const [monitoredStocks, setMonitoredStocks] = useState([]);
  const [loadingStocks, setLoadingStocks] = useState(true);
  const [errorStocks, setErrorStocks] = useState(null);

  // Recommendations State
  const [recommendations, setRecommendations] = useState([]);
  const [loadingRecs, setLoadingRecs] = useState(true);
  const [errorRecs, setErrorRecs] = useState(null);

  // Add Stock Form State
  const [ticker, setTicker] = useState('');
  const [priceThreshold, setPriceThreshold] = useState('');
  const [alertCondition, setAlertCondition] = useState('none');
  const [cadenceDays, setCadenceDays] = useState(7);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);

  // Action States
  const [generating, setGenerating] = useState(false);
  const [checkingAlerts, setCheckingAlerts] = useState(false);
  const [alertResults, setAlertResults] = useState(null);

  // Fetch initial data
  useEffect(() => {
    fetchMonitoredStocks();
    fetchRecommendations();
  }, []);

  const fetchMonitoredStocks = async () => {
    setLoadingStocks(true);
    try {
      const res = await fetch(`${API_BASE}/monitored-stocks`);
      if (!res.ok) throw new Error('Failed to fetch monitored stocks');
      const data = await res.json();
      setMonitoredStocks(data);
      setErrorStocks(null);
    } catch (err) {
      setErrorStocks(err.message);
    } finally {
      setLoadingStocks(false);
    }
  };

  const fetchRecommendations = async () => {
    setLoadingRecs(true);
    try {
      const res = await fetch(`${API_BASE}/weekly-recommendations`);
      if (!res.ok) throw new Error('Failed to fetch recommendations');
      const data = await res.json();
      setRecommendations(data);
      setErrorRecs(null);
    } catch (err) {
      setErrorRecs(err.message);
    } finally {
      setLoadingRecs(false);
    }
  };

  const handleAddStock = async (e) => {
    e.preventDefault();
    if (!ticker) {
      setFormError('Ticker symbol is required');
      return;
    }

    setSubmitting(true);
    setFormError(null);

    const stockPayload = {
      ticker: ticker.trim().toUpperCase(),
      price_threshold: priceThreshold ? parseFloat(priceThreshold) : null,
      alert_condition: alertCondition,
      cadence_days: parseInt(cadenceDays, 10)
    };

    try {
      const res = await fetch(`${API_BASE}/monitored-stocks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(stockPayload),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to add stock');
      }

      setMonitoredStocks((prev) => [...prev, data]);
      // Reset form
      setTicker('');
      setPriceThreshold('');
      setAlertCondition('none');
      setCadenceDays(7);
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteStock = async (tickerToDelete) => {
    if (!window.confirm(`Stop monitoring ${tickerToDelete}?`)) return;

    try {
      const res = await fetch(`${API_BASE}/monitored-stocks/${tickerToDelete}`, {
        method: 'DELETE',
      });
      if (!res.ok) throw new Error('Failed to delete stock');

      setMonitoredStocks((prev) => prev.filter((s) => s.ticker !== tickerToDelete));
    } catch (err) {
      alert(err.message);
    }
  };

  const handleGenerateRecommendation = async () => {
    setGenerating(true);
    try {
      const res = await fetch(`${API_BASE}/weekly-recommendations/generate`, {
        method: 'POST',
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Failed to generate recommendation');
      }
      const newRec = await res.json();
      setRecommendations((prev) => [newRec, ...prev]);
    } catch (err) {
      alert(err.message);
    } finally {
      setGenerating(false);
    }
  };

  const handleCheckAlerts = async () => {
    setCheckingAlerts(true);
    setAlertResults(null);
    try {
      const res = await fetch(`${API_BASE}/test-alert-check`, {
        method: 'POST',
      });
      if (!res.ok) throw new Error('Failed to run alert check');
      const data = await res.json();
      setAlertResults(data);
      // Refresh list to show updated last notified dates
      fetchMonitoredStocks();
    } catch (err) {
      alert(err.message);
    } finally {
      setCheckingAlerts(false);
    }
  };

  const latestPick = recommendations[0];
  const historyPicks = recommendations.slice(1);

  return (
    <div className="app-container">
      {/* Header Section */}
      <header className="app-header">
        <div className="brand-section">
          <h1>Stock Picker</h1>
          <p>AI-driven weekly recommendations & manual price/cadence notifications</p>
        </div>
        <div className="header-actions">
          <button
            className="btn btn-secondary"
            onClick={handleCheckAlerts}
            disabled={checkingAlerts}
          >
            {checkingAlerts ? <span className="loader"></span> : '🔔 Test Alert Check'}
          </button>
          <button
            className="btn btn-primary"
            onClick={handleGenerateRecommendation}
            disabled={generating}
          >
            {generating ? <span className="loader"></span> : '✨ Generate Weekly Pick'}
          </button>
        </div>
      </header>

      {/* Alert Check Notification Panel */}
      {alertResults && (
        <div className="alert-notification-panel">
          <h4 className="alert-notification-title">
            🔔 Test Alert Scan Completed
          </h4>
          <p>
            Checked <strong>{alertResults.checked_count}</strong> stocks.
            Triggered <strong>{alertResults.triggered_count}</strong> alerts.
          </p>
          {alertResults.triggered_alerts.length > 0 ? (
            <ul className="triggered-list">
              {alertResults.triggered_alerts.map((alert, index) => (
                <li key={index}>
                  📢 <strong>{alert.ticker}</strong> ({alert.name}) is at{' '}
                  <strong>${alert.current_price}</strong>. Alert triggered because:{' '}
                  <em>{alert.reason}</em> (Mock email sent to inbox).
                </li>
              ))}
            </ul>
          ) : (
            <p style={{ margin: 0, fontStyle: 'italic', color: 'var(--text-secondary)' }}>
              No alert thresholds breached or cadence limits reached.
            </p>
          )}
        </div>
      )}

      {/* Grid Layout */}
      <div className="dashboard-grid">
        {/* Left Side: Weekly LLM Recommendation */}
        <section className="glass-card recommendation-card">
          <h2 className="card-title">
            <span>💡 Weekly LLM Recommendation</span>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              {latestPick ? `Week of ${latestPick.week_start_date}` : ''}
            </span>
          </h2>

          {loadingRecs ? (
            <div className="text-center" style={{ padding: '3rem' }}>
              <span className="loader"></span>
              <p style={{ marginTop: '1rem', color: 'var(--text-secondary)' }}>Analyzing market trends...</p>
            </div>
          ) : latestPick ? (
            <div>
              <div className="pick-header">
                <div className="pick-meta">
                  <span className={`pick-tag ${latestPick.criteria || 'underrated'}`}>
                    {(latestPick.criteria || 'underrated').replace('_', ' ')}
                  </span>
                  <span className="ticker-badge">{latestPick.ticker}</span>
                  <span className="company-name">{latestPick.name}</span>
                </div>
                <div className="price-container">
                  <div className="price-value">
                    ${latestPick.price ? latestPick.price.toFixed(2) : 'N/A'}
                  </div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    Price at recommendation
                  </div>
                </div>
              </div>

              <div className="reasoning-box">
                <strong>Analysis Details:</strong>
                <p style={{ marginTop: '0.5rem' }}>{latestPick.reasoning}</p>
              </div>

              {/* History Sub-section */}
              {historyPicks.length > 0 && (
                <div className="history-section">
                  <h3>Previous Picks</h3>
                  <div className="history-list">
                    {historyPicks.map((pick) => (
                      <div key={pick.id} className="history-item">
                        <div>
                          <span className="history-ticker">{pick.ticker}</span>
                          <span style={{ color: 'var(--text-muted)', marginLeft: '0.5rem' }}>
                            ({pick.name})
                          </span>
                        </div>
                        <div style={{ color: 'var(--text-secondary)' }}>
                          <strong>${pick.price?.toFixed(2)}</strong> on {pick.week_start_date}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="empty-state">
              No recommendations generated yet. Click "Generate Weekly Pick" in the top right to start evaluation!
            </div>
          )}
        </section>

        {/* Right Side: Manual Stock Monitor */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          {/* Add Stock Form */}
          <section className="glass-card">
            <h2 className="card-title">➕ Monitor New Stock</h2>
            <form onSubmit={handleAddStock}>
              <div className="form-group">
                <label htmlFor="ticker">Stock Ticker Symbol</label>
                <input
                  type="text"
                  id="ticker"
                  placeholder="e.g. AAPL, TSLA, NVDA"
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value)}
                  disabled={submitting}
                />
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="alertCondition">Condition</label>
                  <select
                    id="alertCondition"
                    value={alertCondition}
                    onChange={(e) => setAlertCondition(e.target.value)}
                    disabled={submitting}
                  >
                    <option value="none">No Price Alert</option>
                    <option value="above">Crosses Above</option>
                    <option value="below">Drops Below</option>
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor="priceThreshold">Target Price ($)</label>
                  <input
                    type="number"
                    id="priceThreshold"
                    step="0.01"
                    placeholder="e.g. 150.00"
                    value={priceThreshold}
                    onChange={(e) => setPriceThreshold(e.target.value)}
                    disabled={submitting || alertCondition === 'none'}
                  />
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="cadenceDays">Email Notification Cadence (Days)</label>
                <input
                  type="number"
                  id="cadenceDays"
                  min="0"
                  placeholder="e.g. 7"
                  value={cadenceDays}
                  onChange={(e) => setCadenceDays(e.target.value)}
                  disabled={submitting}
                />
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Notify every X days. Set to 0 to disable periodic alerts.
                </span>
              </div>

              {formError && (
                <p style={{ color: 'var(--danger)', fontSize: '0.85rem', margin: '0 0 1rem 0' }}>
                  ❌ {formError}
                </p>
              )}

              <button
                type="submit"
                className="btn btn-primary"
                style={{ width: '100%' }}
                disabled={submitting}
              >
                {submitting ? <span className="loader"></span> : 'Monitor Stock'}
              </button>
            </form>
          </section>

          {/* Monitored Stocks List */}
          <section className="glass-card">
            <h2 className="card-title">📋 Monitored Stocks</h2>
            {loadingStocks ? (
              <div className="text-center" style={{ padding: '2rem' }}>
                <span className="loader"></span>
              </div>
            ) : monitoredStocks.length > 0 ? (
              <div className="stock-list">
                {monitoredStocks.map((stock) => (
                  <div key={stock.ticker} className="stock-item">
                    <div className="stock-info">
                      <span className="stock-ticker">{stock.ticker}</span>
                      <span className="stock-name" title={stock.name}>
                        {stock.name && stock.name.length > 20
                          ? `${stock.name.substring(0, 17)}...`
                          : stock.name}
                      </span>
                    </div>

                    <div className="stock-price-block">
                      <span className="stock-price">
                        ${stock.current_price ? stock.current_price.toFixed(2) : 'N/A'}
                      </span>
                      {stock.daily_change_percent !== null && (
                        <span
                          className={`stock-change ${stock.daily_change_percent >= 0 ? 'change-up' : 'change-down'
                            }`}
                        >
                          {stock.daily_change_percent >= 0 ? '▲' : '▼'}{' '}
                          {Math.abs(stock.daily_change_percent).toFixed(2)}%
                        </span>
                      )}
                    </div>

                    <div className="stock-alert-config">
                      {stock.alert_condition !== 'none' && stock.price_threshold ? (
                        <span>
                          Alert if{' '}
                          <span className="alert-highlight">
                            {stock.alert_condition} ${stock.price_threshold.toFixed(2)}
                          </span>
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>No Price Alert</span>
                      )}
                      <span>
                        Cadence:{' '}
                        <strong>
                          {stock.cadence_days > 0 ? `${stock.cadence_days}d` : 'None'}
                        </strong>
                      </span>
                    </div>

                    <div className="stock-actions">
                      <button
                        className="btn btn-danger btn-sm"
                        onClick={() => handleDeleteStock(stock.ticker)}
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-state">
                Not monitoring any stocks yet. Add one above!
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}

export default App
