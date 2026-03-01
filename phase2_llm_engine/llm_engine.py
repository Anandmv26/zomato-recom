"""
phase2_llm_engine/llm_engine.py
---------------------------------
Phase 2 — LLM Selection Engine

Entry point: `get_recommendations(candidates, filter_params)`

Flow:
  1. If 0 candidates → return [] immediately (no LLM call)
  2. Build prompt via prompt_builder (all candidates, no cap)
  3. Call Groq API (async, no timeout — Groq manages its own latency)
  4. Parse + validate JSON response
  5. Enforce top-5 cap and dedup
  6. Graceful degradation: raise LLMUnavailableError on failure so
     the API layer can return a clean HTTP error
"""

import json
import logging
import os
from typing import Optional

from dotenv import load_dotenv
from groq import AsyncGroq, APIStatusError, APITimeoutError, APIConnectionError

from phase2_llm_engine.prompt_builder import build_prompt

load_dotenv()  # loads .env from project root if present

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults (overridable via .env or function args)
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "llama-3.3-70b-versatile"


def _get_config():
    """Read config fresh from .env every call so hot-reload picks up changes."""
    load_dotenv(override=True)
    return os.getenv("GROQ_API_KEY", ""), os.getenv("GROQ_MODEL", DEFAULT_MODEL)

# Fields the LLM must return (url/phone are merged back from candidates)
REQUIRED_OUTPUT_FIELDS = {
    "rank", "name", "cuisine", "restaurant_type",
    "rating", "avg_cost_for_two", "city",
    "online_ordering", "table_booking", "llm_blurb",
}

# Full output fields (after enrichment from original candidates)
FULL_OUTPUT_FIELDS = REQUIRED_OUTPUT_FIELDS | {"zomato_url", "phone"}

MAX_RESULTS = 5


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class LLMUnavailableError(Exception):
    """Raised when Groq is unreachable or returns a bad response."""
    pass


class LLMResponseParseError(Exception):
    """Raised when the LLM response cannot be parsed as valid JSON."""
    pass


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_llm_response(raw_text: str) -> list[dict]:
    """
    Parse raw LLM text into a list of recommendation dicts.
    Handles edge cases: leading/trailing whitespace, accidental markdown fences.

    Raises:
        LLMResponseParseError: if the text is not valid JSON or not a list.
    """
    text = raw_text.strip()

    # Strip accidental markdown code fences (```json ... ```)
    if text.startswith("```"):
        lines = text.splitlines()
        inner = [l for l in lines if not l.startswith("```")]
        text = "\n".join(inner).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise LLMResponseParseError(f"LLM response is not valid JSON: {e}\nRaw: {raw_text[:300]}")

    if not isinstance(data, list):
        raise LLMResponseParseError(
            f"Expected a JSON array from LLM, got {type(data).__name__}. Raw: {raw_text[:300]}"
        )

    return data


def _validate_and_clean(recommendations: list[dict]) -> list[dict]:
    """
    Validate each recommendation against the required output schema.
    Drops items with missing required fields and enforces the top-5 cap.
    Re-assigns rank sequentially after any drops.
    """
    valid = []
    seen_names = set()

    for rec in recommendations:
        missing = REQUIRED_OUTPUT_FIELDS - rec.keys()
        if missing:
            logger.warning(f"Dropping recommendation missing fields {missing}: {rec.get('name', '?')}")
            continue

        # Deduplicate by name (secondary safety check)
        name = str(rec.get("name", "")).strip().lower()
        if name in seen_names:
            logger.warning(f"Dropping duplicate recommendation: {rec.get('name')}")
            continue
        seen_names.add(name)

        valid.append(rec)

        if len(valid) >= MAX_RESULTS:
            break

    # Re-assign rank sequentially after drops/dedup
    for i, rec in enumerate(valid, start=1):
        rec["rank"] = i

    return valid


def _enrich_from_candidates(
    validated: list[dict],
    candidates: list[dict],
) -> list[dict]:
    """
    Merge back fields that were stripped before sending to the LLM
    (zomato_url, phone) by matching on restaurant name.
    """
    # Build a lookup by lowercase name for O(1) matching
    lookup = {}
    for c in candidates:
        key = str(c.get("name", "")).strip().lower()
        if key and key not in lookup:
            lookup[key] = c

    for rec in validated:
        name_key = str(rec.get("name", "")).strip().lower()
        original = lookup.get(name_key, {})
        rec.setdefault("zomato_url", original.get("zomato_url", "N/A"))
        rec.setdefault("phone", original.get("phone", "N/A"))

    return validated


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_recommendations(
    candidates: list[dict],
    cuisines: Optional[list[str]] = None,
    rest_types: Optional[list[str]] = None,
    city: Optional[str] = None,
    online_ordering: Optional[str] = None,
    table_booking: Optional[str] = None,
    min_cost: Optional[int] = None,
    max_cost: Optional[int] = None,
    min_rating: Optional[float] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> list[dict]:
    """
    Main entry point for Phase 2.

    Takes the candidate pool from Phase 1 and returns up to 5 ranked
    restaurant recommendations with LLM-generated blurbs.

    All candidates are sent to the LLM in full — no artificial size cap.
    No client-side timeout is set; Groq handles its own latency.

    Args:
        candidates:    Pre-filtered list of restaurant dicts from Phase 1.
        cuisines/...:  User filter params — forwarded to prompt builder for context.
        api_key:       Override GROQ_API_KEY (useful for tests and direct calls).
        model:         Override GROQ_MODEL.

    Returns:
        List of up to 5 validated recommendation dicts.

    Raises:
        LLMUnavailableError:   If Groq API is unreachable or errors.
        LLMResponseParseError: If the LLM response cannot be parsed into valid JSON.
    """
    # --- Short-circuit: 0 candidates means no LLM call ---
    if not candidates:
        logger.info("0 candidates — skipping LLM call.")
        return []

    system_prompt, user_prompt = build_prompt(
        candidates=candidates,
        cuisines=cuisines,
        rest_types=rest_types,
        city=city,
        online_ordering=online_ordering,
        table_booking=table_booking,
        min_cost=min_cost,
        max_cost=max_cost,
        min_rating=min_rating,
    )

    env_key, env_model = _get_config()
    key = api_key or env_key
    mdl = model   or env_model

    if not key:
        raise LLMUnavailableError(
            "GROQ_API_KEY is not set. Add it to your .env file."
        )

    client = AsyncGroq(api_key=key)  # No timeout — Groq manages its own latency

    try:
        logger.info(f"Calling Groq model={mdl} with {len(candidates)} candidates...")
        response = await client.chat.completions.create(
            model=mdl,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=1024,   # 5 recs × ~150 tokens each
        )
    except APITimeoutError as e:
        raise LLMUnavailableError(f"Groq request timed out: {e}")
    except APIConnectionError as e:
        raise LLMUnavailableError(f"Groq connection error: {e}")
    except APIStatusError as e:
        raise LLMUnavailableError(f"Groq API error {e.status_code}: {e.message}")
    except Exception as e:
        raise LLMUnavailableError(f"Unexpected Groq error: {e}")

    raw_text = response.choices[0].message.content or ""
    logger.info(f"Groq response received ({len(raw_text)} chars).")

    recommendations = _parse_llm_response(raw_text)
    validated       = _validate_and_clean(recommendations)

    # Enrich with fields we stripped before sending to LLM (zomato_url, phone)
    enriched = _enrich_from_candidates(validated, candidates)

    logger.info(f"Returning {len(enriched)} recommendations.")
    return enriched
