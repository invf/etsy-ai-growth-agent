# Etsy AI Growth Agent — AI & Agent Architecture Specification

> Session 4 of 4. Companion to `backend-spec.md` (Session 2) and `frontend-spec.md` (Session 3).

---

## Table of Contents

1. [AI Layer Overview](#1-ai-layer-overview)
2. [Daily Autonomous Workflow](#2-daily-autonomous-workflow)
3. [Claude Fable 5 Prompt Library](#3-claude-fable-5-prompt-library)
4. [RAG Architecture for Competitor Data](#4-rag-architecture-for-competitor-data)
5. [Embeddings Strategy](#5-embeddings-strategy)
6. [API Rate Limits & Cost Management](#6-api-rate-limits--cost-management)
7. [Agent Observability & Logging](#7-agent-observability--logging)

---

## 1. AI Layer Overview

### 1.1 Model Routing Policy

Every AI call is routed to one of two primary models based on task complexity and frequency:

| Model | ID | Input | Output | Use Cases |
|---|---|---|---|---|
| Claude Fable 5 | `claude-fable-5` | $10/1M | $50/1M | Deep analysis, synthesis, planning, content generation, image analysis |
| Claude Haiku 4.5 | `claude-haiku-4-5` | $1/1M | $5/1M | Classification, extraction, intent detection, tag scoring, bulk operations |

**Routing rule:** Default to Haiku for tasks that are (a) high-frequency >10/day per store, (b) require only extraction or classification not synthesis, or (c) have easily verified outputs. Escalate to Fable 5 when the task requires creative judgment, multi-source synthesis, or strategic reasoning.

### 1.2 Thinking Configuration

```python
# claude-fable-5: adaptive thinking only — omit param for no thinking
# NEVER use budget_tokens on Fable 5 — returns 400
# NEVER use thinking: {type: "disabled"} on Fable 5 — returns 400

# Complex reasoning tasks (SEO analysis, competitor synthesis, strategic planning)
fable5_thinking = {
    "thinking": {"type": "adaptive"}           # Fable 5 / Opus 4.x — adaptive only
}

# For visible thinking progress in streaming UI
fable5_thinking_visible = {
    "thinking": {"type": "adaptive", "display": "summarized"}
}

# Fast extraction tasks — omit thinking entirely
haiku_no_thinking = {}  # just omit the thinking param
```

### 1.3 Structured Output Contract

**Rule:** All AI responses that feed downstream code MUST use `tool_use` with a Pydantic-validated schema. Never parse free-form text.

```python
from anthropic import Anthropic
from pydantic import BaseModel, Field
from typing import Any

client = Anthropic()

def call_with_structured_output(
    model: str,
    system: str,
    user_message: str,
    tool_schema: dict,
    tool_name: str,
    thinking: bool = False,
) -> dict[str, Any]:
    """
    All AI calls go through this function to enforce structured output via tool_use.
    Raises ValueError if Claude does not call the tool.
    """
    kwargs = {
        "model": model,
        "max_tokens": 8192,
        "system": system,
        "messages": [{"role": "user", "content": user_message}],
        "tools": [tool_schema],
        "tool_choice": {"type": "tool", "name": tool_name},  # force tool call
    }
    if thinking:
        kwargs["thinking"] = {"type": "adaptive"}

    response = client.messages.create(**kwargs)

    for block in response.content:
        if block.type == "tool_use" and block.name == tool_name:
            return block.input

    raise ValueError(f"Claude did not call {tool_name} — this should never happen with tool_choice forced")
```

### 1.4 Prompt Caching Strategy

System prompts are identical across all calls for a given feature. Use the `cache_control` breakpoint on the system prompt to avoid re-paying input tokens.

```python
# System prompt with cache_control on static content
system_with_cache = [
    {
        "type": "text",
        "text": STATIC_SYSTEM_PROMPT,              # persona + context + instructions
        "cache_control": {"type": "ephemeral"}     # TTL: 5 min, 90% discount on cache hit
    }
]
```

Cache hit savings: system prompts average ~2,000 tokens. At 90% discount on cached tokens, Fable 5 cost per cached-hit call = ~$0.001 vs $0.02 cold.

---

## 2. Daily Autonomous Workflow

### 2.1 Architecture Overview

```
Celery Beat (07:00 UTC daily)
    │
    ▼
run_daily_agent_scheduler          ← fan-out: one task per active store
    │
    ├─── acquire_lock(store_id)     ← Redis SET NX PX 3600000 (1h TTL)
    ├─── reserve_credits(user_id)   ← atomic credit check + reservation
    │
    ▼
daily_agent_pipeline(store_id)     ← main orchestration task
    │
    ├── [PHASE 1: Data Sync]
    │       sync_etsy_listings      ← Etsy API, cache 6h
    │       sync_store_analytics    ← Etsy stats endpoint
    │
    ├── [PHASE 2: Parallel Analysis — Celery chord]
    │       ├── seo_analysis_task          (top 20 listings by revenue)
    │       ├── competitor_scan_task       (3 competitors per listing category)
    │       ├── trend_fetch_task           (Google Trends + Reddit + Pinterest)
    │       └── pricing_intelligence_task  (market price range per category)
    │
    ├── [PHASE 3: Synthesis — chord callback]
    │       daily_synthesis_task    ← Fable 5, aggregates all Phase 2 results
    │
    ├── [PHASE 4: Content Generation — parallel, gated by synthesis]
    │       ├── generate_listing_optimizations (for recommended listings only)
    │       └── image_analysis_task (for flagged low-performing listings)
    │
    ├── [PHASE 5: Embedding Updates]
    │       update_embeddings_task  ← re-embed stale entries (content_hash mismatch)
    │
    ├── [PHASE 6: Notifications]
    │       ├── create_notifications     ← in-app alerts
    │       └── queue_email_digest       ← SendGrid, scheduled for 09:00 local time
    │
    └── [PHASE 7: Cleanup]
            release_credits_reservation
            release_lock
            finalize_agent_run_record   ← log total tokens, cost_usd, duration
```

### 2.2 Celery Task Implementation

```python
# tasks/daily_agent.py
from celery import chord, group, chain
from app.celery_app import celery
from app.db.session import get_db_session
from app.services.credit_service import CreditService
from app.services.lock_service import AcquireDistributedLock
from app.models.agent_run import AgentRun, AgentRunStatus
import logging

logger = logging.getLogger(__name__)

DAILY_AGENT_CREDIT_RESERVE = 50  # conservative upper bound per store


@celery.task(name="tasks.run_daily_agent_scheduler")
def run_daily_agent_scheduler():
    """Triggered by Celery Beat at 07:00 UTC. Fan-out to all active stores."""
    with get_db_session() as db:
        active_stores = db.execute(
            """
            SELECT s.id, s.user_id
            FROM stores s
            JOIN users u ON s.user_id = u.id
            WHERE s.is_active = TRUE
              AND u.subscription_status IN ('active', 'trial')
              AND u.credits_balance >= 5  -- skip stores with no credits
            ORDER BY s.created_at
            """
        ).fetchall()

    for store in active_stores:
        daily_agent_pipeline.apply_async(
            args=[str(store.id), str(store.user_id)],
            queue="scheduled",
            countdown=0,
        )

    logger.info(f"Scheduled daily agent for {len(active_stores)} stores")


@celery.task(
    name="tasks.daily_agent_pipeline",
    bind=True,
    max_retries=2,
    default_retry_delay=300,  # 5 min before retry
    queue="high",
)
def daily_agent_pipeline(self, store_id: str, user_id: str):
    lock_key = f"lock:daily_agent:{store_id}"

    with AcquireDistributedLock(lock_key, ttl_ms=3_600_000) as lock:
        if not lock.acquired:
            logger.warning(f"Daily agent already running for store {store_id}, skipping")
            return

        with get_db_session() as db:
            # Create agent_run record
            run = AgentRun(
                store_id=store_id,
                user_id=user_id,
                run_type="daily",
                status=AgentRunStatus.RUNNING,
            )
            db.add(run)
            db.flush()
            run_id = str(run.id)

        credit_service = CreditService()
        credit_service.reserve(user_id, DAILY_AGENT_CREDIT_RESERVE, run_id)

        try:
            _execute_pipeline(store_id, user_id, run_id)
        except Exception as exc:
            credit_service.release_reservation(run_id)
            _finalize_run(run_id, status="failed", error=str(exc))
            raise self.retry(exc=exc)

        # Credits are consumed precisely at finalization
        credit_service.settle_reservation(run_id)


def _execute_pipeline(store_id: str, user_id: str, run_id: str):
    from tasks.sync import sync_etsy_listings_task, sync_store_analytics_task
    from tasks.analysis import (
        seo_analysis_task,
        competitor_scan_task,
        trend_fetch_task,
        pricing_intelligence_task,
    )
    from tasks.synthesis import daily_synthesis_task
    from tasks.content import generate_listing_optimizations_task, image_analysis_task
    from tasks.embeddings import update_embeddings_task
    from tasks.notifications import create_notifications_task, queue_email_digest_task

    ctx = {"store_id": store_id, "user_id": user_id, "run_id": run_id}

    # Phase 1: sync (sequential, others depend on fresh data)
    sync_etsy_listings_task.apply(args=[ctx], throw=True)
    sync_store_analytics_task.apply(args=[ctx], throw=True)

    # Phase 2: parallel analysis
    analysis_chord = chord(
        group(
            seo_analysis_task.s(ctx),
            competitor_scan_task.s(ctx),
            trend_fetch_task.s(ctx),
            pricing_intelligence_task.s(ctx),
        ),
        daily_synthesis_task.s(ctx),  # callback receives list of 4 results
    )
    synthesis_result = analysis_chord.apply_async().get(timeout=600)

    # Phase 3: content generation (parallel, gated by synthesis)
    content_tasks = group(
        generate_listing_optimizations_task.s(synthesis_result, ctx),
        image_analysis_task.s(synthesis_result, ctx),
    )
    content_tasks.apply_async().get(timeout=300)

    # Phase 4: embeddings
    update_embeddings_task.apply_async(args=[ctx]).get(timeout=120)

    # Phase 5: notifications
    group(
        create_notifications_task.s(synthesis_result, ctx),
        queue_email_digest_task.s(synthesis_result, ctx),
    ).apply_async()

    _finalize_run(run_id, status="completed")
```

### 2.3 Phase 1: Data Sync

```python
# tasks/sync.py
import hashlib
import json
from app.integrations.etsy_client import EtsyClient
from app.db.session import get_db_session

LISTING_FIELDS = "listing_id,title,description,tags,price,quantity,views,num_favorers,state"


@celery.task(name="tasks.sync_etsy_listings", queue="high")
def sync_etsy_listings_task(ctx: dict):
    store_id = ctx["store_id"]
    cache_key = f"etsy:listings:{store_id}"

    # Skip if cache is fresh (<6h old)
    if redis.exists(cache_key) and redis.ttl(cache_key) > 21600 - 600:
        return {"synced": 0, "from_cache": True}

    etsy = EtsyClient(store_id=store_id)
    listings = etsy.get_active_listings(fields=LISTING_FIELDS, limit=100)

    with get_db_session() as db:
        for listing in listings:
            content_hash = hashlib.sha256(
                json.dumps({"title": listing["title"], "description": listing["description"],
                            "tags": listing["tags"]}, sort_keys=True).encode()
            ).hexdigest()

            db.execute("""
                INSERT INTO listings (store_id, etsy_listing_id, title, description, tags,
                    price_usd, quantity, views_count, favorites_count, content_hash)
                VALUES (:store_id, :listing_id, :title, :description, :tags,
                    :price, :quantity, :views, :favorites, :content_hash)
                ON CONFLICT (etsy_listing_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    tags = EXCLUDED.tags,
                    price_usd = EXCLUDED.price_usd,
                    quantity = EXCLUDED.quantity,
                    views_count = EXCLUDED.views_count,
                    favorites_count = EXCLUDED.favorites_count,
                    content_hash = EXCLUDED.content_hash,
                    updated_at = NOW()
                WHERE listings.content_hash != EXCLUDED.content_hash
            """, {
                "store_id": store_id,
                "listing_id": listing["listing_id"],
                "title": listing["title"],
                "description": listing["description"],
                "tags": listing.get("tags", []),
                "price": listing["price"]["amount"] / listing["price"]["divisor"],
                "quantity": listing["quantity"],
                "views": listing.get("views", 0),
                "favorites": listing.get("num_favorers", 0),
                "content_hash": content_hash,
            })

    redis.setex(cache_key, 21600, json.dumps([l["listing_id"] for l in listings]))
    return {"synced": len(listings), "from_cache": False}
```

### 2.4 Phase 2: SEO Analysis Task

```python
# tasks/analysis.py — SEO analysis using model routing
from app.services.ai_service import AIService
from app.db.session import get_db_session

@celery.task(name="tasks.seo_analysis", queue="default")
def seo_analysis_task(ctx: dict) -> dict:
    store_id = ctx["store_id"]
    run_id = ctx["run_id"]
    ai = AIService(run_id=run_id)

    with get_db_session() as db:
        # Top 20 listings by revenue proxy (views * conversion_estimate * price)
        listings = db.execute("""
            SELECT id, etsy_listing_id, title, description, tags, price_usd,
                   views_count, favorites_count, content_hash
            FROM listings
            WHERE store_id = :store_id AND state = 'active'
            ORDER BY (views_count * price_usd) DESC
            LIMIT 20
        """, {"store_id": store_id}).fetchall()

    results = []
    for listing in listings:
        # Use Haiku for quick tag quality scan (cheap, high frequency)
        tag_score = ai.quick_tag_scan(listing)   # haiku-4-5

        # Use Fable 5 only for listings with low tag scores or high revenue impact
        if tag_score["score"] < 70 or listing.views_count > 500:
            full_analysis = ai.deep_seo_analysis(listing)  # fable-5
        else:
            full_analysis = {"skip": True, "quick_score": tag_score}

        results.append({"listing_id": str(listing.id), **full_analysis})

    return {"seo_results": results}
```

### 2.5 Phase 3: Competitor Scan

```python
@celery.task(name="tasks.competitor_scan", queue="bulk")
def competitor_scan_task(ctx: dict) -> dict:
    store_id = ctx["store_id"]
    run_id = ctx["run_id"]

    with get_db_session() as db:
        # Get top categories from store listings
        categories = db.execute("""
            SELECT DISTINCT primary_category, COUNT(*) as listing_count
            FROM listings WHERE store_id = :store_id AND state = 'active'
            GROUP BY primary_category ORDER BY listing_count DESC LIMIT 5
        """, {"store_id": store_id}).fetchall()

    etsy = EtsyClient(store_id=store_id)
    all_competitors = []

    for category in categories:
        # Search top listings in category to find competitors
        top_listings = etsy.search_listings(
            keywords=category.primary_category,
            sort_on="score",
            limit=50,
        )
        # Exclude own store listings
        competitors = [l for l in top_listings if l["shop_id"] != store_id][:10]
        all_competitors.extend(competitors)

        # Upsert to competitor_listings table
        _upsert_competitor_listings(competitors)

    # Embed new/changed competitor listings
    _trigger_competitor_embeddings(all_competitors, run_id)

    return {"categories_scanned": len(categories), "competitors_found": len(all_competitors)}
```

---

## 3. Claude Fable 5 Prompt Library

All prompts use `tool_use` with forced tool calls (`tool_choice: {type: "tool", name: ...}`). Python code uses the Anthropic SDK directly — no LangChain.

### 3.1 SEO Analyzer

**When:** Deep analysis on high-traffic or low-converting listings. Fable 5 with adaptive thinking.

```python
# prompts/seo_analyzer.py
from anthropic import Anthropic
from pydantic import BaseModel, Field
import json

client = Anthropic()

SEO_SYSTEM_PROMPT = """You are an expert Etsy SEO strategist with deep knowledge of the Etsy search algorithm (2024–2025), buyer psychology, and e-commerce copywriting. You have analyzed thousands of successful Etsy listings.

Your analysis is grounded in:
- Etsy's relevancy score factors: title match, tag match, recency, conversion rate, listing quality score
- Long-tail keyword research for artisan/handmade goods
- Seasonal and trend-aware optimization
- Buyer search behavior on mobile vs desktop

You output only structured, actionable data. Every recommendation includes a specific change, its rationale, and expected impact."""

SEO_TOOL = {
    "name": "record_seo_analysis",
    "description": "Record the complete SEO analysis for an Etsy listing",
    "input_schema": {
        "type": "object",
        "properties": {
            "overall_score": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "SEO quality score 0-100"
            },
            "title_analysis": {
                "type": "object",
                "properties": {
                    "score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "character_count": {"type": "integer"},
                    "primary_keyword_present": {"type": "boolean"},
                    "primary_keyword_position": {"type": "string", "enum": ["first_3_words", "first_half", "second_half", "absent"]},
                    "issues": {"type": "array", "items": {"type": "string"}},
                    "optimized_title": {"type": "string", "maxLength": 140},
                    "title_change_rationale": {"type": "string"}
                },
                "required": ["score", "character_count", "primary_keyword_present", "primary_keyword_position", "issues", "optimized_title", "title_change_rationale"]
            },
            "tags_analysis": {
                "type": "object",
                "properties": {
                    "score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "current_tag_count": {"type": "integer"},
                    "unused_slots": {"type": "integer"},
                    "weak_tags": {"type": "array", "items": {"type": "string"}, "description": "Tags that are too generic or redundant"},
                    "missing_high_value_tags": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
                    "replacement_tags": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "remove": {"type": "string"},
                                "add": {"type": "string"},
                                "reason": {"type": "string"}
                            },
                            "required": ["remove", "add", "reason"]
                        }
                    },
                    "full_optimized_tag_set": {
                        "type": "array",
                        "items": {"type": "string", "maxLength": 20},
                        "maxItems": 13,
                        "description": "Complete recommended tag set, Etsy max 13 tags of 20 chars each"
                    }
                },
                "required": ["score", "current_tag_count", "unused_slots", "weak_tags", "missing_high_value_tags", "replacement_tags", "full_optimized_tag_set"]
            },
            "description_analysis": {
                "type": "object",
                "properties": {
                    "score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "keyword_density_ok": {"type": "boolean"},
                    "missing_sections": {"type": "array", "items": {"type": "string"}},
                    "first_paragraph_optimized": {"type": "boolean"},
                    "recommended_additions": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["score", "keyword_density_ok", "missing_sections", "first_paragraph_optimized", "recommended_additions"]
            },
            "priority": {
                "type": "string",
                "enum": ["critical", "high", "medium", "low"],
                "description": "Priority of implementing these changes"
            },
            "estimated_traffic_lift_percent": {
                "type": "integer",
                "description": "Conservative estimate of search traffic increase if all recommendations implemented"
            },
            "competitor_gap_summary": {
                "type": "string",
                "description": "1-2 sentences on what top competitors are doing that this listing is not"
            }
        },
        "required": ["overall_score", "title_analysis", "tags_analysis", "description_analysis", "priority", "estimated_traffic_lift_percent", "competitor_gap_summary"]
    }
}


def analyze_listing_seo(
    listing: dict,
    competitor_context: list[dict],  # top 5 similar competitor listings from RAG
    trending_keywords: list[str],     # from trend_fetch
) -> dict:
    """
    Full SEO analysis for a single listing using Fable 5 with adaptive thinking.
    competitor_context and trending_keywords are injected from RAG pipeline.
    """
    competitor_text = "\n".join([
        f"Competitor {i+1}: Title: {c['title']} | Tags: {', '.join(c['tags'][:5])} | Views: {c.get('views', '?')} | Favorites: {c.get('favorites', '?')}"
        for i, c in enumerate(competitor_context[:5])
    ])

    user_message = f"""Analyze this Etsy listing for SEO optimization:

## Listing to Analyze
Title: {listing['title']}
Tags: {', '.join(listing.get('tags', []))}
Description (first 500 chars): {listing.get('description', '')[:500]}
Price: ${listing.get('price_usd', 0):.2f}
Current Views: {listing.get('views_count', 0)}
Favorites: {listing.get('favorites_count', 0)}

## Top Competitor Listings in Same Category (from Etsy search results)
{competitor_text if competitor_text else 'No competitor data available'}

## Currently Trending Keywords in This Niche
{', '.join(trending_keywords[:15]) if trending_keywords else 'No trend data available'}

Provide a thorough SEO analysis. Be specific about what to change and why. All recommended tags must be ≤20 characters (Etsy limit)."""

    response = client.messages.create(
        model="claude-fable-5",
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=[{
            "type": "text",
            "text": SEO_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"}
        }],
        messages=[{"role": "user", "content": user_message}],
        tools=[SEO_TOOL],
        tool_choice={"type": "tool", "name": "record_seo_analysis"},
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "record_seo_analysis":
            result = block.input
            # Validate tag constraints before returning
            assert len(result["tags_analysis"]["full_optimized_tag_set"]) <= 13
            assert all(len(t) <= 20 for t in result["tags_analysis"]["full_optimized_tag_set"])
            return result

    raise ValueError("SEO analysis tool not called")
```

### 3.2 Competitor Analyzer

**When:** Identifying competitive positioning gaps and opportunities. Fable 5 with adaptive thinking.

```python
# prompts/competitor_analyzer.py

COMPETITOR_SYSTEM_PROMPT = """You are an expert e-commerce competitive intelligence analyst specializing in Etsy marketplaces. You understand pricing strategy, positioning, visual merchandising signals, and buyer decision psychology in handmade/vintage goods markets.

You identify actionable gaps between a seller's current positioning and what top competitors are doing successfully. You focus on differences that can be acted on within 1-2 weeks, not structural advantages that cannot be quickly replicated."""

COMPETITOR_TOOL = {
    "name": "record_competitor_analysis",
    "description": "Record structured competitive intelligence analysis",
    "input_schema": {
        "type": "object",
        "properties": {
            "market_position": {
                "type": "object",
                "properties": {
                    "price_percentile": {"type": "integer", "minimum": 0, "maximum": 100, "description": "Where seller sits in market price range (0=cheapest, 100=most expensive)"},
                    "positioning": {"type": "string", "enum": ["budget", "mid_market", "premium", "luxury"]},
                    "positioning_consistency_score": {"type": "integer", "minimum": 0, "maximum": 100, "description": "How consistent pricing/presentation is across store"}
                },
                "required": ["price_percentile", "positioning", "positioning_consistency_score"]
            },
            "top_competitor_patterns": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string"},
                        "frequency": {"type": "string", "enum": ["all_top_10", "most", "some"]},
                        "seller_does_this": {"type": "boolean"},
                        "impact": {"type": "string", "enum": ["high", "medium", "low"]}
                    },
                    "required": ["pattern", "frequency", "seller_does_this", "impact"]
                },
                "maxItems": 8
            },
            "pricing_opportunities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "listing_title_fragment": {"type": "string"},
                        "current_price": {"type": "number"},
                        "competitor_avg_price": {"type": "number"},
                        "recommended_price": {"type": "number"},
                        "rationale": {"type": "string"}
                    },
                    "required": ["listing_title_fragment", "current_price", "competitor_avg_price", "recommended_price", "rationale"]
                }
            },
            "content_gaps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific things top competitors include that this seller does not",
                "maxItems": 5
            },
            "quick_wins": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string"},
                        "effort": {"type": "string", "enum": ["5_min", "30_min", "1_hour", "half_day"]},
                        "expected_impact": {"type": "string"}
                    },
                    "required": ["action", "effort", "expected_impact"]
                },
                "maxItems": 5
            },
            "differentiation_opportunities": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Unmet needs or underserved niches in the competitive landscape",
                "maxItems": 3
            }
        },
        "required": ["market_position", "top_competitor_patterns", "pricing_opportunities", "content_gaps", "quick_wins", "differentiation_opportunities"]
    }
}


def analyze_competitors(
    store_listings: list[dict],
    competitor_listings: list[dict],
    category: str,
) -> dict:
    store_summary = "\n".join([
        f"- {l['title'][:60]} | ${l['price_usd']:.2f} | {l['views_count']} views | {l['favorites_count']} faves"
        for l in store_listings[:15]
    ])

    competitor_summary = "\n".join([
        f"- [{c.get('shop_name', 'Unknown')}] {c['title'][:60]} | ${c.get('price', 0):.2f} | {c.get('views', 0)} views | Tags: {', '.join(c.get('tags', [])[:5])}"
        for c in competitor_listings[:20]
    ])

    response = client.messages.create(
        model="claude-fable-5",
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=[{
            "type": "text",
            "text": COMPETITOR_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"}
        }],
        messages=[{
            "role": "user",
            "content": f"""Analyze the competitive landscape for this Etsy store in the '{category}' category.

## Our Store Listings
{store_summary}

## Top Competitor Listings (from Etsy search, sorted by relevance score)
{competitor_summary}

Identify actionable gaps and opportunities. Focus on changes the seller can make in the next 1-2 weeks."""
        }],
        tools=[COMPETITOR_TOOL],
        tool_choice={"type": "tool", "name": "record_competitor_analysis"},
    )

    for block in response.content:
        if block.type == "tool_use":
            return block.input

    raise ValueError("Competitor analysis tool not called")
```

### 3.3 Trend Synthesizer

**When:** Daily trend synthesis from Google Trends + Reddit + Pinterest. Fable 5.

```python
# prompts/trend_synthesizer.py

TREND_SYSTEM_PROMPT = """You are a market trends analyst specializing in consumer product trends for artisan and handmade goods. You synthesize signals from multiple platforms (social media, search trends, seasonal patterns) into concrete, actionable opportunities for Etsy sellers.

You understand the lifecycle of trends on Etsy:
- Emerging (3-6 months before peak): high upside, first-mover advantage
- Growing (1-3 months before peak): best time to optimize listings
- Peak: high competition, diminishing returns on new listings
- Declining: clear out inventory, don't invest in new content

Your outputs are specific enough to generate new listing ideas or modify existing ones."""

TREND_TOOL = {
    "name": "record_trend_synthesis",
    "description": "Record synthesized trend intelligence for an Etsy store category",
    "input_schema": {
        "type": "object",
        "properties": {
            "trend_opportunities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "trend_name": {"type": "string"},
                        "lifecycle_stage": {"type": "string", "enum": ["emerging", "growing", "peak", "declining"]},
                        "relevance_score": {"type": "integer", "minimum": 0, "maximum": 100, "description": "How relevant to this specific store's product catalog"},
                        "sources": {"type": "array", "items": {"type": "string", "enum": ["google_trends", "reddit", "pinterest", "tiktok", "etsy_search"]}},
                        "search_volume_trend": {"type": "string", "enum": ["sharply_rising", "rising", "stable", "declining"]},
                        "recommended_keywords": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
                        "listing_ideas": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
                        "time_sensitivity": {"type": "string", "enum": ["act_now", "this_week", "this_month", "monitor"]}
                    },
                    "required": ["trend_name", "lifecycle_stage", "relevance_score", "sources", "search_volume_trend", "recommended_keywords", "listing_ideas", "time_sensitivity"]
                },
                "maxItems": 10
            },
            "seasonal_calendar": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "event_name": {"type": "string"},
                        "days_until": {"type": "integer"},
                        "preparation_deadline": {"type": "integer", "description": "Days from now to have listings live"},
                        "relevant_product_ideas": {"type": "array", "items": {"type": "string"}, "maxItems": 3}
                    },
                    "required": ["event_name", "days_until", "preparation_deadline", "relevant_product_ideas"]
                }
            },
            "declining_to_deprioritize": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Keywords/trends that are declining and should be removed from listings",
                "maxItems": 5
            },
            "executive_summary": {
                "type": "string",
                "description": "2-3 sentence summary of biggest trend opportunity this week",
                "maxLength": 400
            }
        },
        "required": ["trend_opportunities", "seasonal_calendar", "declining_to_deprioritize", "executive_summary"]
    }
}


def synthesize_trends(
    store_categories: list[str],
    google_trends_data: dict,    # {keyword: {interest_over_time, related_queries}}
    reddit_signals: list[dict],  # [{subreddit, post_title, upvotes, comments}]
    pinterest_data: list[dict],  # [{term, trend_direction, weekly_searches}]
    current_date: str,
) -> dict:
    trends_text = _format_trends_data(google_trends_data, reddit_signals, pinterest_data)

    response = client.messages.create(
        model="claude-fable-5",
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=[{
            "type": "text",
            "text": TREND_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"}
        }],
        messages=[{
            "role": "user",
            "content": f"""Synthesize trend intelligence for an Etsy seller in these categories: {', '.join(store_categories)}.

Current date: {current_date}

## Google Trends Data
{trends_text['google']}

## Reddit Signals (craft/DIY/gifts subreddits)
{trends_text['reddit']}

## Pinterest Trend Data
{trends_text['pinterest']}

Synthesize these signals into actionable opportunities ranked by relevance and time-sensitivity."""
        }],
        tools=[TREND_TOOL],
        tool_choice={"type": "tool", "name": "record_trend_synthesis"},
    )

    for block in response.content:
        if block.type == "tool_use":
            return block.input

    raise ValueError("Trend synthesis tool not called")
```

### 3.4 Content Generator

**When:** Generating optimized listing titles, descriptions, and tags after SEO analysis confirms changes needed. Fable 5 for premium listings; Haiku for bulk.

```python
# prompts/content_generator.py

CONTENT_SYSTEM_PROMPT = """You are a world-class Etsy copywriter specializing in handmade, vintage, and artisan goods. You write listings that rank well in Etsy search AND convert browsers into buyers.

Your writing principles:
- Front-load the most important keyword in the title (first 3 words buyers see in search)
- Use sensory and emotional language that resonates with handmade buyers
- Address the buyer's intent: gift-giving, self-care, home decor, personal style
- Include size, material, color, and customization options naturally in description
- First paragraph of description is searchable on Etsy — make it keyword-rich but readable
- Tags are separate from title: don't duplicate title words in tags unnecessarily
- Etsy character limits: title 140, tags 13 × 20 chars, description no hard limit"""

CONTENT_TOOL = {
    "name": "record_content_variants",
    "description": "Record optimized listing content variants for A/B testing",
    "input_schema": {
        "type": "object",
        "properties": {
            "title_variants": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "maxLength": 140},
                        "primary_keyword": {"type": "string"},
                        "strategy": {"type": "string", "description": "Why this title variant"},
                        "confidence": {"type": "integer", "minimum": 0, "maximum": 100}
                    },
                    "required": ["title", "primary_keyword", "strategy", "confidence"]
                },
                "minItems": 2,
                "maxItems": 3
            },
            "recommended_tags": {
                "type": "array",
                "items": {"type": "string", "maxLength": 20},
                "minItems": 13,
                "maxItems": 13
            },
            "description": {
                "type": "object",
                "properties": {
                    "full_text": {"type": "string", "description": "Complete optimized description"},
                    "first_paragraph": {"type": "string", "description": "First paragraph (keyword-rich, appears in Etsy search snippet)"},
                    "word_count": {"type": "integer"},
                    "keywords_included": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["full_text", "first_paragraph", "word_count", "keywords_included"]
            },
            "best_title_index": {
                "type": "integer",
                "minimum": 0,
                "description": "Index of the recommended title variant (0-based)"
            },
            "personalization_prompt": {
                "type": "string",
                "description": "Optional: text to add to description if listing supports customization"
            }
        },
        "required": ["title_variants", "recommended_tags", "description", "best_title_index"]
    }
}


def generate_listing_content(
    listing: dict,
    seo_analysis: dict,         # output from analyze_listing_seo
    competitor_context: list[dict],
    trending_keywords: list[str],
    brand_voice: str = "warm and artisanal",
) -> dict:
    """
    Generate optimized title, description, and tags.
    Model routing: Fable 5 if listing revenue > threshold, else Haiku.
    """
    revenue_proxy = listing.get("views_count", 0) * listing.get("price_usd", 0)
    model = "claude-fable-5" if revenue_proxy > 5000 else "claude-haiku-4-5"

    # Build context from SEO analysis
    seo_context = f"""
Current Issues Identified:
- Title: {'; '.join(seo_analysis['title_analysis']['issues']) or 'None'}
- Weak tags to replace: {', '.join(seo_analysis['tags_analysis']['weak_tags'][:5])}
- Missing high-value tags: {', '.join(seo_analysis['tags_analysis']['missing_high_value_tags'])}
- Description gaps: {', '.join(seo_analysis['description_analysis']['missing_sections'])}
"""

    response = client.messages.create(
        model=model,
        max_tokens=3000,
        **({"thinking": {"type": "adaptive"}} if model == "claude-fable-5" else {}),
        system=[{
            "type": "text",
            "text": CONTENT_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"}
        }],
        messages=[{
            "role": "user",
            "content": f"""Rewrite this Etsy listing for maximum SEO impact and conversion.

## Current Listing
Title: {listing['title']}
Description (excerpt): {listing.get('description', '')[:600]}
Tags: {', '.join(listing.get('tags', []))}
Price: ${listing.get('price_usd', 0):.2f}
Category: {listing.get('primary_category', 'Unknown')}

## SEO Analysis Results
{seo_context}

## Competitor Successful Keywords (from top-ranking similar listings)
{', '.join([t for c in competitor_context[:3] for t in c.get('tags', [])[:5]])}

## Currently Trending in This Niche
{', '.join(trending_keywords[:10])}

## Brand Voice to Maintain
{brand_voice}

Generate 2-3 title variants plus the full optimized description and complete tag set (exactly 13 tags, each ≤20 chars)."""
        }],
        tools=[CONTENT_TOOL],
        tool_choice={"type": "tool", "name": "record_content_variants"},
    )

    for block in response.content:
        if block.type == "tool_use":
            result = block.input
            # Enforce Etsy constraints before persisting
            assert len(result["recommended_tags"]) == 13, "Must supply exactly 13 tags"
            assert all(len(t) <= 20 for t in result["recommended_tags"]), "Tag exceeds 20 chars"
            assert len(result["title_variants"][result["best_title_index"]]["title"]) <= 140
            return result

    raise ValueError("Content generation tool not called")
```

### 3.5 Image Analyzer

**When:** Flagged listings with low favorites-to-views ratio (<2%). Vision capability of Fable 5.

```python
# prompts/image_analyzer.py
import base64
import httpx

IMAGE_SYSTEM_PROMPT = """You are an expert Etsy product photographer and visual merchandising consultant. You evaluate product photography for its ability to stop the scroll, convey product quality, and drive clicks in the Etsy search grid.

Etsy-specific visual best practices you apply:
- Thumbnail (first image) must be instantly readable at 170×135px (search grid size)
- White or lifestyle backgrounds — lifestyle backgrounds outperform white on non-jewelry categories
- First image should show the complete product (not a detail shot)
- Include scale reference (hand, common object) unless size is obvious
- Multiple angles: front, back, detail, scale, in-use/lifestyle, packaging
- Text overlays on images are allowed and effective for custom/personalized items
- Images count: 10 allowed, 5+ strongly correlated with conversion"""

IMAGE_ANALYSIS_TOOL = {
    "name": "record_image_analysis",
    "description": "Record structured image quality analysis and recommendations",
    "input_schema": {
        "type": "object",
        "properties": {
            "overall_visual_score": {"type": "integer", "minimum": 0, "maximum": 100},
            "thumbnail_effectiveness": {
                "type": "object",
                "properties": {
                    "score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "issues": {"type": "array", "items": {"type": "string"}},
                    "readable_at_small_size": {"type": "boolean"},
                    "recommended_change": {"type": "string"}
                },
                "required": ["score", "issues", "readable_at_small_size", "recommended_change"]
            },
            "image_count": {"type": "integer"},
            "missing_shot_types": {
                "type": "array",
                "items": {"type": "string", "enum": ["lifestyle", "detail", "scale_reference", "back_view", "packaging", "in_use", "flat_lay", "group_variety"]},
                "description": "Shot types that would improve conversion"
            },
            "lighting_quality": {"type": "string", "enum": ["excellent", "good", "needs_improvement", "poor"]},
            "background_recommendation": {"type": "string"},
            "priority_improvements": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "improvement": {"type": "string"},
                        "effort": {"type": "string", "enum": ["easy_edit", "reshoot", "new_props_needed"]},
                        "impact": {"type": "string", "enum": ["high", "medium", "low"]}
                    },
                    "required": ["improvement", "effort", "impact"]
                },
                "maxItems": 5
            }
        },
        "required": ["overall_visual_score", "thumbnail_effectiveness", "image_count", "missing_shot_types", "lighting_quality", "background_recommendation", "priority_improvements"]
    }
}


def analyze_listing_images(listing_id: str, image_urls: list[str]) -> dict:
    """
    Downloads and analyzes listing images using Fable 5 vision.
    Capped at 5 images to control cost.
    """
    image_content = []
    for url in image_urls[:5]:
        img_data = httpx.get(url, timeout=10).content
        b64 = base64.standard_b64encode(img_data).decode()
        image_content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}
        })

    image_content.append({
        "type": "text",
        "text": f"This Etsy listing has {len(image_urls)} total images (showing first {min(5, len(image_urls))}). Analyze the photography quality and provide specific, actionable improvement recommendations."
    })

    response = client.messages.create(
        model="claude-fable-5",
        max_tokens=2048,
        system=[{
            "type": "text",
            "text": IMAGE_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"}
        }],
        messages=[{"role": "user", "content": image_content}],
        tools=[IMAGE_ANALYSIS_TOOL],
        tool_choice={"type": "tool", "name": "record_image_analysis"},
    )

    for block in response.content:
        if block.type == "tool_use":
            return block.input

    raise ValueError("Image analysis tool not called")
```

### 3.6 Pricing Advisor (Haiku)

**When:** Market price range check. High-frequency, low-complexity → Haiku.

```python
# prompts/pricing_advisor.py

PRICING_SYSTEM_PROMPT = """You are a pricing strategist for Etsy sellers. Given market data, recommend optimal price points that maximize revenue while remaining competitive. Consider: price elasticity in handmade markets, perceived value signals, bundle/variant opportunities."""

PRICING_TOOL = {
    "name": "record_pricing_recommendations",
    "description": "Record pricing recommendations for a set of listings",
    "input_schema": {
        "type": "object",
        "properties": {
            "recommendations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "listing_id": {"type": "string"},
                        "current_price": {"type": "number"},
                        "recommended_price": {"type": "number"},
                        "price_direction": {"type": "string", "enum": ["increase", "decrease", "hold"]},
                        "rationale": {"type": "string"},
                        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                        "market_min": {"type": "number"},
                        "market_max": {"type": "number"},
                        "market_median": {"type": "number"}
                    },
                    "required": ["listing_id", "current_price", "recommended_price", "price_direction", "rationale", "confidence", "market_min", "market_max", "market_median"]
                }
            }
        },
        "required": ["recommendations"]
    }
}


def get_pricing_recommendations(
    listings: list[dict],
    competitor_prices: dict[str, list[float]],  # {category: [prices]}
) -> dict:
    listings_text = "\n".join([
        f"ID:{l['id']} Title:{l['title'][:40]} Price:${l['price_usd']:.2f} Category:{l.get('primary_category', 'Unknown')}"
        for l in listings[:20]
    ])

    market_text = "\n".join([
        f"{cat}: min=${min(prices):.2f} max=${max(prices):.2f} median=${sorted(prices)[len(prices)//2]:.2f} (n={len(prices)})"
        for cat, prices in competitor_prices.items()
    ])

    response = client.messages.create(
        model="claude-haiku-4-5",  # Haiku sufficient for pricing logic
        max_tokens=2048,
        system=[{
            "type": "text",
            "text": PRICING_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"}
        }],
        messages=[{
            "role": "user",
            "content": f"""Analyze pricing for these listings against market data:

## Listings
{listings_text}

## Competitor Market Prices by Category
{market_text}

Recommend price changes where there is clear evidence of underpricing (>10% below median) or overpricing (>30% above median with low conversion signals)."""
        }],
        tools=[PRICING_TOOL],
        tool_choice={"type": "tool", "name": "record_pricing_recommendations"},
    )

    for block in response.content:
        if block.type == "tool_use":
            return block.input

    raise ValueError("Pricing recommendation tool not called")
```

### 3.7 Audience Discovery

**When:** Monthly deep-dive on buyer personas and new audience segments. Fable 5.

```python
# prompts/audience_discovery.py

AUDIENCE_SYSTEM_PROMPT = """You are an expert in consumer psychology and audience segmentation for artisan e-commerce. You identify distinct buyer personas for Etsy sellers and map them to specific content strategies, product angles, and platform targeting approaches.

You understand that Etsy buyers are not monolithic: a ceramic mug seller may have distinct buyer segments for 'daily coffee ritual self-care', 'unique gift for foodie friends', 'home decor aesthetic completer', and 'local pottery support'. Each segment needs different messaging."""

AUDIENCE_TOOL = {
    "name": "record_audience_analysis",
    "description": "Record buyer persona and audience targeting analysis",
    "input_schema": {
        "type": "object",
        "properties": {
            "primary_buyer_personas": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "persona_name": {"type": "string", "description": "Short memorable name e.g. 'Gifting Planner'"},
                        "estimated_share_of_buyers": {"type": "integer", "minimum": 0, "maximum": 100, "description": "Estimated % of current buyers"},
                        "primary_motivation": {"type": "string"},
                        "search_keywords": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
                        "price_sensitivity": {"type": "string", "enum": ["low", "medium", "high"]},
                        "seasonality": {"type": "array", "items": {"type": "string"}},
                        "listing_angle_for_this_persona": {"type": "string"},
                        "underserved": {"type": "boolean", "description": "Is this persona currently underserved by the store?"}
                    },
                    "required": ["persona_name", "estimated_share_of_buyers", "primary_motivation", "search_keywords", "price_sensitivity", "seasonality", "listing_angle_for_this_persona", "underserved"]
                },
                "maxItems": 5
            },
            "untapped_segments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "segment_description": {"type": "string"},
                        "entry_point": {"type": "string", "description": "Specific product or angle that would attract this segment"},
                        "estimated_market_size": {"type": "string", "enum": ["small", "medium", "large", "very_large"]}
                    },
                    "required": ["segment_description", "entry_point", "estimated_market_size"]
                },
                "maxItems": 3
            },
            "messaging_recommendations": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific messaging angles to test across listings",
                "maxItems": 5
            }
        },
        "required": ["primary_buyer_personas", "untapped_segments", "messaging_recommendations"]
    }
}


def discover_audiences(
    store_description: str,
    listing_summaries: list[dict],
    analytics_data: dict,          # views, favorites, orders by listing
    reddit_comments: list[str],    # buyer-adjacent subreddit discussions (from RAG)
) -> dict:
    listings_text = "\n".join([
        f"- {l['title'][:50]} | ${l['price_usd']:.2f} | {l['views_count']} views | {l['favorites_count']} faves"
        for l in listing_summaries[:20]
    ])

    response = client.messages.create(
        model="claude-fable-5",
        max_tokens=3000,
        thinking={"type": "adaptive"},
        system=[{
            "type": "text",
            "text": AUDIENCE_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"}
        }],
        messages=[{
            "role": "user",
            "content": f"""Identify buyer personas and audience opportunities for this Etsy store.

## Store Description
{store_description}

## Active Listings
{listings_text}

## Community Signals (Reddit discussions related to this product category)
{chr(10).join(reddit_comments[:10]) if reddit_comments else 'No community data available'}

Identify 3-5 distinct buyer personas and 2-3 untapped audience segments."""
        }],
        tools=[AUDIENCE_TOOL],
        tool_choice={"type": "tool", "name": "record_audience_analysis"},
    )

    for block in response.content:
        if block.type == "tool_use":
            return block.input

    raise ValueError("Audience analysis tool not called")
```

### 3.8 Daily Action Synthesizer

**When:** Once per day, after all Phase 2 analyses complete. Fable 5, adaptive thinking. This is the highest-value AI call in the pipeline.

```python
# prompts/daily_synthesizer.py

SYNTHESIS_SYSTEM_PROMPT = """You are the AI growth strategist for an Etsy seller. You receive daily intelligence reports from multiple analysis agents (SEO, competitors, trends, pricing) and synthesize them into a single prioritized action plan.

Your synthesis principles:
- Prioritize actions by ROI: highest impact × lowest effort first
- Surface conflicts between analyses (e.g., SEO recommends one keyword, trends show it declining)
- Group related actions to minimize context-switching for the seller
- Distinguish between "do today" (30 min), "do this week" (1-2 hrs), and "strategic" (multi-day)
- Keep total "do today" actions ≤5 — seller time is the bottleneck
- Credit costs matter: only recommend AI-assisted rewrites for high-revenue listings"""

SYNTHESIS_TOOL = {
    "name": "record_daily_synthesis",
    "description": "Record the synthesized daily action plan",
    "input_schema": {
        "type": "object",
        "properties": {
            "headline_insight": {
                "type": "string",
                "description": "The single most important insight from today's analysis, ≤ 160 chars",
                "maxLength": 160
            },
            "do_today": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "action_title": {"type": "string", "maxLength": 80},
                        "action_type": {"type": "string", "enum": ["update_listing", "update_price", "update_photos", "add_listing", "review_optimization"]},
                        "listing_id": {"type": "string", "description": "UUID if action is listing-specific, null otherwise"},
                        "estimated_time_minutes": {"type": "integer"},
                        "expected_impact": {"type": "string"},
                        "instructions": {"type": "string", "description": "Step-by-step what to do"},
                        "source_analyses": {"type": "array", "items": {"type": "string", "enum": ["seo", "competitor", "trend", "pricing", "image"]}}
                    },
                    "required": ["action_title", "action_type", "estimated_time_minutes", "expected_impact", "instructions", "source_analyses"]
                },
                "maxItems": 5
            },
            "this_week": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "action_title": {"type": "string"},
                        "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                        "rationale": {"type": "string"}
                    },
                    "required": ["action_title", "priority", "rationale"]
                },
                "maxItems": 7
            },
            "strategic": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "initiative": {"type": "string"},
                        "time_horizon": {"type": "string", "enum": ["2_weeks", "1_month", "quarter"]}
                    },
                    "required": ["initiative", "time_horizon"]
                },
                "maxItems": 3
            },
            "store_health_score": {
                "type": "object",
                "properties": {
                    "overall": {"type": "integer", "minimum": 0, "maximum": 100},
                    "seo_score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "competitive_position_score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "trend_alignment_score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "trend_vs_yesterday": {"type": "string", "enum": ["up", "down", "stable"]}
                },
                "required": ["overall", "seo_score", "competitive_position_score", "trend_alignment_score", "trend_vs_yesterday"]
            },
            "optimizations_to_review": {
                "type": "array",
                "description": "IDs of listing_optimization records pending user approval",
                "items": {"type": "string"}
            }
        },
        "required": ["headline_insight", "do_today", "this_week", "strategic", "store_health_score", "optimizations_to_review"]
    }
}


def synthesize_daily_intelligence(
    seo_results: dict,
    competitor_results: dict,
    trend_results: dict,
    pricing_results: dict,
    store_context: dict,
    yesterday_score: int | None,
) -> dict:
    response = client.messages.create(
        model="claude-fable-5",
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=[{
            "type": "text",
            "text": SYNTHESIS_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"}
        }],
        messages=[{
            "role": "user",
            "content": f"""Synthesize today's intelligence reports into a prioritized action plan.

## Store Context
Shop: {store_context.get('shop_name', 'Unknown')}
Active Listings: {store_context.get('active_listing_count', 0)}
Yesterday's Store Health Score: {yesterday_score or 'No prior data'}

## SEO Analysis Summary
Listings analyzed: {len(seo_results.get('seo_results', []))}
Critical issues: {sum(1 for r in seo_results.get('seo_results', []) if r.get('priority') == 'critical')}
Average SEO score: {sum(r.get('overall_score', 0) for r in seo_results.get('seo_results', [])) // max(1, len(seo_results.get('seo_results', [])))}
Top SEO opportunities: {_extract_top_seo_issues(seo_results)}

## Competitor Intelligence Summary
Market position: {competitor_results.get('market_position', {}).get('positioning', 'unknown')}
Key gaps: {'; '.join(competitor_results.get('content_gaps', [])[:3])}
Quick wins available: {len(competitor_results.get('quick_wins', []))}

## Trend Intelligence Summary
{trend_results.get('executive_summary', 'No trend data')}
Emerging opportunities: {', '.join(t['trend_name'] for t in trend_results.get('trend_opportunities', []) if t.get('lifecycle_stage') == 'emerging')[:3]}
Declining to remove: {', '.join(trend_results.get('declining_to_deprioritize', [])[:3])}

## Pricing Intelligence Summary
Listings needing price changes: {sum(1 for r in pricing_results.get('recommendations', []) if r.get('price_direction') != 'hold')}
Underpriced listings: {sum(1 for r in pricing_results.get('recommendations', []) if r.get('price_direction') == 'increase')}

Synthesize these into the prioritized daily action plan. The seller has approximately 30-60 minutes today."""
        }],
        tools=[SYNTHESIS_TOOL],
        tool_choice={"type": "tool", "name": "record_daily_synthesis"},
    )

    for block in response.content:
        if block.type == "tool_use":
            return block.input

    raise ValueError("Daily synthesis tool not called")
```

### 3.9 Weekly Report Generator

**When:** Every Sunday. Fable 5, no streaming (full doc generation).

```python
# prompts/weekly_report.py

WEEKLY_REPORT_SYSTEM_PROMPT = """You are a growth analytics writer for e-commerce businesses. You produce clear, data-driven weekly performance summaries that help sellers understand what's working, what isn't, and what to focus on next week. You write for busy people: lead with the most important insight, use numbers, avoid vague statements."""

WEEKLY_REPORT_TOOL = {
    "name": "record_weekly_report",
    "description": "Record a structured weekly performance report",
    "input_schema": {
        "type": "object",
        "properties": {
            "week_headline": {"type": "string", "description": "One sentence summary of the week", "maxLength": 200},
            "key_metrics": {
                "type": "object",
                "properties": {
                    "total_views": {"type": "integer"},
                    "total_favorites": {"type": "integer"},
                    "estimated_orders": {"type": "integer"},
                    "avg_store_health_score": {"type": "integer"},
                    "views_vs_prior_week_pct": {"type": "number"},
                    "top_performing_listing": {"type": "string"},
                    "worst_performing_listing": {"type": "string"}
                },
                "required": ["total_views", "total_favorites", "estimated_orders", "avg_store_health_score", "views_vs_prior_week_pct", "top_performing_listing", "worst_performing_listing"]
            },
            "what_worked": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific actions taken that had measurable positive impact",
                "maxItems": 5
            },
            "what_didnt_work": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Changes made or opportunities missed that didn't pay off",
                "maxItems": 3
            },
            "next_week_priorities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "priority": {"type": "string"},
                        "why_now": {"type": "string"},
                        "success_metric": {"type": "string"}
                    },
                    "required": ["priority", "why_now", "success_metric"]
                },
                "maxItems": 3
            },
            "narrative_summary": {
                "type": "string",
                "description": "2-3 paragraph human-readable summary of the week",
                "maxLength": 1200
            }
        },
        "required": ["week_headline", "key_metrics", "what_worked", "what_didnt_work", "next_week_priorities", "narrative_summary"]
    }
}
```

### 3.10 Monthly Strategic Planner

**When:** First of each month. Fable 5, maximum effort, longest context.

```python
# prompts/monthly_planner.py

MONTHLY_PLAN_SYSTEM_PROMPT = """You are a senior e-commerce growth strategist. Given 30 days of store performance data, market trends, and competitive intelligence, you produce a 30-day strategic growth plan with specific, measurable objectives.

You think in terms of: (1) quick revenue recovery if metrics are down, (2) market-share expansion if metrics are strong, (3) portfolio optimization (add/remove listings), (4) seasonal preparation."""

MONTHLY_PLAN_TOOL = {
    "name": "record_monthly_plan",
    "description": "Record a 30-day strategic growth plan",
    "input_schema": {
        "type": "object",
        "properties": {
            "month_theme": {"type": "string", "description": "Strategic focus for the month, ≤ 80 chars", "maxLength": 80},
            "growth_goal": {
                "type": "object",
                "properties": {
                    "target_metric": {"type": "string", "enum": ["views", "favorites", "conversion_rate", "revenue", "new_listings"]},
                    "current_value": {"type": "number"},
                    "target_value": {"type": "number"},
                    "rationale": {"type": "string"}
                },
                "required": ["target_metric", "current_value", "target_value", "rationale"]
            },
            "week_by_week_plan": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "week_number": {"type": "integer", "minimum": 1, "maximum": 4},
                        "theme": {"type": "string"},
                        "primary_tasks": {"type": "array", "items": {"type": "string"}, "maxItems": 4}
                    },
                    "required": ["week_number", "theme", "primary_tasks"]
                },
                "minItems": 4,
                "maxItems": 4
            },
            "listings_to_add": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "product_idea": {"type": "string"},
                        "target_keyword": {"type": "string"},
                        "opportunity_rationale": {"type": "string"}
                    },
                    "required": ["product_idea", "target_keyword", "opportunity_rationale"]
                },
                "maxItems": 5
            },
            "listings_to_retire": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "listing_title_fragment": {"type": "string"},
                        "reason": {"type": "string"}
                    },
                    "required": ["listing_title_fragment", "reason"]
                }
            },
            "risk_factors": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Market or operational risks to monitor this month",
                "maxItems": 3
            }
        },
        "required": ["month_theme", "growth_goal", "week_by_week_plan", "listings_to_add", "listings_to_retire", "risk_factors"]
    }
}
```

---

## 4. RAG Architecture for Competitor Data

### 4.1 Pipeline Overview

```
Data Sources                     Processing                    Storage & Retrieval
────────────                     ──────────                    ───────────────────
Etsy API competitor              Text extraction               PostgreSQL (pgvector)
listings (titles,                    │                              │
tags, descriptions) ─────────► Chunking & cleaning ──────► embeddings table
                                     │                         (vector 1024-dim)
Reddit discussions ──────────► Metadata tagging ─────────►       │
                                     │                            │
Google Trends ───────────────► voyage-3 embedding ────────► ivfflat index
                                     │                            │
Trend reports ───────────────► content_hash check ────────► cosine similarity
                                                               search at query time
                                                                    │
                                                                    ▼
                                                           Top-k results injected
                                                           into AI prompt context
```

### 4.2 Document Chunking Strategy

```python
# services/rag/chunker.py
from dataclasses import dataclass
from typing import Literal
import hashlib
import json
import re

CHUNK_SIZES = {
    "listing": 512,          # Title + description + tags — keep as single chunk
    "trend_report": 512,     # Paragraph-level chunks
    "reddit_thread": 256,    # Post-level chunks
    "competitor_shop": 384,  # Shop description + top listing summaries
}

CHUNK_OVERLAP = 64  # tokens, for trend/reddit paragraph chunks


@dataclass
class DocumentChunk:
    entity_type: Literal["listing", "competitor_listing", "trend_report", "reddit_thread"]
    entity_id: str          # UUID of source record
    chunk_index: int
    content_text: str       # text that was embedded
    content_hash: str       # SHA-256 for staleness detection
    metadata: dict          # searchable filter metadata


def chunk_competitor_listing(listing: dict) -> list[DocumentChunk]:
    """
    A competitor listing is one chunk.
    Concatenate: title + tags (comma-joined) + first 400 chars of description.
    This keeps semantic context intact and fits within embedding limits.
    """
    tags_str = ", ".join(listing.get("tags", []))
    desc_excerpt = listing.get("description", "")[:400].strip()

    text = f"Title: {listing['title']}\nTags: {tags_str}\nDescription: {desc_excerpt}"

    content_hash = hashlib.sha256(text.encode()).hexdigest()

    return [DocumentChunk(
        entity_type="competitor_listing",
        entity_id=listing["id"],
        chunk_index=0,
        content_text=text,
        content_hash=content_hash,
        metadata={
            "shop_id": listing.get("shop_id"),
            "category": listing.get("primary_category"),
            "price_usd": listing.get("price"),
            "views": listing.get("views", 0),
            "favorites": listing.get("favorites", 0),
            "tags": listing.get("tags", []),
        }
    )]


def chunk_trend_report(report: dict) -> list[DocumentChunk]:
    """
    Trend reports are chunked by paragraph with 64-token overlap.
    Each chunk carries the report date and category for temporal filtering.
    """
    paragraphs = re.split(r'\n{2,}', report["content"].strip())
    chunks = []

    for i, para in enumerate(paragraphs):
        if len(para.split()) < 20:  # skip very short paragraphs
            continue

        # Add overlap: append first 64 tokens of next paragraph
        overlap = ""
        if i + 1 < len(paragraphs):
            next_words = paragraphs[i + 1].split()[:CHUNK_OVERLAP]
            overlap = " " + " ".join(next_words)

        text = para + overlap
        content_hash = hashlib.sha256(text.encode()).hexdigest()

        chunks.append(DocumentChunk(
            entity_type="trend_report",
            entity_id=report["id"],
            chunk_index=i,
            content_text=text,
            content_hash=content_hash,
            metadata={
                "category": report.get("category"),
                "report_date": report.get("created_at"),
                "source": report.get("source"),  # google_trends|reddit|pinterest
            }
        ))

    return chunks
```

### 4.3 Embedding Generation

```python
# services/rag/embedder.py
import voyageai
from anthropic import Anthropic
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Primary: voyage-3 (1024-dim, optimized for retrieval)
# Fallback: text-embedding-3-small via OpenAI (1536-dim, higher cost)
voyage_client = voyageai.Client()


def embed_chunks(
    chunks: list[DocumentChunk],
    batch_size: int = 128,
) -> list[tuple[DocumentChunk, list[float]]]:
    """
    Batch embed chunks using voyage-3.
    Returns list of (chunk, embedding_vector) pairs.
    voyage-3 produces 1024-dim vectors, matches our pgvector schema.
    """
    results = []

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        texts = [c.content_text for c in batch]

        try:
            response = voyage_client.embed(
                texts,
                model="voyage-3",
                input_type="document",  # "document" for indexing, "query" for search
            )
            embeddings = response.embeddings  # list of 1024-dim float lists
            results.extend(zip(batch, embeddings))

        except voyageai.error.RateLimitError:
            logger.warning("voyage-3 rate limit hit, sleeping 5s")
            import time; time.sleep(5)
            # Retry once
            response = voyage_client.embed(texts, model="voyage-3", input_type="document")
            results.extend(zip(batch, response.embeddings))

    return results


def embed_query(query_text: str) -> list[float]:
    """Embed a search query. Must use input_type='query' for asymmetric retrieval."""
    response = voyage_client.embed(
        [query_text],
        model="voyage-3",
        input_type="query",
    )
    return response.embeddings[0]
```

### 4.4 pgvector Storage

```python
# services/rag/vector_store.py
from app.db.session import get_db_session
import json


def upsert_embeddings(chunk_embedding_pairs: list[tuple[DocumentChunk, list[float]]]):
    """
    Upsert embeddings using content_hash for staleness detection.
    Skip if hash unchanged (no re-embedding needed).
    """
    with get_db_session() as db:
        for chunk, embedding in chunk_embedding_pairs:
            db.execute("""
                INSERT INTO embeddings (
                    entity_type, entity_id, chunk_index,
                    content_text, content_hash, embedding, metadata
                )
                VALUES (
                    :entity_type, :entity_id, :chunk_index,
                    :content_text, :content_hash, :embedding::vector, :metadata
                )
                ON CONFLICT (entity_id, chunk_index) DO UPDATE SET
                    content_text = EXCLUDED.content_text,
                    content_hash = EXCLUDED.content_hash,
                    embedding = EXCLUDED.embedding,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
                WHERE embeddings.content_hash != EXCLUDED.content_hash
                -- skip update if content unchanged (hash match = no re-embedding)
            """, {
                "entity_type": chunk.entity_type,
                "entity_id": chunk.entity_id,
                "chunk_index": chunk.chunk_index,
                "content_text": chunk.content_text,
                "content_hash": chunk.content_hash,
                "embedding": f"[{','.join(map(str, embedding))}]",
                "metadata": json.dumps(chunk.metadata),
            })


def retrieve_similar_listings(
    query: str,
    category: Optional[str] = None,
    limit: int = 5,
    min_similarity: float = 0.7,
) -> list[dict]:
    """
    Retrieve top-k similar competitor listings using cosine similarity.
    Filters by category metadata if provided for precision.
    Uses ivfflat approximate nearest neighbor — orders of magnitude faster
    than exact search at >10k vectors.
    """
    query_embedding = embed_query(query)

    # ivfflat probes: higher = more accurate, slower
    # 10 probes balances speed and recall at our data scale
    with get_db_session() as db:
        db.execute("SET LOCAL ivfflat.probes = 10")

        results = db.execute("""
            SELECT
                e.entity_id,
                e.content_text,
                e.metadata,
                1 - (e.embedding <=> :query_embedding::vector) AS similarity
            FROM embeddings e
            WHERE e.entity_type = 'competitor_listing'
              AND (
                  :category IS NULL
                  OR e.metadata->>'category' = :category
              )
              AND 1 - (e.embedding <=> :query_embedding::vector) >= :min_similarity
            ORDER BY e.embedding <=> :query_embedding::vector  -- cosine distance
            LIMIT :limit
        """, {
            "query_embedding": f"[{','.join(map(str, query_embedding))}]",
            "category": category,
            "min_similarity": min_similarity,
            "limit": limit,
        }).fetchall()

    return [
        {
            "entity_id": str(r.entity_id),
            "content_text": r.content_text,
            "similarity": round(r.similarity, 3),
            **r.metadata,
        }
        for r in results
    ]
```

### 4.5 RAG Context Injection Pattern

```python
# services/rag/context_builder.py


def build_seo_rag_context(listing: dict) -> dict:
    """
    For a given listing, retrieve relevant competitor context and trend context
    to inject into the SEO analyzer prompt.
    """
    # Query embedding: represent the listing as a search query
    query = f"{listing['title']} {' '.join(listing.get('tags', [])[:5])}"

    # Retrieve similar competitors
    similar_competitors = retrieve_similar_listings(
        query=query,
        category=listing.get("primary_category"),
        limit=5,
        min_similarity=0.65,  # lower threshold for broader context
    )

    # Retrieve trending keyword context
    trend_context = retrieve_similar_listings(
        query=f"trending keywords {listing.get('primary_category', '')} {listing.get('title', '')[:30]}",
        limit=3,
        min_similarity=0.6,
    )

    # Extract trending keywords from trend chunk text
    trending_keywords = _extract_keywords_from_trend_chunks(
        [t["content_text"] for t in trend_context]
    )

    return {
        "competitor_context": similar_competitors,
        "trending_keywords": trending_keywords,
    }


def _extract_keywords_from_trend_chunks(texts: list[str]) -> list[str]:
    """Haiku call to extract keywords from trend text (cheap extraction task)."""
    if not texts:
        return []

    combined = "\n".join(texts[:3])

    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=256,
        tools=[{
            "name": "extract_keywords",
            "description": "Extract trending search keywords",
            "input_schema": {
                "type": "object",
                "properties": {
                    "keywords": {"type": "array", "items": {"type": "string"}, "maxItems": 20}
                },
                "required": ["keywords"]
            }
        }],
        tool_choice={"type": "tool", "name": "extract_keywords"},
        messages=[{
            "role": "user",
            "content": f"Extract the 10-20 most relevant search keywords from this trend text:\n\n{combined}"
        }],
    )

    for block in response.content:
        if block.type == "tool_use":
            return block.input["keywords"]

    return []
```

---

## 5. Embeddings Strategy

### 5.1 Content Types and Dimensions

| Content Type | Chunk Strategy | Typical Tokens | Update Trigger |
|---|---|---|---|
| Competitor listing | Single chunk (title + tags + desc[:400]) | 100–180 | content_hash change |
| Own listing | Single chunk (title + tags + desc[:400]) | 100–180 | content_hash change |
| Trend report paragraph | 512 tokens + 64 overlap | 512–576 | New report created |
| Reddit discussion post | Single chunk (title + body[:600]) | 150–200 | New post ingested |
| Shop policy text | Paragraph chunks | 128–256 | Shop update |

### 5.2 Model Selection

```python
# config/embedding_config.py
from enum import Enum

class EmbeddingModel(str, Enum):
    VOYAGE_3 = "voyage-3"               # 1024-dim, primary — best Etsy retrieval quality
    VOYAGE_3_LITE = "voyage-3-lite"     # 512-dim, 2x faster, 60% cheaper — bulk competitor scans

# Routing policy
def select_embedding_model(entity_type: str, batch_size: int) -> EmbeddingModel:
    if entity_type in ("listing", "competitor_listing") and batch_size <= 100:
        return EmbeddingModel.VOYAGE_3          # quality matters for SEO/competitor retrieval
    elif batch_size > 100:
        return EmbeddingModel.VOYAGE_3_LITE     # bulk: 100+ items, use lite
    else:
        return EmbeddingModel.VOYAGE_3

# Embedding dimensions by model — must match pgvector column
EMBEDDING_DIMS = {
    EmbeddingModel.VOYAGE_3: 1024,
    EmbeddingModel.VOYAGE_3_LITE: 512,
}
```

**Note:** pgvector column is `vector(1024)`. If using voyage-3-lite (512-dim), pad or use a separate embeddings table with `vector(512)` and a different ivfflat index. MVP should standardize on voyage-3/1024 for simplicity.

### 5.3 Staleness Detection and Re-embedding

```python
# services/rag/staleness.py
import hashlib
import json
from app.db.session import get_db_session


def get_stale_entity_ids(entity_type: str, candidate_ids: list[str]) -> list[str]:
    """
    Returns IDs from candidate_ids that either have no embedding or
    have a content_hash mismatch with the current DB record.
    """
    with get_db_session() as db:
        # Get current embeddings
        existing = db.execute("""
            SELECT entity_id, content_hash FROM embeddings
            WHERE entity_type = :entity_type
              AND entity_id = ANY(:ids)
        """, {"entity_type": entity_type, "ids": candidate_ids}).fetchall()

    existing_hashes = {str(r.entity_id): r.content_hash for r in existing}

    # Compute current hashes
    source_records = _fetch_source_records(entity_type, candidate_ids)
    stale_ids = []

    for record in source_records:
        current_hash = _compute_content_hash(record, entity_type)
        stored_hash = existing_hashes.get(str(record["id"]))

        if stored_hash is None or stored_hash != current_hash:
            stale_ids.append(str(record["id"]))

    return stale_ids


def _compute_content_hash(record: dict, entity_type: str) -> str:
    if entity_type in ("listing", "competitor_listing"):
        content = {
            "title": record.get("title", ""),
            "description": (record.get("description") or "")[:400],
            "tags": sorted(record.get("tags") or []),
        }
    elif entity_type == "trend_report":
        content = {"content": record.get("content", "")}
    else:
        content = record

    return hashlib.sha256(
        json.dumps(content, sort_keys=True).encode()
    ).hexdigest()
```

### 5.4 Index Management

```sql
-- pgvector index strategy
-- ivfflat: fast approximate search, good up to ~2M vectors
-- lists parameter: sqrt(row_count) is the standard heuristic
--   * 100 lists for 10K vectors
--   * 316 lists for 100K vectors
--   * 1000 lists for 1M vectors

-- Current index (MVP, assumes <100K competitor listings)
CREATE INDEX idx_embeddings_vector
ON embeddings USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Search-time: SET LOCAL ivfflat.probes = 10;
-- probes × lists = fraction of index searched
-- 10/100 = 10% of index — fast + good recall for our data scale

-- When to migrate to HNSW:
--   ivfflat degrades when filtering by metadata (must post-filter)
--   hnsw supports pre-filtering natively
--   Migrate at >500K vectors or when recall drops below 85%

-- HNSW migration (no rebuild needed — just add new index, drop old):
-- CREATE INDEX idx_embeddings_hnsw
-- ON embeddings USING hnsw (embedding vector_cosine_ops)
-- WITH (m = 16, ef_construction = 64);
```

### 5.5 Embedding Update Celery Task

```python
# tasks/embeddings.py

@celery.task(name="tasks.update_embeddings", queue="bulk")
def update_embeddings_task(ctx: dict):
    """
    Runs after daily sync. Re-embeds only changed records.
    Operates in batches to respect voyage-3 rate limits.
    """
    store_id = ctx["store_id"]
    run_id = ctx["run_id"]

    # Get all active listing IDs for this store
    with get_db_session() as db:
        listing_ids = [str(r.id) for r in db.execute(
            "SELECT id FROM listings WHERE store_id = :sid AND state = 'active'",
            {"sid": store_id}
        ).fetchall()]

        # Get recent competitor listing IDs (scanned in last 24h)
        competitor_ids = [str(r.id) for r in db.execute(
            """SELECT id FROM competitor_listings
               WHERE last_seen_at > NOW() - INTERVAL '24 hours'""",
        ).fetchall()]

    stale_listing_ids = get_stale_entity_ids("listing", listing_ids)
    stale_competitor_ids = get_stale_entity_ids("competitor_listing", competitor_ids)

    all_stale = [("listing", stale_listing_ids), ("competitor_listing", stale_competitor_ids)]
    total_embedded = 0

    for entity_type, stale_ids in all_stale:
        if not stale_ids:
            continue

        records = _fetch_source_records(entity_type, stale_ids)
        chunks = []
        for record in records:
            if entity_type == "listing":
                chunks.extend(chunk_competitor_listing(record))  # same structure
            else:
                chunks.extend(chunk_competitor_listing(record))

        # Batch embed (voyage-3 rate limit: 300 RPM, batch up to 128)
        chunk_embeddings = embed_chunks(chunks, batch_size=128)
        upsert_embeddings(chunk_embeddings)
        total_embedded += len(chunks)

    # Log to agent_run
    _log_embedding_stats(run_id, total_embedded)
    return {"embeddings_updated": total_embedded}
```

---

## 6. API Rate Limits & Cost Management

### 6.1 Per-Provider Rate Limits

| Provider | Limit | Scope | Handling Strategy |
|---|---|---|---|
| Etsy API v3 | 10 req/sec | Per OAuth token | Redis token bucket (Lua atomic), per-store |
| Anthropic (Fable 5) | ~2,000 RPM | Account-wide | Client retry with exponential backoff |
| Anthropic (Haiku 4.5) | ~4,000 RPM | Account-wide | Client retry with exponential backoff |
| voyage-3 | 300 RPM | Account-wide | Batch up to 128 texts per request |
| Reddit API | 60 req/min | Per OAuth app | Sleep between requests, cache results 4h |
| Google Trends (pytrends) | Unofficial, ~30 req/hr | IP-based | Rate limit + 5s delay, cache results 12h |
| Pinterest API | 1,000 req/day | Per app | Cache results 24h, batch queries |
| SendGrid | 600 emails/min | Account | Async batch sending |

### 6.2 Etsy Rate Limiter (Redis Token Bucket)

```python
# services/rate_limiter.py — Etsy token bucket, 10 req/sec per store
import redis
import time

ETSY_RATE_LIMIT_LUA = """
local key = KEYS[1]
local rate = tonumber(ARGV[1])     -- 10 req/sec
local capacity = tonumber(ARGV[2]) -- burst capacity = 20
local now = tonumber(ARGV[3])      -- current time as float
local cost = tonumber(ARGV[4])     -- tokens to consume (usually 1)

local last_time = tonumber(redis.call('HGET', key, 'last_time') or now)
local tokens = tonumber(redis.call('HGET', key, 'tokens') or capacity)

-- Refill tokens based on elapsed time
local elapsed = math.max(0, now - last_time)
tokens = math.min(capacity, tokens + elapsed * rate)
last_time = now

if tokens >= cost then
    tokens = tokens - cost
    redis.call('HSET', key, 'tokens', tokens, 'last_time', last_time)
    redis.call('EXPIRE', key, 60)
    return 1  -- allowed
else
    redis.call('HSET', key, 'tokens', tokens, 'last_time', last_time)
    redis.call('EXPIRE', key, 60)
    return 0  -- denied, caller must wait
end
"""

_lua_script = None


def _get_lua_script(r: redis.Redis):
    global _lua_script
    if _lua_script is None:
        _lua_script = r.register_script(ETSY_RATE_LIMIT_LUA)
    return _lua_script


def acquire_etsy_token(r: redis.Redis, store_id: str, cost: int = 1) -> bool:
    key = f"rate:etsy:{store_id}"
    script = _get_lua_script(r)
    result = script(
        keys=[key],
        args=[10, 20, time.time(), cost]  # 10 req/sec, burst 20
    )
    return bool(result)


async def wait_for_etsy_token(r: redis.Redis, store_id: str, max_wait: float = 5.0):
    """Async wait for rate limit token with backoff."""
    start = time.time()
    wait = 0.1
    while time.time() - start < max_wait:
        if acquire_etsy_token(r, store_id):
            return
        await asyncio.sleep(wait)
        wait = min(wait * 1.5, 1.0)
    raise TimeoutError(f"Etsy rate limit wait exceeded {max_wait}s for store {store_id}")
```

### 6.3 AI Cost Table per Operation

| Operation | Model | Avg Input Tokens | Avg Output Tokens | Cost per Call | Frequency |
|---|---|---|---|---|---|
| SEO analysis (deep) | Fable 5 | 2,500 | 800 | $0.065 | 5-20 listings/day |
| SEO quick scan | Haiku 4.5 | 400 | 150 | $0.001 | 20 listings/day |
| Competitor analysis | Fable 5 | 3,000 | 600 | $0.060 | 1/day/category |
| Trend synthesis | Fable 5 | 2,800 | 700 | $0.063 | 1/day |
| Content generation (premium) | Fable 5 | 1,500 | 900 | $0.060 | 2-5 listings/day |
| Content generation (standard) | Haiku 4.5 | 800 | 600 | $0.004 | 5-10 listings/day |
| Image analysis | Fable 5 | 1,000 + images | 500 | $0.035 | 2-3 listings/day |
| Pricing advisor | Haiku 4.5 | 600 | 300 | $0.002 | 1/day |
| Audience discovery | Fable 5 | 2,000 | 800 | $0.060 | 1/month |
| Daily synthesis | Fable 5 | 3,500 | 1,200 | $0.095 | 1/day |
| Weekly report | Fable 5 | 4,000 | 1,500 | $0.115 | 1/week |
| Monthly plan | Fable 5 | 5,000 | 2,000 | $0.150 | 1/month |
| Keyword extraction | Haiku 4.5 | 300 | 100 | $0.0008 | 5-10/day |

**Estimated daily AI cost per store:** $0.40–$0.85 (typical), $1.20 (heavy analysis day with images)

**Embedding cost (voyage-3):** ~$0.06 per 1M tokens. 50 listings × 150 tokens = 7,500 tokens/day = $0.0005/day.

### 6.4 Credit System: Cost Per Credit

```python
# Mapping from credits consumed to USD cost
# Credits are sold to users at margin; internal cost is what we pay to AI providers

CREDITS_PER_OPERATION = {
    "daily_agent_run": 5,           # full daily run = 5 credits ($0.50 at 10¢/credit)
    "seo_analysis_deep": 2,         # manual deep SEO for one listing
    "seo_analysis_quick": 0,        # included in daily run, no extra charge
    "content_generation": 1,        # per listing content rewrite
    "competitor_analysis": 2,       # per-category competitive intelligence
    "image_analysis": 1,            # per listing image review
    "trend_report": 1,              # on-demand trend fetch
    "weekly_report": 3,             # weekly digest
    "monthly_plan": 5,              # monthly strategic plan
}

# User pricing: 50 credits = $9.99/mo (Starter), 200 = $29.99/mo (Growth)
# Internal AI cost per credit: ~$0.08 (leaves ~20% margin after overhead)
```

### 6.5 Response Caching

```python
# services/cache/ai_cache.py
import hashlib
import json
import redis

def get_cached_ai_response(
    r: redis.Redis,
    cache_key_components: dict,
    ttl_seconds: int = 21600,  # 6 hours default
) -> dict | None:
    """
    Cache AI responses by content hash of inputs.
    Avoids re-analyzing listings that haven't changed.
    """
    key_str = json.dumps(cache_key_components, sort_keys=True)
    cache_key = f"ai_cache:{hashlib.sha256(key_str.encode()).hexdigest()}"
    cached = r.get(cache_key)
    if cached:
        return json.loads(cached)
    return None


def set_cached_ai_response(
    r: redis.Redis,
    cache_key_components: dict,
    response: dict,
    ttl_seconds: int = 21600,
):
    key_str = json.dumps(cache_key_components, sort_keys=True)
    cache_key = f"ai_cache:{hashlib.sha256(key_str.encode()).hexdigest()}"
    r.setex(cache_key, ttl_seconds, json.dumps(response))


# Usage in SEO analysis: cache by (listing_id, content_hash, competitor_hash)
def cached_seo_analysis(listing: dict, competitor_context: list[dict]) -> dict:
    cache_components = {
        "type": "seo",
        "listing_content_hash": listing["content_hash"],
        "competitor_hash": hashlib.sha256(
            json.dumps([c["entity_id"] for c in competitor_context[:5]], sort_keys=True).encode()
        ).hexdigest(),
    }

    cached = get_cached_ai_response(redis_client, cache_components)
    if cached:
        return cached  # skip AI call entirely

    result = analyze_listing_seo(listing, competitor_context, [])
    set_cached_ai_response(redis_client, cache_components, result)
    return result
```

**Cache hit rates (expected):**
- SEO analysis: ~60% hit rate (listings don't change daily)
- Competitor analysis: ~40% hit rate (new competitors discovered)
- Trend synthesis: ~0% (fresh data each day by design)
- Content generation: 0% (always new on request)

### 6.6 Model Routing Decision Tree

```python
# services/ai/model_router.py
from enum import Enum

class AITask(str, Enum):
    SEO_DEEP = "seo_deep"
    SEO_QUICK = "seo_quick"
    COMPETITOR_ANALYSIS = "competitor_analysis"
    TREND_SYNTHESIS = "trend_synthesis"
    CONTENT_GENERATION_PREMIUM = "content_gen_premium"
    CONTENT_GENERATION_STANDARD = "content_gen_standard"
    IMAGE_ANALYSIS = "image_analysis"
    PRICING_ADVISOR = "pricing_advisor"
    DAILY_SYNTHESIS = "daily_synthesis"
    WEEKLY_REPORT = "weekly_report"
    MONTHLY_PLAN = "monthly_plan"
    KEYWORD_EXTRACTION = "keyword_extraction"
    AUDIENCE_DISCOVERY = "audience_discovery"


MODEL_ROUTING: dict[AITask, str] = {
    # Fable 5: complex reasoning, synthesis, generation, vision
    AITask.SEO_DEEP: "claude-fable-5",
    AITask.COMPETITOR_ANALYSIS: "claude-fable-5",
    AITask.TREND_SYNTHESIS: "claude-fable-5",
    AITask.CONTENT_GENERATION_PREMIUM: "claude-fable-5",
    AITask.IMAGE_ANALYSIS: "claude-fable-5",
    AITask.DAILY_SYNTHESIS: "claude-fable-5",
    AITask.WEEKLY_REPORT: "claude-fable-5",
    AITask.MONTHLY_PLAN: "claude-fable-5",
    AITask.AUDIENCE_DISCOVERY: "claude-fable-5",

    # Haiku 4.5: classification, extraction, bulk, low-stakes
    AITask.SEO_QUICK: "claude-haiku-4-5",
    AITask.CONTENT_GENERATION_STANDARD: "claude-haiku-4-5",
    AITask.PRICING_ADVISOR: "claude-haiku-4-5",
    AITask.KEYWORD_EXTRACTION: "claude-haiku-4-5",
}

THINKING_BY_TASK: dict[AITask, bool] = {
    # Adaptive thinking enabled for tasks requiring judgment
    AITask.SEO_DEEP: True,
    AITask.COMPETITOR_ANALYSIS: True,
    AITask.TREND_SYNTHESIS: True,
    AITask.CONTENT_GENERATION_PREMIUM: True,
    AITask.DAILY_SYNTHESIS: True,
    AITask.WEEKLY_REPORT: True,
    AITask.MONTHLY_PLAN: True,
    AITask.AUDIENCE_DISCOVERY: True,

    # No thinking for extraction/classification tasks
    AITask.SEO_QUICK: False,
    AITask.CONTENT_GENERATION_STANDARD: False,
    AITask.IMAGE_ANALYSIS: False,       # vision tasks: thinking adds latency with minimal benefit
    AITask.PRICING_ADVISOR: False,
    AITask.KEYWORD_EXTRACTION: False,
}


def get_model_config(task: AITask) -> dict:
    model = MODEL_ROUTING[task]
    use_thinking = THINKING_BY_TASK.get(task, False)

    config = {"model": model}
    if use_thinking:
        config["thinking"] = {"type": "adaptive"}
    return config
```

### 6.7 Credit Reservation and Settlement

```python
# services/credit_service.py
import redis
import json
from app.db.session import get_db_session
from app.models.credit_transaction import CreditTransaction

RESERVATION_TTL = 3600  # 1 hour, matches lock TTL


class CreditService:
    def __init__(self, r: redis.Redis):
        self.r = r

    def reserve(self, user_id: str, amount: int, run_id: str) -> bool:
        """
        Atomically check and reserve credits. Returns False if insufficient balance.
        Uses Redis to prevent concurrent overdraft during AI calls.
        """
        reserve_key = f"credits:reserved:{user_id}"
        balance_key = f"credits:balance:{user_id}"

        with self.r.pipeline() as pipe:
            while True:
                try:
                    pipe.watch(balance_key, reserve_key)
                    balance = int(pipe.get(balance_key) or 0)
                    reserved = int(pipe.get(reserve_key) or 0)
                    available = balance - reserved

                    if available < amount:
                        return False

                    pipe.multi()
                    pipe.incrby(reserve_key, amount)
                    pipe.expire(reserve_key, RESERVATION_TTL)
                    pipe.set(f"credits:run:{run_id}", amount, ex=RESERVATION_TTL)
                    pipe.execute()
                    return True

                except redis.WatchError:
                    continue  # retry on concurrent modification

    def settle_reservation(self, run_id: str, actual_cost: int | None = None):
        """
        On completion: deduct actual cost from DB, release reservation.
        actual_cost may differ from reserved amount (reserve was conservative).
        """
        reserved_key = f"credits:run:{run_id}"
        reserved = int(self.r.get(reserved_key) or 0)
        cost = actual_cost or reserved

        with get_db_session() as db:
            # Atomic credit deduction with balance tracking
            db.execute("""
                WITH deducted AS (
                    UPDATE users SET credits_balance = credits_balance - :cost
                    WHERE id = (SELECT user_id FROM agent_runs WHERE id = :run_id)
                      AND credits_balance >= :cost
                    RETURNING id, credits_balance AS new_balance
                )
                INSERT INTO credit_transactions
                    (user_id, amount, transaction_type, run_id, balance_after)
                SELECT id, -:cost, 'agent_run', :run_id, new_balance
                FROM deducted
            """, {"cost": cost, "run_id": run_id})

        user_id = self._get_user_id(run_id)
        self.r.decrby(f"credits:reserved:{user_id}", reserved)
        self.r.delete(reserved_key)
        # Invalidate cached balance
        self.r.delete(f"credits:balance:{user_id}")

    def release_reservation(self, run_id: str):
        """On failure: release reservation without deducting credits."""
        reserved_key = f"credits:run:{run_id}"
        reserved = int(self.r.get(reserved_key) or 0)
        user_id = self._get_user_id(run_id)

        if reserved:
            self.r.decrby(f"credits:reserved:{user_id}", reserved)
        self.r.delete(reserved_key)
```

### 6.8 Anthropic SDK Error Handling and Retries

```python
# services/ai/client_wrapper.py
import anthropic
import time
import logging

logger = logging.getLogger(__name__)

client = anthropic.Anthropic()


def create_with_retry(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    **kwargs
) -> anthropic.types.Message:
    """
    Wraps client.messages.create with exponential backoff for transient errors.
    The Anthropic SDK has built-in retry but this adds logging and budget awareness.
    """
    for attempt in range(max_retries):
        try:
            return client.messages.create(**kwargs)

        except anthropic.RateLimitError as e:
            wait = initial_delay * (2 ** attempt)
            logger.warning(f"Anthropic rate limit (attempt {attempt+1}), waiting {wait}s: {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(wait)

        except anthropic.APIStatusError as e:
            if e.status_code in (529, 503):  # overloaded
                wait = initial_delay * (2 ** attempt)
                logger.warning(f"Anthropic overloaded (attempt {attempt+1}), waiting {wait}s")
                time.sleep(wait)
            elif e.status_code == 400:
                logger.error(f"Anthropic 400 — bad request, check params: {e.message}")
                raise  # don't retry bad requests
            else:
                raise

        except anthropic.APITimeoutError:
            if attempt < max_retries - 1:
                time.sleep(initial_delay)
            else:
                raise
```

### 6.9 Cost Monitoring and Alerts

```python
# services/monitoring/cost_tracker.py

def log_ai_call_cost(
    run_id: str,
    task: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
):
    """
    Calculate and record cost for each AI call in agent_run_logs.
    Prices: Fable 5 $10/$50/1M, Haiku 4.5 $1/$5/1M
    Cache reads: 10% of input price, cache writes: 125% of input price
    """
    PRICES = {
        "claude-fable-5":   {"input": 10.0, "output": 50.0, "cache_read": 1.0, "cache_write": 12.5},
        "claude-haiku-4-5": {"input": 1.0,  "output": 5.0,  "cache_read": 0.1, "cache_write": 1.25},
    }
    p = PRICES.get(model, PRICES["claude-haiku-4-5"])

    cost_usd = (
        (input_tokens / 1_000_000) * p["input"] +
        (output_tokens / 1_000_000) * p["output"] +
        (cache_read_tokens / 1_000_000) * p["cache_read"] +
        (cache_write_tokens / 1_000_000) * p["cache_write"]
    )

    with get_db_session() as db:
        db.execute("""
            INSERT INTO agent_run_logs
                (run_id, task_name, model, input_tokens, output_tokens,
                 cache_read_tokens, cache_write_tokens, cost_usd)
            VALUES (:run_id, :task, :model, :input, :output, :cache_read, :cache_write, :cost)
        """, {
            "run_id": run_id, "task": task, "model": model,
            "input": input_tokens, "output": output_tokens,
            "cache_read": cache_read_tokens, "cache_write": cache_write_tokens,
            "cost": cost_usd,
        })

    # Alert if single run exceeds $2 (indicates runaway token usage)
    if cost_usd > 0.50:
        logger.warning(f"High AI cost for task {task}: ${cost_usd:.4f} in run {run_id}")


# Daily budget alert: check aggregate cost per user
DAILY_COST_ALERT_THRESHOLD_USD = 2.00

def check_daily_cost_alert(user_id: str):
    with get_db_session() as db:
        total = db.execute("""
            SELECT COALESCE(SUM(l.cost_usd), 0) as total_cost
            FROM agent_run_logs l
            JOIN agent_runs r ON l.run_id = r.id
            WHERE r.user_id = :user_id
              AND r.created_at > NOW() - INTERVAL '24 hours'
        """, {"user_id": user_id}).scalar()

    if total > DAILY_COST_ALERT_THRESHOLD_USD:
        _send_internal_cost_alert(user_id, total)
```

---

## 7. Agent Observability & Logging

### 7.1 Agent Run Record Schema (Supplement to backend-spec.md)

```sql
-- agent_run_logs: granular per-task cost tracking
CREATE TABLE agent_run_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
    task_name VARCHAR(100) NOT NULL,          -- 'seo_analysis', 'daily_synthesis', etc.
    model VARCHAR(50) NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens INTEGER NOT NULL DEFAULT 0,
    cache_write_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd NUMERIC(10,6) NOT NULL,
    duration_ms INTEGER,
    cache_hit BOOLEAN DEFAULT FALSE,          -- was response served from Redis cache?
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_agent_run_logs_run_id ON agent_run_logs(run_id);
CREATE INDEX idx_agent_run_logs_cost ON agent_run_logs(cost_usd DESC);
```

### 7.2 SSE Streaming for Live Agent Progress

The daily agent streams progress events to the frontend via SSE at `GET /agent/runs/{run_id}/stream`.

```python
# api/routes/agent.py
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import asyncio
import json

router = APIRouter()


@router.get("/agent/runs/{run_id}/stream")
async def stream_agent_run(run_id: str):
    """
    SSE endpoint for real-time agent progress.
    Frontend useAgentStream hook connects here.
    Events are published to Redis channel by Celery tasks.
    """
    async def event_generator():
        pubsub = redis_client.pubsub()
        pubsub.subscribe(f"agent:progress:{run_id}")

        yield f"data: {json.dumps({'type': 'connected', 'run_id': run_id})}\n\n"

        timeout_at = asyncio.get_event_loop().time() + 3600  # 1h max
        while asyncio.get_event_loop().time() < timeout_at:
            message = pubsub.get_message(timeout=0.1)
            if message and message["type"] == "message":
                data = json.loads(message["data"])
                yield f"data: {json.dumps(data)}\n\n"

                if data.get("type") in ("completed", "failed"):
                    break

            await asyncio.sleep(0.1)

        pubsub.unsubscribe()
        yield f"data: {json.dumps({'type': 'stream_ended'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable Nginx buffering
        },
    )


# Published from Celery tasks:
AGENT_PROGRESS_EVENTS = [
    # type, message, progress (0-100)
    {"type": "phase_started", "phase": "data_sync", "message": "Syncing store listings...", "progress": 5},
    {"type": "phase_started", "phase": "seo_analysis", "message": "Analyzing SEO for top 20 listings...", "progress": 20},
    {"type": "phase_started", "phase": "competitor_scan", "message": "Scanning competitor listings...", "progress": 35},
    {"type": "phase_started", "phase": "trend_fetch", "message": "Fetching trend signals...", "progress": 50},
    {"type": "phase_started", "phase": "synthesis", "message": "Synthesizing daily intelligence...", "progress": 70},
    {"type": "phase_started", "phase": "content_gen", "message": "Generating optimization suggestions...", "progress": 85},
    {"type": "phase_started", "phase": "notifications", "message": "Preparing your daily briefing...", "progress": 95},
    {"type": "completed", "message": "Daily analysis complete", "progress": 100},
]
```

### 7.3 Human-in-the-Loop Gate

Before any listing content is written back to Etsy, the user must approve via the dashboard.

```python
# services/optimization_service.py

async def apply_optimization(
    optimization_id: str,
    user_id: str,
    approved_by: str,
) -> dict:
    """
    Called when user clicks 'Apply' in dashboard.
    Two-step: validate with Etsy API, then write.
    """
    with get_db_session() as db:
        opt = db.execute(
            "SELECT * FROM listing_optimizations WHERE id = :id AND status = 'pending'",
            {"id": optimization_id}
        ).fetchone()

        if not opt:
            raise ValueError("Optimization not found or not pending")

        # Validate Etsy constraints before API call
        if opt.suggested_tags:
            tags = opt.suggested_tags
            assert len(tags) <= 13, f"Too many tags: {len(tags)}"
            assert all(len(t) <= 20 for t in tags), f"Tag too long: {[t for t in tags if len(t) > 20]}"

        if opt.suggested_title:
            assert len(opt.suggested_title) <= 140, "Title exceeds 140 chars"

        # Mark as applying
        db.execute(
            "UPDATE listing_optimizations SET status = 'applying', applied_by = :by, applied_at = NOW() WHERE id = :id",
            {"by": approved_by, "id": optimization_id}
        )

    # Call Etsy API
    etsy = EtsyClient(store_id=opt.store_id)
    await wait_for_etsy_token(redis_client, str(opt.store_id))

    update_payload = {}
    if opt.suggested_title:
        update_payload["title"] = opt.suggested_title
    if opt.suggested_tags:
        update_payload["tags"] = opt.suggested_tags
    if opt.suggested_description:
        update_payload["description"] = opt.suggested_description

    try:
        etsy.update_listing(opt.etsy_listing_id, update_payload)

        with get_db_session() as db:
            db.execute(
                "UPDATE listing_optimizations SET status = 'applied' WHERE id = :id",
                {"id": optimization_id}
            )
        return {"status": "applied"}

    except etsy.EtsyAPIError as e:
        with get_db_session() as db:
            db.execute(
                "UPDATE listing_optimizations SET status = 'failed', error_message = :err WHERE id = :id",
                {"err": str(e), "id": optimization_id}
            )
        raise
```

---

## Appendix A: Environment Variables

```bash
# AI Providers
ANTHROPIC_API_KEY=sk-ant-...
VOYAGE_API_KEY=pa-...

# Etsy OAuth
ETSY_CLIENT_ID=
ETSY_CLIENT_SECRET=
ETSY_TOKEN_ENCRYPTION_KEY=  # 32-byte hex for AES-256-GCM

# External APIs
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
PINTEREST_ACCESS_TOKEN=

# Infrastructure
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://...
CELERY_BROKER_URL=redis://...
CELERY_RESULT_BACKEND=redis://...
```

## Appendix B: Cost Estimation at Scale

| Users | Stores | Daily Agent Runs | Estimated Daily AI Cost | Monthly AI Cost |
|---|---|---|---|---|
| 50 (beta) | 50 | 50 | $25–$40 | $750–$1,200 |
| 200 (launch) | 200 | 200 | $100–$165 | $3,000–$5,000 |
| 1,000 (growth) | 1,000 | 1,000 | $500–$825 | $15,000–$25,000 |
| 5,000 (scale) | 5,000 | 5,000 | $2,500–$4,000 | $75,000–$120,000 |

At scale, prompt caching (60% hit rate) reduces costs by ~40%. Monthly plan cost per user at 1,000 users: ~$15–25 (at Starter $9.99 plan, margins require either credit limits or tier pricing adjustments after 500 users).
