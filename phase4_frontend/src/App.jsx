import { useState, useEffect } from 'react';
import './App.css';
import FilterPanel from './components/FilterPanel';
import ResultCard from './components/ResultCard';
import SkeletonCard from './components/SkeletonCard';
import FoodSpinner from './components/FoodSpinner';
import EmptyState from './components/EmptyState';
import { fetchFilters, fetchRecommendations } from './api';

export default function App() {
  const [filtersData, setFiltersData] = useState(null);
  const [filtersError, setFiltersError] = useState('');
  const [results, setResults] = useState(null);   // null = idle, [] = empty, [...] = found
  const [resultMsg, setResultMsg] = useState('');
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState('');

  // Load filter options on mount
  useEffect(() => {
    fetchFilters()
      .then(data => setFiltersData(data))
      .catch(() => setFiltersError('Could not load filters. Is the backend running?'));
  }, []);

  async function handleSubmit(payload) {
    setLoading(true);
    setApiError('');
    setResults(null);

    try {
      const data = await fetchRecommendations(payload);
      setResults(data.restaurants || []);
      setResultMsg(data.message || '');
    } catch (err) {
      setApiError(err.message || 'Something went wrong. Please try again.');
      setResults(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app-wrapper">

      {/* Hero Header */}
      <header className="hero-header">
        <span className="hero-emoji" aria-hidden="true">🍛</span>
        <h1 className="hero-title">
          Zomato<span>AI</span> Recommendations
        </h1>
        <p className="hero-subtitle">
          AI-powered picks tailored to your taste, location &amp; budget
        </p>
      </header>

      {/* Main layout */}
      <main className="main-content">

        {/* Filter Panel */}
        {filtersError ? (
          <div className="filter-panel" role="alert">
            <p style={{ color: '#ffb3b3' }}>⚠️ {filtersError}</p>
          </div>
        ) : (
          <FilterPanel
            filtersData={filtersData}
            onSubmit={handleSubmit}
            loading={loading}
          />
        )}

        {/* Results area */}
        <section className="results-area" aria-live="polite" aria-label="Restaurant recommendations">

          {/* API error */}
          {apiError && (
            <div className="filter-error" role="alert" data-testid="api-error">
              ⚠️ {apiError}
            </div>
          )}

          {/* Loading state */}
          {loading && (
            <>
              <FoodSpinner />
              {[1, 2, 3].map(i => <SkeletonCard key={i} />)}
            </>
          )}

          {/* Results header + cards */}
          {!loading && results !== null && results.length > 0 && (
            <>
              <div className="results-header" data-testid="results-summary">
                <strong>{resultMsg}</strong>
              </div>
              {results.map(r => (
                <ResultCard key={r.rank} restaurant={r} />
              ))}
            </>
          )}

          {/* Zero results */}
          {!loading && results !== null && results.length === 0 && (
            <EmptyState />
          )}

          {/* Idle placeholder */}
          {!loading && results === null && !apiError && (
            <div className="idle-placeholder" data-testid="idle-state">
              <span className="idle-icon" aria-hidden="true">🍽️</span>
              <p>Set your preferences and let our AI find the perfect restaurant for you.</p>
            </div>
          )}

        </section>
      </main>

    </div>
  );
}
