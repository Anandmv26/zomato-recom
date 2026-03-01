"""
phase3_rest_api/tests/test_api.py
----------------------------------
Phase 3 — REST API integration tests

All tests run against the real FastAPI app using FastAPI's TestClient.
- pipeline.bootstrap() is mocked → no HuggingFace download
- app_state is populated manually with test data
- build_candidate_pool and get_recommendations are mocked per-test or per-class

Test classes:
  TestHealthEndpoint        — GET /health
  TestFiltersEndpoint       — GET /filters (schema, values, 503 when unloaded)
  TestRecommendValidation   — POST /recommend Pydantic + enum validation
  TestRecommendHappyPath    — POST /recommend successful flows (1, 3, 5 results)
  TestRecommendZeroResults  — POST /recommend with 0 candidate matches
  TestRecommendErrors       — LLM 503 / 500 error propagation
  TestResponseSchema        — contract tests on field presence and types
  TestConcurrentRequests    — concurrent load via asyncio + httpx.AsyncClient
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from phase3_rest_api.app import app
from phase1_data_pipeline.pipeline import app_state as _app_state
from phase2_llm_engine.llm_engine import LLMUnavailableError, LLMResponseParseError


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

_TEST_CITIES    = ["BTM", "Koramangala", "MG Road", "Brookfield"]
_TEST_CUISINES  = ["Continental", "Biryani", "South Indian", "North Indian"]
_TEST_REST_TYPES = ["Casual Dining", "Fine Dining", "Brewery", "Café"]

_MOCK_CANDIDATE = {
    "name": "Truffles", "cuisine": "Continental",
    "restaurant_type": "Casual Dining", "rating": 4.2,
    "avg_cost_for_two": 600, "city": "BTM",
    "online_ordering": "yes", "table_booking": "no",
    "zomato_url": "https://zomato.com/truffles", "phone": "9876543210",
}

_MOCK_RECOMMENDATION = {
    **_MOCK_CANDIDATE,
    "rank": 1,
    "llm_blurb": "Truffles is a continental gem — the perfect spot for a relaxed evening!",
}


def _make_recommendations(n: int) -> list[dict]:
    return [
        {**_MOCK_RECOMMENDATION, "rank": i + 1, "name": f"Restaurant {i + 1}"}
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def populated_app_state():
    """
    Populate the global AppState singleton with test data before each test.
    Resets to empty after each test so tests don't bleed into each other.
    """
    _app_state.is_loaded    = True
    _app_state.cuisines     = _TEST_CUISINES
    _app_state.rest_types   = _TEST_REST_TYPES
    _app_state.cities       = _TEST_CITIES
    _app_state.min_cost     = 100
    _app_state.max_cost     = 5000
    _app_state.min_rating   = 2.0
    _app_state.max_rating   = 5.0
    _app_state.df           = MagicMock()   # placeholder; filters only use app_state fields
    yield
    # Teardown
    _app_state.is_loaded  = False
    _app_state.cuisines   = []
    _app_state.rest_types = []
    _app_state.cities     = []
    _app_state.df         = None


@pytest.fixture
def client():
    """TestClient that skips the real lifespan bootstrap (already mocked via app_state fixture)."""
    with patch("phase3_rest_api.app.pipeline.bootstrap"):
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_returns_200(self, client):
        r = client.get("/health")
        assert r.status_code == 200

    def test_data_loaded_true(self, client):
        r = client.get("/health")
        assert r.json()["data_loaded"] is True

    def test_status_ok(self, client):
        r = client.get("/health")
        assert r.json()["status"] == "ok"

    def test_not_loaded_shows_false(self, client):
        _app_state.is_loaded = False
        r = client.get("/health")
        assert r.json()["data_loaded"] is False


# ---------------------------------------------------------------------------
# GET /filters
# ---------------------------------------------------------------------------

class TestFiltersEndpoint:
    def test_returns_200(self, client):
        r = client.get("/filters")
        assert r.status_code == 200

    def test_schema_has_all_required_keys(self, client):
        data = client.get("/filters").json()
        expected_keys = {
            "cuisines", "rest_types", "cities",
            "cost_range", "rating_range",
            "online_ordering_options", "table_booking_options",
        }
        assert expected_keys.issubset(data.keys())

    def test_cuisines_from_app_state(self, client):
        data = client.get("/filters").json()
        assert data["cuisines"] == _TEST_CUISINES

    def test_cities_from_app_state(self, client):
        data = client.get("/filters").json()
        assert data["cities"] == _TEST_CITIES

    def test_rest_types_from_app_state(self, client):
        data = client.get("/filters").json()
        assert data["rest_types"] == _TEST_REST_TYPES

    def test_cost_range_schema(self, client):
        data = client.get("/filters").json()
        assert "min" in data["cost_range"]
        assert "max" in data["cost_range"]
        assert data["cost_range"]["min"] <= data["cost_range"]["max"]

    def test_rating_range_schema(self, client):
        data = client.get("/filters").json()
        assert data["rating_range"]["min"] <= data["rating_range"]["max"]

    def test_online_ordering_options(self, client):
        data = client.get("/filters").json()
        assert set(data["online_ordering_options"]) == {"yes", "no"}

    def test_returns_503_when_not_loaded(self, client):
        _app_state.is_loaded = False
        r = client.get("/filters")
        assert r.status_code == 503


# ---------------------------------------------------------------------------
# POST /recommend — Pydantic + enum validation
# ---------------------------------------------------------------------------

class TestRecommendValidation:
    def test_no_filters_returns_422(self, client):
        r = client.post("/recommend", json={})
        assert r.status_code == 422

    def test_no_filters_error_message(self, client):
        r = client.post("/recommend", json={})
        body = r.json()
        detail_str = json.dumps(body["detail"])
        assert "filter" in detail_str.lower()

    def test_invalid_online_ordering_value(self, client):
        r = client.post("/recommend", json={"online_ordering": "maybe"})
        assert r.status_code == 422

    def test_invalid_table_booking_value(self, client):
        r = client.post("/recommend", json={"table_booking": "sometimes"})
        assert r.status_code == 422

    def test_negative_min_cost_rejected(self, client):
        r = client.post("/recommend", json={"min_cost": -100})
        assert r.status_code == 422

    def test_rating_above_5_rejected(self, client):
        r = client.post("/recommend", json={"min_rating": 5.5})
        assert r.status_code == 422

    def test_min_cost_greater_than_max_cost_rejected(self, client):
        r = client.post("/recommend", json={"min_cost": 2000, "max_cost": 500})
        assert r.status_code == 422

    def test_invalid_city_returns_422(self, client):
        with patch("phase3_rest_api.app.build_candidate_pool", return_value=[]):
            r = client.post("/recommend", json={"city": "NonexistentCity"})
        assert r.status_code == 422

    def test_invalid_cuisine_returns_422(self, client):
        with patch("phase3_rest_api.app.build_candidate_pool", return_value=[]):
            r = client.post("/recommend", json={"cuisines": ["MartianFood"]})
        assert r.status_code == 422

    def test_invalid_rest_type_returns_422(self, client):
        with patch("phase3_rest_api.app.build_candidate_pool", return_value=[]):
            r = client.post("/recommend", json={"rest_types": ["SpaceStation"]})
        assert r.status_code == 422

    def test_valid_city_passes_validation(self, client):
        with patch("phase3_rest_api.app.build_candidate_pool", return_value=[]):
            r = client.post("/recommend", json={"city": "BTM"})
        # 200 even though result is 0 (mocked build_candidate_pool)
        assert r.status_code == 200

    def test_case_insensitive_city_accepted(self, client):
        """City validation should be case-insensitive — 'btm' == 'BTM'."""
        with patch("phase3_rest_api.app.build_candidate_pool", return_value=[]):
            r = client.post("/recommend", json={"city": "btm"})
        assert r.status_code == 200

    def test_returns_503_when_not_loaded(self, client):
        _app_state.is_loaded = False
        r = client.post("/recommend", json={"city": "BTM"})
        assert r.status_code == 503


# ---------------------------------------------------------------------------
# POST /recommend — Happy Path
# ---------------------------------------------------------------------------

class TestRecommendHappyPath:
    def _post(self, client, body: dict):
        return client.post("/recommend", json=body)

    def test_single_result_singular_message(self, client):
        with patch("phase3_rest_api.app.build_candidate_pool", return_value=[_MOCK_CANDIDATE]), \
             patch("phase3_rest_api.app.get_recommendations", new_callable=AsyncMock,
                   return_value=_make_recommendations(1)):
            r = self._post(client, {"city": "BTM"})
        assert r.status_code == 200
        assert r.json()["count"] == 1
        assert "1 restaurant" in r.json()["message"]

    def test_multiple_results_plural_message(self, client):
        with patch("phase3_rest_api.app.build_candidate_pool", return_value=[_MOCK_CANDIDATE] * 3), \
             patch("phase3_rest_api.app.get_recommendations", new_callable=AsyncMock,
                   return_value=_make_recommendations(3)):
            r = self._post(client, {"city": "BTM"})
        assert r.status_code == 200
        assert r.json()["count"] == 3
        assert "3 restaurants" in r.json()["message"]

    def test_five_results_max(self, client):
        with patch("phase3_rest_api.app.build_candidate_pool", return_value=[_MOCK_CANDIDATE] * 5), \
             patch("phase3_rest_api.app.get_recommendations", new_callable=AsyncMock,
                   return_value=_make_recommendations(5)):
            r = self._post(client, {"city": "BTM"})
        assert r.status_code == 200
        assert r.json()["count"] == 5

    def test_restaurants_list_in_response(self, client):
        with patch("phase3_rest_api.app.build_candidate_pool", return_value=[_MOCK_CANDIDATE]), \
             patch("phase3_rest_api.app.get_recommendations", new_callable=AsyncMock,
                   return_value=_make_recommendations(1)):
            r = self._post(client, {"city": "BTM"})
        assert isinstance(r.json()["restaurants"], list)
        assert len(r.json()["restaurants"]) == 1

    def test_llm_blurb_present_in_results(self, client):
        with patch("phase3_rest_api.app.build_candidate_pool", return_value=[_MOCK_CANDIDATE]), \
             patch("phase3_rest_api.app.get_recommendations", new_callable=AsyncMock,
                   return_value=_make_recommendations(1)):
            r = self._post(client, {"city": "BTM"})
        rest = r.json()["restaurants"][0]
        assert "llm_blurb" in rest
        assert len(rest["llm_blurb"]) > 0

    def test_multiple_filters_combined(self, client):
        with patch("phase3_rest_api.app.build_candidate_pool", return_value=[_MOCK_CANDIDATE]), \
             patch("phase3_rest_api.app.get_recommendations", new_callable=AsyncMock,
                   return_value=_make_recommendations(1)):
            r = self._post(client, {
                "city": "BTM",
                "cuisines": ["Continental"],
                "online_ordering": "yes",
                "min_rating": 4.0,
            })
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# POST /recommend — Zero Results
# ---------------------------------------------------------------------------

class TestRecommendZeroResults:
    def test_zero_results_returns_200(self, client):
        with patch("phase3_rest_api.app.build_candidate_pool", return_value=[]):
            r = client.post("/recommend", json={"city": "BTM"})
        assert r.status_code == 200

    def test_zero_results_count_is_0(self, client):
        with patch("phase3_rest_api.app.build_candidate_pool", return_value=[]):
            r = client.post("/recommend", json={"city": "BTM"})
        assert r.json()["count"] == 0

    def test_zero_results_message(self, client):
        with patch("phase3_rest_api.app.build_candidate_pool", return_value=[]):
            r = client.post("/recommend", json={"city": "BTM"})
        assert "No restaurants found" in r.json()["message"]

    def test_zero_results_empty_list(self, client):
        with patch("phase3_rest_api.app.build_candidate_pool", return_value=[]):
            r = client.post("/recommend", json={"city": "BTM"})
        assert r.json()["restaurants"] == []

    def test_zero_results_no_llm_call(self, client):
        """When candidate pool is empty, get_recommendations must NOT be called."""
        with patch("phase3_rest_api.app.build_candidate_pool", return_value=[]), \
             patch("phase3_rest_api.app.get_recommendations", new_callable=AsyncMock) as mock_llm:
            client.post("/recommend", json={"city": "BTM"})
        mock_llm.assert_not_called()


# ---------------------------------------------------------------------------
# POST /recommend — Error Handling
# ---------------------------------------------------------------------------

class TestRecommendErrors:
    def test_llm_unavailable_returns_503(self, client):
        with patch("phase3_rest_api.app.build_candidate_pool", return_value=[_MOCK_CANDIDATE]), \
             patch("phase3_rest_api.app.get_recommendations", new_callable=AsyncMock,
                   side_effect=LLMUnavailableError("Groq is down")):
            r = client.post("/recommend", json={"city": "BTM"})
        assert r.status_code == 503

    def test_llm_unavailable_error_message(self, client):
        with patch("phase3_rest_api.app.build_candidate_pool", return_value=[_MOCK_CANDIDATE]), \
             patch("phase3_rest_api.app.get_recommendations", new_callable=AsyncMock,
                   side_effect=LLMUnavailableError("Groq is down")):
            r = client.post("/recommend", json={"city": "BTM"})
        assert "Groq is down" in r.json()["detail"]

    def test_llm_parse_error_returns_500(self, client):
        with patch("phase3_rest_api.app.build_candidate_pool", return_value=[_MOCK_CANDIDATE]), \
             patch("phase3_rest_api.app.get_recommendations", new_callable=AsyncMock,
                   side_effect=LLMResponseParseError("Bad JSON")):
            r = client.post("/recommend", json={"city": "BTM"})
        assert r.status_code == 500


# ---------------------------------------------------------------------------
# Response Schema Contract Tests
# ---------------------------------------------------------------------------

class TestResponseSchema:
    REQUIRED_RESTAURANT_FIELDS = {
        "rank", "name", "cuisine", "restaurant_type",
        "rating", "avg_cost_for_two", "city",
        "online_ordering", "table_booking",
        "zomato_url", "phone", "llm_blurb",
    }

    def test_recommend_response_schema(self, client):
        with patch("phase3_rest_api.app.build_candidate_pool", return_value=[_MOCK_CANDIDATE]), \
             patch("phase3_rest_api.app.get_recommendations", new_callable=AsyncMock,
                   return_value=_make_recommendations(2)):
            r = client.post("/recommend", json={"city": "BTM"})
        body = r.json()
        assert "count" in body
        assert "message" in body
        assert "restaurants" in body
        assert isinstance(body["count"], int)
        assert isinstance(body["message"], str)
        assert isinstance(body["restaurants"], list)

    def test_each_restaurant_has_required_fields(self, client):
        with patch("phase3_rest_api.app.build_candidate_pool", return_value=[_MOCK_CANDIDATE]), \
             patch("phase3_rest_api.app.get_recommendations", new_callable=AsyncMock,
                   return_value=_make_recommendations(2)):
            r = client.post("/recommend", json={"city": "BTM"})
        for rest in r.json()["restaurants"]:
            missing = self.REQUIRED_RESTAURANT_FIELDS - rest.keys()
            assert not missing, f"Missing fields: {missing}"

    def test_count_matches_restaurants_length(self, client):
        with patch("phase3_rest_api.app.build_candidate_pool", return_value=[_MOCK_CANDIDATE] * 3), \
             patch("phase3_rest_api.app.get_recommendations", new_callable=AsyncMock,
                   return_value=_make_recommendations(3)):
            r = client.post("/recommend", json={"city": "BTM"})
        body = r.json()
        assert body["count"] == len(body["restaurants"])

    def test_filters_response_schema(self, client):
        r = client.get("/filters")
        body = r.json()
        assert isinstance(body["cuisines"], list)
        assert isinstance(body["cities"], list)
        assert isinstance(body["rest_types"], list)
        assert isinstance(body["cost_range"]["min"], int)
        assert isinstance(body["cost_range"]["max"], int)


# ---------------------------------------------------------------------------
# Concurrent Request Test
# ---------------------------------------------------------------------------

class TestConcurrentRequests:
    @pytest.mark.asyncio
    async def test_concurrent_filter_requests(self):
        """GET /filters should handle multiple simultaneous requests correctly."""
        with patch("phase3_rest_api.app.pipeline.bootstrap"):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
                tasks = [ac.get("/filters") for _ in range(10)]
                responses = await asyncio.gather(*tasks)
        for r in responses:
            assert r.status_code == 200
            assert "cuisines" in r.json()

    @pytest.mark.asyncio
    async def test_concurrent_recommend_requests(self):
        """POST /recommend should handle multiple simultaneous requests."""
        with patch("phase3_rest_api.app.pipeline.bootstrap"), \
             patch("phase3_rest_api.app.build_candidate_pool", return_value=[_MOCK_CANDIDATE]), \
             patch("phase3_rest_api.app.get_recommendations", new_callable=AsyncMock,
                   return_value=_make_recommendations(1)):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
                tasks = [ac.post("/recommend", json={"city": "BTM"}) for _ in range(5)]
                responses = await asyncio.gather(*tasks)
        for r in responses:
            assert r.status_code == 200
            assert r.json()["count"] == 1
