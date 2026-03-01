// API base URL — default to /api for production/Vercel, or localhost:8000 for local dev
const BASE_URL = import.meta.env.VITE_API_URL || (window.location.hostname === 'localhost' ? 'http://localhost:8000' : '/api');

import filtersData from './data/filters.json';

export async function fetchFilters() {
    // Return static values from the local JSON file
    return filtersData;
}

export async function fetchRecommendations(filters) {
    const res = await fetch(`${BASE_URL}/recommend`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(filters),
    });
    const data = await res.json();
    if (!res.ok) {
        // Handle detail being a string or an array of strings (validation errors)
        const message = Array.isArray(data.detail) 
            ? data.detail.join('\n') 
            : (data.detail || 'Request failed');
        throw new Error(message);
    }
    return data;
}
