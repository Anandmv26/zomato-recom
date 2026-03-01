"""
phase3_rest_api/models.py
--------------------------
Pydantic request/response models for Phase 3 REST API.

All validation that can be done statically (types, ranges, required-one-of)
is encoded here using Pydantic v2.  Dynamic enum validation (values that come
from the dataset at runtime) lives in validators.py.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------

class FilterRequest(BaseModel):
    """Body of POST /recommend. At least one field must be non-None."""

    cuisines: Optional[list[str]] = Field(
        default=None,
        description="Multi-select cuisine types sourced from GET /filters."
    )
    rest_types: Optional[list[str]] = Field(
        default=None,
        description="Multi-select restaurant types sourced from GET /filters."
    )
    city: Optional[str] = Field(
        default=None,
        description="Single city/location sourced from GET /filters."
    )
    online_ordering: Optional[Literal["yes", "no"]] = Field(
        default=None,
        description="'yes' or 'no'. Omit to ignore this filter."
    )
    table_booking: Optional[Literal["yes", "no"]] = Field(
        default=None,
        description="'yes' or 'no'. Omit to ignore this filter."
    )
    min_cost: Optional[int] = Field(
        default=None, ge=0,
        description="Minimum average cost for two (₹)."
    )
    max_cost: Optional[int] = Field(
        default=None, ge=0,
        description="Maximum average cost for two (₹)."
    )
    min_rating: Optional[float] = Field(
        default=None, ge=0.0, le=5.0,
        description="Minimum restaurant rating (0.0–5.0)."
    )

    @model_validator(mode="after")
    def check_at_least_one_filter(self) -> "FilterRequest":
        has_filter = any([
            self.cuisines,
            self.rest_types,
            self.city,
            self.online_ordering is not None,
            self.table_booking is not None,
            self.min_cost is not None,
            self.max_cost is not None,
            self.min_rating is not None,
        ])
        if not has_filter:
            raise ValueError(
                "Please select at least one filter before searching."
            )
        return self

    @model_validator(mode="after")
    def check_cost_range(self) -> "FilterRequest":
        if (
            self.min_cost is not None
            and self.max_cost is not None
            and self.min_cost > self.max_cost
        ):
            raise ValueError(
                "min_cost must not be greater than max_cost."
            )
        return self


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class CostRange(BaseModel):
    min: int
    max: int


class RatingRange(BaseModel):
    min: float
    max: float


class FiltersResponse(BaseModel):
    """Response schema for GET /filters."""
    cuisines: list[str]
    rest_types: list[str]
    cities: list[str]
    cost_range: CostRange
    rating_range: RatingRange
    online_ordering_options: list[str]
    table_booking_options: list[str]


class RecommendResponse(BaseModel):
    """Response schema for POST /recommend."""
    count: int
    message: str
    restaurants: list[dict]
