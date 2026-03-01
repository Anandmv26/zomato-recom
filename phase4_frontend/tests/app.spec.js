/**
 * phase4_frontend/tests/app.spec.js
 * ------------------------------------
 * Playwright E2E tests for the ZomatoAI frontend.
 *
 * All backend API calls are intercepted via page.route() — no real server needed.
 *
 * Test groups:
 *  1. Page Load          — title, hero, idle state
 *  2. Filters Loading    — filter panel populated from mocked /filters
 *  3. Filter Validation  — at-least-one-filter inline error
 *  4. Recommendation Flow — submit, loading state, result cards
 *  5. Zero Results       — empty state render
 *  6. API Error          — network error display
 *  7. Mobile Responsive  — layout on small viewport
 */

import { test, expect } from '@playwright/test';

// ---- Shared mock data --------------------------------------------------------

const MOCK_FILTERS = {
    cuisines: ['Continental', 'Biryani', 'South Indian', 'North Indian'],
    rest_types: ['Casual Dining', 'Fine Dining', 'Brewery'],
    cities: ['BTM', 'Koramangala', 'MG Road'],
    cost_range: { min: 100, max: 5000 },
    rating_range: { min: 2.0, max: 5.0 },
    online_ordering_options: ['yes', 'no'],
    table_booking_options: ['yes', 'no'],
};

const MOCK_RECOMMENDATIONS = [
    {
        rank: 1, name: 'Truffles', cuisine: 'Continental',
        restaurant_type: 'Casual Dining', rating: 4.2,
        avg_cost_for_two: 600, city: 'BTM',
        online_ordering: 'yes', table_booking: 'no',
        zomato_url: 'https://zomato.com/truffles', phone: '9876543210',
        llm_blurb: 'Truffles is an absolute delight for continental food lovers!',
    },
    {
        rank: 2, name: 'Meghana Foods', cuisine: 'Biryani',
        restaurant_type: 'Casual Dining', rating: 3.9,
        avg_cost_for_two: 500, city: 'Koramangala',
        online_ordering: 'no', table_booking: 'yes',
        zomato_url: 'https://zomato.com/meghana', phone: '9876543211',
        llm_blurb: 'The biryani here is legendary — a must-visit for rice lovers!',
    },
];

// ---- Helper: mock both API routes -------------------------------------------

async function mockAPIs(page, {
    filtersData = MOCK_FILTERS,
    recommendData = { count: 2, message: 'We found 2 restaurants matching your preferences.', restaurants: MOCK_RECOMMENDATIONS },
} = {}) {
    await page.route('**/filters', route =>
        route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(filtersData) })
    );
    await page.route('**/recommend', route =>
        route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(recommendData) })
    );
}

// =============================================================================
// 1. Page Load
// =============================================================================

test.describe('Page Load', () => {
    test('has correct page title', async ({ page }) => {
        await mockAPIs(page);
        await page.goto('/');
        await expect(page).toHaveTitle(/ZomatoAI/i);
    });

    test('displays hero heading', async ({ page }) => {
        await mockAPIs(page);
        await page.goto('/');
        await expect(page.getByRole('heading', { level: 1 })).toContainText('ZomatoAI');
    });

    test('shows idle placeholder on initial load', async ({ page }) => {
        await mockAPIs(page);
        await page.goto('/');
        await expect(page.getByTestId('idle-state')).toBeVisible();
    });

    test('does not show result cards on initial load', async ({ page }) => {
        await mockAPIs(page);
        await page.goto('/');
        await expect(page.getByTestId('result-card')).toHaveCount(0);
    });
});

// =============================================================================
// 2. Filters Loading
// =============================================================================

