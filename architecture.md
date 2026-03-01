# Zomato Restaurant Recommendation WebApp - Architecture Document

## 1. System Overview
**Stack:** Python (Backend), React (Frontend), Groq LLM, HuggingFace (`ManikaSaini/zomato-restaurant-recommendation`)

This application is an intelligent restaurant recommendation engine where **the LLM directly acts as the recommendation engine**. The system leverages dataset-driven dynamic filtering to narrow down options, and then delegates the final selection, ranking, and description generation entirely to the Groq LLM.

## 2. Core Components

### 2.1 Dataset & Intelligence Layer (Data Pipeline)
- **Lifecycle:** Preprocessed strictly once at application startup.
- **Data Source:** HuggingFace Dataset (`ManikaSaini/zomato-restaurant-recommendation`).
- **Processing Strategy:**
  - **Deduplication:** Uses composite key (name + location + phone).
  - **Normalization:** Format ratings (float), cost (integer), standardize casing, strip whitespaces.
  - **Null Handling:** Drop missing essential fields (name/location); fallback optional fields to "N/A".
- **State Management (Dataset Caching):** The dataset gracefully fits in memory for this application size. The optimal approach is to load, clean, and cache the complete dataset as an in-memory application state object (e.g., `app.state.df` in FastAPI) during server startup. This eliminates repetitive disk I/O, serving both the dropdown options and the filtered candidate pools instantly across concurrent requests.

### 2.2 Backend API (REST Layer)
- **Framework:** Python (e.g., FastAPI or Flask).
- **Endpoints:**
  - `GET /filters`: Serves dynamic dropdown and slider options extracted from the dataset during startup.
  - `POST /recommend`: Accepts user filters to return ranked matches.
- **Pre-filtering:**
  - Uses the chosen filters (which are strict dataset enums) to query the in-memory dataset, yielding a candidate pool of valid restaurants.
  - Resolves edge cases: If the candidate pool has 0 results, immediately return 0 results without calling the LLM.
- **LLM Recommendation Engine (Groq):**
  - Prompt Engineering: Injects the user's selected preferences and the candidate pool (or a manageable chunk of it) into the LLM context.
  - The LLM is instructed to:
    1. Select the top (up to 5) best-matching restaurants from the provided dataset context.
    2. Rank them appropriately based on the user's parameters.
    3. Generate the "Why you'll love this" blurbs for each selected restaurant.
    4. Conform strictly to the prescribed JSON output schema.
  - Features graceful degradation: If Groq API fails/times out, a traditional fallback ranking can be used or an error returned if strictly enforcing LLM recommendations.

### 2.3 Frontend Application
- **Framework:** React Single-Page Application (SPA).
- **Theme & UX:** Warm reds/oranges, food-themed micro-animations, responsive design (Mobile-first).
- **Components:**
  - **Dynamic Filter Panel:** Populated purely via `GET /filters` (no hardcoded dropdown enums allowed). Uses Sliders for rating/price, multi-selects for categories, checkboxes for booking/ordering.
  - **Result Cards:** Shows Rank, Name, Details, Badges (Booking/Online), external links, and the generated LLM Blurb based on the reviews.
  - **Loading State:** Food-themed spinner and Skeleton cards before results render (accounts for LLM generation time).
  - **Validation UI:** Inline friendly errors for 0-filter form submissions before triggering API.
- **Zero-Result State:** Clean, strict messaging ("No restaurants found matching your preferences") without alternative suggestions or relaxed filters.

## 3. Data Flow & Output Contract
**Output Schema Reference (JSON):**
```json
{
  "rank": 1,
  "name": "",
  "cuisine": "",
  "restaurant_type": "",
  "rating": 0.0,
  "avg_cost_for_two": 0,
  "city": "",
  "online_ordering": true,
  "table_booking": false,
  "zomato_url": "",
  "phone": "",
  "llm_blurb": "Why you'll love this place..."
}
```

## 4. Implementation Phases & Testing Strategy

*Development Approach:* The project is designed for **phase-wise, modular development**. Each phase represents an independently deployable module that can be developed and unit-tested in isolation using mock inputs, but integrated seamlessly via strict data contracts (like the JSON Output Schema). This ensures decoupled architecture while stacking functionality.

| Phase | Focus Area | Key Testing Strategies |
|-------|-----------|------------------------|
| **1** | Data Pipeline, Filter & Context Builder | Validate dataset preprocessing (dedup, dtypes); unit test in-memory candidate pool subsetting based on strict frontend filters (test 0-candidate edge cases). |
| **2** | LLM Selection Engine | Mock Groq service, validate LLM context window limits, assert strict JSON response conformity, confirm top 5 selection restraint. |
| **3** | REST API Layer | Contract/Schema tests, concurrent load testing, enforce 0-filter validation rejection. Seamlessly wires Phase 1 and 2 behind the HTTP endpoints. |
| **4** | Frontend UI | E2E Testing (Playwright), form logic flow, render states (skeletons, mobile layout, zero-results). Can be developed against mock JSON responses before API completion. |
| **5** | Polish & Resilience | In-memory query caching hit/miss tests, conversational state continuity (refine results), LLM failure fallbacks. |

## 5. Global Architecture Constraints
1. **Dynamic Options Only:** No hardcoded values for dropdowns on Frontend. Always source from the startup cached data via `GET /filters`.
2. **Performance:** Dataset is parsed, cleaned, and cached in a one-time startup operation.
3. **Strict Filter Validation:** The user *must* apply at least one filter; this is enforced securely on both Frontend forms and Backend API controllers.
4. **Absolute 0-Result Restraint:** If 0 matching candidate results occur, the system provides zero alternatives and no automatic filter relaxation, entirely bypassing the LLM.
