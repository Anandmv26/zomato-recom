"""
phase2_llm_engine/tests/test_prompt_builder.py
-----------------------------------------------
Unit tests for Phase 2 — Prompt Builder

All tests are synchronous and require no network/API calls.
"""

import json
import pytest

from phase2_llm_engine.prompt_builder import (
    build_prompt,
    _format_preferences,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_candidates():
    return [
        {
            "name": "Truffles", "cuisine": "Continental", "restaurant_type": "Casual Dining",
            "rating": 4.2, "avg_cost_for_two": 600, "city": "BTM",
            "online_ordering": "yes", "table_booking": "no",
            "zomato_url": "url1", "phone": "123",
        },
        {
            "name": "Meghana Foods", "cuisine": "Biryani, Andhra", "restaurant_type": "Casual Dining",
            "rating": 3.8, "avg_cost_for_two": 1200, "city": "Koramangala",
            "online_ordering": "no", "table_booking": "yes",
            "zomato_url": "url2", "phone": "456",
        },
        {
            "name": "Only Place", "cuisine": "Continental", "restaurant_type": "Fine Dining",
            "rating": 4.5, "avg_cost_for_two": 700, "city": "MG Road",
            "online_ordering": "yes", "table_booking": "no",
            "zomato_url": "url3", "phone": "789",
        },
    ]


# ---------------------------------------------------------------------------
# Tests: _format_preferences
# ---------------------------------------------------------------------------

class TestFormatPreferences:
    def test_all_none_returns_fallback(self):
        result = _format_preferences(None, None, None, None, None, None, None, None)
        assert "Best overall" in result

    def test_city_included(self):
        result = _format_preferences(None, None, "BTM", None, None, None, None, None)
        assert "BTM" in result

    def test_cuisines_joined(self):
        result = _format_preferences(["Continental", "Biryani"], None, None, None, None, None, None, None)
        assert "Continental" in result
        assert "Biryani" in result

    def test_budget_range_both_ends(self):
        result = _format_preferences(None, None, None, None, None, 500, 1500, None)
        assert "500" in result
        assert "1500" in result

    def test_budget_range_min_only(self):
        result = _format_preferences(None, None, None, None, None, 500, None, None)
        assert "500" in result
        assert "any" in result.lower()

    def test_online_ordering_yes(self):
        result = _format_preferences(None, None, None, "yes", None, None, None, None)
        assert "yes" in result.lower() or "online" in result.lower()

    def test_online_ordering_no(self):
        result = _format_preferences(None, None, None, "no", None, None, None, None)
        assert "no" in result.lower() or "online" in result.lower()

    def test_table_booking_yes(self):
        result = _format_preferences(None, None, None, None, "yes", None, None, None)
        assert "yes" in result.lower() or "booking" in result.lower()

    def test_min_rating_included(self):
        result = _format_preferences(None, None, None, None, None, None, None, 4.2)
        assert "4.2" in result





# ---------------------------------------------------------------------------
# Tests: build_prompt
# ---------------------------------------------------------------------------

class TestBuildPrompt:
    def test_returns_tuple_of_two_strings(self, sample_candidates):
        sys_p, usr_p = build_prompt(sample_candidates)
        assert isinstance(sys_p, str)
        assert isinstance(usr_p, str)

    def test_candidate_names_in_user_prompt(self, sample_candidates):
        _, usr_p = build_prompt(sample_candidates)
        assert "Truffles" in usr_p
        assert "Meghana Foods" in usr_p

    def test_system_prompt_mentions_json_array(self, sample_candidates):
        sys_p, _ = build_prompt(sample_candidates)
        assert "JSON array" in sys_p or "json" in sys_p.lower()

    def test_system_prompt_mentions_top_5(self, sample_candidates):
        sys_p, _ = build_prompt(sample_candidates)
        assert "5" in sys_p

    def test_system_prompt_mentions_llm_blurb(self, sample_candidates):
        sys_p, _ = build_prompt(sample_candidates)
        assert "llm_blurb" in sys_p

    def test_city_preference_in_user_prompt(self, sample_candidates):
        _, usr_p = build_prompt(sample_candidates, city="BTM")
        assert "BTM" in usr_p

    def test_user_prompt_candidate_count_label(self, sample_candidates):
        _, usr_p = build_prompt(sample_candidates)
        # The prompt should say how many candidates are provided
        assert "3 provided" in usr_p or "3" in usr_p

    def test_all_candidates_present_in_prompt(self, sample_candidates):
        """All candidates (no trimming) must appear in the user prompt."""
        _, usr_p = build_prompt(sample_candidates)
        assert "Truffles" in usr_p
        assert "Meghana Foods" in usr_p
        assert "Only Place" in usr_p

    def test_candidate_json_is_valid_json_in_prompt(self, sample_candidates):
        """The candidate list embedded in the user prompt must be valid JSON."""
        _, usr_p = build_prompt(sample_candidates)
        # The candidate JSON block starts after the label line
        start = usr_p.index("[")
        end   = usr_p.rindex("]") + 1
        embedded = usr_p[start:end]
        parsed = json.loads(embedded)
        assert isinstance(parsed, list)
