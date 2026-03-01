"""
phase1_data_pipeline/tests/test_filter_engine.py
------------------------------------------------
Unit tests for Phase 1 — Filter & Context Builder (filter_engine.py)

All tests operate on a local synthetic DataFrame — no app_state/bootstrap needed.
The `df` parameter override in build_candidate_pool() enables full isolation.
"""

import pytest
import pandas as pd

from phase1_data_pipeline.filter_engine import build_candidate_pool, FilterParams
from phase1_data_pipeline.pipeline import (
    COL_NAME, COL_LOCATION, COL_PHONE, COL_RATING,
    COL_COST, COL_CUISINE, COL_REST_TYPE,
    COL_ONLINE_ORDER, COL_BOOK_TABLE, COL_URL,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_df():
    """
    Clean, already-preprocessed DataFrame (mimics post-pipeline state).
    Values are already normalized (lowercase yes/no, float rating, int cost, title-cased).
    """
    return pd.DataFrame({
        COL_NAME:         ["Truffles", "Meghana Foods", "Only Place", "Byg Brewski", "Vidyarthi Bhavan"],
        COL_LOCATION:     ["BTM", "Koramangala", "MG Road", "Brookfield", "Gandhi Bazaar"],
        COL_PHONE:        ["123", "456", "789", "111", "222"],
        COL_RATING:       [4.2, 3.8, 4.5, 4.3, 4.4],
        COL_COST:         [600, 1200, 700, 2000, 150],
        COL_CUISINE:      ["Continental, North Indian", "Biryani, Andhra", "Continental", "Craft Beer, Continental", "South Indian"],
        COL_REST_TYPE:    ["Casual Dining", "Casual Dining", "Fine Dining", "Brewery", "Casual Dining"],
        COL_ONLINE_ORDER: ["yes", "no", "yes", "no", "no"],
        COL_BOOK_TABLE:   ["no", "yes", "no", "yes", "no"],
        COL_URL:          ["url1", "url2", "url3", "url4", "url5"],
    })


# ---------------------------------------------------------------------------
# Tests: FilterParams — validation
# ---------------------------------------------------------------------------

class TestFilterParamsValidation:
    def test_empty_params_has_no_filter(self):
        params = FilterParams()
        assert not params.has_at_least_one_filter()

    def test_city_counts_as_filter(self):
        params = FilterParams(city="BTM")
        assert params.has_at_least_one_filter()

    def test_cuisine_counts_as_filter(self):
        params = FilterParams(cuisines=["Continental"])
        assert params.has_at_least_one_filter()

    def test_min_cost_counts_as_filter(self):
        params = FilterParams(min_cost=500)
        assert params.has_at_least_one_filter()

    def test_min_rating_counts_as_filter(self):
        params = FilterParams(min_rating=4.0)
        assert params.has_at_least_one_filter()

    def test_online_ordering_false_str_counts(self):
        params = FilterParams(online_ordering="no")
        assert params.has_at_least_one_filter()


# ---------------------------------------------------------------------------
# Tests: No-filter guard
# ---------------------------------------------------------------------------

class TestNoFilterGuard:
    def test_raises_value_error_on_empty_filters(self, sample_df):
        with pytest.raises(ValueError, match="At least one filter"):
            build_candidate_pool(FilterParams(), df=sample_df)


# ---------------------------------------------------------------------------
# Tests: City filter
# ---------------------------------------------------------------------------

class TestCityFilter:
    def test_exact_city_match(self, sample_df):
        results = build_candidate_pool(FilterParams(city="BTM"), df=sample_df)
        assert len(results) == 1
        assert results[0]["name"] == "Truffles"

    def test_city_case_insensitive(self, sample_df):
        results_lower = build_candidate_pool(FilterParams(city="btm"), df=sample_df)
        results_upper = build_candidate_pool(FilterParams(city="BTM"), df=sample_df)
        assert len(results_lower) == len(results_upper)

    def test_city_no_match_returns_empty(self, sample_df):
        results = build_candidate_pool(FilterParams(city="Mars"), df=sample_df)
        assert results == []


# ---------------------------------------------------------------------------
# Tests: Cuisine filter (multi-select)
# ---------------------------------------------------------------------------

class TestCuisineFilter:
    def test_single_cuisine_match(self, sample_df):
        results = build_candidate_pool(FilterParams(cuisines=["South Indian"]), df=sample_df)
        assert len(results) == 1
        assert results[0]["name"] == "Vidyarthi Bhavan"

    def test_multi_cuisine_match_any(self, sample_df):
        """Selecting multiple cuisines should return restaurants matching ANY of them."""
        results = build_candidate_pool(FilterParams(cuisines=["Biryani", "South Indian"]), df=sample_df)
        names = {r["name"] for r in results}
        assert "Meghana Foods" in names
        assert "Vidyarthi Bhavan" in names

    def test_cuisine_case_insensitive(self, sample_df):
        results_lower = build_candidate_pool(FilterParams(cuisines=["south indian"]), df=sample_df)
        results_title = build_candidate_pool(FilterParams(cuisines=["South Indian"]), df=sample_df)
        assert len(results_lower) == len(results_title)

    def test_nonexistent_cuisine_returns_empty(self, sample_df):
        results = build_candidate_pool(FilterParams(cuisines=["Martian"]), df=sample_df)
        assert results == []


# ---------------------------------------------------------------------------
# Tests: Restaurant type filter (multi-select)
# ---------------------------------------------------------------------------

class TestRestTypeFilter:
    def test_single_rest_type(self, sample_df):
        results = build_candidate_pool(FilterParams(rest_types=["Brewery"]), df=sample_df)
        assert len(results) == 1
        assert results[0]["name"] == "Byg Brewski"

    def test_multi_rest_type_match_any(self, sample_df):
        results = build_candidate_pool(FilterParams(rest_types=["Fine Dining", "Brewery"]), df=sample_df)
        names = {r["name"] for r in results}
        assert "Only Place" in names
        assert "Byg Brewski" in names


# ---------------------------------------------------------------------------
# Tests: Online ordering / table booking filters
# ---------------------------------------------------------------------------

class TestBooleanFilters:
    def test_online_ordering_yes(self, sample_df):
        results = build_candidate_pool(FilterParams(online_ordering="yes"), df=sample_df)
        assert all(r["online_ordering"] == "yes" for r in results)

    def test_online_ordering_no(self, sample_df):
        results = build_candidate_pool(FilterParams(online_ordering="no"), df=sample_df)
        assert all(r["online_ordering"] == "no" for r in results)

    def test_table_booking_yes(self, sample_df):
        results = build_candidate_pool(FilterParams(table_booking="yes"), df=sample_df)
        assert all(r["table_booking"] == "yes" for r in results)


# ---------------------------------------------------------------------------
# Tests: Cost range filter
# ---------------------------------------------------------------------------

class TestCostFilter:
    def test_min_cost_filter(self, sample_df):
        results = build_candidate_pool(FilterParams(min_cost=1000), df=sample_df)
        names = {r["name"] for r in results}
        assert "Meghana Foods" in names
        assert "Byg Brewski" in names
        assert "Truffles" not in names

    def test_max_cost_filter(self, sample_df):
        results = build_candidate_pool(FilterParams(max_cost=700), df=sample_df)
        names = {r["name"] for r in results}
        assert "Truffles" in names
        assert "Only Place" in names
        assert "Vidyarthi Bhavan" in names
        assert "Meghana Foods" not in names

    def test_cost_range_combined(self, sample_df):
        results = build_candidate_pool(FilterParams(min_cost=500, max_cost=800), df=sample_df)
        for r in results:
            cost = r["avg_cost_for_two"]
            if cost is not None:
                assert 500 <= cost <= 800


# ---------------------------------------------------------------------------
# Tests: Minimum rating filter
# ---------------------------------------------------------------------------

class TestRatingFilter:
    def test_min_rating_filters_correctly(self, sample_df):
        results = build_candidate_pool(FilterParams(min_rating=4.3), df=sample_df)
        names = {r["name"] for r in results}
        assert "Only Place" in names
        assert "Byg Brewski" in names
        assert "Vidyarthi Bhavan" in names
        assert "Truffles" not in names
        assert "Meghana Foods" not in names

    def test_very_high_rating_threshold_returns_empty(self, sample_df):
        results = build_candidate_pool(FilterParams(min_rating=5.0), df=sample_df)
        assert results == []


# ---------------------------------------------------------------------------
# Tests: Combined filters
# ---------------------------------------------------------------------------

class TestCombinedFilters:
    def test_cuisine_and_city_combined(self, sample_df):
        results = build_candidate_pool(
            FilterParams(cuisines=["Continental"], city="BTM"), df=sample_df
        )
        assert len(results) == 1
        assert results[0]["name"] == "Truffles"

    def test_online_and_rating_combined(self, sample_df):
        results = build_candidate_pool(
            FilterParams(online_ordering="yes", min_rating=4.0), df=sample_df
        )
        for r in results:
            assert r["online_ordering"] == "yes"
            if r["rating"] is not None:
                assert r["rating"] >= 4.0

    def test_all_filters_strict_returns_few(self, sample_df):
        """Very tight combined filters should yield exactly 1 result."""
        results = build_candidate_pool(
            FilterParams(
                city="BTM",
                cuisines=["Continental"],
                online_ordering="yes",
                min_rating=4.0,
            ),
            df=sample_df,
        )
        assert len(results) == 1
        assert results[0]["name"] == "Truffles"


# ---------------------------------------------------------------------------
# Tests: Output schema integrity
# ---------------------------------------------------------------------------

class TestOutputSchema:
    EXPECTED_KEYS = {
        "name", "cuisine", "restaurant_type", "rating",
        "avg_cost_for_two", "city", "online_ordering",
        "table_booking", "zomato_url", "phone",
    }

    def test_output_schema_keys(self, sample_df):
        results = build_candidate_pool(FilterParams(city="BTM"), df=sample_df)
        assert len(results) > 0
        for result in results:
            assert self.EXPECTED_KEYS.issubset(result.keys()), \
                f"Missing keys: {self.EXPECTED_KEYS - result.keys()}"

    def test_no_duplicate_names_in_results(self, sample_df):
        results = build_candidate_pool(FilterParams(min_rating=3.0), df=sample_df)
        names = [r["name"] for r in results]
        assert len(names) == len(set(names))

    def test_result_is_list(self, sample_df):
        results = build_candidate_pool(FilterParams(city="BTM"), df=sample_df)
        assert isinstance(results, list)

    def test_zero_result_returns_empty_list(self, sample_df):
        results = build_candidate_pool(FilterParams(city="Nonexistent"), df=sample_df)
        assert results == []
