"""
phase2_llm_engine/tests/test_llm_engine.py
-------------------------------------------
Unit tests for Phase 2 — LLM Engine

All Groq API calls are fully mocked — no real network calls are made.
Tests cover: happy path, JSON parsing, schema validation, dedup,
top-5 enforcement, 0-candidate short-circuit, and error handling.
"""

import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from phase2_llm_engine.llm_engine import (
    get_recommendations,
    _parse_llm_response,
    _validate_and_clean,
    _enrich_from_candidates,
    LLMUnavailableError,
    LLMResponseParseError,
    REQUIRED_OUTPUT_FIELDS,
    FULL_OUTPUT_FIELDS,
    MAX_RESULTS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_rec(rank=1, name="Truffles", rating=4.2, cost=600,
             cuisine="Continental", rest_type="Casual Dining",
             city="BTM", online="yes", booking="no",
             url="url1", phone="123", blurb="You will love it!"):
    return {
        "rank": rank, "name": name,
        "cuisine": cuisine, "restaurant_type": rest_type,
        "rating": rating, "avg_cost_for_two": cost,
        "city": city, "online_ordering": online,
        "table_booking": booking, "zomato_url": url,
        "phone": phone, "llm_blurb": blurb,
    }


def make_groq_response(content: str):
    """Build a minimal mock Groq chat completion response."""
    message = MagicMock()
    message.content = content

    choice = MagicMock()
    choice.message = message

    response = MagicMock()
    response.choices = [choice]
    return response


@pytest.fixture
def one_candidate():
    return [
        {
            "name": "Truffles", "cuisine": "Continental",
            "restaurant_type": "Casual Dining", "rating": 4.2,
            "avg_cost_for_two": 600, "city": "BTM",
            "online_ordering": "yes", "table_booking": "no",
            "zomato_url": "url1", "phone": "123",
        }
    ]


@pytest.fixture
def five_candidates():
    """Exactly 5 candidates — LLM should return all 5."""
    return [
        {
            "name": f"Restaurant {i}", "cuisine": "Continental",
            "restaurant_type": "Casual Dining", "rating": round(4.0 + i * 0.1, 1),
            "avg_cost_for_two": 600 + i * 100, "city": "BTM",
            "online_ordering": "yes", "table_booking": "no",
            "zomato_url": f"url{i}", "phone": f"12{i}",
        }
        for i in range(1, 6)
    ]


@pytest.fixture
def seven_candidates():
    """7 candidates — LLM must trim output to 5."""
    return [
        {
            "name": f"Restaurant {i}", "cuisine": "Continental",
            "restaurant_type": "Casual Dining", "rating": round(3.5 + i * 0.1, 1),
            "avg_cost_for_two": 500 + i * 100, "city": "BTM",
            "online_ordering": "yes", "table_booking": "no",
            "zomato_url": f"url{i}", "phone": f"10{i}",
        }
        for i in range(1, 8)
    ]


# ---------------------------------------------------------------------------
# Tests: _parse_llm_response
# ---------------------------------------------------------------------------

class TestParseLlmResponse:
    def test_parses_clean_json_array(self):
        raw = json.dumps([make_rec()])
        result = _parse_llm_response(raw)
        assert isinstance(result, list)
        assert result[0]["name"] == "Truffles"

    def test_strips_whitespace(self):
        raw = "  " + json.dumps([make_rec()]) + "  "
        result = _parse_llm_response(raw)
        assert len(result) == 1

    def test_strips_markdown_fences(self):
        raw = "```json\n" + json.dumps([make_rec()]) + "\n```"
        result = _parse_llm_response(raw)
        assert isinstance(result, list)
        assert result[0]["name"] == "Truffles"

    def test_raises_on_invalid_json(self):
        with pytest.raises(LLMResponseParseError, match="not valid JSON"):
            _parse_llm_response("this is not json at all")

    def test_raises_when_not_a_list(self):
        with pytest.raises(LLMResponseParseError, match="JSON array"):
            _parse_llm_response(json.dumps({"name": "Truffles"}))

    def test_empty_array_is_valid(self):
        result = _parse_llm_response("[]")
        assert result == []


# ---------------------------------------------------------------------------
# Tests: _validate_and_clean
# ---------------------------------------------------------------------------

class TestValidateAndClean:
    def test_valid_rec_passes_through(self):
        recs = [make_rec()]
        result = _validate_and_clean(recs)
        assert len(result) == 1

    def test_drops_rec_missing_required_field(self):
        rec = make_rec()
        del rec["llm_blurb"]  # remove a required field
        result = _validate_and_clean([rec])
        assert result == []

    def test_dedup_by_name_case_insensitive(self):
        recs = [make_rec(name="Truffles", rank=1), make_rec(name="truffles", rank=2)]
        result = _validate_and_clean(recs)
        assert len(result) == 1

    def test_caps_at_max_results(self):
        recs = [make_rec(rank=i, name=f"R{i}") for i in range(1, 10)]
        result = _validate_and_clean(recs)
        assert len(result) == MAX_RESULTS

    def test_re_assigns_ranks_sequentially(self):
        # First rec is missing a field → dropped → second becomes rank 1
        r1 = make_rec(rank=1)
        del r1["llm_blurb"]
        r2 = make_rec(rank=2, name="Meghana")
        result = _validate_and_clean([r1, r2])
        assert result[0]["rank"] == 1
        assert result[0]["name"] == "Meghana"

    def test_all_required_fields_present_in_output(self):
        recs = [make_rec()]
        result = _validate_and_clean(recs)
        assert REQUIRED_OUTPUT_FIELDS.issubset(result[0].keys())


# ---------------------------------------------------------------------------
# Tests: get_recommendations — happy path (mocked Groq)
# ---------------------------------------------------------------------------

class TestGetRecommendations:
    @pytest.mark.asyncio
    async def test_zero_candidates_returns_empty_no_api_call(self):
        """0 candidates must short-circuit before any Groq call."""
        with patch("phase2_llm_engine.llm_engine.AsyncGroq") as mock_groq_cls:
            result = await get_recommendations([], api_key="fake-key")
        assert result == []
        mock_groq_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_happy_path_returns_recommendations(self, one_candidate):
        valid_response = json.dumps([make_rec()])
        mock_response = make_groq_response(valid_response)

        with patch("phase2_llm_engine.llm_engine.AsyncGroq") as MockGroq:
            instance = MockGroq.return_value
            instance.chat = MagicMock()
            instance.chat.completions = MagicMock()
            instance.chat.completions.create = AsyncMock(return_value=mock_response)

            result = await get_recommendations(one_candidate, api_key="fake-key")

        assert len(result) == 1
        assert result[0]["name"] == "Truffles"
        assert "llm_blurb" in result[0]

    @pytest.mark.asyncio
    async def test_enforces_top_5_cap(self, seven_candidates):
        """Even if LLM returns 7 items, only 5 should come back."""
        seven_recs = [make_rec(rank=i, name=f"Restaurant {i}") for i in range(1, 8)]
        mock_response = make_groq_response(json.dumps(seven_recs))

        with patch("phase2_llm_engine.llm_engine.AsyncGroq") as MockGroq:
            instance = MockGroq.return_value
            instance.chat.completions.create = AsyncMock(return_value=mock_response)
            result = await get_recommendations(seven_candidates, api_key="fake-key")

        assert len(result) <= MAX_RESULTS

    @pytest.mark.asyncio
    async def test_ranks_are_sequential_1_to_n(self, one_candidate):
        recs = [make_rec(rank=5)]  # LLM assigns wrong rank
        mock_response = make_groq_response(json.dumps(recs))

        with patch("phase2_llm_engine.llm_engine.AsyncGroq") as MockGroq:
            instance = MockGroq.return_value
            instance.chat.completions.create = AsyncMock(return_value=mock_response)
            result = await get_recommendations(one_candidate, api_key="fake-key")

        # rank must be re-assigned as 1
        assert result[0]["rank"] == 1

    @pytest.mark.asyncio
    async def test_output_schema_conformity(self, one_candidate):
        mock_response = make_groq_response(json.dumps([make_rec()]))

        with patch("phase2_llm_engine.llm_engine.AsyncGroq") as MockGroq:
            instance = MockGroq.return_value
            instance.chat.completions.create = AsyncMock(return_value=mock_response)
            result = await get_recommendations(one_candidate, api_key="fake-key")

        assert REQUIRED_OUTPUT_FIELDS.issubset(result[0].keys())

    @pytest.mark.asyncio
    async def test_no_duplicates_in_output(self, five_candidates):
        """Verify dedup even if LLM returns two entries with the same name."""
        recs = [make_rec(rank=1, name="Truffles"), make_rec(rank=2, name="Truffles")]
        mock_response = make_groq_response(json.dumps(recs))

        with patch("phase2_llm_engine.llm_engine.AsyncGroq") as MockGroq:
            instance = MockGroq.return_value
            instance.chat.completions.create = AsyncMock(return_value=mock_response)
            result = await get_recommendations(five_candidates, api_key="fake-key")

        names = [r["name"] for r in result]
        assert len(names) == len(set(names))


# ---------------------------------------------------------------------------
# Tests: get_recommendations — error / degradation paths
# ---------------------------------------------------------------------------

class TestGetRecommendationsErrors:
    @pytest.mark.asyncio
    async def test_raises_llm_unavailable_on_no_api_key(self, one_candidate):
        with patch("phase2_llm_engine.llm_engine._get_config", return_value=("", "llama-3.3-70b-versatile")):
            with pytest.raises(LLMUnavailableError, match="GROQ_API_KEY"):
                await get_recommendations(one_candidate, api_key="")

    @pytest.mark.asyncio
    async def test_raises_llm_unavailable_on_timeout(self, one_candidate):
        from groq import APITimeoutError as GroqTimeout

        with patch("phase2_llm_engine.llm_engine.AsyncGroq") as MockGroq:
            instance = MockGroq.return_value
            instance.chat.completions.create = AsyncMock(
                side_effect=GroqTimeout(request=MagicMock())
            )
            with pytest.raises(LLMUnavailableError, match="timed out"):
                await get_recommendations(one_candidate, api_key="fake-key")

    @pytest.mark.asyncio
    async def test_raises_llm_unavailable_on_connection_error(self, one_candidate):
        from groq import APIConnectionError as GroqConnError

        with patch("phase2_llm_engine.llm_engine.AsyncGroq") as MockGroq:
            instance = MockGroq.return_value
            instance.chat.completions.create = AsyncMock(
                side_effect=GroqConnError(request=MagicMock())
            )
            with pytest.raises(LLMUnavailableError, match="connection"):
                await get_recommendations(one_candidate, api_key="fake-key")

    @pytest.mark.asyncio
    async def test_raises_parse_error_on_bad_json(self, one_candidate):
        mock_response = make_groq_response("I'm sorry, I cannot do that.")

        with patch("phase2_llm_engine.llm_engine.AsyncGroq") as MockGroq:
            instance = MockGroq.return_value
            instance.chat.completions.create = AsyncMock(return_value=mock_response)
            with pytest.raises(LLMResponseParseError):
                await get_recommendations(one_candidate, api_key="fake-key")

    @pytest.mark.asyncio
    async def test_drops_recs_with_missing_fields_gracefully(self, one_candidate):
        """If LLM omits required fields on some items, those are silently dropped."""
        incomplete = {"rank": 1, "name": "Truffles"}  # missing most fields
        good = make_rec(rank=2, name="Meghana", rating=3.8)
        mock_response = make_groq_response(json.dumps([incomplete, good]))

        with patch("phase2_llm_engine.llm_engine.AsyncGroq") as MockGroq:
            instance = MockGroq.return_value
            instance.chat.completions.create = AsyncMock(return_value=mock_response)
            result = await get_recommendations(one_candidate, api_key="fake-key")

        # Only the valid one should survive
        assert len(result) == 1
        assert result[0]["name"] == "Meghana"

    @pytest.mark.asyncio
    async def test_handles_markdown_fenced_response(self, one_candidate):
        """LLM sometimes wraps JSON in ```json ... ``` — it should still parse."""
        fenced = "```json\n" + json.dumps([make_rec()]) + "\n```"
        mock_response = make_groq_response(fenced)

        with patch("phase2_llm_engine.llm_engine.AsyncGroq") as MockGroq:
            instance = MockGroq.return_value
            instance.chat.completions.create = AsyncMock(return_value=mock_response)
            result = await get_recommendations(one_candidate, api_key="fake-key")

        assert len(result) == 1
        assert result[0]["name"] == "Truffles"
