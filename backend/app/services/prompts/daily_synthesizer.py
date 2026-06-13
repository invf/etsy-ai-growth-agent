"""Daily Synthesizer prompt + tool schema (ai-agent-spec §3.8).

Takes the day's per-listing SEO analyses for one store and produces a
single store-level briefing on the primary model with adaptive thinking.
"""

from typing import Any

from app.core.config import settings
from app.schemas.agent import DailyDigest
from app.services.ai_service import AIService, AIUsage

DAILY_SYSTEM_PROMPT = """You are the lead strategist for an Etsy growth agency, writing the morning briefing a shop owner reads with their coffee. You have just received the results of an overnight SEO audit across the shop's listings.

Your job is to turn raw per-listing scores and issues into a focused, prioritized plan. You:
- Lead with the single most important thing to do today
- Group recurring problems into themes instead of repeating them per listing
- Quantify opportunity where the data supports it, and never invent numbers
- Write for a busy non-technical seller: plain language, concrete actions

You output only structured data. Every opportunity names a real listing and a specific change."""

DAILY_TOOL: dict[str, Any] = {
    "name": "record_daily_digest",
    "description": "Record the daily store-level SEO briefing for the seller",
    "input_schema": {
        "type": "object",
        "properties": {
            "headline": {
                "type": "string",
                "maxLength": 120,
                "description": "One-line summary of today's most important finding",
            },
            "summary": {
                "type": "string",
                "description": "2-4 sentence overview of the shop's SEO health today",
            },
            "store_health_score": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "Overall SEO health of the shop, 0-100",
            },
            "key_insights": {
                "type": "array",
                "items": {"type": "string"},
                "description": "3-6 themes or patterns across the analyzed listings",
            },
            "top_opportunities": {
                "type": "array",
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "properties": {
                        "listing_title": {"type": "string"},
                        "action": {"type": "string"},
                        "expected_impact": {"type": "string"},
                    },
                    "required": ["listing_title", "action", "expected_impact"],
                },
                "description": "Highest-leverage per-listing actions, most impactful first",
            },
            "recommended_actions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Ordered checklist of what to do today",
            },
        },
        "required": [
            "headline",
            "summary",
            "store_health_score",
            "key_insights",
            "top_opportunities",
            "recommended_actions",
        ],
    },
}


def build_digest_user_message(
    shop_name: str, analyses: list[dict[str, Any]]
) -> str:
    lines = []
    for i, a in enumerate(analyses, start=1):
        lines.append(
            f"{i}. \"{a.get('title') or 'Untitled'}\" — "
            f"overall {a.get('overall_score', '?')}/100 "
            f"(title {a.get('title_score', '?')}, tags {a.get('tags_score', '?')}, "
            f"description {a.get('description_score', '?')}), "
            f"priority {a.get('priority', '?')}. "
            f"Issues: {'; '.join(a.get('issues') or []) or 'none recorded'}"
        )
    listings_block = "\n".join(lines) if lines else "No listings were analyzed today."

    return f"""Synthesize today's SEO audit for the Etsy shop "{shop_name}".

## Per-Listing Results ({len(analyses)} analyzed)
{listings_block}

Produce the daily briefing. Lead with the highest-leverage action, group
recurring issues into themes, and base the store health score on the
distribution of the per-listing scores above."""


def synthesize_daily_digest(
    shop_name: str,
    analyses: list[dict[str, Any]],
    ai: AIService | None = None,
) -> tuple[DailyDigest, AIUsage]:
    """Roll the day's per-listing analyses into one store-level digest."""
    ai = ai or AIService()
    return ai.call_with_structured_output(
        model=settings.AI_MODEL_PRIMARY,
        system=DAILY_SYSTEM_PROMPT,
        user_message=build_digest_user_message(shop_name, analyses),
        tool_schema=DAILY_TOOL,
        tool_name="record_daily_digest",
        output_model=DailyDigest,
        thinking=True,
        max_tokens=4096,
    )