test.describe('Filters Loading', () => {
    test('filter panel is visible after load', async ({ page }) => {
        await mockAPIs(page);
        await page.goto('/');
        await expect(page.locator('.filter-panel')).toBeVisible();
    });

    test('city dropdown is populated from /filters', async ({ page }) => {
        await mockAPIs(page);
        await page.goto('/');
        const select = page.locator('#city-select');
        await expect(select).toBeVisible();
        const options = await select.locator('option').allTextContents();
        expect(options).toContain('BTM');
        expect(options).toContain('Koramangala');
    });

    test('cuisine checkboxes are rendered from /filters', async ({ page }) => {
        await mockAPIs(page);
        await page.goto('/');
        const cuisineSection = page.getByTestId('cuisine-filter');
        await expect(cuisineSection).toBeVisible();
        await expect(cuisineSection.getByRole('checkbox', { name: 'Continental' })).toBeVisible();
        await expect(cuisineSection.getByRole('checkbox', { name: 'Biryani' })).toBeVisible();
    });

    test('restaurant type checkboxes rendered from /filters', async ({ page }) => {
        await mockAPIs(page);
        await page.goto('/');
        const typeSection = page.getByTestId('rest-type-filter');
        await expect(typeSection.getByRole('checkbox', { name: 'Casual Dining' })).toBeVisible();
    });

    test('submit button is present', async ({ page }) => {
        await mockAPIs(page);
        await page.goto('/');
        await expect(page.locator('#find-restaurants-btn')).toBeVisible();
    });
});

// =============================================================================
// 3. Filter Validation — at-least-one-filter
// =============================================================================

test.describe('Filter Validation', () => {
    test('clicking submit with no filters shows inline error', async ({ page }) => {
        await mockAPIs(page);
        await page.goto('/');
        await page.locator('#find-restaurants-btn').click();
        await expect(page.getByTestId('filter-error')).toBeVisible();
    });

    test('inline error contains "filter" keyword', async ({ page }) => {
        await mockAPIs(page);
        await page.goto('/');
        await page.locator('#find-restaurants-btn').click();
        await expect(page.getByTestId('filter-error')).toContainText(/filter/i);
    });

    test('error disappears when user applies a filter and submits', async ({ page }) => {
        await mockAPIs(page);
        await page.goto('/');
        // Trigger error first
        await page.locator('#find-restaurants-btn').click();
        await expect(page.getByTestId('filter-error')).toBeVisible();
        // Now select a city and re-submit
        await page.locator('#city-select').selectOption('BTM');
        await page.locator('#find-restaurants-btn').click();
        // Error should be gone
        await expect(page.getByTestId('filter-error')).toHaveCount(0);
    });

    test('no API call is made when validation fails', async ({ page }) => {
        let apiCalled = false;
        await page.route('**/filters', route =>
            route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_FILTERS) })
        );
        await page.route('**/recommend', route => {
            apiCalled = true;
            route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ count: 0, message: '', restaurants: [] }) });
        });
        await page.goto('/');
        await page.locator('#find-restaurants-btn').click();
        expect(apiCalled).toBe(false);
    });
});

// =============================================================================
// 4. Recommendation Flow
// =============================================================================

test.describe('Recommendation Flow', () => {
    test('selecting a city and submitting shows result cards', async ({ page }) => {
        await mockAPIs(page);
        await page.goto('/');
        await page.locator('#city-select').selectOption('BTM');
        await page.locator('#find-restaurants-btn').click();
        await expect(page.getByTestId('result-card')).toHaveCount(2);
    });

    test('result card displays restaurant name', async ({ page }) => {
        await mockAPIs(page);
        await page.goto('/');
        await page.locator('#city-select').selectOption('BTM');
        await page.locator('#find-restaurants-btn').click();
        const cards = page.getByTestId('result-card');
        await expect(cards.first().getByRole('heading')).toContainText('Truffles');
        await expect(cards.nth(1).getByRole('heading')).toContainText('Meghana Foods');
    });

    test('result card shows LLM blurb', async ({ page }) => {
        await mockAPIs(page);
        await page.goto('/');
        await page.locator('#city-select').selectOption('BTM');
        await page.locator('#find-restaurants-btn').click();
        await expect(page.getByText(/absolute delight/i)).toBeVisible();
    });

    test('results summary message is shown', async ({ page }) => {
        await mockAPIs(page);
        await page.goto('/');
        await page.locator('#city-select').selectOption('BTM');
        await page.locator('#find-restaurants-btn').click();
        await expect(page.getByTestId('results-summary')).toContainText('We found');
    });

    test('selecting a cuisine checkbox and submitting works', async ({ page }) => {
        await mockAPIs(page);
        await page.goto('/');
        await page.getByRole('checkbox', { name: 'Continental' }).check();
        await page.locator('#find-restaurants-btn').click();
        await expect(page.getByTestId('result-card')).toHaveCount(2);
    });

    test('online ordering checkbox works', async ({ page }) => {
        await mockAPIs(page);
        await page.goto('/');
        await page.locator('#online-yes').check();
        await page.locator('#find-restaurants-btn').click();
        await expect(page.getByTestId('result-card')).toHaveCount(2);
    });

    test('Zomato link is present in result card', async ({ page }) => {
        await mockAPIs(page);
        await page.goto('/');
        await page.locator('#city-select').selectOption('BTM');
        await page.locator('#find-restaurants-btn').click();
        await expect(page.locator('#zomato-link-1')).toBeVisible();
        await expect(page.locator('#zomato-link-1')).toHaveAttribute('href', /zomato\.com/);
    });

    test('idle placeholder is hidden after submission', async ({ page }) => {
        await mockAPIs(page);
        await page.goto('/');
        await page.locator('#city-select').selectOption('BTM');
        await page.locator('#find-restaurants-btn').click();
        await expect(page.getByTestId('idle-state')).toHaveCount(0);
    });
});

