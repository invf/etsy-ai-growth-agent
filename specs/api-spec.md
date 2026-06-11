# Etsy AI Growth Agent — REST API Specification

> Canonical API reference. Supersedes API sections in `backend-spec.md`.
> Base URL: `https://api.etsyagent.com/v1`

---

## Table of Contents

1. [API Conventions](#1-api-conventions)
2. [Authentication](#2-authentication)
3. [Stores](#3-stores)
4. [Listings](#4-listings)
5. [SEO Analysis](#5-seo-analysis)
6. [Competitors](#6-competitors)
7. [Trends](#7-trends)
8. [Audience](#8-audience)
9. [Content Generation](#9-content-generation)
10. [Pricing](#10-pricing)
11. [Image Analysis](#11-image-analysis)
12. [Optimizations](#12-optimizations)
13. [Agent Runs](#13-agent-runs)
14. [Reports](#14-reports)
15. [Notifications](#15-notifications)
16. [Billing & Credits](#16-billing--credits)
17. [Webhooks (Inbound)](#17-webhooks-inbound)
18. [API Keys (Pro+)](#18-api-keys-pro)
19. [Admin](#19-admin)
20. [Rate Limiting](#20-rate-limiting)
21. [Error Catalog](#21-error-catalog)

---

## 1. API Conventions

### 1.1 Request / Response Envelope

```
All responses use a consistent envelope:

Success (2xx):
{
  "data": { ... } | [ ... ],
  "meta": {                       // only on paginated list responses
    "page": 1,
    "per_page": 20,
    "total": 143,
    "total_pages": 8
  }
}

Error (4xx / 5xx):
{
  "error": {
    "code": "VALIDATION_ERROR",   // machine-readable code (see Section 21)
    "message": "Human-readable description",
    "details": { ... }            // optional: field-level validation errors
  },
  "data": null
}
```

### 1.2 Authentication

```
Header: Authorization: Bearer {jwt}
Alternative (API keys, Pro+): X-API-Key: eag_{key}

JWT lifetime: 24 hours
Refresh via: POST /auth/refresh (returns new access_token)
API keys: no expiry unless set by user; check X-Credits-Available header
```

### 1.3 Response Headers

```
X-Request-Id: uuid                  — trace ID for every response
X-Credits-Available: 87             — remaining credits (authenticated routes)
X-Credits-Balance: 100              — total balance including reserved
X-Rate-Limit-Limit: 120             — requests allowed per minute
X-Rate-Limit-Remaining: 117         — requests left this minute
X-Rate-Limit-Reset: 1749557460      — Unix timestamp when window resets
```

### 1.4 Pagination

```
GET /stores/{id}/listings?page=2&per_page=50

Default per_page: 20
Maximum per_page: 100
Page is 1-indexed.
```

### 1.5 Filtering & Sorting

```
Standard query params available where noted:
  sort=field_name          (prefix with - for descending: sort=-created_at)
  filter[field]=value      (exact match)
  q=search_term            (full-text search on primary text field)
```

### 1.6 Feature Tier Enforcement

Tier-gated endpoints return `403 UPGRADE_REQUIRED` if the user's tier is insufficient.
The error response includes `required_tier` and `upgrade_url`.

```json
{
  "error": {
    "code": "UPGRADE_REQUIRED",
    "message": "Audience discovery requires Growth plan or higher.",
    "details": {
      "required_tier": "growth",
      "current_tier": "starter",
      "upgrade_url": "/billing/upgrade"
    }
  }
}
```

### 1.7 Async Job Pattern

Several endpoints queue Celery tasks and return immediately.
Poll `GET /agent/runs/{run_id}` or connect to SSE at `GET /agent/runs/{run_id}/stream`.

```json
// Immediate response from trigger endpoints:
{
  "data": {
    "run_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "pending",
    "estimated_seconds": 45
  }
}
```

---

## 2. Authentication

### POST /auth/register

Creates a new user account and starts 14-day trial.

```
Request:
  Content-Type: application/json
  {
    "email": "seller@example.com",       // required, valid email
    "name": "Jane Smith",                // required, 2-100 chars
    "password": "SecurePass123!",        // required, min 8 chars, 1 upper, 1 digit
    "timezone": "America/New_York"       // optional, defaults to UTC
  }

Response 201:
  {
    "data": {
      "user": {
        "id": "uuid",
        "email": "seller@example.com",
        "name": "Jane Smith",
        "subscription_tier": "trial",
        "credits_balance": 30,
        "trial_ends_at": "2026-06-24T00:00:00Z",
        "onboarding_completed": false
      },
      "access_token": "eyJ...",
      "refresh_token": "eyJ...",
      "expires_in": 86400
    }
  }

Errors:
  409 EMAIL_ALREADY_EXISTS   — email is already registered
  422 VALIDATION_ERROR       — invalid email, weak password
```

---

### POST /auth/login

```
Request:
  {
    "email": "seller@example.com",
    "password": "SecurePass123!"
  }

Response 200:
  {
    "data": {
      "user": { ...same as register... },
      "access_token": "eyJ...",
      "refresh_token": "eyJ...",
      "expires_in": 86400
    }
  }

Errors:
  401 INVALID_CREDENTIALS   — wrong email or password
  429 TOO_MANY_ATTEMPTS     — 5 failed attempts in 15 min; lockout active
```

---

### POST /auth/refresh

```
Request:
  { "refresh_token": "eyJ..." }

Response 200:
  { "data": { "access_token": "eyJ...", "expires_in": 86400 } }

Errors:
  401 TOKEN_EXPIRED     — refresh token expired (>7 days)
  401 TOKEN_INVALID     — token malformed or revoked
```

---

### POST /auth/logout

```
Auth: Bearer token required
Request: {} (empty)

Response 200:
  { "data": { "success": true } }

Side effects: revokes current session token_hash in sessions table
```

---

### POST /auth/forgot-password

```
Request: { "email": "seller@example.com" }

Response 200:
  { "data": { "message": "If that email exists, a reset link was sent." } }
  // Always 200 to prevent email enumeration

Side effects: creates password_reset_token, queues SendGrid email
```

---

### POST /auth/reset-password

```
Request:
  {
    "token": "reset-token-from-email",
    "new_password": "NewSecurePass456!"
  }

Response 200:
  { "data": { "success": true } }

Errors:
  400 TOKEN_INVALID    — token not found or already used
  400 TOKEN_EXPIRED    — token older than 1 hour
  422 VALIDATION_ERROR — password too weak
```

---

### GET /auth/me

```
Auth: Bearer token

Response 200:
  {
    "data": {
      "id": "uuid",
      "email": "seller@example.com",
      "name": "Jane Smith",
      "avatar_url": null,
      "timezone": "America/New_York",
      "subscription_status": "active",
      "subscription_tier": "growth",
      "billing_interval": "monthly",
      "subscription_current_period_end": "2026-07-10T00:00:00Z",
      "credits_balance": 247,
      "credits_available": 230,           // balance - reserved
      "email_notifications": true,
      "email_digest_frequency": "daily",
      "onboarding_completed": true,
      "store_count": 2,
      "last_login_at": "2026-06-10T08:30:00Z"
    }
  }
```

---

### PATCH /auth/me

```
Request (all fields optional):
  {
    "name": "Jane S.",
    "timezone": "Europe/London",
    "email_notifications": false,
    "email_digest_frequency": "weekly",
    "current_password": "OldPass123!",  // required when changing password
    "new_password": "NewPass456!"
  }

Response 200: { "data": { ...updated user object... } }

Errors:
  400 WRONG_PASSWORD   — current_password incorrect
  422 VALIDATION_ERROR — invalid field values
```

---

## 3. Stores

### GET /stores

```
Auth: Bearer token

Response 200:
  {
    "data": [
      {
        "id": "uuid",
        "etsy_shop_id": "12345678",
        "shop_name": "JanesHandmade",
        "shop_url": "https://www.etsy.com/shop/JanesHandmade",
        "icon_url": "https://...",
        "currency_code": "USD",
        "status": "active",
        "sync_status": "idle",
        "listing_count": 47,
        "health_score": 74,
        "health_computed_at": "2026-06-10T07:15:00Z",
        "agent_enabled": true,
        "agent_last_run_at": "2026-06-10T07:00:00Z",
        "last_synced_at": "2026-06-10T07:05:00Z",
        "created_at": "2026-01-15T14:22:00Z"
      }
    ]
  }
```

---

### POST /stores/connect/initiate

Initiates Etsy OAuth2 PKCE flow.

```
Auth: Bearer token

Request: {} (empty)

Response 200:
  {
    "data": {
      "oauth_url": "https://www.etsy.com/oauth/connect?...",
      "state": "csrf-token-abc123",        // stored server-side in Redis (TTL 10min)
      "expires_in": 600
    }
  }

Errors:
  403 STORE_LIMIT_REACHED — user already has max stores for their tier
```

---

### GET /stores/connect/callback

```
// OAuth redirect target — not called directly by frontend
Query params: code=xxx&state=xxx  (from Etsy)

Response: 302 redirect to /dashboard/stores?connected=true&shop_name=JanesHandmade

Errors: 302 redirect to /dashboard/stores?error=OAUTH_STATE_MISMATCH|OAUTH_DENIED
```

---

### GET /stores/{store_id}

```
Auth: Bearer token (must own store)

Response 200:
  {
    "data": {
      "id": "uuid",
      "etsy_shop_id": "12345678",
      "shop_name": "JanesHandmade",
      "shop_url": "...",
      "icon_url": "...",
      "banner_url": "...",
      "currency_code": "USD",
      "country_code": "US",
      "listing_count": 47,
      "sale_count": 1243,
      "average_rating": 4.9,
      "review_count": 387,
      "status": "active",
      "sync_status": "idle",
      "last_synced_at": "2026-06-10T07:05:00Z",
      "health_score": 74,
      "health_breakdown": {
        "seo": 68,
        "pricing": 72,
        "images": 85,
        "trends": 55,
        "reviews": 70
      },
      "agent_enabled": true,
      "agent_schedule": "0 7 * * *",
      "agent_last_run_at": "2026-06-10T07:00:00Z",
      "brand_voice": null
    }
  }

Errors:
  403 FORBIDDEN   — store belongs to different user
  404 NOT_FOUND
```

---

### DELETE /stores/{store_id}

```
Auth: Bearer token (must own store)

Response 200:
  { "data": { "success": true } }

Side effects:
  - Revokes Etsy OAuth tokens via Etsy API
  - Soft-deletes store record
  - Cancels any pending agent runs
  - Clears Redis cache keys for store
```

---

### POST /stores/{store_id}/sync

```
Auth: Bearer token

Response 202:
  { "data": { "job_id": "celery-uuid", "status": "queued", "estimated_seconds": 60 } }

Errors:
  409 SYNC_IN_PROGRESS — sync already running for this store
```

---

### GET /stores/{store_id}/health

```
Auth: Bearer token

Response 200:
  {
    "data": {
      "overall_score": 74,
      "breakdown": {
        "seo": 68,
        "pricing": 72,
        "images": 85,
        "trends": 55,
        "reviews": 70
      },
      "top_issues": [
        "12 listings have fewer than 10 tags",
        "3 listings are priced 25% below market median",
        "8 listings haven't been analyzed in 7+ days"
      ],
      "trend_vs_yesterday": "up",
      "computed_at": "2026-06-10T07:15:00Z"
    }
  }
```

---

### GET /stores/{store_id}/dashboard

```
Auth: Bearer token

Response 200:
  {
    "data": {
      "store": { ...store object... },
      "health": { ...health object... },
      "pending_optimizations_count": 5,
      "agent_runs": {
        "last_run": { "id": "uuid", "status": "completed", "created_at": "..." },
        "next_scheduled": "2026-06-11T07:00:00Z"
      },
      "top_listings": [
        { "id": "uuid", "title": "...", "views": 1240, "seo_score": 82, "price_usd": 34.00 }
      ],
      "today_insights": {
        "headline": "3 listings can gain 20%+ traffic with tag updates",
        "new_optimizations": 5,
        "trending_keywords": ["boho earrings", "cottagecore decor"]
      },
      "credits": { "available": 230, "balance": 247, "next_renewal": "2026-07-01" }
    }
  }
```

---

### PATCH /stores/{store_id}

```
Request (all optional):
  {
    "agent_enabled": true,
    "agent_schedule": "0 9 * * *"    // Pro+ only; cron expression; validates before saving
  }

Response 200: { "data": { ...updated store object... } }

Errors:
  403 UPGRADE_REQUIRED — agent_schedule requires Pro tier
  422 VALIDATION_ERROR — invalid cron expression
```

---

## 4. Listings

### GET /stores/{store_id}/listings

```
Auth: Bearer token

Query params:
  page=1, per_page=20 (max 100)
  state=active|inactive|all       (default: active)
  sort=seo_score|views|favorites|sales|price|updated_at   (default: -views)
  q=search_term                   (searches title using trigram index)
  min_seo_score=0, max_seo_score=100
  has_pending_optimization=true   (filter to listings with pending opts)

Response 200:
  {
    "data": [
      {
        "id": "uuid",
        "etsy_listing_id": 987654321,
        "title": "Handmade Ceramic Mug Blue Glaze",
        "price_usd": 34.00,
        "currency_code": "USD",
        "state": "active",
        "main_image_url": "https://...",
        "image_count": 7,
        "views_count": 1240,
        "favorites_count": 89,
        "sales_count": 34,
        "seo_score": 72,
        "image_score": 85,
        "tags": ["ceramic mug", "handmade pottery", "blue glaze"],
        "primary_category": "Home & Living",
        "pending_optimizations": 2,
        "etsy_updated_at": "2026-05-20T14:00:00Z",
        "synced_at": "2026-06-10T07:05:00Z"
      }
    ],
    "meta": { "page": 1, "per_page": 20, "total": 47, "total_pages": 3 }
  }
```

---

### GET /stores/{store_id}/listings/{listing_id}

```
Auth: Bearer token

Response 200:
  {
    "data": {
      "id": "uuid",
      "etsy_listing_id": 987654321,
      "title": "Handmade Ceramic Mug Blue Glaze",
      "description": "...",
      "tags": ["ceramic mug", "handmade pottery", "blue glaze", ...],
      "materials": ["stoneware", "food-safe glaze"],
      "price_usd": 34.00,
      "quantity": 12,
      "state": "active",
      "main_image_url": "https://...",
      "image_urls": ["https://..."],
      "image_count": 7,
      "views_count": 1240,
      "favorites_count": 89,
      "sales_count": 34,
      "average_rating": 4.9,
      "review_count": 22,
      "seo_score": 72,
      "seo_scored_at": "2026-06-10T07:10:00Z",
      "image_score": 85,
      "taxonomy_path": ["Home & Living", "Kitchen & Dining", "Mugs"],
      "primary_category": "Home & Living",
      "etsy_created_at": "2024-03-10T10:00:00Z",
      "etsy_updated_at": "2026-05-20T14:00:00Z",
      "latest_seo_analysis": { ...seo analysis object or null... },
      "latest_pricing_analysis": { ...pricing object or null... },
      "pending_optimizations_count": 2
    }
  }
```

---

### GET /stores/{store_id}/listings/{listing_id}/metrics

```
Auth: Bearer token

Query params: range=7d|30d|90d  (default: 30d)

Response 200:
  {
    "data": {
      "range": "30d",
      "history": [
        {
          "date": "2026-05-11",
          "views_count": 38,
          "favorites_count": 3,
          "sales_count": 1,
          "seo_score": 65
        }
        // ...30 entries
      ],
      "totals": {
        "views": 987,
        "favorites": 67,
        "sales": 22
      },
      "changes": {
        "views_pct": 12.4,       // % change vs previous period
        "favorites_pct": 8.1,
        "sales_pct": -5.2
      }
    }
  }
```

---

## 5. SEO Analysis

### GET /listings/{listing_id}/seo

Returns the most recent SEO analysis for a listing.

```
Auth: Bearer token

Response 200:
  {
    "data": {
      "id": "uuid",
      "overall_score": 72,
      "title_score": 65,
      "tags_score": 78,
      "description_score": 68,
      "priority": "high",

      "title_analysis": {
        "current_title": "Handmade Ceramic Mug Blue Glaze",
        "optimized_title": "Blue Ceramic Mug Handmade Pottery Gift for Coffee Lovers",
        "primary_keyword": "ceramic mug",
        "keyword_position": "first_half",
        "issues": ["Primary keyword not in first 3 words"],
        "change_rationale": "Moving 'blue ceramic mug' to the start increases search match weight"
      },

      "tags_analysis": {
        "current_tags": ["ceramic mug", "handmade pottery", ...],
        "optimized_tags": ["ceramic mug gift", "handmade coffee cup", ...],
        "weak_tags": ["blue", "mug"],
        "missing_high_value_tags": ["coffee lover gift", "pottery gift", "unique mug"],
        "unused_slots": 2
      },

      "description_analysis": {
        "issues": ["First paragraph not keyword-optimized"],
        "recommended_additions": ["Include 'handmade in [location]'", "Add gift occasion context"]
      },

      "estimated_traffic_lift_pct": 22,
      "competitor_gap_summary": "Top competitors use 'gift' in 4+ tags; you have 0.",
      "from_cache": false,
      "model_used": "claude-fable-5",
      "cost_usd": 0.063,
      "created_at": "2026-06-10T07:10:00Z"
    }
  }

Response 404: No SEO analysis exists yet (trigger one with POST /analyze)
```

---

### POST /listings/{listing_id}/seo/analyze

```
Auth: Bearer token
Credits: 2 (deducted if not included in active daily run)

Request: {} (empty — all context fetched server-side)

Response 202:
  {
    "data": {
      "run_id": "uuid",
      "status": "pending",
      "estimated_seconds": 20
    }
  }

Errors:
  402 INSUFFICIENT_CREDITS  — available credits < 2
  409 ANALYSIS_IN_PROGRESS  — analysis already running for this listing
```

---

### POST /listings/{listing_id}/seo/apply

```
Auth: Bearer token

Request:
  {
    "fields": ["title", "tags", "description"]  // optional; defaults to all recommended fields
  }

Response 201:
  {
    "data": {
      "optimization_ids": ["uuid1", "uuid2", "uuid3"],
      "message": "3 optimizations created. Review and approve in the Optimizations tab."
    }
  }

Errors:
  404 NO_ANALYSIS_FOUND    — no SEO analysis exists; run analyze first
  409 OPTIMIZATIONS_EXIST  — pending optimizations already exist for this listing
```

---

## 6. Competitors

### GET /listings/{listing_id}/competitors

```
Auth: Bearer token

Query params:
  page, per_page
  sort=competitor_score|price|sales_estimate|rank_position  (default: rank_position)

Response 200:
  {
    "data": [
      {
        "id": "uuid",
        "etsy_listing_id": 111222333,
        "etsy_shop_id": "PotteryByMax",
        "shop_name": "PotteryByMax",
        "title": "Handmade Blue Coffee Mug Ceramic Gift",
        "price_usd": 28.00,
        "views_count": 4502,
        "favorites_count": 312,
        "sales_estimate": 480,
        "review_count": 97,
        "average_rating": 4.95,
        "rank_position": 1,
        "search_keyword": "blue ceramic mug",
        "competitor_score": 88,
        "main_image_url": "https://...",
        "tags": ["blue ceramic mug", "coffee lover gift", ...],
        "last_seen_at": "2026-06-10T07:05:00Z"
      }
    ],
    "meta": { "page": 1, "per_page": 20, "total": 28 }
  }
```

---

### GET /stores/{store_id}/competitors/analysis

```
Auth: Bearer token

Query params: category=Home+%26+Living

Response 200:
  {
    "data": {
      "id": "uuid",
      "category": "Home & Living",
      "market_position": {
        "price_percentile": 42,
        "positioning": "mid_market",
        "consistency_score": 71
      },
      "top_competitor_patterns": [
        {
          "pattern": "Include 'gift' in 3+ tags",
          "frequency": "all_top_10",
          "seller_does_this": false,
          "impact": "high"
        }
      ],
      "pricing_opportunities": [
        {
          "listing_title_fragment": "Blue Ceramic Mug",
          "current_price": 34.00,
          "competitor_avg_price": 38.50,
          "recommended_price": 37.00,
          "rationale": "Underpriced vs comparable quality competitors"
        }
      ],
      "content_gaps": ["'gift' keyword absent from all tags", "No lifestyle images"],
      "quick_wins": [
        { "action": "Add 'coffee lover gift' tag to top 5 mugs", "effort": "5_min", "expected_impact": "10-15% CTR lift" }
      ],
      "differentiation_opportunities": ["Local pottery angle underused in category"],
      "created_at": "2026-06-10T07:12:00Z"
    }
  }
```

---

### POST /listings/{listing_id}/competitors/refresh

```
Auth: Bearer token
Credits: 2

Response 202: { "data": { "run_id": "uuid", "status": "pending", "estimated_seconds": 45 } }
```

---

## 7. Trends

### GET /trends

```
Auth: Bearer token

Query params:
  category=Home+%26+Living
  source=google_trends|pinterest|reddit|etsy_search
  region=US   (default)
  lifecycle=emerging|growing|peak|declining
  sort=-trend_score   (default: trend_score DESC)
  page, per_page

Response 200:
  {
    "data": [
      {
        "id": "uuid",
        "keyword": "cottagecore decor",
        "source": "google_trends",
        "region": "US",
        "category": "Home & Living",
        "trend_score": 87,
        "volume_index": 72,
        "search_volume_trend": "rising",
        "growth_rate_pct": 34.2,
        "lifecycle_stage": "growing",
        "peak_predicted_date": "2026-08-15",
        "is_seasonal": false,
        "related_keywords": ["cottage style", "farmhouse decor", "wildflower prints"],
        "recorded_at": "2026-06-10T02:00:00Z"
      }
    ],
    "meta": { ... }
  }
```

---

### GET /stores/{store_id}/trends/report

```
Auth: Bearer token

Query params: type=daily|weekly|monthly  (default: daily)

Response 200:
  {
    "data": {
      "id": "uuid",
      "report_type": "daily",
      "period_start": "2026-06-10",
      "period_end": "2026-06-10",
      "executive_summary": "Cottagecore decor is in growing stage with 34% week-over-week...",
      "trend_opportunities": [
        {
          "trend_name": "cottagecore decor",
          "lifecycle_stage": "growing",
          "relevance_score": 91,
          "recommended_keywords": ["cottagecore ceramic", "cottage style mug"],
          "listing_ideas": ["Cottagecore floral ceramic mug set"],
          "time_sensitivity": "this_week"
        }
      ],
      "seasonal_calendar": [
        {
          "event_name": "Back to School",
          "days_until": 62,
          "preparation_deadline": 47,
          "relevant_product_ideas": ["Teacher appreciation mug", "College dorm decor"]
        }
      ],
      "declining_to_remove": ["minimalist style"],
      "created_at": "2026-06-10T07:20:00Z"
    }
  }
```

---

### POST /stores/{store_id}/trends/refresh

```
Auth: Bearer token
Credits: 1

Response 202: { "data": { "run_id": "uuid", "status": "pending", "estimated_seconds": 30 } }
```

---

## 8. Audience

> Growth+ tier required.

### GET /stores/{store_id}/audience/personas

```
Auth: Bearer token
Tier: growth+

Response 200:
  {
    "data": [
      {
        "id": "uuid",
        "persona_name": "Gifting Planner",
        "estimated_share_pct": 40,
        "primary_motivation": "Finding unique, memorable gifts for loved ones",
        "price_sensitivity": "low",
        "interests": ["unique gifts", "handmade crafts", "home decor"],
        "search_keywords": ["handmade gift", "unique ceramic gift", "pottery gift"],
        "seasonality": ["Christmas", "Mother's Day", "Valentines Day"],
        "platforms": ["pinterest", "instagram"],
        "listing_angle": "Emphasize gift-giving occasions and packaging presentation",
        "is_underserved": false,
        "created_at": "2026-06-03T08:00:00Z"
      }
    ]
  }
```

---

### POST /stores/{store_id}/audience/analyze

```
Auth: Bearer token
Tier: growth+
Credits: 4

Response 202: { "data": { "run_id": "uuid", "status": "pending", "estimated_seconds": 60 } }
```

---

### GET /stores/{store_id}/audience/communities

```
Auth: Bearer token
Tier: growth+

Response 200:
  {
    "data": [
      {
        "id": "uuid",
        "platform": "reddit",
        "name": "r/PotteryLovers",
        "url": "https://reddit.com/r/PotteryLovers",
        "member_count": 42000,
        "engagement_score": 72,
        "relevance_score": 89,
        "description": "Community for pottery enthusiasts and collectors",
        "analyzed_at": "2026-06-03T08:00:00Z"
      }
    ]
  }
```

---

## 9. Content Generation

### POST /content/generate

```
Auth: Bearer token
Credits: 1 (standard/Haiku) or 1 (premium/Fable 5 — routed by revenue)

Request:
  {
    "store_id": "uuid",
    "listing_id": "uuid",           // optional; if provided, uses listing context
    "content_type": "etsy_title",   // required; see content_type enum in database-spec
    "context": {
      "keywords": ["ceramic mug", "handmade pottery"],   // optional extra keywords
      "tone": "warm",                                     // optional override
      "additional_instructions": "Mention it's food-safe" // optional
    }
  }

Response 202:
  { "data": { "run_id": "uuid", "status": "pending", "estimated_seconds": 15 } }

Errors:
  422 INVALID_CONTENT_TYPE
  402 INSUFFICIENT_CREDITS
```

---

### GET /content/{content_id}

```
Auth: Bearer token

Response 200:
  {
    "data": {
      "id": "uuid",
      "store_id": "uuid",
      "listing_id": "uuid",
      "content_type": "etsy_title",
      "content": "Blue Ceramic Mug Handmade Pottery Gift for Coffee Lovers",
      "tone": "warm",
      "keywords_used": ["ceramic mug", "handmade pottery", "gift"],
      "is_seo_optimized": true,
      "user_rating": null,
      "is_applied": false,
      "model_used": "claude-fable-5",
      "cost_usd": 0.063,
      "created_at": "2026-06-10T10:30:00Z"
    }
  }
```

---

### GET /stores/{store_id}/content

```
Auth: Bearer token

Query params:
  content_type=etsy_title|etsy_description|etsy_tags|...
  listing_id=uuid
  is_applied=true|false
  page, per_page

Response 200: { "data": [...content objects...], "meta": {...} }
```

---

### POST /content/{content_id}/apply

```
// Copies content to the listing and creates a listing_optimization for approval
Auth: Bearer token

Response 201:
  { "data": { "optimization_id": "uuid", "status": "pending" } }

Errors:
  404 NOT_FOUND        — content_id not found
  409 ALREADY_APPLIED  — content already applied
```

---

### POST /content/{content_id}/rate

```
Request: { "rating": 4 }  // 1-5

Response 200: { "data": { "success": true } }
```

---

### DELETE /content/{content_id}

```
Response 200: { "data": { "success": true } }
```

---

## 10. Pricing

### GET /listings/{listing_id}/pricing

```
Auth: Bearer token

Response 200:
  {
    "data": {
      "id": "uuid",
      "current_price": 34.00,
      "market_min": 18.00,
      "market_max": 75.00,
      "market_avg": 38.40,
      "market_median": 36.50,
      "recommended_price": 37.00,
      "price_direction": "increase",
      "price_position": "below_market",
      "demand_level": "high",
      "confidence": "medium",
      "rationale": "Comparable handmade ceramic mugs with similar review counts sell for $35-42.",
      "bundle_opportunities": [
        {
          "description": "Mug + matching saucer set",
          "suggested_price": 58.00
        }
      ],
      "competitor_prices": [
        { "shop_name": "PotteryByMax", "price": 38.00 },
        { "shop_name": "ClayAndFire", "price": 42.00 }
      ],
      "model_used": "claude-haiku-4-5",
      "created_at": "2026-06-10T07:11:00Z"
    }
  }

Response 404: No pricing analysis; trigger with POST /analyze
```

---

### POST /listings/{listing_id}/pricing/analyze

```
Auth: Bearer token
Credits: 0 (included in daily run) or 1 (on-demand, Starter)

Response 202: { "data": { "run_id": "uuid", "status": "pending", "estimated_seconds": 20 } }
```

---

## 11. Image Analysis

### GET /listings/{listing_id}/images/analysis

```
Auth: Bearer token

Response 200:
  {
    "data": {
      "id": "uuid",
      "overall_visual_score": 71,
      "image_count_analyzed": 5,
      "thumbnail_score": 65,
      "thumbnail_issues": ["Product too small in frame", "Background too busy"],
      "thumbnail_readable": false,
      "thumbnail_recommendation": "Zoom in 30%, use clean white/neutral background",
      "lighting_quality": "good",
      "background_recommendation": "Switch hero image to neutral linen texture background",
      "missing_shot_types": ["scale_reference", "lifestyle", "packaging"],
      "priority_improvements": [
        {
          "improvement": "Recrop thumbnail — product occupies only 40% of frame",
          "effort": "easy_edit",
          "impact": "high"
        },
        {
          "improvement": "Add a lifestyle shot (mug on morning coffee table scene)",
          "effort": "reshoot",
          "impact": "high"
        }
      ],
      "model_used": "claude-fable-5",
      "analyzed_at": "2026-06-10T07:15:00Z"
    }
  }
```

---

### POST /listings/{listing_id}/images/analyze

```
Auth: Bearer token
Credits: 1

Response 202: { "data": { "run_id": "uuid", "status": "pending", "estimated_seconds": 30 } }
```

---

## 12. Optimizations

### GET /stores/{store_id}/optimizations

```
Auth: Bearer token

Query params:
  status=pending|approved|rejected|applying|applied|failed   (default: pending)
  optimization_type=title|description|tags|price|images
  listing_id=uuid
  page, per_page

Response 200:
  {
    "data": [
      {
        "id": "uuid",
        "listing_id": "uuid",
        "listing_title": "Handmade Ceramic Mug Blue Glaze",
        "listing_image_url": "https://...",
        "optimization_type": "tags",
        "old_value": "[\"ceramic mug\",\"handmade\",\"blue\"]",
        "new_value": "[\"ceramic mug gift\",\"handmade coffee cup\",\"blue pottery\",\"coffee lover gift\"]",
        "change_summary": "Replaced 3 weak tags with high-value alternatives. Added 'gift' keyword in 2 forms.",
        "impact_estimate": {
          "seo_score_delta": 14,
          "estimated_views_lift_pct": 18
        },
        "status": "pending",
        "created_at": "2026-06-10T07:10:00Z"
      }
    ],
    "meta": { "page": 1, "per_page": 20, "total": 7 }
  }
```

---

### GET /optimizations/{optimization_id}

```
Response 200:
  {
    "data": {
      ...full optimization object with all fields...
      "listing": { "id": "uuid", "title": "...", "etsy_listing_id": 987654321 },
      "run_id": "uuid"
    }
  }
```

---

### POST /optimizations/{optimization_id}/approve

```
Auth: Bearer token

Request: {} (empty)

Response 200:
  {
    "data": {
      "id": "uuid",
      "status": "approved",
      "approved_at": "2026-06-10T11:00:00Z",
      "approved_by": "user"
    }
  }

Errors:
  409 INVALID_STATUS  — optimization is not in 'pending' state
```

---

### POST /optimizations/{optimization_id}/reject

```
Auth: Bearer token

Request: { "reason": "Tags don't match my brand voice" }  // optional

Response 200:
  { "data": { "id": "uuid", "status": "rejected", "rejected_at": "..." } }
```

---

### POST /optimizations/{optimization_id}/apply

```
Auth: Bearer token

// Sends the approved change to Etsy API. Requires status=approved.
// This is the only endpoint that writes to Etsy. Validates constraints before PUT.

Response 200:
  {
    "data": {
      "id": "uuid",
      "status": "applied",
      "applied_at": "2026-06-10T11:01:00Z",
      "etsy_update_status": "success"
    }
  }

Errors:
  409 NOT_APPROVED         — optimization status is not 'approved'
  424 ETSY_UPDATE_FAILED   — Etsy API returned an error; details in error.details
  503 ETSY_UNAVAILABLE     — Etsy API timeout; retry later
```

---

### POST /stores/{store_id}/optimizations/approve-all

```
Auth: Bearer token

// Bulk approve all pending optimizations for a store

Request:
  {
    "optimization_type": "tags"   // optional; if omitted, approves all types
  }

Response 200:
  { "data": { "approved_count": 5, "optimization_ids": ["uuid1", "uuid2", ...] } }
```

---

### GET /optimizations/{optimization_id}/results

```
Auth: Bearer token

Response 200:
  {
    "data": [
      {
        "measurement_period": "7d",
        "views_before": 38,
        "views_after": 52,
        "favorites_before": 3,
        "favorites_after": 5,
        "seo_score_before": 72,
        "seo_score_after": 86,
        "views_delta_pct": 36.8,
        "measured_at": "2026-06-17T07:00:00Z"
      }
    ]
  }

// Returns empty array if no measurements yet (optimization recently applied)
```

---

## 13. Agent Runs

### GET /stores/{store_id}/agent/runs

```
Auth: Bearer token

Query params:
  status=pending|running|completed|failed|cancelled
  run_type=daily|seo_analysis|...
  page, per_page

Response 200:
  {
    "data": [
      {
        "id": "uuid",
        "run_type": "daily",
        "status": "completed",
        "triggered_by": "scheduler",
        "progress_pct": 100,
        "credits_used": 5,
        "total_cost_usd": 0.47,
        "result_summary": {
          "headline_insight": "3 listings can gain 20%+ traffic with tag updates",
          "new_optimizations_count": 7,
          "store_health_score": 76
        },
        "started_at": "2026-06-10T07:00:02Z",
        "completed_at": "2026-06-10T07:08:41Z",
        "duration_ms": 519000,
        "created_at": "2026-06-10T07:00:00Z"
      }
    ],
    "meta": { ... }
  }
```

---

### GET /agent/runs/{run_id}

```
Auth: Bearer token

Response 200:
  {
    "data": {
      "id": "uuid",
      "store_id": "uuid",
      "run_type": "daily",
      "status": "running",
      "progress_pct": 55,
      "current_phase": "competitor_scan",
      "credits_used": 0,          // 0 during run; settled on completion
      "credits_reserved": 5,
      "total_cost_usd": 0,
      "result_summary": null,
      "started_at": "2026-06-10T07:00:02Z",
      "completed_at": null,
      "created_at": "2026-06-10T07:00:00Z"
    }
  }
```

---

### GET /agent/runs/{run_id}/tasks

```
Auth: Bearer token

Response 200:
  {
    "data": [
      {
        "id": "uuid",
        "task_name": "sync_etsy_listings",
        "status": "completed",
        "duration_ms": 8200,
        "started_at": "2026-06-10T07:00:03Z",
        "completed_at": "2026-06-10T07:00:11Z"
      },
      {
        "id": "uuid",
        "task_name": "seo_analysis_batch",
        "status": "running",
        "started_at": "2026-06-10T07:00:12Z",
        "completed_at": null
      }
    ]
  }
```

---

### POST /stores/{store_id}/agent/run

```
Auth: Bearer token
Credits: varies by run_type (daily=5, seo_analysis=2, etc.)

Request:
  {
    "run_type": "daily",              // required
    "listing_id": "uuid"              // required only for listing-specific run types
  }

Response 202:
  {
    "data": {
      "run_id": "uuid",
      "status": "pending",
      "credits_reserved": 5,
      "estimated_seconds": 300
    }
  }

Errors:
  402 INSUFFICIENT_CREDITS     — not enough credits
  409 AGENT_RUN_IN_PROGRESS    — daily run already active for this store
  403 UPGRADE_REQUIRED         — run_type requires higher tier
```

---

### GET /agent/runs/{run_id}/stream

SSE (Server-Sent Events) endpoint for real-time progress.

```
Auth: Bearer token (passed as ?token= query param since EventSource doesn't support headers)
Content-Type: text/event-stream
Cache-Control: no-cache
X-Accel-Buffering: no        (disables Nginx buffering)

Connection lifetime: up to 1 hour; auto-closes on completion or failure

Event stream format:
  data: {"type":"connected","run_id":"uuid"}\n\n
  data: {"type":"phase_started","phase":"data_sync","message":"Syncing 47 listings...","progress":5}\n\n
  data: {"type":"phase_complete","phase":"data_sync","progress":15}\n\n
  data: {"type":"phase_started","phase":"seo_analysis","message":"Analyzing SEO for top 20 listings...","progress":20}\n\n
  data: {"type":"listing_analyzed","listing_id":"uuid","listing_title":"...","seo_score":72,"progress":28}\n\n
  data: {"type":"phase_started","phase":"competitor_scan","message":"Scanning 5 categories...","progress":40}\n\n
  data: {"type":"phase_started","phase":"trend_fetch","message":"Fetching trend signals...","progress":55}\n\n
  data: {"type":"phase_started","phase":"synthesis","message":"Synthesizing daily intelligence...","progress":70}\n\n
  data: {"type":"phase_started","phase":"content_gen","message":"Generating 7 optimization suggestions...","progress":85}\n\n
  data: {"type":"completed","run_id":"uuid","result":{"headline":"3 listings can gain 20% traffic...","new_opts":7},"progress":100}\n\n

  // On error:
  data: {"type":"failed","run_id":"uuid","error":"Etsy API rate limit exceeded"}\n\n

Reconnect behavior: If client disconnects mid-run, it can reconnect within 2h.
  The server will send the latest phase and progress on reconnect.
  Use EventSource's built-in reconnect (sets Last-Event-ID header automatically).
```

---

## 14. Reports

### GET /stores/{store_id}/reports

```
Auth: Bearer token

Query params:
  type=daily|weekly|monthly  (default: all)
  page, per_page

Response 200:
  {
    "data": [
      {
        "id": "uuid",
        "report_type": "weekly",
        "period_start": "2026-06-03",
        "period_end": "2026-06-09",
        "executive_summary": "Strong week: cottagecore trend drove 23% views increase...",
        "created_at": "2026-06-10T07:30:00Z"
      }
    ],
    "meta": { ... }
  }
```

---

### GET /reports/{report_id}

```
Auth: Bearer token

Response 200:
  {
    "data": {
      "id": "uuid",
      "store_id": "uuid",
      "report_type": "weekly",
      "period_start": "2026-06-03",
      "period_end": "2026-06-09",
      "executive_summary": "...",
      "trend_opportunities": [...],
      "seasonal_calendar": [...],
      "declining_to_remove": [...],
      "model_used": "claude-fable-5",
      "cost_usd": 0.115,
      "created_at": "2026-06-10T07:30:00Z"
    }
  }
```

---

### POST /stores/{store_id}/reports/generate

```
Auth: Bearer token
Credits: weekly=3, monthly=5

Request: { "type": "weekly" }

Response 202: { "data": { "run_id": "uuid", "status": "pending", "estimated_seconds": 60 } }

Errors:
  403 UPGRADE_REQUIRED   — monthly reports require Growth+
```

---

## 15. Notifications

### GET /notifications

```
Auth: Bearer token

Query params:
  is_read=true|false
  type=agent_complete|seo_opportunity|...
  store_id=uuid
  page, per_page  (default: 20, max: 50)

Response 200:
  {
    "data": [
      {
        "id": "uuid",
        "store_id": "uuid",
        "type": "optimization_ready",
        "priority": "high",
        "title": "7 new optimizations ready for review",
        "message": "Your daily analysis found opportunities across 5 listings.",
        "data": { "optimization_count": 7, "store_name": "JanesHandmade" },
        "action_url": "/dashboard/optimizations",
        "is_read": false,
        "email_sent": true,
        "created_at": "2026-06-10T07:10:00Z"
      }
    ],
    "meta": { "total_unread": 3, "page": 1, "per_page": 20, "total": 3 }
  }
```

---

### PATCH /notifications/{notification_id}/read

```
Response 200: { "data": { "id": "uuid", "is_read": true, "read_at": "..." } }
```

---

### POST /notifications/read-all

```
Auth: Bearer token

Request: { "store_id": "uuid" }   // optional; if omitted, marks all user notifications

Response 200: { "data": { "marked_read": 7 } }
```

---

### DELETE /notifications/{notification_id}

```
Response 200: { "data": { "success": true } }
```

---

## 16. Billing & Credits

### GET /billing/plans

```
// Public endpoint — no auth required

Response 200:
  {
    "data": [
      {
        "name": "starter",
        "display_name": "Starter",
        "price_monthly_usd": 19.00,
        "price_annual_usd": 182.00,
        "annual_savings_pct": 20,
        "max_stores": 1,
        "credits_monthly": 100,
        "features": {
          "stores": 1,
          "daily_agent": true,
          "seo_analysis": true,
          "competitor_analysis": true,
          "trends": true,
          "image_analysis": true,
          "pricing_advisor": true,
          "content_generation": true,
          "audience_discovery": false,
          "monthly_strategic_plan": false,
          "ab_testing": false,
          "api_access": false,
          "white_label": false,
          "team_members": 1
        },
        "is_active": true
      }
    ]
  }
```

---

### GET /billing/subscription

```
Auth: Bearer token

Response 200:
  {
    "data": {
      "subscription_status": "active",
      "subscription_tier": "growth",
      "billing_interval": "monthly",
      "price_usd": 49.00,
      "current_period_end": "2026-07-10T00:00:00Z",
      "cancelled_at": null,
      "paddle_subscription_id": "sub_01j...",
      "paddle_customer_id": "ctm_01j..."
    }
  }
```

---

### GET /billing/portal

```
Auth: Bearer token

// Returns Paddle Customer Portal URL (manage payment method, download invoices, cancel)

Response 200:
  { "data": { "portal_url": "https://customer.paddle.com/login?token=..." } }
```

---

### GET /billing/invoices

```
Auth: Bearer token

Query params: page, per_page

Response 200:
  {
    "data": [
      {
        "id": "txn_01j...",
        "date": "2026-06-10T00:00:00Z",
        "amount_usd": 49.00,
        "currency": "USD",
        "status": "completed",
        "description": "Growth Plan - Monthly",
        "invoice_pdf_url": "https://..."
      }
    ],
    "meta": { ... }
  }
```

---

### GET /billing/credits

```
Auth: Bearer token

Response 200:
  {
    "data": {
      "balance": 247,
      "reserved": 5,
      "available": 242,
      "monthly_allotment": 300,
      "next_renewal_date": "2026-07-10",
      "rollover_percent": 50,
      "estimated_balance_at_renewal": 185   // (242 × 0.5) + 300
    }
  }
```

---

### GET /billing/credits/history

```
Auth: Bearer token

Query params: page, per_page

Response 200:
  {
    "data": [
      {
        "id": "uuid",
        "amount": -5,
        "balance_after": 242,
        "transaction_type": "agent_run_deduction",
        "run_id": "uuid",
        "notes": "Daily agent run — JanesHandmade",
        "created_at": "2026-06-10T07:08:41Z"
      },
      {
        "id": "uuid",
        "amount": 300,
        "balance_after": 247,
        "transaction_type": "subscription_renewal",
        "notes": "Growth plan — June 2026 renewal",
        "created_at": "2026-06-10T00:00:00Z"
      }
    ],
    "meta": { ... }
  }
```

---

### POST /billing/credits/top-up

```
Auth: Bearer token

// Returns a Paddle one-time checkout price_id; frontend opens Paddle overlay
// Actual credit allocation happens via webhook (transaction.completed)

Request:
  { "package": "medium" }   // small|medium|large|xl

Response 200:
  {
    "data": {
      "price_id": "pri_01j...",    // Paddle price ID for checkout
      "credits": 150,
      "price_usd": 12.99
    }
  }
```

---

### POST /billing/upgrade

```
// Returns Paddle price_id for checkout overlay; actual upgrade via webhook

Request:
  {
    "tier": "pro",
    "billing_interval": "monthly"
  }

Response 200:
  {
    "data": {
      "price_id": "pri_01j...",
      "price_usd": 99.00,
      "customer_email": "seller@example.com"
    }
  }

Errors:
  400 ALREADY_ON_TIER     — user is already on requested tier
  400 DOWNGRADE_NOT_ALLOWED — must cancel and resubscribe to downgrade (Paddle limitation)
```

---

## 17. Webhooks (Inbound)

### POST /webhooks/paddle

```
// Paddle event handler. No Bearer auth — verified by HMAC-SHA256 signature.
// Header: Paddle-Signature: ts={timestamp};h1={hmac_hex}

Events handled:
  subscription.created    → allocate monthly credits, send welcome email
  subscription.updated    → update tier, credit differential
  subscription.cancelled  → set status=cancelling (access until period_end)
  subscription.paused     → set status=paused
  subscription.resumed    → restore active status
  transaction.completed   → renewal: allocate credits; top-up: add credits
  transaction.payment_failed → set status=past_due, send email

Response 200: { "status": "ok" }
Response 401: invalid signature
Response 500: processing error (Paddle will retry)

Idempotency: each event_id checked against paddle_events table before processing
```

---

### POST /webhooks/etsy

```
// Etsy push notifications (if enabled on Etsy developer account)
// Header: X-Etsy-Delivery-Token: {token}

Events handled:
  listing.updated         → trigger sync_single_listing task
  shop.updated            → refresh store metadata

Response 200: { "status": "ok" }
```

---

## 18. API Keys (Pro+)

### GET /api-keys

```
Auth: Bearer token
Tier: pro+

Response 200:
  {
    "data": [
      {
        "id": "uuid",
        "name": "Production Integration",
        "key_prefix": "eag_a1b2",     // first 8 chars; full key only shown at creation
        "permissions": ["read:listings", "read:optimizations"],
        "last_used_at": "2026-06-09T14:22:00Z",
        "expires_at": null,
        "is_active": true,
        "created_at": "2026-05-01T10:00:00Z"
      }
    ]
  }
```

---

### POST /api-keys

```
Auth: Bearer token
Tier: pro+

Request:
  {
    "name": "Production Integration",
    "permissions": ["read:listings", "read:optimizations"],  // pro: read only
    "expires_at": null       // optional ISO date
  }

// Agency tier also allows: "write:optimizations"

Response 201:
  {
    "data": {
      "id": "uuid",
      "name": "Production Integration",
      "key": "eag_a1b2c3d4e5f6g7h8i9j0",  // ONLY returned at creation; save immediately
      "key_prefix": "eag_a1b2",
      "permissions": ["read:listings"],
      "created_at": "2026-06-10T12:00:00Z"
    }
  }

Errors:
  403 UPGRADE_REQUIRED   — pro tier required
  409 KEY_LIMIT_REACHED  — max 5 API keys per user
```

---

### DELETE /api-keys/{key_id}

```
Auth: Bearer token
Tier: pro+

Response 200: { "data": { "success": true } }
Side effects: key immediately rejected on next use
```

---

### POST /api-keys/{key_id}/rotate

```
Auth: Bearer token

Response 200:
  {
    "data": {
      "key": "eag_newkey...",   // new key; old key immediately invalid
      "key_prefix": "eag_newk"
    }
  }
```

---

## 19. Admin

> Internal endpoints. Require `X-Admin-Key` header. Not exposed publicly.

### GET /admin/users

```
Auth: X-Admin-Key

Query params: page, per_page, tier, status, q=email_search

Response 200: { "data": [...user objects with full detail...] }
```

---

### POST /admin/users/{user_id}/credits/adjust

```
Request:
  {
    "amount": 50,           // positive or negative
    "reason": "compensation for service disruption"
  }

Response 200: { "data": { "new_balance": 297, "transaction_id": "uuid" } }
```

---

### GET /admin/metrics

```
Response 200:
  {
    "data": {
      "mrr_usd": 22622,
      "active_users": 757,
      "trial_users": 189,
      "new_users_7d": 42,
      "churned_users_7d": 8,
      "daily_agent_runs_today": 612,
      "ai_cost_today_usd": 14.82,
      "avg_credits_per_user": 182,
      "p99_agent_run_ms": 487000
    }
  }
```

---

### POST /admin/feature-flags

```
Request:
  {
    "user_id": "uuid",          // null = global flag
    "flag_name": "new_dashboard_v2",
    "is_enabled": true,
    "expires_at": "2026-07-01T00:00:00Z"
  }

Response 201: { "data": { "id": "uuid", ...flag... } }
```

---

## 20. Rate Limiting

| Endpoint Group | Limit | Window | Scope |
|---|---|---|---|
| Auth (unauthenticated) | 20 req | 1 min | Per IP |
| POST /auth/login | 5 req | 15 min | Per IP + email |
| POST /auth/register | 10 req | 1 hour | Per IP |
| POST /auth/forgot-password | 3 req | 1 hour | Per IP + email |
| All authenticated endpoints | 120 req | 1 min | Per user |
| POST /*/analyze, POST /*/run | 20 req | 1 min | Per user |
| POST /content/generate | 30 req | 1 min | Per user |
| SSE /agent/runs/*/stream | 5 concurrent | — | Per user |
| Inbound webhooks | 1,000 req | 1 min | Per source IP |
| API key endpoints (Pro+) | 300 req | 1 min | Per API key |
| POST /admin/* | 60 req | 1 min | Per admin key |

**Rate limit response (429):**
```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Too many requests. Please slow down.",
    "details": {
      "retry_after_seconds": 23,
      "limit": 120,
      "window_seconds": 60
    }
  }
}
```

---

## 21. Error Catalog

```
CODE                        HTTP    Description
──────────────────────────────────────────────────────────────────────────────
VALIDATION_ERROR            422     Request body or query param validation failed
AUTHENTICATION_REQUIRED     401     No/missing Authorization header
TOKEN_EXPIRED               401     JWT or API key expired
TOKEN_INVALID               401     Malformed or revoked token
WRONG_PASSWORD              400     Incorrect current_password
INVALID_CREDENTIALS         401     Wrong email or password
TOO_MANY_ATTEMPTS           429     Auth brute-force lockout (15 min)
RATE_LIMITED                429     Rate limit exceeded (see Retry-After header)

EMAIL_ALREADY_EXISTS        409     Registration with duplicate email
NOT_FOUND                   404     Resource does not exist or access denied
FORBIDDEN                   403     Authenticated but not authorized (wrong user)
UPGRADE_REQUIRED            403     Feature requires higher subscription tier
STORE_LIMIT_REACHED         403     User has max allowed stores for tier
KEY_LIMIT_REACHED           409     Max API keys (5) already created

INSUFFICIENT_CREDITS        402     Not enough available credits for operation
DAILY_CREDIT_CAP_REACHED    429     Daily credit spend limit hit
SUBSCRIPTION_REQUIRED       402     Trial expired; subscription needed
PAYMENT_FAILED              402     Subscription in past_due state
SUBSCRIPTION_CANCELLED      402     Subscription cancelled; features restricted

SYNC_IN_PROGRESS            409     Store sync already running
AGENT_RUN_IN_PROGRESS       409     Daily agent already running for store
ANALYSIS_IN_PROGRESS        409     Analysis already queued/running for listing
OPTIMIZATION_IN_PROGRESS    409     Optimization being applied; wait for completion
OPTIMIZATIONS_EXIST         409     Pending optimizations already exist for listing
INVALID_STATUS              409     Action not valid for resource's current status
ALREADY_APPLIED             409     Content/optimization already applied
ALREADY_ON_TIER             400     Upgrade request for current tier

OAUTH_STATE_MISMATCH        400     Etsy OAuth CSRF check failed
OAUTH_DENIED                400     User denied Etsy OAuth permission
ETSY_TOKEN_EXPIRED          503     Etsy refresh token expired; re-connect store
ETSY_UPDATE_FAILED          424     Etsy rejected the listing update
ETSY_UNAVAILABLE            503     Etsy API timeout or 5xx error

NO_ANALYSIS_FOUND           404     No analysis exists yet; trigger with POST /analyze
AI_SERVICE_ERROR            503     AI provider returned an error
EMBEDDING_FAILED            503     Embedding generation failed

INTERNAL_ERROR              500     Unexpected server error (logged; include X-Request-Id in support ticket)
```

**Validation error detail format:**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": {
      "fields": {
        "email": ["Invalid email format"],
        "password": ["Must be at least 8 characters", "Must contain at least one digit"]
      }
    }
  }
}
```
