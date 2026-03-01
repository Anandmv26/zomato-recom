"""
phase2_llm_engine/prompt_builder.py
-------------------------------------
Builds the structured prompt sent to the Groq LLM.

Token-optimized for Groq free tier (12k TPM):
  - Only essential fields are sent per candidate (name, cuisine, type, rating, cost, city)
  - Max 15 candidates after top-rating sort
  - Compact JSON (no indent)
  - Concise system prompt
"""

import json
from typing import Optional

# Max candidates sent to LLM — keeps total tokens under ~4k
MAX_CONTEXT_CANDIDATES = 15

# Only these fields are sent to the LLM (saves ~60% tokens per restaurant)
_LLM_FIELDS = ["name", "cuisine", "restaurant_type", "rating", "avg_cost_for_two", "city",
               "online_ordering", "table_booking"]


def _slim_candidate(c: dict) -> dict:
    """Extract only the fields the LLM needs to make a selection."""
    return {k: c.get(k, "N/A") for k in _LLM_FIELDS}


def _format_preferences(
    cuisines: Optional[list[str]],
    rest_types: Optional[list[str]],
    city: Optional[str],
    online_ordering: Optional[str],
    table_booking: Optional[str],
    min_cost: Optional[int],
    max_cost: Optional[int],
    min_rating: Optional[float],
) -> str:
    """Turn filter params into a concise summary for the LLM."""
    parts = []
    if city:
        parts.append(f"Location: {city}")
    if cuisines:
        parts.append(f"Cuisine: {', '.join(cuisines)}")
    if rest_types:
        parts.append(f"Type: {', '.join(rest_types)}")
    if online_ordering is not None:
        parts.append(f"Online order: {online_ordering}")
    if table_booking is not None:
        parts.append(f"Booking: {table_booking}")
    if min_cost is not None or max_cost is not None:
        lo = str(min_cost) if min_cost is not None else "0"
        hi = str(max_cost) if max_cost is not None else "any"
        parts.append(f"Budget: {lo}-{hi}")
    if min_rating is not None:
        parts.append(f"Min rating: {min_rating}")
    return "; ".join(parts) if parts else "Best overall"


def build_prompt(
    candidates: list[dict],
    cuisines: Optional[list[str]] = None,
    rest_types: Optional[list[str]] = None,
    city: Optional[str] = None,
    online_ordering: Optional[str] = None,
    table_booking: Optional[str] = None,
    min_cost: Optional[int] = None,
    max_cost: Optional[int] = None,
    min_rating: Optional[float] = None,
) -> tuple[str, str]:
    """
    Build the (system_prompt, user_prompt) tuple for the Groq chat API.

    Token budget: ~4k tokens total (fits in Groq free tier 12k TPM).
    - Candidates are trimmed to top-15 by rating
    - Only essential fields are included (no url, phone, etc.)
    - JSON is compact (no whitespace)
    """
    # Trim to top candidates by rating
    if len(candidates) > MAX_CONTEXT_CANDIDATES:
        candidates = sorted(
            candidates, key=lambda r: float(r.get("rating", 0)), reverse=True
        )[:MAX_CONTEXT_CANDIDATES]

    # Slim down each candidate to essential fields only
    slim = [_slim_candidate(c) for c in candidates]
    candidate_json = json.dumps(slim, ensure_ascii=False, separators=(",", ":"))

    preferences = _format_preferences(
        cuisines, rest_types, city,
        online_ordering, table_booking,
        min_cost, max_cost, min_rating,
    )

    system_prompt = (
        "You are a Zomato restaurant recommender. "
        "Pick up to 5 best restaurants from the candidates. "
        "Output ONLY a raw JSON array (no markdown). "
        "Each object must have: rank(1-5), name, cuisine, restaurant_type, "
        "rating, avg_cost_for_two, city, online_ordering, table_booking, llm_blurb. "
        "llm_blurb: 1 sentence why user will love it."
    )

    user_prompt = f"Preferences: {preferences}\nCandidates:\n{candidate_json}"

    return system_prompt, user_prompt