// =============================================================================
// 5. Zero Results State
// =============================================================================

test.describe('Zero Results', () => {
    async function mockZero(page) {
        await page.route('**/filters', route =>
            route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_FILTERS) })
        );
        await page.route('**/recommend', route =>
            route.fulfill({
                status: 200, contentType: 'application/json',
                body: JSON.stringify({ count: 0, message: 'No restaurants found matching your preferences.', restaurants: [] }),
            })
        );
    }

    test('shows empty state when 0 results', async ({ page }) => {
        await mockZero(page);
        await page.goto('/');
        await page.locator('#city-select').selectOption('BTM');
        await page.locator('#find-restaurants-btn').click();
        await expect(page.getByTestId('empty-state')).toBeVisible();
    });

    test('zero results shows no restaurant cards', async ({ page }) => {
        await mockZero(page);
        await page.goto('/');
        await page.locator('#city-select').selectOption('BTM');
        await page.locator('#find-restaurants-btn').click();
        await expect(page.getByTestId('result-card')).toHaveCount(0);
    });

    test('empty state contains correct message', async ({ page }) => {
        await mockZero(page);
        await page.goto('/');
        await page.locator('#city-select').selectOption('BTM');
        await page.locator('#find-restaurants-btn').click();
        await expect(page.getByTestId('empty-state')).toContainText('No restaurants found matching your preferences');
    });
});

// =============================================================================
// 6. API Error Handling
// =============================================================================

test.describe('API Error Handling', () => {
    test('shows error message when recommend API fails', async ({ page }) => {
        await page.route('**/filters', route =>
            route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_FILTERS) })
        );
        await page.route('**/recommend', route =>
            route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'LLM unavailable' }) })
        );
        await page.goto('/');
        await page.locator('#city-select').selectOption('BTM');
        await page.locator('#find-restaurants-btn').click();
        await expect(page.getByTestId('api-error')).toBeVisible();
    });
});

// =============================================================================
// 7. Mobile Responsive
// =============================================================================

test.describe('Mobile Responsive', () => {
    test.use({ viewport: { width: 390, height: 844 } });

    test('page renders on mobile viewport', async ({ page }) => {
        await mockAPIs(page);
        await page.goto('/');
        await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    });

    test('filter panel is visible on mobile', async ({ page }) => {
        await mockAPIs(page);
        await page.goto('/');
        await expect(page.locator('.filter-panel')).toBeVisible();
    });

    test('submit button is tappable on mobile', async ({ page }) => {
        await mockAPIs(page);
        await page.goto('/');
        await expect(page.locator('#find-restaurants-btn')).toBeVisible();
        const btn = page.locator('#find-restaurants-btn');
        const box = await btn.boundingBox();
        expect(box.height).toBeGreaterThanOrEqual(40);  // min tap target
    });

    test('result cards render on mobile after search', async ({ page }) => {
        await mockAPIs(page);
        await page.goto('/');
        await page.locator('#city-select').selectOption('BTM');
        await page.locator('#find-restaurants-btn').click();
        await expect(page.getByTestId('result-card')).toHaveCount(2);
    });
});
