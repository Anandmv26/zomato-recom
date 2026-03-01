"""
phase1_data_pipeline/filter_engine.py
--------------------------------------
Phase 1 — Filter & Context Builder

Responsibilities:
  - Accept user-supplied filters (already validated against dataset enums)
  - Query the in-memory DataFrame to produce a candidate pool
  - Return the candidate pool as a list of dicts (JSON-serializable)
  - Handle the 0-candidate edge case cleanly — no LLM is called in this case
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from phase1_data_pipeline.pipeline import (
    app_state,
    COL_NAME, COL_LOCATION, COL_PHONE, COL_RATING,
    COL_COST, COL_CUISINE, COL_REST_TYPE,
    COL_ONLINE_ORDER, COL_BOOK_TABLE, COL_URL,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Filter parameters dataclass — the contract between API layer and this module
# ---------------------------------------------------------------------------

@dataclass
class FilterParams:
    """
    All filter fields are optional. At least one must be set (enforced upstream).
    Multi-select fields are lists; single-select fields are plain strings.
    None means "not filtered on this field".
    """
    cuisines:        Optional[list[str]] = field(default=None)   # multi-select
    rest_types:      Optional[list[str]] = field(default=None)   # multi-select
    city:            Optional[str]       = field(default=None)   # single-select
    online_ordering: Optional[str]       = field(default=None)   # 'yes' | 'no' | None
    table_booking:   Optional[str]       = field(default=None)   # 'yes' | 'no' | None
    min_cost:        Optional[int]       = field(default=None)
    max_cost:        Optional[int]       = field(default=None)
    min_rating:      Optional[float]     = field(default=None)

    def has_at_least_one_filter(self) -> bool:
        return any([
            self.cuisines,
            self.rest_types,
            self.city,
            self.online_ordering is not None,
            self.table_booking is not None,
            self.min_cost is not None,
            self.max_cost is not None,
            self.min_rating is not None,
        ])


# ---------------------------------------------------------------------------
# Filter engine
# ---------------------------------------------------------------------------

def build_candidate_pool(params: FilterParams, df: Optional[pd.DataFrame] = None) -> list[dict]:
    """
    Apply the supplied FilterParams against the in-memory cached DataFrame,
    returning a list of matching restaurant dicts.

    Args:
        params: The validated filter parameters from the API layer.
        df:     Optional override DataFrame (for testing). Defaults to app_state.df.

    Returns:
        List of matching restaurant dicts (empty list if 0 matches).

    Raises:
        RuntimeError: If the data pipeline has not been bootstrapped yet.
        ValueError:   If no filter is active (enforced as a safeguard).
    """
    working_df = df if df is not None else app_state.df

    if working_df is None:
        raise RuntimeError(
            "Data pipeline not initialized. Call pipeline.bootstrap() first."
        )

    if not params.has_at_least_one_filter():
        raise ValueError("At least one filter must be provided.")

    mask = pd.Series([True] * len(working_df), index=working_df.index)

    # --- City filter (single-select, exact match) ---
    if params.city:
        mask &= working_df[COL_LOCATION].str.lower() == params.city.strip().lower()

    # --- Cuisine filter (multi-select — restaurant must match ANY selected cuisine) ---
    if params.cuisines:
        normalized = [c.strip().lower() for c in params.cuisines]
        mask &= working_df[COL_CUISINE].apply(
            lambda val: any(
                c in str(val).lower()
                for c in normalized
            ) if pd.notna(val) and val != "N/A" else False
        )

    # --- Restaurant type filter (multi-select — match ANY selected type) ---
    if params.rest_types:
        normalized = [r.strip().lower() for r in params.rest_types]
        mask &= working_df[COL_REST_TYPE].apply(
            lambda val: any(
                r in str(val).lower()
                for r in normalized
            ) if pd.notna(val) and val != "N/A" else False
        )

    # --- Online ordering filter ---
    if params.online_ordering is not None:
        mask &= working_df[COL_ONLINE_ORDER].str.lower() == params.online_ordering.lower()

    # --- Table booking filter ---
    if params.table_booking is not None:
        mask &= working_df[COL_BOOK_TABLE].str.lower() == params.table_booking.lower()

    # --- Cost range filter ---
    if params.min_cost is not None:
        mask &= working_df[COL_COST].fillna(-1) >= params.min_cost
    if params.max_cost is not None:
        mask &= working_df[COL_COST].fillna(-1) <= params.max_cost

    # --- Minimum rating filter ---
    if params.min_rating is not None:
        mask &= working_df[COL_RATING].fillna(-1.0) >= params.min_rating

    filtered = working_df[mask].copy()

    logger.info(f"Candidate pool: {len(filtered)} restaurants matched.")

    # Convert to list of dicts — only yield LLM-useful fields
    results = []
    for _, row in filtered.iterrows():
        results.append({
            "name":             row.get(COL_NAME,          "N/A"),
            "cuisine":          row.get(COL_CUISINE,       "N/A"),
            "restaurant_type":  row.get(COL_REST_TYPE,     "N/A"),
            "rating":           row.get(COL_RATING),
            "avg_cost_for_two": row.get(COL_COST),
            "city":             row.get(COL_LOCATION,      "N/A"),
            "online_ordering":  row.get(COL_ONLINE_ORDER,  "N/A"),
            "table_booking":    row.get(COL_BOOK_TABLE,    "N/A"),
            "zomato_url":       row.get(COL_URL,           "N/A"),
            "phone":            row.get(COL_PHONE,         "N/A"),
        })

    return results
