"""SEO Analyzer prompt + tool schema (ai-agent-spec §3.1).

Deep per-listing SEO analysis on the primary model with adaptive thinking.
"""

from typing import Any

from app.core.config import settings
from app.schemas.seo import SeoAnalysisResult
from app.services.ai_service import AIService, AIUsage

SEO_SYSTEM_PROMPT = """You are an expert Etsy SEO strategist with deep knowledge of the Etsy search algorithm (2024–2025), buyer psychology, and e-commerce copywriting. You have analyzed thousands of successful Etsy listings.

Your analysis is grounded in:
- Etsy's relevancy score factors: title match, tag match, recency, conversion rate, listing quality score
- Long-tail keyword research for artisan/handmade goods
- Seasonal and trend-aware optimization
- Buyer search behavior on mobile vs desktop

You output only structured, actionable data. Every recommendation includes a specific change, its rationale, and expected impact."""

SEO_TOOL: dict[str, Any] = {
    "name": "record_seo_analysis",
    "description": "Record the complete SEO analysis for an Etsy listing",
    "input_schema": {
        "type": "object",
        "properties": {
            "overall_score": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "SEO quality score 0-100",
            },
            "title_analysis": {
                "type": "object",
                "properties": {
                    "score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "character_count": {"type": "integer"},
                    "primary_keyword_present": {"type": "boolean"},
                    "primary_keyword_position": {
                        "type": "string",
                        "enum": ["first_3_words", "first_half", "second_half", "absent"],
                    },
                    "issues": {"type": "array", "items": {"type": "string"}},
                    "optimized_title": {"type": "string", "maxLength": 140},
                    "title_change_rationale": {"type": "string"},
                },
                "required": [
                    "score",
                    "character_count",
                    "primary_keyword_present",
                    "primary_keyword_position",
                    "issues",
                    "optimized_title",
                    "title_change_rationale",
                ],
            },
            "tags_analysis": {
                "type": "object",
                "properties": {
                    "score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "current_tag_count": {"type": "integer"},
                    "unused_slots": {"type": "integer"},
                    "weak_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags that are too generic or redundant",
                    },
                    "missing_high_value_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 5,
                    },
                    "replacement_tags": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "remove": {"type": "string"},
                                "add": {"type": "string"},
                                "reason": {"type": "string"},
                            },
                            "required": ["remove", "add", "reason"],
                        },
                    },
                    "full_optimized_tag_set": {
                        "type": "array",
                        "items": {"type": "string", "maxLength": 20},
                        "maxItems": 13,
                        "description": "Complete recommended tag set, Etsy max 13 tags of 20 chars each",
                    },
                },
                "required": [
                    "score",
                    "current_tag_count",
                    "unused_slots",
                    "weak_tags",
                    "missing_high_value_tags",
                    "replacement_tags",
                    "full_optimized_tag_set",
                ],
            },
            "description_analysis": {
                "type": "object",
                "properties": {
                    "score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "keyword_density_ok": {"type": "boolean"},
                    "missing_sections": {"type": "array", "items": {"type": "string"}},
                    "first_paragraph_optimized": {"type": "boolean"},
                    "recommended_additions": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "optimized_description": {
                        "type": "string",
                        "description": (
                            "A complete, ready-to-publish Etsy description rewritten "
                            "per the recommendations. Open the first 1-2 sentences "
                            "with the primary keywords (Etsy/Google weight the first "
                            "~160 chars most). Do NOT describe dimensions/sizes or "
                            "shipping terms — those are handled in Etsy's dedicated "
                            "fields and other sections, so omit SIZE and SHIPPING "
                            "blocks entirely. Focus on the product story: weave "
                            "secondary keywords in naturally, describe materials and "
                            "craftsmanship, add a gifting/occasion line, and justify a "
                            "premium price with an artist/process note. Use plain text "
                            "(Etsy descriptions don't render markdown); separate "
                            "sections with line breaks and UPPERCASE labels."
                        ),
                    },
                },
                "required": [
                    "score",
                    "keyword_density_ok",
                    "missing_sections",
                    "first_paragraph_optimized",
                    "recommended_additions",
                    "optimized_description",
                ],
            },
            "image_alt_analysis": {
                "type": "object",
                "properties": {
                    "score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "images_with_alt": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "How many photos already have non-empty ALT text",
                    },
                    "images_total": {"type": "integer", "minimum": 0},
                    "suggestions": {
                        "type": "array",
                        "description": (
                            "One entry per photo that needs a better ALT text. "
                            "Skip photos whose current ALT is already strong."
                        ),
                        "items": {
                            "type": "object",
                            "properties": {
                                "image_index": {
                                    "type": "integer",
                                    "minimum": 0,
                                    "description": "0-based position of the photo",
                                },
                                "current_alt": {
                                    "type": "string",
                                    "description": "Existing ALT text, empty string if none",
                                },
                                "suggested_alt": {
                                    "type": "string",
                                    "maxLength": 250,
                                    "description": (
                                        "A descriptive, keyword-rich ALT text (≤250 "
                                        "chars) that helps accessibility AND Etsy/Google "
                                        "image SEO. Lead with the primary keyword, "
                                        "describe what the photo likely shows (product, "
                                        "color, material, angle/use), and read naturally "
                                        "— not a keyword dump. Vary it per photo."
                                    ),
                                },
                                "issue": {
                                    "type": "string",
                                    "description": "Why the current ALT is weak/missing",
                                },
                            },
                            "required": [
                                "image_index",
                                "current_alt",
                                "suggested_alt",
                                "issue",
                            ],
                        },
                    },
                },
                "required": [
                    "score",
                    "images_with_alt",
                    "images_total",
                    "suggestions",
                ],
            },
            "priority": {
                "type": "string",
                "enum": ["critical", "high", "medium", "low"],
                "description": "Priority of implementing these changes",
            },
            "estimated_traffic_lift_percent": {
                "type": "integer",
                "description": "Conservative estimate of search traffic increase if all recommendations implemented",
            },
            "competitor_gap_summary": {
                "type": "string",
                "description": "1-2 sentences on what top competitors are doing that this listing is not",
            },
        },
        "required": [
            "overall_score",
            "title_analysis",
            "tags_analysis",
            "description_analysis",
            "image_alt_analysis",
            "priority",
            "estimated_traffic_lift_percent",
            "competitor_gap_summary",
        ],
    },
}


