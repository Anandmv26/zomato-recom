import { useState, useEffect } from 'react';
import MultiSelect from './MultiSelect';

/**
 * FilterPanel — all options sourced from the API (no hardcoded values).
 *
 * Props:
 *   filtersData  — response from GET /filters
 *   onSubmit     — callback with the filter payload
 *   loading      — bool, disables submit while request in flight
 */
export default function FilterPanel({ filtersData, onSubmit, loading }) {
    const [city, setCity] = useState('');
    const [selectedCuisines, setCuisines] = useState([]);
    const [selectedTypes, setTypes] = useState([]);
    const [onlineOrdering, setOnlineOrder] = useState('');
    const [tableBooking, setTableBooking] = useState('');
    const [minCost, setMinCost] = useState('');
    const [maxCost, setMaxCost] = useState('');
    const [minRating, setMinRating] = useState(0);
    const [validationError, setValidation] = useState('');

    const costMax = filtersData?.cost_range?.max || 6000;
    const costMin = filtersData?.cost_range?.min || 0;

    useEffect(() => {
        if (filtersData) {
            setMinCost(filtersData.cost_range?.min ?? 0);
            setMaxCost(filtersData.cost_range?.max ?? 6000);
            setMinRating(filtersData.rating_range?.min ?? 0);
        }
    }, [filtersData]);

    function handleSubmit(e) {
        e.preventDefault();

        const hasFilter = city || selectedCuisines.length || selectedTypes.length ||
            onlineOrdering || tableBooking ||
            String(minCost) !== String(costMin) || String(maxCost) !== String(costMax) ||
            minRating > (filtersData?.rating_range?.min ?? 0);

        if (!hasFilter) {
            setValidation('Please select at least one filter before searching.');
            return;
        }
        setValidation('');

        const payload = {};
        if (city) payload.city = city;
        if (selectedCuisines.length) payload.cuisines = selectedCuisines;
        if (selectedTypes.length) payload.rest_types = selectedTypes;
        if (onlineOrdering) payload.online_ordering = onlineOrdering;
        if (tableBooking) payload.table_booking = tableBooking;
        if (String(minCost) !== String(costMin)) payload.min_cost = Number(minCost);
        if (String(maxCost) !== String(costMax)) payload.max_cost = Number(maxCost);
        if (minRating > (filtersData?.rating_range?.min ?? 0)) payload.min_rating = Number(minRating);

        onSubmit(payload);
    }

    if (!filtersData) {
        return (
            <aside className="filter-panel">
                <div className="filter-loading">
                    <span className="filter-loading-icon">⚙️</span>
                    <span>Loading filters…</span>
                </div>
            </aside>
        );
    }

    return (
        <aside className="filter-panel">
            <h2>🔎 Find Your Table</h2>

            <form onSubmit={handleSubmit} id="filter-form" aria-label="Restaurant filters">

                {validationError && (
                    <div className="filter-error" role="alert" id="filter-error" data-testid="filter-error">
                        {validationError}
                    </div>
                )}

                {/* City */}
                <div className="filter-group">
                    <label className="group-label" htmlFor="city-select">City / Location</label>
                    <select
                        id="city-select"
                        className="filter-select"
                        value={city}
                        onChange={e => { setCity(e.target.value); setValidation(''); }}
                    >
                        <option value="">Any city</option>
                        {filtersData.cities.map(c => (
                            <option key={c} value={c}>{c}</option>
                        ))}
                    </select>
                </div>

                {/* Cuisines — multiselect */}
                <div className="filter-group" data-testid="cuisine-filter">
                    <MultiSelect
                        id="cuisine-multiselect"
                        label="Cuisine Type"
                        options={filtersData.cuisines}
                        selected={selectedCuisines}
                        onChange={v => { setCuisines(v); setValidation(''); }}
                        placeholder="Any cuisine…"
                    />
                </div>

                {/* Restaurant Types — multiselect */}
                <div className="filter-group" data-testid="rest-type-filter">
                    <MultiSelect
                        id="resttype-multiselect"
                        label="Restaurant Type"
                        options={filtersData.rest_types}
                        selected={selectedTypes}
                        onChange={v => { setTypes(v); setValidation(''); }}
                        placeholder="Any type…"
                    />
                </div>

                {/* Online Ordering — toggle pills */}
                <div className="filter-group">
                    <span className="group-label">Online Ordering</span>
                    <div className="toggle-pill-group">
                        {[
                            { val: 'yes', label: '🛵 Available' },
                            { val: 'no', label: '🚶 Not needed' },
                        ].map(({ val, label }) => (
                            <button
                                key={val}
                                type="button"
                                id={`online-${val}`}
                                className={`toggle-pill ${onlineOrdering === val ? 'active' : ''}`}
                                onClick={() => { setOnlineOrder(prev => prev === val ? '' : val); setValidation(''); }}
                            >
                                {label}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Table Booking — toggle pills */}
                <div className="filter-group">
                    <span className="group-label">Table Booking</span>
                    <div className="toggle-pill-group">
                        {[
                            { val: 'yes', label: '📅 Required' },
                            { val: 'no', label: '🚪 Walk-in ok' },
                        ].map(({ val, label }) => (
                            <button
                                key={val}
                                type="button"
                                id={`booking-${val}`}
                                className={`toggle-pill ${tableBooking === val ? 'active' : ''}`}
                                onClick={() => { setTableBooking(prev => prev === val ? '' : val); setValidation(''); }}
                            >
                                {label}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Budget Range (Dual Handle) */}
                <div className="filter-group">
                    <span className="group-label">Budget for Two (Range)</span>

                    <div className="dual-range-group">
                        <div className="dual-range-track"></div>
                        <div
                            className="dual-range-highlight"
                            style={{
                                left: `${((minCost - costMin) / (costMax - costMin)) * 100}%`,
                                width: `${((maxCost - minCost) / (costMax - costMin)) * 100}%`
                            }}
                        ></div>
                        <div className="range-input-wrapper">
                            <input
                                type="range"
                                min={costMin} max={costMax} step={50}
                                value={minCost}
                                onChange={e => setMinCost(Math.min(Number(e.target.value), maxCost - 100))}
                                aria-label="Minimum budget"
                            />
                            <input
                                type="range"
                                min={costMin} max={costMax} step={50}
                                value={maxCost}
                                onChange={e => setMaxCost(Math.max(Number(e.target.value), minCost + 100))}
                                aria-label="Maximum budget"
                            />
                        </div>
                    </div>

                    <div className="range-values-row">
                        <div className="slider-col">
                            <span className="range-label-text">Min</span>
                            <span className="range-price-val">₹{minCost}</span>
                        </div>
                        <div className="slider-col" style={{ textAlign: 'right' }}>
                            <span className="range-label-text">Max</span>
                            <span className="range-price-val">₹{maxCost}</span>
                        </div>
                    </div>
                </div>

                {/* Min Rating */}
                <div className="filter-group">
                    <span className="group-label">Min Rating</span>
                    <div className="slider-row">
                        <input
                            type="range"
                            id="min-rating-slider"
                            className="filter-slider"
                            min={filtersData.rating_range?.min ?? 0}
                            max={filtersData.rating_range?.max ?? 5}
                            step={0.1}
                            value={minRating}
                            onChange={e => setMinRating(e.target.value)}
                            aria-label="Minimum rating"
                        />
                        <span className="slider-value">⭐ {Number(minRating).toFixed(1)}</span>
                    </div>
                </div>

                <button
                    type="submit"
                    id="find-restaurants-btn"
                    className="submit-btn"
                    disabled={loading}
                    aria-busy={loading}
                >
                    {loading ? '⏳ Finding…' : '🍴 Find Restaurants'}
                </button>

            </form>
        </aside>
    );
}
