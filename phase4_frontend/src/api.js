// API base URL — default to /api for production/Vercel, or localhost:8000 for local dev
const BASE_URL = import.meta.env.VITE_API_URL || (window.location.hostname === 'localhost' ? 'http://localhost:8000' : '/api');

export async function fetchFilters() {
    const res = await fetch(`${BASE_URL}/filters`);
    if (!res.ok) throw new Error('Failed to load filters');
    return res.json();
}

export async function fetchRecommendations(filters) {
    const res = await fetch(`${BASE_URL}/recommend`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(filters),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Request failed');
    return data;
}
