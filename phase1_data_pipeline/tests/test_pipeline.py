"""
phase1_data_pipeline/tests/test_pipeline.py
--------------------------------------------
Unit tests for Phase 1 — Data Pipeline (pipeline.py)

Tests are fully self-contained: no network calls, no HuggingFace download.
A synthetic DataFrame mimicking the dataset schema is used throughout.
"""

import pytest
import pandas as pd

from phase1_data_pipeline.pipeline import (
    preprocess,
    extract_dropdown_maps,
    _normalize_rating,
    _normalize_cost,
    _normalize_yes_no,
    _split_and_collect,
    COL_NAME, COL_LOCATION, COL_PHONE, COL_RATING,
    COL_COST, COL_CUISINE, COL_REST_TYPE,
    COL_ONLINE_ORDER, COL_BOOK_TABLE, COL_URL,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def raw_df():
    """
    Synthetic raw DataFrame that mirrors the HuggingFace dataset structure,
    including messy/real-world values like rate strings, commas in cost, etc.
    """
    return pd.DataFrame({
        COL_NAME:         ["Truffles", "Truffles", "Meghana Foods", "Only Place", None, "Byg Brewski"],
        COL_LOCATION:     ["BTM", "BTM", "Koramangala", "MG Road", "Indiranagar", None],
        COL_PHONE:        ["123", "123", "456", "789", "000", "111"],
        COL_RATING:       ["4.2/5", "4.2/5", "3.8 ", "NEW", None, "4.1/5"],
        COL_COST:         ["600", "600", "1,200", "700", "500", "2,000"],
        COL_CUISINE:      ["continental, north indian", "continental, north indian", "biryani, andhra", "continental", "chinese", "craft beer, continental"],
        COL_REST_TYPE:    ["casual dining", "casual dining", "casual dining", "fine dining", "casual dining", "brewery"],
        COL_ONLINE_ORDER: ["Yes", "Yes", "No", "yes", "Yes", "No"],
        COL_BOOK_TABLE:   ["No", "No", "Yes", "No", "Yes", "Yes"],
        COL_URL:          ["url1", "url1", "url2", "url3", None, "url4"],
    })


# ---------------------------------------------------------------------------
# Tests: _normalize_rating
# ---------------------------------------------------------------------------

class TestNormalizeRating:
    def test_standard_fraction_string(self):
        assert _normalize_rating("4.2/5") == 4.2

    def test_bare_float_string(self):
        assert _normalize_rating("3.8 ") == 3.8

    def test_new_restaurant(self):
        assert _normalize_rating("NEW") is None

    def test_dash_value(self):
        assert _normalize_rating("-") is None

    def test_none_value(self):
        assert _normalize_rating(None) is None

    def test_nan_value(self):
        assert _normalize_rating(float("nan")) is None

    def test_too_new_to_rate(self):
        assert _normalize_rating("too new to rate") is None


# ---------------------------------------------------------------------------
# Tests: _normalize_cost
# ---------------------------------------------------------------------------

class TestNormalizeCost:
    def test_comma_formatted_cost(self):
        assert _normalize_cost("1,200") == 1200

    def test_plain_integer_string(self):
        assert _normalize_cost("600") == 600

    def test_none_value(self):
        assert _normalize_cost(None) is None

    def test_nan_value(self):
        assert _normalize_cost(float("nan")) is None

    def test_invalid_string(self):
        assert _normalize_cost("free") is None


# ---------------------------------------------------------------------------
# Tests: _normalize_yes_no
# ---------------------------------------------------------------------------

class TestNormalizeYesNo:
    def test_yes_titlecase(self):
        assert _normalize_yes_no("Yes") == "yes"

    def test_no_uppercase(self):
        assert _normalize_yes_no("NO") == "no"

    def test_none_value(self):
        assert _normalize_yes_no(None) is None

    def test_invalid_value(self):
        assert _normalize_yes_no("Maybe") is None


# ---------------------------------------------------------------------------
# Tests: _split_and_collect
# ---------------------------------------------------------------------------

class TestSplitAndCollect:
    def test_splits_and_titles(self):
        series = pd.Series(["north indian, chinese", "chinese, continental"])
        result = _split_and_collect(series)
        assert "Chinese" in result
        assert "North Indian" in result
        assert "Continental" in result

    def test_deduplication(self):
        series = pd.Series(["biryani", "biryani", "biryani"])
        result = _split_and_collect(series)
        assert result.count("Biryani") == 1

    def test_dropped_nans(self):
        series = pd.Series(["north indian", None, float("nan")])
        result = _split_and_collect(series)
        assert all(isinstance(v, str) for v in result)

    def test_sorted_output(self):
        series = pd.Series(["zucchini, apple"])
        result = _split_and_collect(series)
        assert result == sorted(result)


# ---------------------------------------------------------------------------
# Tests: preprocess
# ---------------------------------------------------------------------------

class TestPreprocess:
    def test_row_count_drops_required_nulls(self, raw_df):
        """Rows missing name or location must be dropped."""
        cleaned = preprocess(raw_df)
        assert cleaned[COL_NAME].isna().sum() == 0
        assert cleaned[COL_LOCATION].isna().sum() == 0

    def test_deduplication_on_composite_key(self, raw_df):
        """Truffles BTM 123 appears twice — only one should survive."""
        cleaned = preprocess(raw_df)
        truffle_rows = cleaned[cleaned[COL_NAME] == "Truffles"]
        assert len(truffle_rows) == 1

    def test_row_count_is_less_than_raw(self, raw_df):
        """Cleaned DF must have fewer rows than raw due to nulls + dedup."""
        cleaned = preprocess(raw_df)
        assert len(cleaned) < len(raw_df)

    def test_rating_dtype_is_float(self, raw_df):
        """After preprocessing, the rating column must be float (or None)."""
        cleaned = preprocess(raw_df)
        non_null_ratings = cleaned[COL_RATING].dropna()
        assert all(isinstance(v, float) for v in non_null_ratings)

    def test_cost_dtype_is_numeric(self, raw_df):
        """Cost column must be numeric after normalization."""
        cleaned = preprocess(raw_df)
        non_null_costs = cleaned[COL_COST].dropna()
        assert all(isinstance(v, (int, float)) for v in non_null_costs)

    def test_yes_no_normalized_to_lowercase(self, raw_df):
        cleaned = preprocess(raw_df)
        for val in cleaned[COL_ONLINE_ORDER].dropna():
            assert val in ("yes", "no")
        for val in cleaned[COL_BOOK_TABLE].dropna():
            assert val in ("yes", "no")

    def test_optional_url_filled_with_na(self, raw_df):
        """Optional string fields (URL) should have 'N/A' instead of None."""
        cleaned = preprocess(raw_df)
        assert cleaned[COL_URL].isna().sum() == 0
        assert "N/A" in cleaned[COL_URL].values or cleaned[COL_URL].notna().all()

    def test_cuisine_casing_standardized(self, raw_df):
        """Cuisines must be Title-Cased."""
        cleaned = preprocess(raw_df)
        for entry in cleaned[COL_CUISINE].dropna():
            if entry != "N/A":
                for part in entry.split(","):
                    assert part.strip() == part.strip().title(), f"Not title-cased: '{part}'"

    def test_whitespace_stripped(self):
        """Extra whitespace in name/location must be stripped."""
        df = pd.DataFrame({
            COL_NAME:         ["  Truffles  "],
            COL_LOCATION:     ["  BTM  "],
            COL_PHONE:        ["123"],
            COL_RATING:       ["4.1/5"],
            COL_COST:         ["600"],
            COL_CUISINE:      ["continental"],
            COL_REST_TYPE:    ["casual dining"],
            COL_ONLINE_ORDER: ["Yes"],
            COL_BOOK_TABLE:   ["No"],
            COL_URL:          ["url"],
        })
        cleaned = preprocess(df)
        assert cleaned[COL_NAME].iloc[0] == "Truffles"
        assert cleaned[COL_LOCATION].iloc[0] == "BTM"


# ---------------------------------------------------------------------------
# Tests: extract_dropdown_maps
# ---------------------------------------------------------------------------

class TestExtractDropdownMaps:
    @pytest.fixture
    def cleaned_df(self, raw_df):
        return preprocess(raw_df)

    def test_cuisines_list_is_populated(self, cleaned_df):
        maps = extract_dropdown_maps(cleaned_df)
        assert isinstance(maps["cuisines"], list)
        assert len(maps["cuisines"]) > 0

    def test_rest_types_list_is_populated(self, cleaned_df):
        maps = extract_dropdown_maps(cleaned_df)
        assert isinstance(maps["rest_types"], list)
        assert len(maps["rest_types"]) > 0

    def test_cities_list_is_populated(self, cleaned_df):
        maps = extract_dropdown_maps(cleaned_df)
        assert isinstance(maps["cities"], list)
        assert len(maps["cities"]) > 0

    def test_cost_range_is_valid(self, cleaned_df):
        maps = extract_dropdown_maps(cleaned_df)
        assert maps["cost_range"]["min"] <= maps["cost_range"]["max"]

    def test_rating_range_is_valid(self, cleaned_df):
        maps = extract_dropdown_maps(cleaned_df)
        assert maps["rating_range"]["min"] <= maps["rating_range"]["max"]

    def test_no_duplicates_in_cuisines(self, cleaned_df):
        maps = extract_dropdown_maps(cleaned_df)
        assert len(maps["cuisines"]) == len(set(maps["cuisines"]))

    def test_all_cities_from_dataset(self, cleaned_df):
        """Every city in the dropdown must exist in the actual dataset."""
        maps = extract_dropdown_maps(cleaned_df)
        actual_cities = set(cleaned_df[COL_LOCATION].dropna().unique())
        for city in maps["cities"]:
            assert city in actual_cities

    def test_online_ordering_options_present(self, cleaned_df):
        maps = extract_dropdown_maps(cleaned_df)
        assert set(maps["online_ordering_options"]) == {"yes", "no"}

    def test_table_booking_options_present(self, cleaned_df):
        maps = extract_dropdown_maps(cleaned_df)
        assert set(maps["table_booking_options"]) == {"yes", "no"}
