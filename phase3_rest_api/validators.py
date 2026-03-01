"""
phase3_rest_api/validators.py
------------------------------
Dynamic enum validation against dataset-sourced values in AppState.

Static type validation (yes/no, numeric ranges) is done by Pydantic in models.py.
This module handles values that are only known at runtime (after bootstrap):
  - City must exist in app_state.cities
  - Each cuisine must exist in app_state.cuisines
  - Each rest_type must exist in app_state.rest_types

All comparisons are case-insensitive for a forgiving UX.
"""

from phase1_data_pipeline.pipeline import AppState
from phase3_rest_api.models import FilterRequest


def validate_filter_enums(req: FilterRequest, state: AppState) -> list[str]:
    """
    Check that all user-submitted dropdown values exist in the dataset-sourced
    enums stored in AppState.

    Args:
        req:   The validated FilterRequest (Pydantic has already run type checks).
        state: The in-memory AppState populated by pipeline.bootstrap().

    Returns:
        A list of human-readable error strings (empty if all valid).
    """
    errors: list[str] = []

    # Build lowercase sets for case-insensitive matching
    valid_cities    = {c.lower() for c in state.cities}
    valid_cuisines  = {c.lower() for c in state.cuisines}
    valid_rest_types = {r.lower() for r in state.rest_types}

    if req.city and req.city.lower() not in valid_cities:
        errors.append(
            f"Invalid city: '{req.city}'. "
            "Use GET /filters to see available cities."
        )

    if req.cuisines:
        invalid = [c for c in req.cuisines if c.lower() not in valid_cuisines]
        if invalid:
            errors.append(
                f"Invalid cuisine(s): {invalid}. "
                "Use GET /filters to see available cuisines."
            )

    if req.rest_types:
        invalid = [r for r in req.rest_types if r.lower() not in valid_rest_types]
        if invalid:
            errors.append(
                f"Invalid restaurant type(s): {invalid}. "
                "Use GET /filters to see available types."
            )

    return errors
