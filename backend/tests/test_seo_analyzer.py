from decimal import Decimal
from unittest.mock import MagicMock

from app.schemas.seo import SeoAnalysisResult
from app.services.ai_service import AIUsage
from app.services.prompts.seo_analyzer import (
    SEO_TOOL,
    analyze_listing_seo,
    build_seo_user_message,
)


def _valid_payload() -> dict:
    return {
        "overall_score": 62,
        "title_analysis": {
            "score": 55,
            "character_count": 38,
            "primary_keyword_present": True,
            "primary_keyword_position": "first_half",
            "issues": ["Primary keyword not in first 3 words"],
            "optimized_title": "Ceramic Coffee Mug Handmade — Cozy Gift",
            "title_change_rationale": "Front-loads the primary keyword.",
        },
        "tags_analysis": {
            "score": 60,
            "current_tag_count": 9,
            "unused_slots": 4,
            "weak_tags": ["mug"],
            "missing_high_value_tags": ["ceramic coffee mug"],
            "replacement_tags": [
                {"remove": "mug", "add": "ceramic coffee mug", "reason": "long-tail"}
            ],
            "full_optimized_tag_set": ["ceramic coffee mug", "handmade mug gift"],
        },
        "description_analysis": {
            "score": 70,
            "keyword_density_ok": True,
            "missing_sections": ["care instructions"],
            "first_paragraph_optimized": False,
            "recommended_additions": ["Lead the first paragraph with the keyword"],
            "optimized_description": "Handmade ceramic mug for cozy mornings. CARE: hand wash.",
        },
        "priority": "high",
        "estimated_traffic_lift_percent": 25,
        "competitor_gap_summary": "Competitors use seasonal keywords; this listing does not.",
    }


def test_seo_result_validates_clean_payload():
    result = SeoAnalysisResult.model_validate(_valid_payload())
    assert result.overall_score == 62
    assert result.tags_analysis.full_optimized_tag_set[0] == "ceramic coffee mug"


def test_seo_result_drops_tag_over_20_chars():
    # An over-length tag must not fail the whole analysis — it's dropped instead.
    payload = _valid_payload()
    payload["tags_analysis"]["full_optimized_tag_set"] = ["x" * 21, "good tag"]
    result = SeoAnalysisResult.model_validate(payload)
    assert result.tags_analysis.full_optimized_tag_set == ["good tag"]


def test_seo_result_caps_tags_at_13():
    payload = _valid_payload()
    payload["tags_analysis"]["full_optimized_tag_set"] = [f"tag {i}" for i in range(14)]
    result = SeoAnalysisResult.model_validate(payload)
    assert len(result.tags_analysis.full_optimized_tag_set) == 13


def test_seo_result_clamps_long_title():
    payload = _valid_payload()
    payload["title_analysis"]["optimized_title"] = "T" * 200
    result = SeoAnalysisResult.model_validate(payload)
    assert len(result.title_analysis.optimized_title) == 140


def test_tool_schema_enforces_etsy_tag_limits():
    tag_set = SEO_TOOL["input_schema"]["properties"]["tags_analysis"]["properties"][
        "full_optimized_tag_set"
    ]
    assert tag_set["maxItems"] == 13
    assert tag_set["items"]["maxLength"] == 20


def test_build_user_message_includes_listing_and_context():
    listing = {
        "title": "Handmade mug",
        "tags": ["mug", "ceramic"],
        "description": "A lovely mug",
        "price_usd": Decimal("29.99"),
        "views_count": 42,
        "favorites_count": 7,
    }
    competitors = [{"title": "Top mug", "tags": ["mug"], "views": 100, "favorites": 9}]

    msg = build_seo_user_message(listing, competitors, ["cozy gifts"])

    assert "Handmade mug" in msg
    assert "mug, ceramic" in msg
    assert "$29.99" in msg
    assert "Competitor 1: Title: Top mug" in msg
    assert "cozy gifts" in msg


def test_build_user_message_handles_missing_context():
    msg = build_seo_user_message({"title": "X"}, [], [])
    assert "No competitor data available" in msg
    assert "No trend data available" in msg


def test_analyze_listing_seo_uses_primary_model_with_thinking():
    expected = SeoAnalysisResult.model_validate(_valid_payload())
    usage = AIUsage(
        model="claude-fable-5",
        input_tokens=1,
        output_tokens=1,
        cache_read_tokens=0,
        cache_write_tokens=0,
        cost_usd=Decimal("0.000060"),
    )
    ai = MagicMock()
    ai.call_with_structured_output.return_value = (expected, usage)

    result, returned_usage = analyze_listing_seo({"title": "X"}, ai=ai)

    assert result is expected
    assert returned_usage is usage
    kwargs = ai.call_with_structured_output.call_args.kwargs
    assert kwargs["model"] == "claude-opus-4-8"
    # Thinking on for quality (fills nested fields like ALT suggestions); the
    # gateway has its own forced-tool fallback for reliability.
    assert kwargs["thinking"] is True
    assert kwargs["tool_name"] == "record_seo_analysis"
    assert kwargs["output_model"] is SeoAnalysisResult
