# Etsy AI Growth Agent — Database & Infrastructure Specification

> Canonical reference. Supersedes schema sections in `backend-spec.md`.
> Incorporates all tables from Sessions 2–5 (backend, frontend, AI agent, monetization).

---

## Table of Contents

1. [Schema Conventions & Extensions](#1-schema-conventions--extensions)
2. [Domain: Auth & Users](#2-domain-auth--users)
3. [Domain: Stores & Etsy OAuth](#3-domain-stores--etsy-oauth)
4. [Domain: Listings](#4-domain-listings)
5. [Domain: Analysis (SEO, Competitors, Pricing, Images)](#5-domain-analysis)
6. [Domain: Trends & Audience](#6-domain-trends--audience)
7. [Domain: Content & Optimizations](#7-domain-content--optimizations)
8. [Domain: Agent Runs](#8-domain-agent-runs)
9. [Domain: Billing & Credits (Paddle)](#9-domain-billing--credits)
10. [Domain: System & Config](#10-domain-system--config)
11. [Domain: RAG Embeddings](#11-domain-rag-embeddings)
12. [All Indexes](#12-all-indexes)
13. [Partitioning Strategy](#13-partitioning-strategy)
14. [Alembic Migration Conventions](#14-alembic-migration-conventions)
15. [Redis Cache Strategy](#15-redis-cache-strategy)
16. [Celery Queue Architecture](#16-celery-queue-architecture)

---

## 1. Schema Conventions & Extensions

```sql
-- Required extensions (run once, in migration 0001)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "vector";     -- pgvector for embeddings
CREATE EXTENSION IF NOT EXISTS "pg_trgm";   -- trigram indexes for ILIKE search on titles
CREATE EXTENSION IF NOT EXISTS "btree_gin"; -- GIN indexes on composite types

-- Global conventions
-- • All PKs:              UUID PRIMARY KEY DEFAULT gen_random_uuid()
-- • All timestamps:       TIMESTAMPTZ NOT NULL DEFAULT NOW()
-- • Soft deletes:         deleted_at TIMESTAMPTZ (nullable, NULL = not deleted)
-- • OAuth tokens:         AES-256-GCM encrypted at app layer before INSERT
-- • Money:                NUMERIC(10,2) — no FLOAT for currency
-- • Enum-like columns:    VARCHAR with CHECK constraint (not PG ENUM — easier to migrate)
-- • JSONB:                used for dynamic/variable schema fields only
-- • TEXT[]:               used for flat lists (tags, keywords)
-- • Scores:               SMALLINT CHECK (field BETWEEN 0 AND 100)
```

---

## 2. Domain: Auth & Users

### 2.1 users

```sql
CREATE TABLE users (
    id                              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    email                           VARCHAR(255) NOT NULL UNIQUE,
    name                            VARCHAR(255),
    password_hash                   VARCHAR(255),   -- NULL for OAuth-only accounts
    avatar_url                      TEXT,
    timezone                        VARCHAR(100) NOT NULL DEFAULT 'UTC',

    -- Subscription (Paddle — see monetization-spec.md)
    subscription_status             VARCHAR(20) NOT NULL DEFAULT 'trial'
                                        CHECK (subscription_status IN (
                                            'trial','active','past_due',
                                            'cancelling','cancelled','paused'
                                        )),
    subscription_tier               VARCHAR(20) NOT NULL DEFAULT 'trial'
                                        CHECK (subscription_tier IN (
                                            'trial','starter','growth','pro','agency'
                                        )),
    billing_interval                VARCHAR(10) NOT NULL DEFAULT 'monthly'
                                        CHECK (billing_interval IN ('monthly','annual')),
    trial_ends_at                   TIMESTAMPTZ,
    subscription_started_at         TIMESTAMPTZ,
    subscription_cancelled_at       TIMESTAMPTZ,
    subscription_current_period_end TIMESTAMPTZ,

    -- Paddle identifiers
    paddle_customer_id              VARCHAR(100) UNIQUE,
    paddle_subscription_id          VARCHAR(100) UNIQUE,

    -- AI Credits
    credits_balance                 INTEGER NOT NULL DEFAULT 30,  -- trial grant = 30
    credits_reserved                INTEGER NOT NULL DEFAULT 0,   -- held by in-flight runs

    -- Preferences
    email_notifications             BOOLEAN NOT NULL DEFAULT TRUE,
    email_digest_frequency          VARCHAR(10) NOT NULL DEFAULT 'daily'
                                        CHECK (email_digest_frequency IN ('daily','weekly','never')),
    onboarding_completed            BOOLEAN NOT NULL DEFAULT FALSE,
    onboarding_step                 SMALLINT NOT NULL DEFAULT 0,

    -- Timestamps
    last_login_at                   TIMESTAMPTZ,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at                      TIMESTAMPTZ
);

-- Prevent negative credit balances
ALTER TABLE users ADD CONSTRAINT chk_credits_non_negative
    CHECK (credits_balance >= 0);
ALTER TABLE users ADD CONSTRAINT chk_credits_reserved_non_negative
    CHECK (credits_reserved >= 0);
```

### 2.2 oauth_accounts

```sql
CREATE TABLE oauth_accounts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider            VARCHAR(50) NOT NULL
                            CHECK (provider IN ('google','github')),
    provider_account_id VARCHAR(255) NOT NULL,
    access_token        TEXT,
    refresh_token       TEXT,
    expires_at          TIMESTAMPTZ,
    raw_profile         JSONB,          -- provider profile JSON for debugging
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (provider, provider_account_id)
);
```

### 2.3 sessions

```sql
CREATE TABLE sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(64) NOT NULL UNIQUE,    -- SHA-256(JWT); never store raw JWT
    user_agent  TEXT,
    ip_address  INET,
    device_type VARCHAR(20)
                    CHECK (device_type IN ('web','mobile','api','unknown')),
    is_revoked  BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 2.4 password_reset_tokens

```sql
CREATE TABLE password_reset_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(64) NOT NULL UNIQUE,
    expires_at  TIMESTAMPTZ NOT NULL,
    used        BOOLEAN NOT NULL DEFAULT FALSE,
    used_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 2.5 api_keys (Pro+ tier)

```sql
-- API keys for programmatic access (Pro: read-only, Agency: read+write)
CREATE TABLE api_keys (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            VARCHAR(100) NOT NULL,
    key_hash        VARCHAR(64) NOT NULL UNIQUE,    -- SHA-256 of the raw key
    key_prefix      VARCHAR(8) NOT NULL,            -- first 8 chars shown in UI (e.g. "eag_a1b2")
    permissions     TEXT[] NOT NULL DEFAULT '{}',  -- ['read:listings','write:optimizations']
    last_used_at    TIMESTAMPTZ,
    last_used_ip    INET,
    expires_at      TIMESTAMPTZ,                    -- NULL = never expires
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 3. Domain: Stores & Etsy OAuth

### 3.1 stores

```sql
CREATE TABLE stores (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Etsy identifiers
    etsy_shop_id        VARCHAR(100) NOT NULL UNIQUE,
    shop_name           VARCHAR(255) NOT NULL,
    shop_url            VARCHAR(500),
    icon_url            VARCHAR(500),
    banner_url          VARCHAR(500),
    currency_code       VARCHAR(10) NOT NULL DEFAULT 'USD',
    country_code        VARCHAR(10),
    listing_count       INTEGER NOT NULL DEFAULT 0,
    sale_count          INTEGER NOT NULL DEFAULT 0,
    average_rating      NUMERIC(3,2),
    review_count        INTEGER NOT NULL DEFAULT 0,

    -- Etsy OAuth tokens (AES-256-GCM encrypted, never stored plaintext)
    etsy_access_token   TEXT,
    etsy_refresh_token  TEXT,
    token_expires_at    TIMESTAMPTZ,
    token_scope         TEXT,

    -- Status
    status              VARCHAR(20) NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active','paused','disconnected','error')),
    sync_status         VARCHAR(20) NOT NULL DEFAULT 'idle'
                            CHECK (sync_status IN ('idle','syncing','error')),
    last_synced_at      TIMESTAMPTZ,
    sync_error          TEXT,

    -- Health scores
    health_score        SMALLINT CHECK (health_score BETWEEN 0 AND 100),
    health_computed_at  TIMESTAMPTZ,
    health_breakdown    JSONB,      -- {seo:72, pricing:65, images:80, trends:55, reviews:70}

    -- Agent settings
    agent_enabled       BOOLEAN NOT NULL DEFAULT TRUE,
    agent_schedule      VARCHAR(50) NOT NULL DEFAULT '0 7 * * *',  -- cron expression; Pro+ can customize
    agent_last_run_at   TIMESTAMPTZ,

    -- Tier-specific features
    listing_analysis_cap    SMALLINT,                   -- NULL = unlimited (Pro+); 20 = Starter, 50 = Growth
    brand_voice_id          UUID,                       -- FK to store_brand_voices, Growth+

    -- White-label (Agency tier)
    white_label_config_id   UUID,                       -- FK to white_label_configs

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 3.2 store_brand_voices (Growth+)

```sql
CREATE TABLE store_brand_voices (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id            UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE UNIQUE,
    voice_description   TEXT NOT NULL,                  -- free-form brand voice description
    tone_keywords       TEXT[] NOT NULL DEFAULT '{}',   -- ['warm','artisanal','approachable']
    example_phrases     TEXT[] NOT NULL DEFAULT '{}',   -- example sentences that match brand
    prohibited_words    TEXT[] NOT NULL DEFAULT '{}',   -- words AI must avoid
    custom_instructions TEXT,                           -- extra prompt instructions
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 4. Domain: Listings

### 4.1 listings

```sql
CREATE TABLE listings (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id         UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    etsy_listing_id  BIGINT NOT NULL UNIQUE,

    -- Content
    title            VARCHAR(500),
    description      TEXT,
    tags             TEXT[] NOT NULL DEFAULT '{}',      -- max 13 in Etsy, each max 20 chars
    materials        TEXT[] NOT NULL DEFAULT '{}',
    style            TEXT[] NOT NULL DEFAULT '{}',

    -- Pricing
    price_usd        NUMERIC(10,2),                    -- normalized to USD
    original_price   NUMERIC(10,2),                    -- in currency_code
    currency_code    VARCHAR(10) NOT NULL DEFAULT 'USD',
    quantity         INTEGER,
    is_customizable  BOOLEAN NOT NULL DEFAULT FALSE,

    -- State
    state            VARCHAR(20) NOT NULL DEFAULT 'active'
                         CHECK (state IN ('active','inactive','draft',
                                          'expired','sold_out','removed')),

    -- Taxonomy / category
    taxonomy_id      INTEGER,
    taxonomy_path    TEXT[] NOT NULL DEFAULT '{}',      -- ['Clothing','Tops & Tees','T-Shirts']
    primary_category VARCHAR(255),                      -- derived from taxonomy_path[1]
    section_id       BIGINT,
    section_title    VARCHAR(255),

    -- Images
    main_image_url   TEXT,
    image_urls       TEXT[] NOT NULL DEFAULT '{}',
    image_count      SMALLINT NOT NULL DEFAULT 0,

    -- Etsy analytics
    views_count      INTEGER NOT NULL DEFAULT 0,
    favorites_count  INTEGER NOT NULL DEFAULT 0,
    sales_count      INTEGER NOT NULL DEFAULT 0,
    average_rating   NUMERIC(3,2),
    review_count     INTEGER NOT NULL DEFAULT 0,

    -- Computed scores (set by analysis tasks)
    seo_score        SMALLINT CHECK (seo_score BETWEEN 0 AND 100),
    seo_scored_at    TIMESTAMPTZ,
    image_score      SMALLINT CHECK (image_score BETWEEN 0 AND 100),
    image_scored_at  TIMESTAMPTZ,

    -- Staleness detection for RAG
    content_hash     VARCHAR(64),    -- SHA-256 of (title+description+tags); used by embedding pipeline

    -- Etsy timestamps
    etsy_created_at  TIMESTAMPTZ,
    etsy_updated_at  TIMESTAMPTZ,

    -- Our timestamps
    synced_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 4.2 listing_metrics_history

```sql
-- Daily snapshot for trend charts; one row per listing per day
CREATE TABLE listing_metrics_history (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id      UUID NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    views_count     INTEGER NOT NULL DEFAULT 0,
    favorites_count INTEGER NOT NULL DEFAULT 0,
    sales_count     INTEGER NOT NULL DEFAULT 0,
    price_usd       NUMERIC(10,2),
    seo_score       SMALLINT,
    image_score     SMALLINT,
    recorded_date   DATE NOT NULL,
    UNIQUE (listing_id, recorded_date)
);
```

---

## 5. Domain: Analysis

### 5.1 seo_analyses

```sql
CREATE TABLE seo_analyses (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id              UUID NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    agent_run_id            UUID REFERENCES agent_runs(id) ON DELETE SET NULL,

    -- Scores
    overall_score           SMALLINT NOT NULL CHECK (overall_score BETWEEN 0 AND 100),
    title_score             SMALLINT CHECK (title_score BETWEEN 0 AND 100),
    tags_score              SMALLINT CHECK (tags_score BETWEEN 0 AND 100),
    description_score       SMALLINT CHECK (description_score BETWEEN 0 AND 100),
    priority                VARCHAR(10) NOT NULL DEFAULT 'medium'
                                CHECK (priority IN ('critical','high','medium','low')),

    -- Title recommendations
    current_title           TEXT,
    optimized_title         TEXT,
    title_primary_keyword   VARCHAR(255),
    title_keyword_position  VARCHAR(20)
                                CHECK (title_keyword_position IN
                                    ('first_3_words','first_half','second_half','absent')),
    title_issues            TEXT[] NOT NULL DEFAULT '{}',
    title_change_rationale  TEXT,

    -- Tag recommendations
    current_tags            TEXT[] NOT NULL DEFAULT '{}',
    optimized_tags          TEXT[] NOT NULL DEFAULT '{}',   -- exactly 13, each ≤ 20 chars
    weak_tags               TEXT[] NOT NULL DEFAULT '{}',
    missing_high_value_tags TEXT[] NOT NULL DEFAULT '{}',
    tag_replacements        JSONB,  -- [{remove, add, reason}]

    -- Description recommendations
    description_issues      TEXT[] NOT NULL DEFAULT '{}',
    recommended_additions   TEXT[] NOT NULL DEFAULT '{}',
    first_paragraph_ok      BOOLEAN NOT NULL DEFAULT TRUE,

    -- Impact estimates
    estimated_traffic_lift  SMALLINT,   -- percent
    competitor_gap_summary  TEXT,

    -- Full structured output (raw AI response for debugging)
    raw_analysis            JSONB,

    -- AI metadata
    model_used              VARCHAR(100),
    input_tokens            INTEGER,
    output_tokens           INTEGER,
    cost_usd                NUMERIC(10,6),
    from_cache              BOOLEAN NOT NULL DEFAULT FALSE,

    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 5.2 competitors

```sql
-- Individual competitor listings discovered via Etsy search
CREATE TABLE competitors (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id            UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    etsy_listing_id     BIGINT NOT NULL,
    etsy_shop_id        VARCHAR(100),
    shop_name           VARCHAR(255),

    -- Listing data
    title               VARCHAR(500),
    description         TEXT,
    tags                TEXT[] NOT NULL DEFAULT '{}',
    price_usd           NUMERIC(10,2),
    currency_code       VARCHAR(10),
    main_image_url      TEXT,
    category            VARCHAR(255),

    -- Metrics
    views_count         INTEGER,
    favorites_count     INTEGER,
    sales_estimate      INTEGER,        -- favorites × category_conversion_factor
    review_count        INTEGER,
    average_rating      NUMERIC(3,2),

    -- Discovery metadata
    rank_position       SMALLINT,       -- position in search results (1-indexed)
    search_keyword      VARCHAR(255),   -- keyword that surfaced this competitor
    competitor_score    SMALLINT CHECK (competitor_score BETWEEN 0 AND 100),

    -- Staleness
    content_hash        VARCHAR(64),
    last_seen_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (store_id, etsy_listing_id)
);
```

### 5.3 competitor_analyses

```sql
-- AI-synthesized competitive intelligence per store per category
CREATE TABLE competitor_analyses (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id                 UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    category                 VARCHAR(255),
    agent_run_id             UUID REFERENCES agent_runs(id) ON DELETE SET NULL,

    -- Market position
    price_percentile         SMALLINT CHECK (price_percentile BETWEEN 0 AND 100),
    market_positioning       VARCHAR(20)
                                 CHECK (market_positioning IN ('budget','mid_market','premium','luxury')),
    positioning_consistency  SMALLINT CHECK (positioning_consistency BETWEEN 0 AND 100),

    -- Analysis results
    top_competitor_patterns  JSONB,     -- [{pattern, frequency, seller_does_this, impact}]
    pricing_opportunities    JSONB,     -- [{listing_title_fragment, current, competitor_avg, recommended, rationale}]
    content_gaps             TEXT[] NOT NULL DEFAULT '{}',
    quick_wins               JSONB,     -- [{action, effort, expected_impact}]
    differentiation_ops      TEXT[] NOT NULL DEFAULT '{}',

    -- Raw output
    raw_analysis             JSONB,

    -- AI metadata
    model_used               VARCHAR(100),
    input_tokens             INTEGER,
    output_tokens            INTEGER,
    cost_usd                 NUMERIC(10,6),

    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 5.4 pricing_analyses

```sql
CREATE TABLE pricing_analyses (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id            UUID NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    agent_run_id          UUID REFERENCES agent_runs(id) ON DELETE SET NULL,

    -- Pricing data
    current_price         NUMERIC(10,2) NOT NULL,
    market_min            NUMERIC(10,2),
    market_max            NUMERIC(10,2),
    market_avg            NUMERIC(10,2),
    market_median         NUMERIC(10,2),
    recommended_price     NUMERIC(10,2),
    price_direction       VARCHAR(10) NOT NULL DEFAULT 'hold'
                              CHECK (price_direction IN ('increase','decrease','hold')),
    price_position        VARCHAR(20)
                              CHECK (price_position IN ('below_market','at_market','above_market','premium')),

    -- Insights
    demand_level          VARCHAR(10)
                              CHECK (demand_level IN ('low','medium','high','very_high')),
    confidence            VARCHAR(10)
                              CHECK (confidence IN ('high','medium','low')),
    rationale             TEXT,
    bundle_opportunities  JSONB,     -- [{description, items[], suggested_price}]
    competitor_prices     JSONB,     -- [{shop_name, price}]

    -- AI metadata
    model_used            VARCHAR(100),
    input_tokens          INTEGER,
    output_tokens         INTEGER,
    cost_usd              NUMERIC(10,6),

    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 5.5 image_analyses

```sql
CREATE TABLE image_analyses (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id              UUID NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    agent_run_id            UUID REFERENCES agent_runs(id) ON DELETE SET NULL,

    -- Overall
    overall_visual_score    SMALLINT CHECK (overall_visual_score BETWEEN 0 AND 100),
    image_count_analyzed    SMALLINT NOT NULL DEFAULT 0,

    -- Thumbnail (first image — most critical for CTR)
    thumbnail_score         SMALLINT CHECK (thumbnail_score BETWEEN 0 AND 100),
    thumbnail_issues        TEXT[] NOT NULL DEFAULT '{}',
    thumbnail_readable      BOOLEAN,
    thumbnail_recommendation TEXT,

    -- Image set quality
    lighting_quality        VARCHAR(20)
                                CHECK (lighting_quality IN ('excellent','good','needs_improvement','poor')),
    background_recommendation TEXT,
    missing_shot_types      TEXT[] NOT NULL DEFAULT '{}',
                            -- ['lifestyle','detail','scale_reference','back_view','packaging']

    -- Actionable improvements
    priority_improvements   JSONB,  -- [{improvement, effort, impact}]

    -- Raw AI output
    raw_analysis            JSONB,

    -- AI metadata
    model_used              VARCHAR(100),
    input_tokens            INTEGER,
    output_tokens           INTEGER,
    cost_usd                NUMERIC(10,6),

    analyzed_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 6. Domain: Trends & Audience

### 6.1 trends

```sql
-- Raw trend signals from external sources
CREATE TABLE trends (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    keyword             VARCHAR(255) NOT NULL,
    source              VARCHAR(50) NOT NULL
                            CHECK (source IN ('google_trends','pinterest','reddit',
                                              'tiktok','instagram','etsy_search')),
    region              VARCHAR(10) NOT NULL DEFAULT 'US',
    category            VARCHAR(255),

    -- Metrics
    trend_score         SMALLINT NOT NULL CHECK (trend_score BETWEEN 0 AND 100),
    volume_index        INTEGER,            -- Google Trends 0-100 normalized
    search_volume_trend VARCHAR(20)
                            CHECK (search_volume_trend IN (
                                'sharply_rising','rising','stable','declining'
                            )),
    growth_rate_pct     NUMERIC(8,4),       -- week-over-week %
    lifecycle_stage     VARCHAR(15)
                            CHECK (lifecycle_stage IN ('emerging','growing','peak','declining')),
    peak_predicted_date DATE,
    is_seasonal         BOOLEAN NOT NULL DEFAULT FALSE,
    season_peak_month   SMALLINT CHECK (season_peak_month BETWEEN 1 AND 12),

    -- Related data
    related_keywords    TEXT[] NOT NULL DEFAULT '{}',
    raw_data            JSONB,

    recorded_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (keyword, source, region, DATE_TRUNC('day', recorded_at))
);
```

### 6.2 trend_reports

```sql
-- AI-synthesized trend intelligence per store (daily/weekly/monthly)
CREATE TABLE trend_reports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id        UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    agent_run_id    UUID REFERENCES agent_runs(id) ON DELETE SET NULL,
    report_type     VARCHAR(10) NOT NULL CHECK (report_type IN ('daily','weekly','monthly')),
    period_start    DATE NOT NULL,
    period_end      DATE NOT NULL,

    -- Synthesized content
    executive_summary       TEXT,
    trend_opportunities     JSONB,  -- [{trend_name, lifecycle, relevance_score, recommended_keywords, listing_ideas, time_sensitivity}]
    seasonal_calendar       JSONB,  -- [{event_name, days_until, prep_deadline, product_ideas}]
    declining_to_remove     TEXT[] NOT NULL DEFAULT '{}',

    -- AI metadata
    model_used              VARCHAR(100),
    input_tokens            INTEGER,
    output_tokens           INTEGER,
    cost_usd                NUMERIC(10,6),

    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 6.3 audience_personas

```sql
CREATE TABLE audience_personas (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id                UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    agent_run_id            UUID REFERENCES agent_runs(id) ON DELETE SET NULL,

    -- Persona definition
    persona_name            VARCHAR(255) NOT NULL,
    estimated_share_pct     SMALLINT CHECK (estimated_share_pct BETWEEN 0 AND 100),
    primary_motivation      TEXT,
    price_sensitivity       VARCHAR(10)
                                CHECK (price_sensitivity IN ('low','medium','high')),

    -- Demographics & behavior
    interests               TEXT[] NOT NULL DEFAULT '{}',
    search_keywords         TEXT[] NOT NULL DEFAULT '{}',
    seasonality             TEXT[] NOT NULL DEFAULT '{}',   -- ['Christmas','Valentines Day']
    platforms               TEXT[] NOT NULL DEFAULT '{}',   -- ['instagram','pinterest']
    pain_points             TEXT[] NOT NULL DEFAULT '{}',
    buying_motivations      TEXT[] NOT NULL DEFAULT '{}',
    content_ideas           TEXT[] NOT NULL DEFAULT '{}',

    -- Strategy
    listing_angle           TEXT,
    is_underserved          BOOLEAN NOT NULL DEFAULT FALSE,

    -- AI metadata
    model_used              VARCHAR(100),
    input_tokens            INTEGER,
    output_tokens           INTEGER,
    cost_usd                NUMERIC(10,6),

    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 6.4 communities

```sql
-- Relevant online communities discovered by audience analysis
CREATE TABLE communities (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id         UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    platform         VARCHAR(50) NOT NULL
                         CHECK (platform IN ('reddit','pinterest','instagram','facebook','tiktok')),
    name             VARCHAR(255) NOT NULL,
    url              TEXT,
    member_count     INTEGER,
    engagement_score SMALLINT CHECK (engagement_score BETWEEN 0 AND 100),
    relevance_score  SMALLINT CHECK (relevance_score BETWEEN 0 AND 100),
    description      TEXT,
    top_posts        JSONB,
    analyzed_at      TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (store_id, platform, name)
);
```

---

## 7. Domain: Content & Optimizations

### 7.1 generated_content

```sql
CREATE TABLE generated_content (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id      UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    listing_id    UUID REFERENCES listings(id) ON DELETE SET NULL,
    agent_run_id  UUID REFERENCES agent_runs(id) ON DELETE SET NULL,

    content_type  VARCHAR(50) NOT NULL
                      CHECK (content_type IN (
                          'etsy_title','etsy_description','etsy_tags',
                          'pinterest_pin','instagram_caption','tiktok_script',
                          'facebook_post','email_subject','email_body'
                      )),
    content       TEXT NOT NULL,
    tone          VARCHAR(50),                         -- 'professional','casual','playful'
    keywords_used TEXT[] NOT NULL DEFAULT '{}',
    is_seo_optimized BOOLEAN NOT NULL DEFAULT TRUE,

    -- User feedback
    user_rating   SMALLINT CHECK (user_rating BETWEEN 1 AND 5),
    is_applied    BOOLEAN NOT NULL DEFAULT FALSE,
    applied_at    TIMESTAMPTZ,

    -- AI metadata
    model_used    VARCHAR(100),
    input_tokens  INTEGER,
    output_tokens INTEGER,
    cost_usd      NUMERIC(10,6),

    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 7.2 listing_optimizations

```sql
-- Human-in-the-loop approval gate for all Etsy write-back operations.
-- An optimization is created with status='pending', user approves,
-- then it is applied to Etsy via the API.
CREATE TABLE listing_optimizations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id          UUID NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    agent_run_id        UUID REFERENCES agent_runs(id) ON DELETE SET NULL,

    optimization_type   VARCHAR(20) NOT NULL
                            CHECK (optimization_type IN (
                                'title','description','tags',
                                'price','images'
                            )),

    -- Before / after
    old_value           TEXT,   -- JSON string for tags/complex types
    new_value           TEXT NOT NULL,
    change_summary      TEXT,
    impact_estimate     JSONB,  -- {seo_score_delta: 12, estimated_views_lift_pct: 18}

    -- Approval workflow
    status              VARCHAR(20) NOT NULL DEFAULT 'pending'
                            CHECK (status IN (
                                'pending','approved','rejected','applying','applied','failed'
                            )),
    approved_at         TIMESTAMPTZ,
    approved_by         VARCHAR(50)
                            CHECK (approved_by IN ('user','auto')),
    rejected_at         TIMESTAMPTZ,
    rejection_reason    TEXT,
    applied_at          TIMESTAMPTZ,
    etsy_update_status  VARCHAR(10)
                            CHECK (etsy_update_status IN ('pending','success','failed')),
    etsy_update_error   TEXT,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 7.3 optimization_results

```sql
-- Measures impact of applied optimizations over time (A/B-style tracking)
CREATE TABLE optimization_results (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    optimization_id     UUID NOT NULL REFERENCES listing_optimizations(id) ON DELETE CASCADE,
    measurement_period  VARCHAR(10) NOT NULL
                            CHECK (measurement_period IN ('3d','7d','14d','30d')),

    -- Snapshot: before apply
    views_before        INTEGER,
    favorites_before    INTEGER,
    sales_before        INTEGER,
    seo_score_before    SMALLINT,

    -- Snapshot: after apply
    views_after         INTEGER,
    favorites_after     INTEGER,
    sales_after         INTEGER,
    seo_score_after     SMALLINT,

    -- Deltas (computed)
    views_delta_pct     NUMERIC(8,2),
    favorites_delta_pct NUMERIC(8,2),

    measured_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 7.4 webhook_configs (Pro+ outbound)

```sql
-- User-configured outbound webhooks (Pro+ tier)
-- Fires when agent completes, new optimizations available, etc.
CREATE TABLE webhook_configs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    store_id            UUID REFERENCES stores(id) ON DELETE CASCADE,    -- NULL = all stores
    name                VARCHAR(100) NOT NULL,
    url                 TEXT NOT NULL,
    secret_hash         VARCHAR(64) NOT NULL,    -- SHA-256 of HMAC signing secret
    events              TEXT[] NOT NULL DEFAULT '{}',
                        -- ['agent.completed','optimization.ready','trend.alert']
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    last_triggered_at   TIMESTAMPTZ,
    last_status_code    SMALLINT,
    consecutive_failures SMALLINT NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Auto-disable after 10 consecutive failures
ALTER TABLE webhook_configs ADD CONSTRAINT chk_auto_disable
    CHECK (consecutive_failures <= 10 OR NOT is_active);
```

---

## 8. Domain: Agent Runs

### 8.1 agent_runs

```sql
CREATE TABLE agent_runs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id         UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    user_id          UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    run_type         VARCHAR(50) NOT NULL
                         CHECK (run_type IN (
                             'daily','seo_analysis','competitor_analysis',
                             'trend_discovery','content_generation','image_analysis',
                             'pricing_analysis','audience_discovery',
                             'weekly_report','monthly_plan','manual_audit'
                         )),
    triggered_by     VARCHAR(20) NOT NULL DEFAULT 'scheduler'
                         CHECK (triggered_by IN ('scheduler','user','api')),

    status           VARCHAR(20) NOT NULL DEFAULT 'pending'
                         CHECK (status IN ('pending','running','completed','failed','cancelled')),

    -- Progress (written by Celery tasks, streamed via SSE)
    progress_pct     SMALLINT NOT NULL DEFAULT 0 CHECK (progress_pct BETWEEN 0 AND 100),
    current_phase    VARCHAR(100),

    -- Results
    result_summary   JSONB,  -- daily_synthesis output
    error_message    TEXT,

    -- Aggregate cost tracking
    total_input_tokens      INTEGER NOT NULL DEFAULT 0,
    total_output_tokens     INTEGER NOT NULL DEFAULT 0,
    total_cache_read_tokens INTEGER NOT NULL DEFAULT 0,
    total_cost_usd          NUMERIC(10,6) NOT NULL DEFAULT 0,
    credits_used            INTEGER NOT NULL DEFAULT 0,
    credits_reserved        INTEGER NOT NULL DEFAULT 0,  -- held at start, settled on completion

    -- Timing
    started_at       TIMESTAMPTZ,
    completed_at     TIMESTAMPTZ,
    duration_ms      INTEGER,    -- computed on completion

    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 8.2 agent_run_logs

```sql
-- Granular per-task cost/token tracking within a run
CREATE TABLE agent_run_logs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id              UUID NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,

    task_name           VARCHAR(100) NOT NULL,  -- 'seo_analysis','daily_synthesis', etc.
    model               VARCHAR(50) NOT NULL,
    input_tokens        INTEGER NOT NULL DEFAULT 0,
    output_tokens       INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens   INTEGER NOT NULL DEFAULT 0,
    cache_write_tokens  INTEGER NOT NULL DEFAULT 0,
    cost_usd            NUMERIC(10,6) NOT NULL,
    duration_ms         INTEGER,
    from_cache          BOOLEAN NOT NULL DEFAULT FALSE,     -- Redis response cache hit
    thinking_used       BOOLEAN NOT NULL DEFAULT FALSE,
    error_message       TEXT,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 8.3 agent_tasks

```sql
-- Sub-task level tracking (individual Celery tasks within a run)
CREATE TABLE agent_tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
    task_name       VARCHAR(100) NOT NULL,
    celery_task_id  VARCHAR(255),           -- Celery's internal task UUID
    status          VARCHAR(20) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','running','completed','failed','skipped')),
    input_data      JSONB,
    output_data     JSONB,
    error_message   TEXT,
    retry_count     SMALLINT NOT NULL DEFAULT 0,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    duration_ms     INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 8.4 notifications

```sql
CREATE TABLE notifications (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    store_id    UUID REFERENCES stores(id) ON DELETE CASCADE,
    run_id      UUID REFERENCES agent_runs(id) ON DELETE SET NULL,

    type        VARCHAR(50) NOT NULL
                    CHECK (type IN (
                        'agent_complete','seo_opportunity','trend_alert',
                        'competitor_change','optimization_ready','optimization_applied',
                        'billing','low_credits','report_ready','system'
                    )),
    priority    VARCHAR(10) NOT NULL DEFAULT 'medium'
                    CHECK (priority IN ('low','medium','high')),
    title       VARCHAR(255) NOT NULL,
    message     TEXT NOT NULL,
    data        JSONB,           -- arbitrary metadata (optimization_id, trend_name, etc.)
    action_url  TEXT,

    is_read     BOOLEAN NOT NULL DEFAULT FALSE,
    read_at     TIMESTAMPTZ,
    email_sent  BOOLEAN NOT NULL DEFAULT FALSE,
    email_sent_at TIMESTAMPTZ,

    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 9. Domain: Billing & Credits

### 9.1 subscription_plans

```sql
-- Reference table — seed data, not user data
CREATE TABLE subscription_plans (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                        VARCHAR(20) NOT NULL UNIQUE
                                    CHECK (name IN ('trial','starter','growth','pro','agency')),
    display_name                VARCHAR(100) NOT NULL,
    price_monthly_usd           NUMERIC(10,2) NOT NULL,
    price_annual_usd            NUMERIC(10,2) NOT NULL,    -- full year price (20% off)
    max_stores                  SMALLINT NOT NULL,         -- -1 = unlimited
    credits_monthly             INTEGER NOT NULL,
    credits_rollover_pct        SMALLINT NOT NULL DEFAULT 0,  -- 0, 50, or 100
    listing_analysis_cap        SMALLINT,                  -- NULL = unlimited
    features                    JSONB NOT NULL,            -- {audience: true, monthly_plan: true, ...}

    -- Paddle price IDs (set via admin, not hardcoded)
    paddle_price_id_monthly     VARCHAR(100),
    paddle_price_id_annual      VARCHAR(100),

    is_active                   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed data
INSERT INTO subscription_plans (name, display_name, price_monthly_usd, price_annual_usd,
    max_stores, credits_monthly, credits_rollover_pct, listing_analysis_cap, features)
VALUES
    ('trial',   'Free Trial',  0.00,  0.00,   1,    30,   0,   20,   '{"audience":false,"monthly_plan":false,"ab_testing":false,"api_access":false,"white_label":false}'),
    ('starter', 'Starter',    19.00, 182.00,  1,   100,   0,   20,   '{"audience":false,"monthly_plan":false,"ab_testing":false,"api_access":false,"white_label":false}'),
    ('growth',  'Growth',     49.00, 470.00,  2,   300,  50,   50,   '{"audience":true,"monthly_plan":true,"ab_testing":true,"api_access":false,"white_label":false}'),
    ('pro',     'Pro',        99.00, 950.00,  5,   750,  50, NULL,   '{"audience":true,"monthly_plan":true,"ab_testing":true,"api_access":"read","white_label":false}'),
    ('agency',  'Agency',    299.00,2870.00, 20,  2500, 100, NULL,   '{"audience":true,"monthly_plan":true,"ab_testing":true,"api_access":"read_write","white_label":true}');
```

### 9.2 credit_transactions

```sql
CREATE TABLE credit_transactions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    amount              INTEGER NOT NULL,    -- positive = credit, negative = deduction
    balance_after       INTEGER NOT NULL,    -- denormalized; avoids recalculation

    transaction_type    VARCHAR(30) NOT NULL
                            CHECK (transaction_type IN (
                                'trial_grant',          -- initial 30 credits on signup
                                'subscription_renewal', -- monthly allotment
                                'topup_purchase',       -- one-time credit purchase
                                'agent_run_deduction',  -- AI usage
                                'manual_adjustment',    -- admin correction
                                'referral_bonus',       -- affiliate reward
                                'refund'                -- credit refund
                            )),

    -- References
    run_id              UUID REFERENCES agent_runs(id) ON DELETE SET NULL,
    paddle_transaction_id VARCHAR(100),

    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 9.3 paddle_events

```sql
-- Raw Paddle webhook event log; used for idempotency and debugging
CREATE TABLE paddle_events (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paddle_event_id     VARCHAR(100) NOT NULL UNIQUE,   -- Paddle's notification_id
    event_type          VARCHAR(100) NOT NULL,
    payload             JSONB NOT NULL,
    processed_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id             UUID REFERENCES users(id) ON DELETE SET NULL,
    error_message       TEXT,
    retry_count         SMALLINT NOT NULL DEFAULT 0
);
```

---

## 10. Domain: System & Config

### 10.1 white_label_configs (Agency tier)

```sql
CREATE TABLE white_label_configs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    company_name    VARCHAR(255) NOT NULL,
    custom_domain   VARCHAR(255) UNIQUE,    -- e.g. 'app.myagency.com'
    logo_url        TEXT,
    favicon_url     TEXT,
    primary_color   VARCHAR(7) NOT NULL DEFAULT '#6366F1',    -- hex color
    secondary_color VARCHAR(7) NOT NULL DEFAULT '#4F46E5',
    is_domain_verified BOOLEAN NOT NULL DEFAULT FALSE,
    domain_verified_at TIMESTAMPTZ,
    ssl_provisioned  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 10.2 feature_flags

```sql
-- Per-user or global feature toggles for A/B testing, beta features, gradual rollouts
CREATE TABLE feature_flags (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES users(id) ON DELETE CASCADE,  -- NULL = global flag
    flag_name   VARCHAR(100) NOT NULL,
    is_enabled  BOOLEAN NOT NULL DEFAULT FALSE,
    metadata    JSONB,          -- arbitrary config for the flag
    expires_at  TIMESTAMPTZ,    -- NULL = permanent
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, flag_name),
    UNIQUE NULLS NOT DISTINCT (user_id, flag_name)
);
```

### 10.3 audit_log

```sql
-- Security/compliance audit trail for sensitive actions
CREATE TABLE audit_log (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES users(id) ON DELETE SET NULL,
    action      VARCHAR(100) NOT NULL,  -- 'optimization.applied','store.connected','billing.cancelled'
    entity_type VARCHAR(50),
    entity_id   UUID,
    old_value   JSONB,
    new_value   JSONB,
    ip_address  INET,
    user_agent  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- Partition by month; auto-managed by pg_partman
CREATE TABLE audit_log_2026_06 PARTITION OF audit_log
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
```

---

## 11. Domain: RAG Embeddings

### 11.1 embeddings

```sql
-- pgvector store for all embedded content.
-- voyage-3 → 1024-dim vectors. voyage-3-lite → 512-dim (separate table if needed).
CREATE TABLE embeddings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type     VARCHAR(50) NOT NULL
                        CHECK (entity_type IN (
                            'listing',              -- own store listing
                            'competitor_listing',   -- competitor listing
                            'trend_report',         -- trend report paragraph
                            'reddit_thread',        -- Reddit post
                            'audience_persona'      -- persona description
                        )),
    entity_id       UUID NOT NULL,
    chunk_index     SMALLINT NOT NULL DEFAULT 0,    -- 0 for single-chunk entities
    content_text    TEXT NOT NULL,                  -- the text that was embedded
    content_hash    VARCHAR(64) NOT NULL,           -- SHA-256; skip re-embedding if unchanged
    embedding       vector(1024) NOT NULL,          -- voyage-3 output
    metadata        JSONB,                          -- searchable attributes for pre-filtering
    model_used      VARCHAR(50) NOT NULL DEFAULT 'voyage-3',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (entity_type, entity_id, chunk_index)
);
```

---

## 12. All Indexes

```sql
-- ─────────────────────────────────────────────────────────────
-- USERS & AUTH
-- ─────────────────────────────────────────────────────────────
CREATE INDEX idx_users_email
    ON users(email) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_paddle_customer
    ON users(paddle_customer_id) WHERE paddle_customer_id IS NOT NULL;
CREATE INDEX idx_users_paddle_subscription
    ON users(paddle_subscription_id) WHERE paddle_subscription_id IS NOT NULL;
CREATE INDEX idx_users_subscription_status
    ON users(subscription_status, subscription_tier);

CREATE INDEX idx_sessions_user        ON sessions(user_id);
CREATE INDEX idx_sessions_token       ON sessions(token_hash);
CREATE INDEX idx_sessions_expires     ON sessions(expires_at)
    WHERE is_revoked = FALSE;

CREATE INDEX idx_oauth_user           ON oauth_accounts(user_id);

CREATE UNIQUE INDEX idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_user        ON api_keys(user_id) WHERE is_active = TRUE;

-- ─────────────────────────────────────────────────────────────
-- STORES
-- ─────────────────────────────────────────────────────────────
CREATE INDEX idx_stores_user          ON stores(user_id);
CREATE INDEX idx_stores_etsy_shop     ON stores(etsy_shop_id);
CREATE INDEX idx_stores_active        ON stores(user_id, status)
    WHERE status = 'active';

-- ─────────────────────────────────────────────────────────────
-- LISTINGS
-- ─────────────────────────────────────────────────────────────
CREATE INDEX idx_listings_store       ON listings(store_id);
CREATE INDEX idx_listings_etsy_id     ON listings(etsy_listing_id);
CREATE INDEX idx_listings_store_state ON listings(store_id, state)
    WHERE state = 'active';
CREATE INDEX idx_listings_seo_score   ON listings(store_id, seo_score DESC NULLS LAST);
CREATE INDEX idx_listings_revenue     ON listings(store_id, (views_count * price_usd) DESC)
    WHERE state = 'active';
-- Trigram index for full-text search on title
CREATE INDEX idx_listings_title_trgm  ON listings USING gin(title gin_trgm_ops);

CREATE INDEX idx_metrics_listing_date
    ON listing_metrics_history(listing_id, recorded_date DESC);

-- ─────────────────────────────────────────────────────────────
-- ANALYSIS TABLES
-- ─────────────────────────────────────────────────────────────
-- One analysis per listing per run; most recent is canonical
CREATE INDEX idx_seo_listing_date
    ON seo_analyses(listing_id, created_at DESC);
CREATE INDEX idx_seo_priority
    ON seo_analyses(priority, overall_score)
    WHERE priority IN ('critical','high');

CREATE INDEX idx_competitors_store
    ON competitors(store_id, last_seen_at DESC);
CREATE INDEX idx_competitors_etsy
    ON competitors(etsy_listing_id);

CREATE INDEX idx_competitor_analyses_store
    ON competitor_analyses(store_id, created_at DESC);

CREATE INDEX idx_pricing_listing_date
    ON pricing_analyses(listing_id, created_at DESC);

CREATE INDEX idx_image_analyses_listing_date
    ON image_analyses(listing_id, created_at DESC);

-- ─────────────────────────────────────────────────────────────
-- TRENDS
-- ─────────────────────────────────────────────────────────────
CREATE INDEX idx_trends_keyword_source
    ON trends(keyword, source, region);
CREATE INDEX idx_trends_score
    ON trends(trend_score DESC, recorded_at DESC);
CREATE INDEX idx_trends_category
    ON trends(category, lifecycle_stage, recorded_at DESC)
    WHERE category IS NOT NULL;

CREATE INDEX idx_trend_reports_store
    ON trend_reports(store_id, report_type, period_start DESC);

-- ─────────────────────────────────────────────────────────────
-- CONTENT & OPTIMIZATIONS
-- ─────────────────────────────────────────────────────────────
CREATE INDEX idx_content_store_type
    ON generated_content(store_id, content_type, created_at DESC);
CREATE INDEX idx_content_listing
    ON generated_content(listing_id)
    WHERE listing_id IS NOT NULL;

CREATE INDEX idx_optimizations_listing_status
    ON listing_optimizations(listing_id, status);
CREATE INDEX idx_optimizations_pending
    ON listing_optimizations(status, created_at DESC)
    WHERE status = 'pending';

-- ─────────────────────────────────────────────────────────────
-- AGENT
-- ─────────────────────────────────────────────────────────────
CREATE INDEX idx_agent_runs_store_type
    ON agent_runs(store_id, run_type, created_at DESC);
CREATE INDEX idx_agent_runs_status
    ON agent_runs(status, created_at)
    WHERE status IN ('pending','running');
CREATE INDEX idx_agent_runs_user
    ON agent_runs(user_id, created_at DESC);

CREATE INDEX idx_agent_run_logs_run
    ON agent_run_logs(run_id);
CREATE INDEX idx_agent_run_logs_cost
    ON agent_run_logs(cost_usd DESC);

CREATE INDEX idx_agent_tasks_run
    ON agent_tasks(run_id);

-- ─────────────────────────────────────────────────────────────
-- NOTIFICATIONS
-- ─────────────────────────────────────────────────────────────
CREATE INDEX idx_notifications_user_unread
    ON notifications(user_id, is_read, created_at DESC);
CREATE INDEX idx_notifications_store
    ON notifications(store_id)
    WHERE store_id IS NOT NULL;

-- ─────────────────────────────────────────────────────────────
-- BILLING
-- ─────────────────────────────────────────────────────────────
CREATE INDEX idx_credit_txns_user_date
    ON credit_transactions(user_id, created_at DESC);
CREATE INDEX idx_paddle_events_type
    ON paddle_events(event_type, processed_at DESC);
CREATE INDEX idx_webhook_configs_user
    ON webhook_configs(user_id) WHERE is_active = TRUE;

-- ─────────────────────────────────────────────────────────────
-- EMBEDDINGS (pgvector)
-- ─────────────────────────────────────────────────────────────
CREATE INDEX idx_embeddings_entity
    ON embeddings(entity_type, entity_id);

-- ivfflat: approximate NN, fast at <500K vectors
-- lists = sqrt(expected_row_count), probes = 10 at query time
CREATE INDEX idx_embeddings_vector
    ON embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Partial index for competitor_listings (most frequent retrieval type)
CREATE INDEX idx_embeddings_competitor_vector
    ON embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 50)
    WHERE entity_type = 'competitor_listing';

-- ─────────────────────────────────────────────────────────────
-- AUDIENCE
-- ─────────────────────────────────────────────────────────────
CREATE INDEX idx_personas_store
    ON audience_personas(store_id, created_at DESC);
CREATE INDEX idx_communities_store
    ON communities(store_id, relevance_score DESC);

-- ─────────────────────────────────────────────────────────────
-- AUDIT
-- ─────────────────────────────────────────────────────────────
CREATE INDEX idx_audit_log_user_action
    ON audit_log(user_id, action, created_at DESC);
CREATE INDEX idx_audit_log_entity
    ON audit_log(entity_type, entity_id, created_at DESC);
```

---

## 13. Partitioning Strategy

```sql
-- Tables partitioned by time range (high write volume, queried by date range)

-- agent_run_logs: write-heavy, rarely queried beyond 30 days
-- (already defined above as PARTITION BY RANGE)
-- Use pg_partman to auto-create monthly partitions:
--   SELECT partman.create_parent('public.agent_run_logs', 'created_at', 'native', 'monthly');

-- listing_metrics_history: daily snapshots, high row count
-- Partition by year once table exceeds 5M rows
--   ALTER TABLE listing_metrics_history
--     PARTITION BY RANGE (recorded_date);

-- trends: append-only, high volume from 6 sources × daily
-- Partition by month once table exceeds 2M rows

-- Retention policy (pg_partman background worker):
--   agent_run_logs:          keep 90 days
--   listing_metrics_history: keep 24 months
--   trends:                  keep 12 months
--   audit_log:               keep 24 months (compliance)
--   notifications:           keep 90 days after read
```

---

## 14. Alembic Migration Conventions

```
migrations/
    env.py
    versions/
        0001_extensions_and_conventions.py
        0002_users_auth_tables.py
        0003_stores_etsy_oauth.py
        0004_listings_and_metrics.py
        0005_analysis_tables.py
        0006_trends_audience.py
        0007_content_optimizations.py
        0008_agent_runs_logs.py
        0009_billing_paddle.py
        0010_system_config.py
        0011_rag_embeddings.py
        0012_indexes.py
        0013_partitioning.py
        0014_seed_subscription_plans.py
```

```python
# Migration naming convention:
# {NNNN}_{short_description}.py
# Each migration must be reversible (has both upgrade() and downgrade()).
# Never modify a migration that has been applied to production.
# Always run `alembic upgrade head` in CI before merging.

# Standard migration template:
def upgrade() -> None:
    op.execute("SET statement_timeout = '30s'")  # protect against long locks
    # ... DDL changes ...

def downgrade() -> None:
    # ... reverse DDL ...
```

---

## 15. Redis Cache Strategy

### 15.1 Key Namespace Schema

All keys follow the pattern: `{domain}:{entity}:{id}[:{subfield}]`

```
────────────────────────────────────────────────────────────────────
AUTH & SESSIONS
────────────────────────────────────────────────────────────────────
session:{token_hash}                    STRING (JSON)   TTL 24h
  Payload: {user_id, email, tier, credits_balance, ...}
  Written: on login / token refresh
  Invalidated: on logout, password change, subscription change

user:me:{user_id}                       STRING (JSON)   TTL 5m
  Payload: GET /auth/me response
  Invalidated: on user update, plan change, credit transaction

user:credits:{user_id}                  STRING (int)    TTL 5m
  Current credits_balance (DB shadow)
  Invalidated: on any credit_transaction

credits:reserved:{user_id}             STRING (int)    TTL 3600s
  Sum of credits held by in-flight agent runs for this user
  Managed by: credit_service.reserve() / settle_reservation()

credits:run:{run_id}                    STRING (int)    TTL 3600s
  Credits reserved for a specific run (for settlement on completion)

────────────────────────────────────────────────────────────────────
STORES & LISTINGS
────────────────────────────────────────────────────────────────────
store:{store_id}:health                 STRING (JSON)   TTL 1h
  store_health_score + breakdown + top_issues
  Invalidated: when SEO analysis, optimization applied, store synced

store:{store_id}:listings:page:{n}      STRING (JSON)   TTL 10m
  Paginated listing list response
  Invalidated: on listing sync, on optimization applied

listing:{listing_id}                    STRING (JSON)   TTL 30m
  Full listing object
  Invalidated: on listing sync, on optimization applied

dashboard:overview:{store_id}           STRING (JSON)   TTL 15m
  Dashboard /overview aggregated response
  Invalidated: on agent_run completion, SEO analysis

────────────────────────────────────────────────────────────────────
ANALYSIS RESULTS (expensive AI calls — long TTL)
────────────────────────────────────────────────────────────────────
ai_cache:{content_hash_sha256}          STRING (JSON)   TTL 6h
  Generic AI response cache keyed by SHA-256 of input content.
  Key = sha256(json.dumps({type, listing_content_hash, context_hash}))
  Skips AI call entirely on cache hit.

analysis:seo:{listing_id}               STRING (JSON)   TTL 6h
  Latest SEO analysis for display
  Invalidated: on new seo_analyses row, on optimization applied

analysis:competitors:{store_id}:{cat}   STRING (JSON)   TTL 6h
  Competitor analysis per store/category
  Invalidated: on competitor_analyses row insert

analysis:pricing:{listing_id}           STRING (JSON)   TTL 6h
analysis:images:{listing_id}            STRING (JSON)   TTL 12h
analysis:trends:{store_id}:{date}       STRING (JSON)   TTL 6h

────────────────────────────────────────────────────────────────────
ETSY API RESPONSES (respect provider rate limits)
────────────────────────────────────────────────────────────────────
etsy:listings:{store_id}                STRING (JSON)   TTL 6h
  List of etsy_listing_ids from latest sync
  Used to detect removed listings without API calls

etsy:token:{store_id}                   STRING          TTL = token_expires_in - 5min
  Decrypted Etsy access token (in-memory only for active request lifetime)
  NOTE: this key is short-lived and only set during active API calls

etsy:search:{keyword_hash}:{category}   STRING (JSON)   TTL 30m
  Etsy search results for competitor discovery

google:trends:{keyword}:{region}        STRING (JSON)   TTL 4h
reddit:posts:{subreddit}                STRING (JSON)   TTL 1h
pinterest:search:{keyword}              STRING (JSON)   TTL 2h

────────────────────────────────────────────────────────────────────
AGENT RUN PROGRESS (SSE streaming)
────────────────────────────────────────────────────────────────────
agent:progress:{run_id}                 PubSub channel  —
  SSE events published by Celery tasks, consumed by FastAPI SSE endpoint
  Channel messages: {type, phase, message, progress_pct, data}

agent:run:{run_id}:phase                STRING          TTL 2h
  Current phase name; allows reconnecting SSE clients to catch up

────────────────────────────────────────────────────────────────────
RATE LIMITING
────────────────────────────────────────────────────────────────────
ratelimit:api:{user_id}:{minute_bucket}     STRING (int)    TTL 60s
  Per-user API rate limit counter; INCR + EXPIRE pattern

ratelimit:etsy:{store_id}                   HASH            TTL 60s
  Token bucket state: {tokens: float, last_time: float}
  Updated via Lua script (atomic read-modify-write)

ratelimit:ai:{user_id}:{minute_bucket}      STRING (int)    TTL 60s
  AI calls per minute per user

ratelimit:global:{ip}:{minute_bucket}       STRING (int)    TTL 60s
  Unauthenticated / anonymous request limiter

────────────────────────────────────────────────────────────────────
DISTRIBUTED LOCKS (SET NX PX — only one holder at a time)
────────────────────────────────────────────────────────────────────
lock:daily_agent:{store_id}             STRING          TTL 3600000ms (1h)
  Prevents duplicate daily agent runs for same store

lock:sync:{store_id}                    STRING          TTL 600000ms  (10min)
  Prevents concurrent listing syncs

lock:optimize:{optimization_id}         STRING          TTL 30000ms   (30s)
  Prevents duplicate Etsy write-back for same optimization

lock:embed:{entity_type}:{entity_id}    STRING          TTL 120000ms  (2min)
  Prevents duplicate embedding generation

────────────────────────────────────────────────────────────────────
IDEMPOTENCY
────────────────────────────────────────────────────────────────────
paddle:processed:{event_id}             STRING          TTL 7 days
  Marks Paddle webhook event as processed; prevents double-processing

webhook:delivered:{config_id}:{event_hash} STRING       TTL 24h
  Prevents duplicate outbound webhook delivery
```

### 15.2 Cache Invalidation Matrix

```
Event                                → Keys invalidated
────────────────────────────────────────────────────────────────────────────
Listing synced from Etsy             → listing:{id}
                                       store:{sid}:listings:page:*
                                       dashboard:overview:{sid}

SEO analysis completed               → analysis:seo:{listing_id}
                                       store:{sid}:health
                                       dashboard:overview:{sid}
                                       ai_cache:{related_hashes}

Optimization applied to Etsy         → listing:{id}
                                       analysis:seo:{listing_id}
                                       analysis:competitors:{sid}:*
                                       store:{sid}:health
                                       dashboard:overview:{sid}

Agent run completed                  → dashboard:overview:{sid}
                                       store:{sid}:health
                                       analysis:trends:{sid}:*

Subscription changed (upgrade/down)  → user:me:{uid}
                                       session:{token_hash}  (soft — next auth refresh)

Credit transaction occurred          → user:credits:{uid}
                                       user:me:{uid}
```

### 15.3 Redis Data Structures Reference

| Key Pattern | Structure | Notes |
|---|---|---|
| `session:*` | STRING (JSON) | JWT payload, 24h TTL |
| `user:me:*` | STRING (JSON) | API response cache |
| `credits:reserved:*` | STRING (int) | Atomic INCRBY/DECRBY |
| `ratelimit:api:*` | STRING (int) | INCR + EXPIRE |
| `ratelimit:etsy:*` | HASH `{tokens, last_time}` | Lua token bucket |
| `lock:*` | STRING ("1") | SET NX PX; absent = not locked |
| `analysis:*` | STRING (JSON) | Serialized Pydantic model |
| `ai_cache:*` | STRING (JSON) | AI response, 6h TTL |
| `agent:progress:*` | PubSub | Published by workers, consumed by SSE |

### 15.4 Etsy Token Bucket Lua Script

```lua
-- KEYS[1]: rate limit key (e.g., ratelimit:etsy:{store_id})
-- ARGV[1]: rate (tokens/sec = 10)
-- ARGV[2]: capacity (burst = 20)
-- ARGV[3]: current_time (float seconds)
-- ARGV[4]: cost (tokens to consume = 1)
-- Returns: 1 if allowed, 0 if rate-limited

local key       = KEYS[1]
local rate      = tonumber(ARGV[1])
local capacity  = tonumber(ARGV[2])
local now       = tonumber(ARGV[3])
local cost      = tonumber(ARGV[4])

local last_time = tonumber(redis.call('HGET', key, 'last_time') or now)
local tokens    = tonumber(redis.call('HGET', key, 'tokens') or capacity)

local elapsed = math.max(0, now - last_time)
tokens = math.min(capacity, tokens + elapsed * rate)

if tokens >= cost then
    tokens = tokens - cost
    redis.call('HSET', key, 'tokens', tokens, 'last_time', now)
    redis.call('EXPIRE', key, 60)
    return 1
else
    redis.call('HSET', key, 'tokens', tokens, 'last_time', now)
    redis.call('EXPIRE', key, 60)
    return 0
end
```

---

## 16. Celery Queue Architecture

### 16.1 Queue Definitions

```python
# app/celery_config.py
from kombu import Queue

CELERY_TASK_QUEUES = (
    Queue('critical',  routing_key='critical'),   # priority 10 — UI-blocking (user clicked button)
    Queue('high',      routing_key='high'),        # priority 7  — user-triggered, async
    Queue('default',   routing_key='default'),     # priority 5  — standard background
    Queue('bulk',      routing_key='bulk'),        # priority 3  — batch ops, embeddings, sync
    Queue('scheduled', routing_key='scheduled'),   # priority 1  — cron jobs
)

CELERY_TASK_DEFAULT_QUEUE = 'default'

CELERY_TASK_ROUTES = {
    # UI-blocking (immediate user feedback expected)
    'tasks.seo.analyze_single':             {'queue': 'critical'},
    'tasks.competitors.analyze_single':     {'queue': 'critical'},
    'tasks.content.generate_single':        {'queue': 'critical'},

    # User-triggered async (spinner in UI)
    'tasks.images.analyze_listing':         {'queue': 'high'},
    'tasks.pricing.analyze_listing':        {'queue': 'high'},
    'tasks.agent.run_manual':               {'queue': 'high'},
    'tasks.notifications.send_single':      {'queue': 'high'},

    # Background, no UI feedback
    'tasks.seo.analyze_batch':              {'queue': 'default'},
    'tasks.trends.aggregate':               {'queue': 'default'},
    'tasks.agent.run_daily':                {'queue': 'default'},

    # Batch / slow operations
    'tasks.store.sync_listings':            {'queue': 'bulk'},
    'tasks.embeddings.update_single':       {'queue': 'bulk'},
    'tasks.embeddings.update_batch':        {'queue': 'bulk'},
    'tasks.competitors.scrape_batch':       {'queue': 'bulk'},

    # Cron-triggered only
    'tasks.scheduler.daily_agent_fan_out':  {'queue': 'scheduled'},
    'tasks.scheduler.weekly_report_fan_out':{'queue': 'scheduled'},
    'tasks.scheduler.monthly_plan_fan_out': {'queue': 'scheduled'},
    'tasks.scheduler.trend_fetch_all':      {'queue': 'scheduled'},
    'tasks.notifications.send_all_digests': {'queue': 'scheduled'},
    'tasks.maintenance.cleanup':            {'queue': 'scheduled'},
}

CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_RESULT_EXPIRES = 7200           # 2 hours
CELERY_TASK_TIME_LIMIT = 1800         # 30 min hard kill
CELERY_TASK_SOFT_TIME_LIMIT = 1500    # 25 min soft kill (raises SoftTimeLimitExceeded)
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # one task at a time per worker slot; prevents starvation
CELERY_ACKS_LATE = True               # ack after completion, not on receipt (safe retries)
CELERY_TASK_REJECT_ON_WORKER_LOST = True

BROKER_URL = 'redis://redis:6379/0'
RESULT_BACKEND = 'redis://redis:6379/1'
```

### 16.2 Worker Deployment

```yaml
# docker-compose.yml (dev) / ECS task definition equivalents (prod)
services:
  worker-critical:
    command: celery -A app.celery_app worker -Q critical -c 4 --loglevel=info
    # 4 concurrent slots; critical queue drains fastest

  worker-high:
    command: celery -A app.celery_app worker -Q high -c 4 --loglevel=info

  worker-default-bulk:
    command: celery -A app.celery_app worker -Q default,bulk -c 8 --loglevel=info
    # More slots for parallel SEO/embedding batches

  worker-scheduled:
    command: celery -A app.celery_app worker -Q scheduled -c 2 --loglevel=info
    # Low concurrency; cron tasks are large but infrequent

  beat:
    command: celery -A app.celery_app beat --scheduler redbeat.RedBeatScheduler --loglevel=info
    # RedBeat: Redis-backed Beat scheduler; prevents duplicate fires on multi-instance deploys

  flower:
    command: celery -A app.celery_app flower --port=5555
    # Monitoring UI (internal only, not public)
```

### 16.3 Celery Beat Schedule

```python
# app/beat_schedule.py
from celery.schedules import crontab

CELERYBEAT_SCHEDULE = {
    # Daily agent — 07:00 UTC for all active stores
    'daily-agent-fan-out': {
        'task': 'tasks.scheduler.daily_agent_fan_out',
        'schedule': crontab(minute=0, hour=7),
    },
    # Store sync every 6 hours (offset from agent by 30min)
    'sync-all-stores': {
        'task': 'tasks.scheduler.sync_all_stores',
        'schedule': crontab(minute=30, hour='*/6'),
    },
    # Trend fetch every 2 hours
    'fetch-all-trends': {
        'task': 'tasks.scheduler.trend_fetch_all',
        'schedule': crontab(minute=0, hour='*/2'),
    },
    # Daily email digest — 09:00 UTC (after agent runs)
    'daily-email-digest': {
        'task': 'tasks.notifications.send_all_digests',
        'schedule': crontab(minute=0, hour=9),
    },
    # Weekly report — Monday 07:30 UTC
    'weekly-report-fan-out': {
        'task': 'tasks.scheduler.weekly_report_fan_out',
        'schedule': crontab(minute=30, hour=7, day_of_week=1),
    },
    # Monthly plan — 1st of each month, 08:00 UTC
    'monthly-plan-fan-out': {
        'task': 'tasks.scheduler.monthly_plan_fan_out',
        'schedule': crontab(minute=0, hour=8, day_of_month=1),
    },
    # Optimization result measurement (3d/7d/14d/30d after apply)
    'measure-optimization-results': {
        'task': 'tasks.optimizations.measure_pending_results',
        'schedule': crontab(minute=0, hour=10),  # daily at 10:00 UTC
    },
    # Churn prevention: detect inactive users
    'churn-prevention-check': {
        'task': 'tasks.notifications.send_re_engagement',
        'schedule': crontab(minute=0, hour=11),
    },
    # Cleanup stale sessions, old agent_tasks, expired feature_flags
    'maintenance-cleanup': {
        'task': 'tasks.maintenance.cleanup',
        'schedule': crontab(minute=0, hour=2, day_of_week=0),  # Sunday 02:00 UTC
    },
    # Subscription period-end check (downgrade cancelled accounts)
    'subscription-period-end-check': {
        'task': 'tasks.billing.check_period_end',
        'schedule': crontab(minute=0, hour='*/1'),  # every hour
    },
}
```

### 16.4 Daily Agent Chord Pattern

```python
# tasks/scheduler.py
from celery import chord, group, chain
from app.celery_app import celery

@celery.task(name='tasks.scheduler.daily_agent_fan_out')
def daily_agent_fan_out():
    """
    Celery Beat entry point. Fan-out to all active stores.
    Respects subscription tier: all tiers get daily agent.
    """
    from app.db.session import get_db_session
    with get_db_session() as db:
        stores = db.execute("""
            SELECT s.id, s.user_id, u.subscription_tier,
                   u.credits_balance, u.credits_reserved
            FROM stores s
            JOIN users u ON s.user_id = u.id
            WHERE s.status = 'active'
              AND s.agent_enabled = TRUE
              AND u.subscription_status IN ('active','trial')
              AND (u.credits_balance - u.credits_reserved) >= 5
            ORDER BY s.created_at
        """).fetchall()

    for store in stores:
        run_daily_agent.apply_async(
            args=[str(store.id), str(store.user_id)],
            queue='default',
        )


@celery.task(
    name='tasks.agent.run_daily',
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    soft_time_limit=1500,
    time_limit=1800,
)
def run_daily_agent(self, store_id: str, user_id: str):
    """
    Full daily pipeline. Acquires lock, reserves credits, runs chord.
    Chord pattern:
      Phase 2 group (parallel): [seo, competitors, trends, pricing]
            ↓ chord callback
      Phase 3: daily_synthesis (Fable 5)
            ↓
      Phase 4 group (parallel): [content_gen, image_analysis]
            ↓
      Phase 5: update_embeddings
            ↓
      Phase 6 group (parallel): [create_notifications, queue_email_digest]
    """
    # [see ai-agent-spec.md Section 2.2 for full implementation]
    ...
```

### 16.5 Error Handling and Dead Letter Strategy

```python
# app/celery_config.py — dead letter queue setup
CELERY_TASK_QUEUES += (
    Queue('dead_letter', routing_key='dead_letter'),
)

# tasks/base.py
from celery import Task
from app.db.session import get_db_session
import logging

logger = logging.getLogger(__name__)

class AgentTask(Task):
    """
    Base class for all agent tasks.
    On permanent failure: update agent_run status to 'failed',
    release credit reservation, publish failure SSE event.
    """
    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        run_id = kwargs.get('run_id') or (args[2] if len(args) > 2 else None)
        if run_id:
            try:
                with get_db_session() as db:
                    db.execute(
                        "UPDATE agent_runs SET status='failed', error_message=:err, completed_at=NOW() WHERE id=:id",
                        {'err': str(exc)[:1000], 'id': run_id}
                    )
                from app.services.credit_service import CreditService
                CreditService(redis_client).release_reservation(run_id)
            except Exception as cleanup_exc:
                logger.error(f"Cleanup failed for run {run_id}: {cleanup_exc}")

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        logger.warning(f"Retrying task {self.name} ({task_id}): {exc}")
```

### 16.6 Task Timeout Matrix

| Queue | Task Examples | soft_time_limit | time_limit | max_retries |
|---|---|---|---|---|
| critical | seo_analyze_single, content_generate | 60s | 90s | 2 |
| high | image_analyze, pricing_analyze | 120s | 180s | 2 |
| default | seo_analyze_batch, trend_aggregate | 300s | 400s | 2 |
| bulk | sync_listings, update_embeddings | 600s | 720s | 3 |
| scheduled | run_daily_agent, weekly_report | 1500s | 1800s | 1 |

### 16.7 Monitoring (Flower + CloudWatch)

```python
# Custom CloudWatch metrics published by workers (prod)
CELERY_TASK_ANNOTATIONS = {
    '*': {
        'on_success': _publish_success_metric,
        'on_failure': _publish_failure_metric,
    }
}

def _publish_success_metric(retval, task_id, args, kwargs):
    cloudwatch.put_metric_data(
        Namespace='EtsyAgent/Celery',
        MetricData=[{
            'MetricName': 'TaskSuccess',
            'Dimensions': [{'Name': 'TaskName', 'Value': current_task.name}],
            'Value': 1,
            'Unit': 'Count',
        }]
    )

# CloudWatch alarms:
# - TaskFailureRate > 5% for 5 min  → PagerDuty (SEV-2)
# - CriticalQueueDepth > 50          → PagerDuty (SEV-1)
# - DailyAgentQueueDepth > 500       → Slack alert
```

---

*Full table count: 33 tables across 10 domains. All indexes: 47. Partitioned tables: audit_log (monthly), agent_run_logs (monthly, upcoming).*