def build_seo_user_message(
    listing: dict[str, Any],
    competitor_context: list[dict[str, Any]],
    trending_keywords: list[str],
) -> str:
    competitor_text = "\n".join(
        f"Competitor {i + 1}: Title: {c['title']} | "
        f"Tags: {', '.join(c.get('tags', [])[:5])} | "
        f"Views: {c.get('views', '?')} | Favorites: {c.get('favorites', '?')}"
        for i, c in enumerate(competitor_context[:5])
    )

    alt_texts = listing.get("image_alt_texts") or []
    if alt_texts:
        image_text = "\n".join(
            f"Photo {i} ALT: {alt.strip() or '(no ALT text)'}"
            for i, alt in enumerate(alt_texts)
        )
    else:
        image_text = "No photo data available"

    return f"""Analyze this Etsy listing for SEO optimization:

## Listing to Analyze
Title: {listing.get('title') or ''}
Tags: {', '.join(listing.get('tags') or [])}
Description (first 500 chars): {(listing.get('description') or '')[:500]}
Price: ${float(listing.get('price_usd') or 0):.2f}
Current Views: {listing.get('views_count', 0)}
Favorites: {listing.get('favorites_count', 0)}

## Listing Photos (ALT text, in order)
{image_text}

## Top Competitor Listings in Same Category (from Etsy search results)
{competitor_text if competitor_text else 'No competitor data available'}

## Currently Trending Keywords in This Niche
{', '.join(trending_keywords[:15]) if trending_keywords else 'No trend data available'}

Provide a thorough SEO analysis. Be specific about what to change and why. All recommended tags must be ≤20 characters (Etsy limit). In description_analysis.optimized_description, write the full, ready-to-publish description (not just guidance) following every recommendation. In image_alt_analysis, evaluate each photo's ALT text (you cannot see the photos — infer likely content from the title, tags, and materials) and provide an improved, keyword-rich ALT text for every photo that is missing or weak; set images_total to the number of photos listed above."""


def analyze_listing_seo(
    listing: dict[str, Any],
    competitor_context: list[dict[str, Any]] | None = None,
    trending_keywords: list[str] | None = None,
    ai: AIService | None = None,
) -> tuple[SeoAnalysisResult, AIUsage]:
    """Full SEO analysis for one listing; competitor/trend context comes from RAG."""
    ai = ai or AIService()
    return ai.call_with_structured_output(
        model=settings.AI_MODEL_PRIMARY,
        system=SEO_SYSTEM_PROMPT,
        user_message=build_seo_user_message(
            listing, competitor_context or [], trending_keywords or []
        ),
        tool_schema=SEO_TOOL,
        tool_name="record_seo_analysis",
        output_model=SeoAnalysisResult,
        thinking=True,
        # Adaptive thinking shares this budget with the tool-call output. The
        # result is large — a full rewritten description plus per-photo ALT
        # suggestions — so give generous headroom; 16k truncated the JSON.
        max_tokens=32000,
    )
