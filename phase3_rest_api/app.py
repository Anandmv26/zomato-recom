"""
phase3_rest_api/app.py
-----------------------
Phase 3 — FastAPI REST API Layer

Routes:
  GET  /health    — liveness probe
  GET  /filters   — returns all dynamic dropdown values from the dataset
  POST /recommend — accepts user filters, returns LLM-ranked recommendations

Integration:
  - On startup (lifespan), calls pipeline.bootstrap() → populates app_state
  - /filters reads from app_state (instant, no disk I/O)
  - /recommend → Phase 1 (build_candidate_pool) → Phase 2 (get_recommendations)
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from phase1_data_pipeline import pipeline
from phase1_data_pipeline.pipeline import app_state
from phase1_data_pipeline.filter_engine import build_candidate_pool, FilterParams
from phase2_llm_engine.llm_engine import (
    get_recommendations,
    LLMUnavailableError,
    LLMResponseParseError,
)
from phase3_rest_api.models import FilterRequest, FiltersResponse, RecommendResponse
from phase3_rest_api.validators import validate_filter_enums

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan — runs once at server startup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Bootstrap the data pipeline before the server starts accepting requests."""
    logger.info("Starting up: bootstrapping data pipeline...")
    pipeline.bootstrap()
    logger.info(f"Data pipeline ready — {len(app_state.df)} restaurants loaded.")
    yield
    logger.info("Shutting down.")


# ---------------------------------------------------------------------------
# App instance
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Zomato Restaurant Recommendation API",
    description=(
        "LLM-powered restaurant recommendations backed by the Zomato dataset. "
        "All filter options are dynamically sourced from the dataset via GET /filters."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow the React frontend (Phase 4) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Dependency — guard for unready state
# ---------------------------------------------------------------------------

def _require_loaded() -> None:
    """Raise 503 if the data pipeline hasn't been bootstrapped yet."""
    if not app_state.is_loaded:
        raise HTTPException(
            status_code=503,
            detail="Data pipeline not ready. Please try again shortly.",
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Meta"])
async def health():
    """Liveness probe — returns pipeline readiness status."""
    return {
        "status": "ok",
        "data_loaded": app_state.is_loaded,
        "restaurant_count": len(app_state.df) if app_state.df is not None else 0,
    }


@app.get("/filters", response_model=FiltersResponse, tags=["Filters"])
async def get_filters():
    """
    Returns all dynamic dropdown/slider values sourced from the cleaned dataset.
    The frontend must call this endpoint to populate filter UI — no hardcoded values.
    """
    _require_loaded()
    return FiltersResponse(
        cuisines=app_state.cuisines,
        rest_types=app_state.rest_types,
        cities=app_state.cities,
        cost_range={"min": app_state.min_cost, "max": app_state.max_cost},
        rating_range={"min": app_state.min_rating, "max": app_state.max_rating},
        online_ordering_options=["yes", "no"],
        table_booking_options=["yes", "no"],
    )


@app.post("/recommend", response_model=RecommendResponse, tags=["Recommend"])
async def recommend(req: FilterRequest):
    """
    Main recommendation endpoint.

    1. Validates filter enum values against dataset-sourced options.
    2. Builds a pre-filtered candidate pool (Phase 1).
    3. Passes candidates to the LLM for selection + blurb generation (Phase 2).
    4. Returns up to 5 ranked results.
    """
    _require_loaded()

    # Runtime enum validation (city / cuisines / rest_types vs. dataset values)
    enum_errors = validate_filter_enums(req, app_state)
    if enum_errors:
        raise HTTPException(status_code=422, detail=enum_errors)

    # Build FilterParams from request
    params = FilterParams(
        cuisines=req.cuisines,
        rest_types=req.rest_types,
        city=req.city,
        online_ordering=req.online_ordering,
        table_booking=req.table_booking,
        min_cost=req.min_cost,
        max_cost=req.max_cost,
        min_rating=req.min_rating,
    )

    # Phase 1: build candidate pool
    candidates = build_candidate_pool(params)

    # Short-circuit: 0 matches → no LLM call
    if not candidates:
        return RecommendResponse(
            count=0,
            message="No restaurants found matching your preferences.",
            restaurants=[],
        )

    # Phase 2: LLM selection + blurb generation
    try:
        recommendations = await get_recommendations(
            candidates=candidates,
            cuisines=req.cuisines,
            rest_types=req.rest_types,
            city=req.city,
            online_ordering=req.online_ordering,
            table_booking=req.table_booking,
            min_cost=req.min_cost,
            max_cost=req.max_cost,
            min_rating=req.min_rating,
        )
    except LLMUnavailableError as e:
        logger.error(f"LLM unavailable: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except LLMResponseParseError as e:
        logger.error(f"LLM response parse error: {e}")
        raise HTTPException(status_code=500, detail="LLM returned an unexpected response format.")

    count = len(recommendations)
    if count == 0:
        message = "No restaurants found matching your preferences."
    elif count == 1:
        message = "We found 1 restaurant matching your preferences."
    else:
        message = f"We found {count} restaurants matching your preferences."

    return RecommendResponse(
        count=count,
        message=message,
        restaurants=recommendations,
    )


# ---------------------------------------------------------------------------
# Global exception handler for unexpected errors
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception on {request.method} {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected server error occurred."},
    )
