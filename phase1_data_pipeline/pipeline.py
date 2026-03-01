"""
phase1_data_pipeline/pipeline.py
---------------------------------
Phase 1 — Data Pipeline

Responsibilities:
  - Load the HuggingFace dataset once at startup
  - Preprocess: deduplicate, normalize dtypes, handle nulls
  - Cache cleaned DataFrame in memory
  - Extract and cache all unique dropdown/filter values
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd
from datasets import load_dataset

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Column name constants — single source of truth for the dataset schema
# ---------------------------------------------------------------------------
COL_NAME         = "name"
COL_LOCATION     = "location"
COL_PHONE        = "phone"
COL_RATING       = "rate"
COL_VOTES        = "votes"
COL_COST         = "approx_cost(for two people)"
COL_CUISINE      = "cuisines"
COL_REST_TYPE    = "rest_type"
COL_ONLINE_ORDER = "online_order"
COL_BOOK_TABLE   = "book_table"
COL_URL          = "url"

# Fields required to keep a row; rows missing these are dropped
REQUIRED_FIELDS = [COL_NAME, COL_LOCATION]

# Optional fields — filled with "N/A" if missing
OPTIONAL_FIELDS = [COL_PHONE, COL_URL, COL_CUISINE, COL_REST_TYPE]


# ---------------------------------------------------------------------------
# AppState — in-memory store shared across the application
# ---------------------------------------------------------------------------

@dataclass
class AppState:
    """Holds the cleaned DataFrame and all pre-extracted dropdown maps."""
    df: Optional[pd.DataFrame] = None
    cuisines: list[str] = field(default_factory=list)
    rest_types: list[str] = field(default_factory=list)
    cities: list[str] = field(default_factory=list)
    min_cost: int = 0
    max_cost: int = 10000
    min_rating: float = 0.0
    max_rating: float = 5.0
    is_loaded: bool = False


# Global singleton — all other modules import this object
app_state = AppState()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize_rating(val) -> Optional[float]:
    """Convert messy rating strings like '4.1/5' or '3.8 ' to float."""
    if pd.isna(val):
        return None
    s = str(val).strip().split("/")[0].strip()
    if s.lower() in ("new", "too new to rate", "-", ""):
        return None
    try:
        f = float(s)
        return round(f, 1)
    except ValueError:
        return None


def _normalize_cost(val) -> Optional[int]:
    """Convert cost strings like '1,200' to int."""
    if pd.isna(val):
        return None
    try:
        return int(str(val).replace(",", "").strip())
    except ValueError:
        return None


def _normalize_yes_no(val) -> Optional[str]:
    """Normalize Yes/No columns to lowercase 'yes'/'no'."""
    if pd.isna(val):
        return None
    cleaned = str(val).strip().lower()
    return cleaned if cleaned in ("yes", "no") else None


def _split_and_collect(series: pd.Series) -> list[str]:
    """
    For multi-value columns (e.g., 'North Indian, Chinese'),
    split on comma, strip, standardize casing, and return unique sorted list.
    """
    values = set()
    for entry in series.dropna():
        for item in str(entry).split(","):
            item = item.strip().title()
            if item:
                values.add(item)
    return sorted(values)


# ---------------------------------------------------------------------------
# Core pipeline functions
# ---------------------------------------------------------------------------

def load_raw_dataset(dataset_name: str = "ManikaSaini/zomato-restaurant-recommendation") -> pd.DataFrame:
    """Load raw HuggingFace dataset and return as a Pandas DataFrame."""
    logger.info(f"Loading dataset: {dataset_name}")
    ds = load_dataset(dataset_name, split="train")
    df = ds.to_pandas()
    logger.info(f"Raw dataset loaded: {len(df)} rows, {len(df.columns)} columns")
    return df


def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    """
    Full preprocessing pipeline:
    1. Drop rows missing required fields
    2. Strip whitespace across all string columns
    3. Normalize ratings, costs, yes/no fields
    4. Standardize casing for multi-value columns
    5. Fill optional string fields with 'N/A'
    6. Deduplicate on composite key (name + location + phone)
    """
    logger.info("Starting preprocessing...")
    original_count = len(df)

    # --- Step 1: Drop rows missing required fields ---
    df = df.dropna(subset=REQUIRED_FIELDS)
    logger.info(f"After dropping missing required fields: {len(df)} rows (dropped {original_count - len(df)})")

    # --- Step 2: Strip whitespace on object columns ---
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace({"nan": None, "None": None, "": None})

    # --- Step 3: Normalize rating ---
    df[COL_RATING] = df[COL_RATING].apply(_normalize_rating)

    # --- Step 4: Normalize cost ---
    df[COL_COST] = df[COL_COST].apply(_normalize_cost)

    # --- Step 5: Normalize yes/no fields ---
    df[COL_ONLINE_ORDER] = df[COL_ONLINE_ORDER].apply(_normalize_yes_no)
    df[COL_BOOK_TABLE]   = df[COL_BOOK_TABLE].apply(_normalize_yes_no)

    # --- Step 6: Standardize multi-value casing (cuisines, rest_type) ---
    for col in [COL_CUISINE, COL_REST_TYPE]:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda v: ", ".join(
                    item.strip().title() for item in str(v).split(",")
                ) if pd.notna(v) and v is not None else None
            )

    # --- Step 7: Fill optional string fields ---
    for col in OPTIONAL_FIELDS:
        if col in df.columns:
            df[col] = df[col].fillna("N/A").replace({None: "N/A"})

    # --- Step 8: Deduplicate on composite key ---
    pre_dedup = len(df)
    df = df.drop_duplicates(subset=[COL_NAME, COL_LOCATION, COL_PHONE], keep="first")
    logger.info(f"After deduplication: {len(df)} rows (dropped {pre_dedup - len(df)} duplicates)")

    df = df.reset_index(drop=True)
    logger.info("Preprocessing complete.")
    return df


def extract_dropdown_maps(df: pd.DataFrame) -> dict:
    """
    Extract all unique values for each dropdown/filter field.
    Returns a dict suitable for the GET /filters endpoint.
    """
    cuisines   = _split_and_collect(df[COL_CUISINE])
    rest_types = _split_and_collect(df[COL_REST_TYPE])
    cities     = sorted(df[COL_LOCATION].dropna().unique().tolist())

    # Cost range
    valid_costs = df[COL_COST].dropna()
    min_cost = int(valid_costs.min()) if not valid_costs.empty else 0
    max_cost = int(valid_costs.max()) if not valid_costs.empty else 10000

    # Rating range
    valid_ratings = df[COL_RATING].dropna()
    min_rating = float(valid_ratings.min()) if not valid_ratings.empty else 0.0
    max_rating = float(valid_ratings.max()) if not valid_ratings.empty else 5.0

    return {
        "cuisines":   cuisines,
        "rest_types": rest_types,
        "cities":     cities,
        "cost_range": {"min": min_cost, "max": max_cost},
        "rating_range": {"min": round(min_rating, 1), "max": round(max_rating, 1)},
        "online_ordering_options": ["yes", "no"],
        "table_booking_options":   ["yes", "no"],
    }


def bootstrap(dataset_name: str = "ManikaSaini/zomato-restaurant-recommendation") -> None:
    """
    One-time startup routine.
    Loads, preprocesses, and caches the dataset into `app_state`.
    Optimized for Serverless (Vercel) environments.
    """
    global app_state
    import os

    # Vercel fix: Ensure HuggingFace cache is in /tmp
    if os.environ.get("VERCEL"):
        os.environ["HF_HOME"] = "/tmp/huggingface"
        os.environ["XDG_CACHE_HOME"] = "/tmp/cache"

    logger.info(f"Bootstrapping data pipeline (Serverless Mode: {bool(os.environ.get('VERCEL'))})")
    
    raw_df = load_raw_dataset(dataset_name)

    # Vercel fix: Limit data size to 15k rows to avoid memory/timeout issues in serverless
    if os.environ.get("VERCEL") and len(raw_df) > 15000:
        logger.info("Vercel detected: Truncating dataset to 15,000 rows for stability.")
        raw_df = raw_df.sample(n=15000, random_state=42)

    clean_df = preprocess(raw_df)
    dropdown_maps = extract_dropdown_maps(clean_df)

    app_state.df         = clean_df
    app_state.cuisines   = dropdown_maps["cuisines"]
    app_state.rest_types = dropdown_maps["rest_types"]
    app_state.cities     = dropdown_maps["cities"]
    app_state.min_cost   = dropdown_maps["cost_range"]["min"]
    app_state.max_cost   = dropdown_maps["cost_range"]["max"]
    app_state.min_rating = dropdown_maps["rating_range"]["min"]
    app_state.max_rating = dropdown_maps["rating_range"]["max"]
    app_state.is_loaded  = True

    logger.info(
        f"AppState ready — {len(clean_df)} restaurants | "
        f"{len(app_state.cuisines)} cuisines | "
        f"{len(app_state.rest_types)} rest_types | "
        f"{len(app_state.cities)} cities"
    )
