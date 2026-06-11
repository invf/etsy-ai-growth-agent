# Etsy AI Growth Agent — Backend Technical Specification

---

## 1. PostgreSQL Database Schema

### Conventions
- All primary keys: `UUID` (gen_random_uuid())
- All timestamps: `TIMESTAMPTZ` (timezone-aware)
- Soft deletes: `deleted_at TIMESTAMPTZ` where needed
- Encrypted fields (OAuth tokens): store via application-level AES-256-GCM before insert
- pgvector extension: `CREATE EXTENSION IF NOT EXISTS vector;`
- UUID generation: `CREATE EXTENSION IF NOT EXISTS "pgcrypto";`

---

### 1.1 Users & Auth

```sql
CREATE TABLE users (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email                   VARCHAR(255) NOT NULL UNIQUE,
  name                    VARCHAR(255),
  password_hash           VARCHAR(255),                          -- NULL for OAuth-only users
  plan                    VARCHAR(20) NOT NULL DEFAULT 'starter'
                            CHECK (plan IN ('starter','pro','agency')),
  ai_credits_balance      INTEGER NOT NULL DEFAULT 500,
  stripe_customer_id      VARCHAR(255) UNIQUE,
  stripe_subscription_id  VARCHAR(255),
  subscription_status     VARCHAR(50) DEFAULT 'trialing',        -- trialing, active, past_due, canceled
  billing_cycle_anchor    TIMESTAMPTZ,
  timezone                VARCHAR(100) DEFAULT 'UTC',
  email_notifications     BOOLEAN NOT NULL DEFAULT TRUE,
  onboarding_completed    BOOLEAN NOT NULL DEFAULT FALSE,
  created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  deleted_at              TIMESTAMPTZ
);

CREATE TABLE oauth_accounts (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  provider            VARCHAR(50) NOT NULL,                      -- 'google', 'github'
  provider_account_id VARCHAR(255) NOT NULL,
  access_token        TEXT,
  refresh_token       TEXT,
  expires_at          TIMESTAMPTZ,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (provider, provider_account_id)
);

CREATE TABLE sessions (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash   VARCHAR(64) NOT NULL UNIQUE,                      -- SHA-256 of JWT
  user_agent   TEXT,
  ip_address   INET,
  expires_at   TIMESTAMPTZ NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE password_reset_tokens (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash VARCHAR(64) NOT NULL UNIQUE,
  expires_at TIMESTAMPTZ NOT NULL,
  used       BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

### 1.2 Stores & Etsy OAuth

```sql
CREATE TABLE stores (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  etsy_shop_id        VARCHAR(100) NOT NULL UNIQUE,
  shop_name           VARCHAR(255) NOT NULL,
  shop_url            VARCHAR(500),
  icon_url            VARCHAR(500),
  banner_url          VARCHAR(500),
  currency_code       VARCHAR(10) DEFAULT 'USD',
  country_code        VARCHAR(10),
  listing_count       INTEGER DEFAULT 0,
  sale_count          INTEGER DEFAULT 0,
  -- OAuth tokens (AES-256-GCM encrypted at application layer)
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
  -- Health
  health_score        SMALLINT CHECK (health_score BETWEEN 0 AND 100),
  health_computed_at  TIMESTAMPTZ,
  health_breakdown    JSONB,                                     -- {seo:72, pricing:65, images:80, ...}
  -- Agent
  agent_enabled       BOOLEAN NOT NULL DEFAULT TRUE,
  agent_last_run_at   TIMESTAMPTZ,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

### 1.3 Listings

```sql
CREATE TABLE listings (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id         UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
  etsy_listing_id  BIGINT NOT NULL UNIQUE,
  title            VARCHAR(500),
  description      TEXT,
  tags             TEXT[] DEFAULT '{}',
  materials        TEXT[] DEFAULT '{}',
  price            NUMERIC(10,2),
  currency_code    VARCHAR(10),
  quantity         INTEGER,
  state            VARCHAR(20) NOT NULL DEFAULT 'active'
                     CHECK (state IN ('active','inactive','draft','expired','sold_out','removed')),
  -- Taxonomy
  taxonomy_id      INTEGER,
  category_path    TEXT[] DEFAULT '{}',
  -- Images
  main_image_url   TEXT,
  image_urls       TEXT[] DEFAULT '{}',
  -- Etsy metrics
  views            INTEGER NOT NULL DEFAULT 0,
  favorites        INTEGER NOT NULL DEFAULT 0,
  sales_count      INTEGER NOT NULL DEFAULT 0,
  average_rating   NUMERIC(3,2),
  review_count     INTEGER NOT NULL DEFAULT 0,
  -- Our computed scores
  seo_score        SMALLINT CHECK (seo_score BETWEEN 0 AND 100),
  seo_scored_at    TIMESTAMPTZ,
  image_score      SMALLINT CHECK (image_score BETWEEN 0 AND 100),
  -- Etsy timestamps
  etsy_created_at  TIMESTAMPTZ,
  etsy_updated_at  TIMESTAMPTZ,
  -- Our timestamps
  synced_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE listing_metrics_history (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  listing_id   UUID NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
  views        INTEGER NOT NULL DEFAULT 0,
  favorites    INTEGER NOT NULL DEFAULT 0,
  sales_count  INTEGER NOT NULL DEFAULT 0,
  price        NUMERIC(10,2),
  seo_score    SMALLINT,
  recorded_date DATE NOT NULL,
  UNIQUE (listing_id, recorded_date)
);
```

---

### 1.4 Competitors

```sql
CREATE TABLE competitors (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  listing_id        UUID NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
  etsy_listing_id   BIGINT NOT NULL,
  etsy_shop_id      VARCHAR(100),
  shop_name         VARCHAR(255),
  title             VARCHAR(500),
  description       TEXT,
  tags              TEXT[] DEFAULT '{}',
  price             NUMERIC(10,2),
  currency_code     VARCHAR(10),
  main_image_url    TEXT,
  views             INTEGER,
  favorites         INTEGER,
  sales_estimate    INTEGER,                    -- derived: favorites * conversion_factor
  review_count      INTEGER,
  average_rating    NUMERIC(3,2),
  rank_position     SMALLINT,                   -- position in search results (1-indexed)
  search_keyword    VARCHAR(255),               -- keyword that surfaced this competitor
  competitor_score  SMALLINT CHECK (competitor_score BETWEEN 0 AND 100),
  analyzed_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (listing_id, etsy_listing_id)
);

CREATE TABLE competitor_analyses (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  listing_id              UUID NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
  market_opportunity_score SMALLINT CHECK (market_opportunity_score BETWEEN 0 AND 100),
  competitor_count        INTEGER,
  avg_competitor_price    NUMERIC(10,2),
  price_range_min         NUMERIC(10,2),
  price_range_max         NUMERIC(10,2),
  keyword_gaps            TEXT[] DEFAULT '{}',
  tag_gaps                TEXT[] DEFAULT '{}',
  niche_opportunities     JSONB,               -- [{keyword, opportunity_score, competition_level}]
  gap_analysis            JSONB,
  recommendations         JSONB,
  model_used              VARCHAR(100),
  tokens_used             INTEGER,
  agent_run_id            UUID,
  created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

### 1.5 SEO Analyses

```sql
CREATE TABLE seo_analyses (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  listing_id               UUID NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
  overall_score            SMALLINT NOT NULL CHECK (overall_score BETWEEN 0 AND 100),
  title_score              SMALLINT CHECK (title_score BETWEEN 0 AND 100),
  tags_score               SMALLINT CHECK (tags_score BETWEEN 0 AND 100),
  description_score        SMALLINT CHECK (description_score BETWEEN 0 AND 100),
  -- Analysis results
  missing_keywords         TEXT[] DEFAULT '{}',
  recommended_tags         TEXT[] DEFAULT '{}',
  current_tag_count        SMALLINT,
  recommended_title        TEXT,
  recommended_description  TEXT,
  ranking_probability      NUMERIC(5,2),        -- 0-100%
  keyword_density          JSONB,               -- {keyword: density_pct}
  improvement_suggestions  JSONB,               -- [{field, issue, fix, priority}]
  -- Application status
  applied                  BOOLEAN NOT NULL DEFAULT FALSE,
  applied_at               TIMESTAMPTZ,
  -- Metadata
  model_used               VARCHAR(100),
  tokens_used              INTEGER,
  agent_run_id             UUID,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

### 1.6 Trends

```sql
CREATE TABLE trends (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  keyword             VARCHAR(255) NOT NULL,
  source              VARCHAR(50) NOT NULL
                        CHECK (source IN ('etsy','pinterest','tiktok','instagram','google_trends','reddit')),
  trend_score         SMALLINT NOT NULL CHECK (trend_score BETWEEN 0 AND 100),
  volume_index        INTEGER,                  -- relative search volume (0-100 for Google Trends)
  growth_rate         NUMERIC(8,4),             -- week-over-week % change
  peak_predicted_date DATE,
  is_seasonal         BOOLEAN NOT NULL DEFAULT FALSE,
  season_peak_month   SMALLINT CHECK (season_peak_month BETWEEN 1 AND 12),
  related_keywords    TEXT[] DEFAULT '{}',
  category            VARCHAR(255),
  region              VARCHAR(10) NOT NULL DEFAULT 'US',
  raw_data            JSONB,
  recorded_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (keyword, source, region, DATE_TRUNC('day', recorded_at))
);

CREATE TABLE trend_reports (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id       UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
  report_type    VARCHAR(20) NOT NULL CHECK (report_type IN ('daily','weekly','monthly')),
  period_start   DATE NOT NULL,
  period_end     DATE NOT NULL,
  summary        TEXT,
  top_trends     JSONB,
  opportunities  JSONB,
  recommendations JSONB,
  model_used     VARCHAR(100),
  tokens_used    INTEGER,
  agent_run_id   UUID,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

### 1.7 Audience

```sql
CREATE TABLE audience_personas (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id            UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
  persona_name        VARCHAR(255) NOT NULL,
  age_range           VARCHAR(50),
  gender              VARCHAR(50),
  location            VARCHAR(100),
  income_level        VARCHAR(50),
  interests           TEXT[] DEFAULT '{}',
  pain_points         TEXT[] DEFAULT '{}',
  buying_motivations  TEXT[] DEFAULT '{}',
  platforms           TEXT[] DEFAULT '{}',
  content_ideas       TEXT[] DEFAULT '{}',
  sources_analyzed    JSONB,                    -- what data this persona was derived from
  model_used          VARCHAR(100),
  tokens_used         INTEGER,
  agent_run_id        UUID,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE communities (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id         UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
  platform         VARCHAR(50) NOT NULL,        -- 'reddit', 'pinterest', 'instagram', 'facebook'
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

### 1.8 Content Generation

```sql
CREATE TABLE generated_content (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id      UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
  listing_id    UUID REFERENCES listings(id) ON DELETE SET NULL,
  content_type  VARCHAR(50) NOT NULL
                  CHECK (content_type IN (
                    'etsy_title','etsy_description','etsy_tags',
                    'pinterest_pin','instagram_caption','tiktok_script',
                    'facebook_post','blog_post','email_campaign'
                  )),
  content       TEXT NOT NULL,
  tone          VARCHAR(50),                    -- 'professional','casual','playful','luxurious'
  keywords_used TEXT[] DEFAULT '{}',
  seo_optimized BOOLEAN NOT NULL DEFAULT TRUE,
  user_rating   SMALLINT CHECK (user_rating BETWEEN 1 AND 5),
  applied       BOOLEAN NOT NULL DEFAULT FALSE,
  applied_at    TIMESTAMPTZ,
  model_used    VARCHAR(100),
  tokens_used   INTEGER,
  agent_run_id  UUID,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

### 1.9 Pricing Intelligence

```sql
CREATE TABLE pricing_analyses (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  listing_id            UUID NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
  our_price             NUMERIC(10,2) NOT NULL,
  market_min            NUMERIC(10,2),
  market_max            NUMERIC(10,2),
  market_avg            NUMERIC(10,2),
  market_median         NUMERIC(10,2),
  recommended_price     NUMERIC(10,2),
  price_position        VARCHAR(20)
                          CHECK (price_position IN ('below_market','at_market','above_market','premium')),
  demand_level          VARCHAR(20)
                          CHECK (demand_level IN ('low','medium','high','very_high')),
  price_elasticity      NUMERIC(5,4),           -- estimated price sensitivity
  discount_suggestion   NUMERIC(5,2),           -- % discount
  bundle_opportunities  JSONB,                  -- [{title, items[], suggested_price}]
  competitor_prices     JSONB,                  -- [{shop, listing_id, price}]
  analysis_notes        TEXT,
  model_used            VARCHAR(100),
  tokens_used           INTEGER,
  agent_run_id          UUID,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

### 1.10 Image Analyses

```sql
CREATE TABLE image_analyses (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  listing_id            UUID NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
  image_url             TEXT NOT NULL,
  image_position        SMALLINT NOT NULL DEFAULT 0,           -- 0 = main image
  image_type            VARCHAR(20)
                          CHECK (image_type IN ('main','secondary','lifestyle','detail','infographic')),
  visual_quality_score  SMALLINT CHECK (visual_quality_score BETWEEN 0 AND 100),
  clickability_score    SMALLINT CHECK (clickability_score BETWEEN 0 AND 100),
  conversion_score      SMALLINT CHECK (conversion_score BETWEEN 0 AND 100),
  overall_score         SMALLINT CHECK (overall_score BETWEEN 0 AND 100),
  issues                JSONB,                                 -- [{type, severity, description}]
  recommendations       JSONB,                                 -- [{action, priority, example_url}]
  model_used            VARCHAR(100),
  tokens_used           INTEGER,
  agent_run_id          UUID,
  analyzed_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

### 1.11 Listing Optimizations (Approval Workflow)

```sql
CREATE TABLE listing_optimizations (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  listing_id           UUID NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
  optimization_type    VARCHAR(20) NOT NULL
                         CHECK (optimization_type IN ('title','description','tags','price','category')),
  old_value            TEXT,
  new_value            TEXT NOT NULL,
  change_summary       TEXT,
  impact_estimate      JSONB,                  -- {seo_score_delta, estimated_views_lift}
  status               VARCHAR(20) NOT NULL DEFAULT 'pending'
                         CHECK (status IN ('pending','approved','rejected','applied','failed')),
  approved_by_user     BOOLEAN NOT NULL DEFAULT FALSE,
  approved_at          TIMESTAMPTZ,
  rejected_at          TIMESTAMPTZ,
  rejection_reason     TEXT,
  applied              BOOLEAN NOT NULL DEFAULT FALSE,
  applied_at           TIMESTAMPTZ,
  etsy_update_status   VARCHAR(20)
                         CHECK (etsy_update_status IN ('pending','success','failed')),
  etsy_update_error    TEXT,
  agent_run_id         UUID,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE optimization_results (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  optimization_id   UUID NOT NULL REFERENCES listing_optimizations(id) ON DELETE CASCADE,
  measured_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  days_after_apply  SMALLINT,
  views_before      INTEGER,
  views_after       INTEGER,
  favorites_before  INTEGER,
  favorites_after   INTEGER,
  sales_before      INTEGER,
  sales_after       INTEGER,
  seo_score_before  SMALLINT,
  seo_score_after   SMALLINT
);
```

---

### 1.12 Agent Runs & Tasks

```sql
CREATE TABLE agent_runs (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id         UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
  run_type         VARCHAR(50) NOT NULL
                     CHECK (run_type IN (
                       'daily_scan','seo_analysis','competitor_analysis',
                       'trend_discovery','content_generation','image_analysis',
                       'pricing_analysis','audience_discovery',
                       'weekly_report','monthly_plan','manual_audit'
                     )),
  status           VARCHAR(20) NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending','running','completed','failed','cancelled')),
  triggered_by     VARCHAR(20) NOT NULL DEFAULT 'scheduler'
                     CHECK (triggered_by IN ('scheduler','user','api','webhook')),
  input_data       JSONB,
  result_summary   JSONB,
  error_message    TEXT,
  tokens_used      INTEGER NOT NULL DEFAULT 0,
  cost_usd         NUMERIC(10,6) NOT NULL DEFAULT 0,
  ai_credits_used  INTEGER NOT NULL DEFAULT 0,
  progress_pct     SMALLINT NOT NULL DEFAULT 0,
  started_at       TIMESTAMPTZ,
  completed_at     TIMESTAMPTZ,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE agent_tasks (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id          UUID NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
  task_name       VARCHAR(100) NOT NULL,
  task_type       VARCHAR(100) NOT NULL,
  status          VARCHAR(20) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','running','completed','failed','skipped')),
  input_data      JSONB,
  output_data     JSONB,
  error_message   TEXT,
  tokens_used     INTEGER NOT NULL DEFAULT 0,
  started_at      TIMESTAMPTZ,
  completed_at    TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

### 1.13 Notifications

```sql
CREATE TABLE notifications (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  store_id    UUID REFERENCES stores(id) ON DELETE CASCADE,
  type        VARCHAR(50) NOT NULL
                CHECK (type IN (
                  'agent_complete','seo_opportunity','trend_alert',
                  'competitor_change','listing_update','optimization_ready',
                  'billing','system','report_ready'
                )),
  priority    VARCHAR(10) NOT NULL DEFAULT 'medium'
                CHECK (priority IN ('low','medium','high')),
  title       VARCHAR(255) NOT NULL,
  message     TEXT NOT NULL,
  data        JSONB,
  action_url  TEXT,
  read        BOOLEAN NOT NULL DEFAULT FALSE,
  read_at     TIMESTAMPTZ,
  sent_email  BOOLEAN NOT NULL DEFAULT FALSE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

### 1.14 Billing & Credits

```sql
CREATE TABLE subscription_plans (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name                    VARCHAR(20) NOT NULL UNIQUE
                            CHECK (name IN ('starter','pro','agency')),
  display_name            VARCHAR(100) NOT NULL,
  price_monthly_usd       NUMERIC(10,2) NOT NULL,
  price_yearly_usd        NUMERIC(10,2) NOT NULL,
  max_stores              SMALLINT NOT NULL DEFAULT 1,   -- -1 = unlimited
  ai_credits_monthly      INTEGER NOT NULL,
  features                JSONB NOT NULL,
  stripe_price_id_monthly VARCHAR(255),
  stripe_price_id_yearly  VARCHAR(255),
  is_active               BOOLEAN NOT NULL DEFAULT TRUE,
  created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE credit_transactions (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  type           VARCHAR(20) NOT NULL
                   CHECK (type IN ('monthly_grant','purchase','usage','refund','bonus','adjustment')),
  amount         INTEGER NOT NULL,               -- positive = credit, negative = debit
  balance_after  INTEGER NOT NULL,
  description    TEXT,
  agent_run_id   UUID REFERENCES agent_runs(id) ON DELETE SET NULL,
  stripe_charge_id VARCHAR(255),
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

### 1.15 RAG Embeddings (pgvector)

```sql
-- Requires: CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE embeddings (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_type   VARCHAR(50) NOT NULL
                  CHECK (entity_type IN ('listing','competitor','trend','content','persona')),
  entity_id     UUID NOT NULL,
  chunk_index   SMALLINT NOT NULL DEFAULT 0,     -- for multi-chunk entities
  content_text  TEXT NOT NULL,                   -- the text that was embedded
  content_hash  VARCHAR(64) NOT NULL,            -- SHA-256; detect staleness
  embedding     vector(1024) NOT NULL,           -- voyage-3 dims
  metadata      JSONB,
  model_used    VARCHAR(100) NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (entity_type, entity_id, chunk_index)
);
```

---

### 1.16 All Indexes

```sql
-- Users
CREATE INDEX idx_users_email          ON users(email) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_stripe         ON users(stripe_customer_id) WHERE stripe_customer_id IS NOT NULL;

-- Sessions
CREATE INDEX idx_sessions_user        ON sessions(user_id);
CREATE INDEX idx_sessions_token       ON sessions(token_hash);
CREATE INDEX idx_sessions_expires     ON sessions(expires_at);

-- Stores
CREATE INDEX idx_stores_user          ON stores(user_id);
CREATE INDEX idx_stores_etsy_shop     ON stores(etsy_shop_id);
CREATE INDEX idx_stores_status        ON stores(status) WHERE status = 'active';

-- Listings
CREATE INDEX idx_listings_store       ON listings(store_id);
CREATE INDEX idx_listings_etsy_id     ON listings(etsy_listing_id);
CREATE INDEX idx_listings_state       ON listings(store_id, state) WHERE state = 'active';
CREATE INDEX idx_listings_seo_score   ON listings(store_id, seo_score);
CREATE INDEX idx_listings_sales       ON listings(store_id, sales_count DESC);

-- Listing metrics history
CREATE INDEX idx_metrics_listing_date ON listing_metrics_history(listing_id, recorded_date DESC);

-- Competitors
CREATE INDEX idx_competitors_listing  ON competitors(listing_id);
CREATE INDEX idx_competitors_analyzed ON competitors(listing_id, analyzed_at DESC);

-- SEO analyses
CREATE INDEX idx_seo_listing_date     ON seo_analyses(listing_id, created_at DESC);
CREATE INDEX idx_seo_score            ON seo_analyses(overall_score);

-- Trends
CREATE INDEX idx_trends_keyword       ON trends(keyword, source);
CREATE INDEX idx_trends_score         ON trends(trend_score DESC, recorded_at DESC);
CREATE INDEX idx_trends_category      ON trends(category, recorded_at DESC) WHERE category IS NOT NULL;
CREATE INDEX idx_trends_recorded      ON trends(recorded_at DESC);

-- Agent runs
CREATE INDEX idx_runs_store_type      ON agent_runs(store_id, run_type, created_at DESC);
CREATE INDEX idx_runs_status          ON agent_runs(status) WHERE status IN ('pending','running');
CREATE INDEX idx_runs_created         ON agent_runs(created_at DESC);

-- Agent tasks
CREATE INDEX idx_tasks_run            ON agent_tasks(run_id);

-- Notifications
CREATE INDEX idx_notifs_user_unread   ON notifications(user_id, read, created_at DESC);
CREATE INDEX idx_notifs_store         ON notifications(store_id) WHERE store_id IS NOT NULL;

-- Content
CREATE INDEX idx_content_store_type   ON generated_content(store_id, content_type, created_at DESC);
CREATE INDEX idx_content_listing      ON generated_content(listing_id) WHERE listing_id IS NOT NULL;

-- Optimizations
CREATE INDEX idx_optim_listing        ON listing_optimizations(listing_id, status);
CREATE INDEX idx_optim_pending        ON listing_optimizations(status) WHERE status = 'pending';

-- Credits
CREATE INDEX idx_credits_user_date    ON credit_transactions(user_id, created_at DESC);

-- Embeddings (IVFFlat for approximate nearest-neighbor)
CREATE INDEX idx_embeddings_entity    ON embeddings(entity_type, entity_id);
CREATE INDEX idx_embeddings_vector    ON embeddings USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);
```

---

## 2. Redis Cache Strategy

### Key Schema (namespace:scope:id[:subfield])

```
# Sessions & Auth
session:{token_hash}                    TTL 24h     — JWT session data
user:me:{user_id}                       TTL 5m      — /auth/me response

# Store & Listing data
store:health:{store_id}                 TTL 1h      — health score + breakdown
store:listings:page:{store_id}:{page}   TTL 10m     — paginated listing list
listing:detail:{listing_id}             TTL 30m     — full listing object

# Analysis results (expensive AI calls — long TTL)
analysis:seo:{listing_id}               TTL 6h      — latest SEO analysis
analysis:competitors:{listing_id}       TTL 6h      — competitor list + gap analysis
analysis:pricing:{listing_id}           TTL 6h      — pricing recommendation
analysis:images:{listing_id}            TTL 12h     — image scores

# External API responses (respect provider rate limits)
etsy:search:{keyword_sha256}            TTL 30m     — Etsy search results
etsy:listing:{etsy_listing_id}          TTL 1h      — individual Etsy listing
google:trends:{keyword}:{region}        TTL 4h      — Google Trends data
reddit:posts:{subreddit}                TTL 1h      — Reddit top posts
pinterest:search:{keyword}              TTL 2h      — Pinterest search

# Trend aggregations
trends:top:{category}:{date}            TTL 2h      — top trends by category
trends:report:{store_id}:{date}         TTL 6h      — daily trend report

# Dashboard aggregates
dashboard:overview:{store_id}           TTL 15m     — overview page data
dashboard:reports:{store_id}            TTL 30m     — reports page metrics

# Background job tracking
job:status:{celery_task_id}             TTL 2h      — {status, progress, result}
agent:run:{run_id}:progress             TTL 2h      — SSE progress data

# Rate limiting (sliding window counters)
ratelimit:api:{user_id}:{endpoint}      TTL 60s     — request count
ratelimit:etsy:{store_id}               TTL 1s      — Etsy API token bucket
ratelimit:ai:{user_id}                  TTL 60s     — AI API calls per minute
ratelimit:global:{ip}                   TTL 60s     — unauthenticated requests

# Deduplication locks (prevent double-processing)
lock:sync:{store_id}                    TTL 10m     — listing sync in-progress
lock:agent:{store_id}:{run_type}        TTL 60m     — agent run in-progress
lock:optimize:{listing_id}              TTL 5m      — optimization apply in-progress

# Credit reservation (prevent over-spend race condition)
credits:reserved:{user_id}             TTL 5m      — credits held during AI call
```

### Cache Invalidation Rules

```
Event                          →  Invalidate keys
────────────────────────────────────────────────────────────────────────
Listing synced from Etsy       →  listing:detail:{id}, analysis:seo:{id},
                                  store:listings:page:{store_id}:*,
                                  dashboard:overview:{store_id}
SEO analysis completed         →  analysis:seo:{listing_id},
                                  store:health:{store_id},
                                  dashboard:overview:{store_id}
Optimization applied           →  listing:detail:{id}, analysis:seo:{id},
                                  analysis:competitors:{id}, store:health:{store_id}
Store health recomputed        →  store:health:{store_id}, dashboard:overview:{store_id}
User plan changed              →  user:me:{user_id}
Credit transaction             →  user:me:{user_id}
```

### Redis Data Structures

| Key Pattern | Structure | Notes |
|---|---|---|
| `session:*` | STRING (JSON) | JWT payload |
| `ratelimit:api:*` | STRING (counter) | INCR + EXPIRE |
| `ratelimit:etsy:*` | STRING (float) | Token bucket: INCR/DECR |
| `lock:*` | STRING ("1") | SET NX PX |
| `job:status:*` | HASH | {status, progress, result, error} |
| `analysis:*` | STRING (JSON) | Serialized Pydantic model |
| `credits:reserved:*` | STRING (int) | Atomic INCRBY/DECRBY |

---

## 3. Celery Queue Structure

### Queue Definitions (priority descending)

```python
# celery_config.py
CELERY_TASK_QUEUES = {
    "critical":  {"priority": 10},  # user-triggered, blocks UI (SEO analyze button)
    "high":      {"priority": 7},   # user-triggered, async (content generate)
    "default":   {"priority": 5},   # standard background work
    "bulk":      {"priority": 3},   # batch operations (store sync)
    "scheduled": {"priority": 1},   # cron jobs (daily agent, reports)
}

CELERY_TASK_ROUTES = {
    "tasks.seo.analyze_single":         "critical",
    "tasks.competitors.analyze_single": "critical",
    "tasks.content.generate":           "high",
    "tasks.pricing.analyze":            "high",
    "tasks.images.analyze":             "high",
    "tasks.store.sync_listings":        "bulk",
    "tasks.agent.run_daily":            "scheduled",
    "tasks.reports.generate_weekly":    "scheduled",
    "tasks.reports.generate_monthly":   "scheduled",
    "tasks.notifications.send_digest":  "scheduled",
    "tasks.embeddings.update":          "bulk",
    "tasks.maintenance.cleanup":        "scheduled",
}

CELERY_BROKER_URL = "redis://redis:6379/0"
CELERY_RESULT_BACKEND = "redis://redis:6379/1"
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_EXPIRES = 7200   # 2h
CELERY_WORKER_CONCURRENCY = 4  # per worker process
```

### Task Catalog

```python
# ── STORE TASKS ──────────────────────────────────────────────────────────────

@app.task(bind=True, max_retries=3, default_retry_delay=60)
def sync_store_listings(self, store_id: str):
    """
    Pull all active listings from Etsy API.
    Upserts listings table. Updates store.last_synced_at.
    Queue: bulk | ETA: 2-3 min per store
    """

@app.task(bind=True, max_retries=2)
def sync_single_listing(self, store_id: str, etsy_listing_id: int):
    """
    Refresh one listing. Used after optimization is applied.
    Queue: high | ETA: 5s
    """

# ── SEO TASKS ────────────────────────────────────────────────────────────────

@app.task(bind=True, max_retries=2)
def analyze_listing_seo(self, listing_id: str, agent_run_id: str | None = None):
    """
    Run SEO analysis on a single listing via claude-fable-5.
    Stores result in seo_analyses. Updates listing.seo_score.
    Queue: critical | ETA: 10-20s
    """

@app.task(bind=True)
def analyze_store_seo_batch(self, store_id: str, agent_run_id: str):
    """
    Fan-out: creates analyze_listing_seo subtasks for every active listing.
    Uses Celery chord to aggregate results when all complete.
    Queue: default | ETA: varies
    """

# ── COMPETITOR TASKS ─────────────────────────────────────────────────────────

@app.task(bind=True, max_retries=3, default_retry_delay=120)
def scrape_competitors(self, listing_id: str, agent_run_id: str | None = None):
    """
    Search Etsy for top 10 competitors for a listing.
    Stores in competitors + runs competitor_analyses.
    Queue: critical | ETA: 30-60s
    """

# ── TREND TASKS ──────────────────────────────────────────────────────────────

@app.task(bind=True, max_retries=3)
def fetch_google_trends(self, keywords: list[str], region: str = "US"):
    """Fetches pytrends data. Queue: default | ETA: 10-15s"""

@app.task(bind=True, max_retries=2)
def fetch_reddit_trends(self, subreddits: list[str]):
    """Polls relevant subreddits via Reddit API. Queue: default | ETA: 15s"""

@app.task(bind=True)
def aggregate_trends(self, store_id: str, agent_run_id: str):
    """
    Chord callback: called when all source fetches complete.
    Runs AI synthesis to rank opportunities. Stores trend_report.
    Queue: default | ETA: 20-30s
    """

# ── CONTENT TASKS ────────────────────────────────────────────────────────────

@app.task(bind=True, max_retries=2)
def generate_content(
    self,
    store_id: str,
    listing_id: str | None,
    content_type: str,
    context: dict,
    agent_run_id: str | None = None
):
    """
    Generate one content piece via claude-fable-5.
    Queue: high | ETA: 10-30s
    """

# ── IMAGE TASKS ──────────────────────────────────────────────────────────────

@app.task(bind=True, max_retries=2)
def analyze_listing_images(self, listing_id: str, agent_run_id: str | None = None):
    """
    Multimodal image analysis via claude-fable-5 (vision).
    Stores in image_analyses. Updates listing.image_score.
    Queue: high | ETA: 20-40s
    """

# ── PRICING TASKS ────────────────────────────────────────────────────────────

@app.task(bind=True, max_retries=2)
def analyze_pricing(self, listing_id: str, agent_run_id: str | None = None):
    """
    Competitor price survey + AI recommendation.
    Queue: high | ETA: 15-25s
    """

# ── AGENT ORCHESTRATION ──────────────────────────────────────────────────────

@app.task(bind=True, max_retries=1)
def run_daily_agent(self, store_id: str):
    """
    Full daily autonomous workflow. Creates agent_run record.
    Fans out to: sync_store_listings → (seo_batch, scrape_competitors_batch,
    fetch_trends, analyze_pricing_batch) → aggregate_daily_results → notify_user.
    Queue: scheduled | ETA: 5-15 min
    """

@app.task(bind=True)
def aggregate_daily_results(self, store_id: str, run_id: str, subtask_results: list):
    """
    Chord callback for run_daily_agent.
    AI synthesis of all results → top 5 recommendations.
    Queue: default | ETA: 20-40s
    """

# ── REPORTS ──────────────────────────────────────────────────────────────────

@app.task(bind=True, max_retries=2)
def generate_weekly_report(self, store_id: str):
    """
    Aggregates 7-day data. Long-context AI synthesis.
    Queue: scheduled | ETA: 30-60s
    """

@app.task(bind=True, max_retries=2)
def generate_monthly_plan(self, store_id: str):
    """
    Full context window strategic plan via claude-fable-5.
    Queue: scheduled | ETA: 60-120s
    """

# ── NOTIFICATIONS ────────────────────────────────────────────────────────────

@app.task(bind=True)
def send_notification(self, user_id: str, notification_id: str):
    """
    Push WebSocket event + optionally send email via SendGrid.
    Queue: high | ETA: 2-5s
    """

@app.task(bind=True)
def send_daily_email_digest(self, user_id: str):
    """
    Aggregates unread notifications → sends HTML email via SendGrid.
    Queue: scheduled | ETA: 5s
    """

# ── MAINTENANCE ──────────────────────────────────────────────────────────────

@app.task(bind=True)
def update_embeddings(self, entity_type: str, entity_id: str):
    """
    Re-embed changed entity for RAG. Detects staleness via content_hash.
    Queue: bulk | ETA: 5-10s
    """

@app.task(bind=True)
def cleanup_old_data(self):
    """
    Prune: agent_tasks > 90d, old trend records, stale sessions.
    Queue: scheduled | ETA: 1-5 min
    """
```

### Celery Beat Schedule

```python
# beat_schedule.py
CELERYBEAT_SCHEDULE = {
    # Sync all active stores every 6 hours
    "sync-all-stores": {
        "task": "tasks.store.sync_all_stores_fan_out",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    # Daily agent — 6am UTC for all active stores
    "daily-agent": {
        "task": "tasks.agent.run_daily_agent_all_stores",
        "schedule": crontab(minute=0, hour=6),
    },
    # Trend polling every 2 hours
    "fetch-trends": {
        "task": "tasks.trends.fetch_all_sources",
        "schedule": crontab(minute=30, hour="*/2"),
    },
    # Daily email digest at 8am UTC
    "email-digest": {
        "task": "tasks.notifications.send_all_digests",
        "schedule": crontab(minute=0, hour=8),
    },
    # Weekly report — Monday 7am UTC
    "weekly-report": {
        "task": "tasks.reports.generate_all_weekly_reports",
        "schedule": crontab(minute=0, hour=7, day_of_week=1),
    },
    # Monthly plan — 1st of month 8am UTC
    "monthly-plan": {
        "task": "tasks.reports.generate_all_monthly_plans",
        "schedule": crontab(minute=0, hour=8, day_of_month=1),
    },
    # DB cleanup — Sunday 2am UTC
    "cleanup": {
        "task": "tasks.maintenance.cleanup_old_data",
        "schedule": crontab(minute=0, hour=2, day_of_week=0),
    },
}
```

---

## 4. REST API Endpoints

Base URL: `https://api.etsyagent.com/v1`

All requests require `Authorization: Bearer {jwt}` except public auth endpoints.

Response envelope:
```json
{
  "data": {},
  "meta": { "page": 1, "per_page": 20, "total": 145 },
  "error": null
}
```

---

### 4.1 Auth

```
POST   /auth/register
POST   /auth/login
POST   /auth/logout
POST   /auth/refresh
POST   /auth/forgot-password
POST   /auth/reset-password/{token}
GET    /auth/me
PATCH  /auth/me

POST /auth/register
Request:  { email, name, password }
Response: { data: { user, access_token, refresh_token } }

POST /auth/login
Request:  { email, password }
Response: { data: { user, access_token, refresh_token } }

GET /auth/me
Response: {
  data: {
    id, email, name, plan, ai_credits_balance,
    subscription_status, onboarding_completed
  }
}
```

---

### 4.2 Stores

```
GET    /stores
POST   /stores/connect/initiate          — returns Etsy OAuth URL
GET    /stores/connect/callback          — OAuth callback (handled server-side)
GET    /stores/{store_id}
DELETE /stores/{store_id}
POST   /stores/{store_id}/sync           — trigger manual listing sync
GET    /stores/{store_id}/health         — health score + breakdown
POST   /stores/{store_id}/audit          — trigger full store audit (queues agent run)
GET    /stores/{store_id}/dashboard      — overview page aggregate

GET /stores
Response: {
  data: [{
    id, etsy_shop_id, shop_name, shop_url, icon_url,
    status, listing_count, health_score, last_synced_at,
    agent_last_run_at
  }]
}

GET /stores/{store_id}/health
Response: {
  data: {
    overall_score: 74,
    breakdown: {
      seo: 68, pricing: 72, images: 85, review_velocity: 61,
      listing_completeness: 82
    },
    top_issues: ["12 listings have duplicate tags", "..."],
    computed_at: "2026-06-10T06:00:00Z"
  }
}

POST /stores/{store_id}/sync
Response: {
  data: { job_id: "celery-task-uuid", status: "queued" }
}
```

---

### 4.3 Listings

```
GET  /stores/{store_id}/listings
GET  /stores/{store_id}/listings/{listing_id}
GET  /stores/{store_id}/listings/{listing_id}/metrics

GET /stores/{store_id}/listings
Query params:
  page, per_page (default 20, max 100)
  state: active | inactive | all
  sort: seo_score | sales | views | favorites | updated_at
  order: asc | desc
  q: full-text search on title

Response: {
  data: [{
    id, etsy_listing_id, title, price, state,
    main_image_url, views, favorites, sales_count,
    seo_score, image_score, tags, created_at
  }],
  meta: { page, per_page, total }
}

GET /stores/{store_id}/listings/{listing_id}/metrics
Query params: range=7d|30d|90d
Response: {
  data: {
    history: [{ date, views, favorites, sales_count, seo_score }],
    totals: { views, favorites, sales_count }
  }
}
```

---

### 4.4 SEO

```
GET  /listings/{listing_id}/seo
POST /listings/{listing_id}/seo/analyze
POST /listings/{listing_id}/seo/apply        — apply recommended optimizations

GET /listings/{listing_id}/seo
Response: {
  data: {
    id, overall_score, title_score, tags_score, description_score,
    missing_keywords, recommended_tags, recommended_title,
    recommended_description, ranking_probability,
    improvement_suggestions: [{field, issue, fix, priority}],
    applied, created_at
  }
}

POST /listings/{listing_id}/seo/analyze
Response: { data: { job_id, status: "queued", estimated_seconds: 15 } }

POST /listings/{listing_id}/seo/apply
Request:  { fields: ["title", "tags", "description"] }  -- optional, defaults to all
Response: { data: { optimization_ids: ["uuid1", "uuid2"] } }
          -- creates listing_optimizations with status=pending, awaiting approval
```

---

### 4.5 Competitors

```
GET  /listings/{listing_id}/competitors
GET  /listings/{listing_id}/competitors/analysis
POST /listings/{listing_id}/competitors/refresh

GET /listings/{listing_id}/competitors
Query: page, per_page, sort=competitor_score|price|sales_estimate
Response: {
  data: [{
    id, etsy_listing_id, shop_name, title, price,
    sales_estimate, review_count, average_rating,
    rank_position, competitor_score, main_image_url, tags
  }]
}

GET /listings/{listing_id}/competitors/analysis
Response: {
  data: {
    market_opportunity_score,
    avg_competitor_price, price_range_min, price_range_max,
    keyword_gaps, tag_gaps,
    niche_opportunities: [{keyword, opportunity_score, competition_level}],
    recommendations,
    created_at
  }
}
```

---

### 4.6 Trends

```
GET  /trends
GET  /trends/{trend_id}
GET  /stores/{store_id}/trends/opportunities
POST /stores/{store_id}/trends/refresh

GET /trends
Query: category, source, region=US, sort=trend_score|growth_rate, page, per_page
Response: {
  data: [{
    id, keyword, source, trend_score, volume_index,
    growth_rate, is_seasonal, peak_predicted_date,
    related_keywords, category, recorded_at
  }]
}

GET /stores/{store_id}/trends/opportunities
Response: {
  data: {
    opportunities: [{
      keyword, trend_score, opportunity_type,
      matching_listings: [{ listing_id, title }],
      recommended_action, potential_impact
    }],
    report_date: "2026-06-10"
  }
}
```

---

### 4.7 Audience

```
GET  /stores/{store_id}/audience/personas
POST /stores/{store_id}/audience/analyze
GET  /stores/{store_id}/audience/communities
GET  /stores/{store_id}/audience/personas/{persona_id}

POST /stores/{store_id}/audience/analyze
Response: { data: { job_id, status: "queued" } }

GET /stores/{store_id}/audience/personas
Response: {
  data: [{
    id, persona_name, age_range, interests, pain_points,
    buying_motivations, platforms, content_ideas, created_at
  }]
}
```

---

### 4.8 Content Generation

```
POST /content/generate
GET  /stores/{store_id}/content
GET  /content/{content_id}
POST /content/{content_id}/apply
POST /content/{content_id}/rate
DELETE /content/{content_id}

POST /content/generate
Request: {
  store_id: "uuid",
  listing_id: "uuid | null",
  content_type: "etsy_title | etsy_description | etsy_tags | instagram_caption | ...",
  context: {
    keywords: ["minimalist", "handmade"],
    tone: "professional",
    target_audience: "young professionals",
    product_description: "..."
  }
}
Response: {
  data: { job_id, status: "queued" }
}

GET /stores/{store_id}/content
Query: content_type, listing_id, applied, page, per_page
Response: { data: [{ id, content_type, content, keywords_used, applied, user_rating, created_at }] }
```

---

### 4.9 Pricing

```
GET  /listings/{listing_id}/pricing
POST /listings/{listing_id}/pricing/analyze

GET /listings/{listing_id}/pricing
Response: {
  data: {
    our_price, market_avg, market_median, market_min, market_max,
    recommended_price, price_position, demand_level,
    discount_suggestion, bundle_opportunities,
    competitor_prices: [{ shop, price }],
    created_at
  }
}
```

---

### 4.10 Images

```
GET  /listings/{listing_id}/images
POST /listings/{listing_id}/images/analyze

GET /listings/{listing_id}/images
Response: {
  data: [{
    id, image_url, image_position, image_type,
    visual_quality_score, clickability_score, conversion_score, overall_score,
    issues, recommendations, analyzed_at
  }]
}
```

---

### 4.11 Optimizations

```
GET    /stores/{store_id}/optimizations
GET    /optimizations/{optimization_id}
POST   /optimizations/{optimization_id}/approve
POST   /optimizations/{optimization_id}/reject
POST   /optimizations/{optimization_id}/apply
POST   /stores/{store_id}/optimizations/approve-all
GET    /optimizations/{optimization_id}/results

GET /stores/{store_id}/optimizations
Query: status=pending|approved|applied|rejected, listing_id, page, per_page
Response: {
  data: [{
    id, listing_id, listing_title, optimization_type,
    old_value, new_value, change_summary, impact_estimate,
    status, created_at
  }]
}

POST /optimizations/{optimization_id}/apply
(Requires status=approved and store Etsy OAuth active)
Response: { data: { status: "applied", applied_at, etsy_update_status } }
```

---

### 4.12 Agent Runs

```
GET  /stores/{store_id}/agent/runs
GET  /agent/runs/{run_id}
GET  /agent/runs/{run_id}/tasks
POST /stores/{store_id}/agent/run
GET  /agent/runs/{run_id}/stream       — SSE endpoint

POST /stores/{store_id}/agent/run
Request:  { run_type: "daily_scan | seo_analysis | competitor_analysis | ..." }
Response: { data: { run_id, status: "pending", created_at } }

GET /agent/runs/{run_id}/stream
Content-Type: text/event-stream
Events:
  data: {"type":"progress","pct":35,"message":"Analyzing SEO for 12 listings..."}
  data: {"type":"task_complete","task":"seo_analysis","listing_id":"uuid"}
  data: {"type":"complete","run_id":"uuid","summary":{...}}
  data: {"type":"error","message":"..."}
```

---

### 4.13 Reports

```
GET  /stores/{store_id}/reports
GET  /reports/{report_id}
POST /stores/{store_id}/reports/generate

GET /stores/{store_id}/reports
Query: report_type=daily|weekly|monthly, page, per_page
Response: { data: [{ id, report_type, period_start, period_end, summary, created_at }] }

GET /reports/{report_id}
Response: { data: { ...full report with top_trends, opportunities, recommendations } }
```

---

### 4.14 Notifications

```
GET    /notifications
PATCH  /notifications/{id}/read
POST   /notifications/read-all
DELETE /notifications/{id}

GET /notifications
Query: read=true|false, type, page, per_page
Response: { data: [{ id, type, priority, title, message, read, action_url, created_at }] }
```

---

### 4.15 Billing

```
GET    /billing/plans
GET    /billing/subscription
POST   /billing/subscribe
POST   /billing/cancel
POST   /billing/portal
GET    /billing/credits
GET    /billing/credits/history
POST   /billing/credits/purchase

GET /billing/plans
Response: {
  data: [{
    name, display_name, price_monthly_usd, price_yearly_usd,
    max_stores, ai_credits_monthly, features
  }]
}

POST /billing/subscribe
Request: { plan: "pro", interval: "monthly|yearly", payment_method_id: "pm_xxx" }
Response: { data: { subscription_id, status, current_period_end } }

POST /billing/portal
Response: { data: { url: "https://billing.stripe.com/..." } }

GET /billing/credits
Response: { data: { balance: 847, monthly_grant: 1000, next_grant_date: "2026-07-01" } }
```

---

### 4.16 Webhooks

```
POST /webhooks/stripe          — Stripe event handler (no auth, uses webhook signature)
POST /webhooks/etsy            — Etsy push updates (if available on plan)

# Stripe events handled:
#   customer.subscription.updated
#   customer.subscription.deleted
#   invoice.payment_succeeded
#   invoice.payment_failed
#   checkout.session.completed
```

---

## 5. Etsy API Integration Plan

### 5.1 API Overview

```
Base URL:  https://openapi.etsy.com/v3
Auth:      OAuth 2.0 Authorization Code (PKCE supported)
Rate Limit: ~10 requests/second (token bucket, per application)
Daily Limit: ~10,000 requests/day (free tier); negotiate higher with Etsy
Pagination: limit (max 100) + offset params
```

### 5.2 OAuth2 Flow

```
Step 1 — User clicks "Connect Etsy Store" in dashboard
Step 2 — Backend generates:
           state = secrets.token_urlsafe(32)  [stored in Redis, TTL 10min]
           code_verifier = secrets.token_urlsafe(64)
           code_challenge = base64url(sha256(code_verifier))
Step 3 — Redirect user to:
           https://www.etsy.com/oauth/connect
             ?response_type=code
             &client_id={ETSY_CLIENT_ID}
             &redirect_uri={REDIRECT_URI}
             &scope=listings_r listings_w shops_r shops_w transactions_r
             &state={state}
             &code_challenge={code_challenge}
             &code_challenge_method=S256
Step 4 — Etsy redirects to /stores/connect/callback?code=xxx&state=xxx
Step 5 — Verify state matches Redis value (CSRF protection)
Step 6 — POST to https://api.etsy.com/v3/public/oauth/token
           { grant_type, client_id, redirect_uri, code, code_verifier }
           → { access_token, refresh_token, token_type, expires_in }
Step 7 — AES-256-GCM encrypt tokens, store in stores table
Step 8 — Immediately trigger sync_store_listings Celery task
```

### 5.3 Token Refresh Strategy

```python
# Etsy tokens expire every 3600 seconds (1 hour)
# Refresh tokens valid for 90 days

async def get_valid_token(store_id: str) -> str:
    store = await Store.get(store_id)
    
    # Check Redis cache first
    cached = await redis.get(f"etsy:token:{store_id}")
    if cached:
        return cached
    
    if store.token_expires_at > datetime.utcnow() + timedelta(minutes=5):
        # Still valid, cache it
        ttl = int((store.token_expires_at - datetime.utcnow()).total_seconds()) - 300
        await redis.setex(f"etsy:token:{store_id}", ttl, store.etsy_access_token_decrypted)
        return store.etsy_access_token_decrypted
    
    # Refresh
    resp = await httpx.post("https://api.etsy.com/v3/public/oauth/token", data={
        "grant_type": "refresh_token",
        "client_id": ETSY_CLIENT_ID,
        "refresh_token": store.etsy_refresh_token_decrypted,
    })
    tokens = resp.json()
    
    # Encrypt and persist
    await store.update_tokens(
        access_token=encrypt(tokens["access_token"]),
        refresh_token=encrypt(tokens["refresh_token"]),
        expires_at=datetime.utcnow() + timedelta(seconds=tokens["expires_in"])
    )
    return tokens["access_token"]
```

### 5.4 Endpoints Used

| Operation | Etsy Endpoint | Our Usage |
|---|---|---|
| Get shop details | `GET /application/shops/{shop_id}` | Initial store setup, health metrics |
| List active listings | `GET /application/shops/{shop_id}/listings/active` | Sync all listings |
| Get single listing | `GET /application/listings/{listing_id}` | Detailed sync |
| Get listing images | `GET /application/listings/{listing_id}/images` | Image analysis |
| Update listing | `PUT /application/listings/{listing_id}` | Apply optimizations |
| Get transactions | `GET /application/shops/{shop_id}/transactions` | Sales data for metrics |
| Search listings | `GET /application/listings/active?keywords={kw}` | Competitor discovery |
| Get shop reviews | `GET /application/shops/{shop_id}/reviews` | Review analysis |
| Get listing variations | `GET /application/listings/{listing_id}/variation-images` | Full product data |
| Get shop sections | `GET /application/shops/{shop_id}/sections` | Category structure |

### 5.5 Listing Sync Implementation

```python
async def sync_store_listings(store_id: str):
    token = await get_valid_token(store_id)
    store = await Store.get(store_id)
    
    await Store.update(store_id, sync_status="syncing")
    
    offset = 0
    limit = 100
    etsy_ids_seen = set()
    
    async with httpx.AsyncClient() as client:
        while True:
            # Rate limit: token bucket, max 10 req/sec
            await rate_limiter.acquire(f"etsy:{store_id}")
            
            resp = await client.get(
                f"https://openapi.etsy.com/v3/application/shops/{store.etsy_shop_id}/listings/active",
                headers={"x-api-key": ETSY_CLIENT_ID, "Authorization": f"Bearer {token}"},
                params={
                    "limit": limit,
                    "offset": offset,
                    "includes": ["Images", "MainImage"],
                }
            )
            resp.raise_for_status()
            data = resp.json()
            
            listings = data.get("results", [])
            if not listings:
                break
            
            for raw in listings:
                etsy_ids_seen.add(raw["listing_id"])
                await upsert_listing(store_id, raw)
            
            if len(listings) < limit:
                break
            offset += limit
    
    # Mark listings no longer on Etsy as removed
    await Listing.mark_removed(store_id, etsy_ids_seen)
    await Store.update(store_id, sync_status="idle", last_synced_at=datetime.utcnow())
    
    # Kick off embedding updates for changed listings
    changed = await Listing.get_recently_changed(store_id, since=store.last_synced_at)
    for listing in changed:
        update_embeddings.delay("listing", str(listing.id))
```

### 5.6 Applying Optimizations Back to Etsy

```python
async def apply_optimization(optimization_id: str):
    opt = await ListingOptimization.get(optimization_id)
    
    # Verify user approved
    assert opt.status == "approved", "Optimization must be approved before applying"
    
    listing = await Listing.get(opt.listing_id)
    token = await get_valid_token(listing.store_id)
    
    # Build update payload — only changed fields
    payload = {}
    if opt.optimization_type == "title":
        payload["title"] = opt.new_value
    elif opt.optimization_type == "description":
        payload["description"] = opt.new_value
    elif opt.optimization_type == "tags":
        # Etsy tags: list of strings, max 13 tags, each max 20 chars
        tags = json.loads(opt.new_value)
        assert len(tags) <= 13
        assert all(len(t) <= 20 for t in tags)
        payload["tags"] = tags
    
    async with httpx.AsyncClient() as client:
        await rate_limiter.acquire(f"etsy:{listing.store_id}")
        resp = await client.put(
            f"https://openapi.etsy.com/v3/application/listings/{listing.etsy_listing_id}",
            headers={"x-api-key": ETSY_CLIENT_ID, "Authorization": f"Bearer {token}"},
            json=payload
        )
    
    if resp.status_code == 200:
        await ListingOptimization.update(optimization_id,
            status="applied", applied=True, applied_at=datetime.utcnow(),
            etsy_update_status="success")
        # Re-sync the listing from Etsy to confirm
        sync_single_listing.delay(str(listing.store_id), listing.etsy_listing_id)
    else:
        await ListingOptimization.update(optimization_id,
            etsy_update_status="failed",
            etsy_update_error=f"{resp.status_code}: {resp.text}")
        raise EtsyUpdateError(resp.text)
```

### 5.7 Rate Limiting Strategy

```python
# Token bucket: 10 req/sec per application (not per store)
# Implement at the application level to avoid 429s

class EtsyRateLimiter:
    def __init__(self, redis_client, rate=10, capacity=10):
        self.redis = redis_client
        self.rate = rate        # tokens per second
        self.capacity = capacity

    async def acquire(self, key: str = "etsy:global"):
        # Lua script for atomic token bucket
        lua = """
        local key = KEYS[1]
        local capacity = tonumber(ARGV[1])
        local rate = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])
        
        local last = tonumber(redis.call('hget', key, 'last') or now)
        local tokens = tonumber(redis.call('hget', key, 'tokens') or capacity)
        
        local delta = math.max(0, now - last)
        tokens = math.min(capacity, tokens + delta * rate)
        
        if tokens >= 1 then
            redis.call('hset', key, 'tokens', tokens - 1, 'last', now)
            return 1
        end
        return 0
        """
        while True:
            result = await self.redis.eval(lua, 1, key,
                self.capacity, self.rate, time.time())
            if result == 1:
                return
            await asyncio.sleep(0.1)
```

### 5.8 Competitor Discovery via Etsy Search

```python
async def discover_competitors(listing_id: str) -> list[dict]:
    listing = await Listing.get(listing_id)
    
    # Extract primary keywords from listing title (top 3 meaningful phrases)
    keywords = await extract_search_keywords(listing.title, listing.tags)
    
    competitors = []
    for keyword in keywords[:3]:
        await rate_limiter.acquire()
        resp = await etsy_client.get(
            "/application/listings/active",
            params={
                "keywords": keyword,
                "limit": 25,
                "sort_on": "score",
                "includes": ["MainImage"],
                "taxonomy_id": listing.taxonomy_id,  # same category
            }
        )
        results = resp.json().get("results", [])
        
        for i, item in enumerate(results):
            if item["listing_id"] == listing.etsy_listing_id:
                continue  # skip our own listing
            competitors.append({
                **item,
                "rank_position": i + 1,
                "search_keyword": keyword,
            })
    
    # Deduplicate, keep highest rank position per listing
    seen = {}
    for c in competitors:
        lid = c["listing_id"]
        if lid not in seen or c["rank_position"] < seen[lid]["rank_position"]:
            seen[lid] = c
    
    return sorted(seen.values(), key=lambda x: x["rank_position"])[:10]
```

### 5.9 Error Handling & Retry Policy

```
HTTP 429 Too Many Requests  → exponential backoff (2s, 4s, 8s), max 3 retries
HTTP 401 Unauthorized       → refresh OAuth token once, then retry
HTTP 403 Forbidden          → log + notify user (scope missing or store disconnected)
HTTP 404 Not Found          → mark listing as removed in DB, continue
HTTP 500/503 Etsy errors    → retry with 60s delay, max 3 attempts; alert if persistent
Network timeout             → 30s timeout, retry with 10s delay
```

---
