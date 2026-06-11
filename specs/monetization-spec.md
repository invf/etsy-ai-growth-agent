# Etsy AI Growth Agent — Monetization & Business Architecture Specification

> Session 5 of 5. Companion to `backend-spec.md`, `frontend-spec.md`, `ai-agent-spec.md`.

---

## Table of Contents

1. [Pricing Tiers](#1-pricing-tiers)
2. [AI Credits System Design](#2-ai-credits-system-design)
3. [Revenue Projections — Year 1](#3-revenue-projections--year-1)
4. [Scaling Strategy — 0 to 1,000 Users](#4-scaling-strategy--0-to-1000-users)
5. [Paddle Payment Integration](#5-paddle-payment-integration)
6. [Financial Controls & Risk](#6-financial-controls--risk)

---

## 1. Pricing Tiers

### 1.1 Competitive Positioning

The Etsy tools market is well-established with commodity keyword research products priced $9.99–$29.99/month (Marmalead, eRank, Sale Samurai, EverBee). We are positioned above them as an **AI-native automation platform** — the distinction is *acting* on insights, not just displaying them.

```
Price axis (monthly)
                                                            [Agency $299]
                                        [Pro $99]
                  [Growth $49]
  [Starter $19]
────────────────────────────────────────────────────────────────────────►
 Keyword research  Full analysis   Automation + multi-store  White-label
 (Marmalead tier)  (Alura tier)    (no direct competitor)   (no competitor)
```

### 1.2 Tier Definitions

#### Free Trial
- **Duration:** 14 days, no credit card required
- **Scope:** Full Starter feature access
- **Credits:** 30 trial credits (enough for 6 daily agent runs)
- **Store limit:** 1 store
- **Restriction:** Optimizations are read-only — no Etsy write-back during trial
- **Goal:** Let sellers see the AI recommendations before committing; builds intent

#### Starter — $19/month | $182/year (20% annual discount)

| Limit | Value |
|---|---|
| Stores | 1 |
| AI credits/month | 100 |
| Daily agent runs | Automated (consumes 5 credits/run → 20 automated days/month) |
| Listings analyzed/run | Top 20 by revenue |
| SEO optimization | Yes (review + apply) |
| Competitor analysis | Yes (top 3 competitors per category) |
| Trend intelligence | Yes |
| Image analysis | Yes |
| Pricing advisor | Yes |
| Content generation | Yes |
| Monthly strategic plan | No (Pro+) |
| Audience discovery | No (Growth+) |
| Email digest | Weekly |
| Team members | 1 (solo) |
| Support | Email (48h SLA) |
| API access | No |

#### Growth — $49/month | $470/year

| Limit | Value |
|---|---|
| Stores | 2 |
| AI credits/month | 300 |
| Daily agent runs | Automated for all stores (~30 full days per store/month) |
| Listings analyzed/run | Top 50 by revenue |
| All Starter features | Yes |
| Audience discovery | Yes |
| Monthly strategic plan | Yes |
| Weekly + daily email digest | Yes |
| A/B test tracking | Yes (track which optimization version won) |
| Custom brand voice | Yes (stored per store) |
| Credit top-up | Yes |
| Team members | 2 |
| Support | Email (24h SLA) |
| API access | No |

#### Pro — $99/month | $950/year

| Limit | Value |
|---|---|
| Stores | 5 |
| AI credits/month | 750 |
| Daily agent runs | Automated for all stores, full listings |
| Listings analyzed/run | All active listings (no cap) |
| All Growth features | Yes |
| Priority analysis queue | Yes (high Celery queue, not bulk) |
| Custom Celery schedule | Run agent at custom time (not just 07:00 UTC) |
| Bulk content generation | Yes (rewrite all listings in category at once) |
| CSV export | Yes (all recommendations, analytics) |
| Zapier/webhook outbound | Yes (notify external tools on new recommendations) |
| Team members | 5 |
| Support | Email + live chat (4h SLA) |
| API access | Read-only (fetch recommendations programmatically) |

#### Agency — $299/month | $2,870/year

| Limit | Value |
|---|---|
| Stores | 20 |
| AI credits/month | 2,500 (overage at $0.08/credit) |
| Daily agent runs | Automated for all stores, all listings |
| All Pro features | Yes |
| White-label dashboard | Yes (custom domain, logo, color scheme) |
| Client reporting | Branded PDF reports generated automatically |
| Sub-accounts | Yes (manage client stores under one account) |
| Full API access | Read + write (apply optimizations via API) |
| SLA dashboard | Uptime and response time monitoring |
| Team members | Unlimited |
| Support | Dedicated Slack channel (2h SLA) |
| Custom onboarding | 1:1 setup call |

### 1.3 Credit Top-Up Packages (All Tiers)

| Package | Credits | Price | Price per Credit |
|---|---|---|---|
| Small | 50 | $4.99 | $0.10 |
| Medium | 150 | $12.99 | $0.087 |
| Large | 400 | $29.99 | $0.075 |
| XL | 1,000 | $59.99 | $0.06 |

Top-ups never expire. Subscription credits reset monthly (no rollover at Starter; 50% rollover at Growth+).

### 1.4 Feature Gate Matrix

```
Feature                          Trial  Starter  Growth  Pro   Agency
─────────────────────────────────────────────────────────────────────
Daily agent (auto)                 ✓       ✓        ✓      ✓      ✓
SEO optimization                   ✓       ✓        ✓      ✓      ✓
Competitor analysis                ✓       ✓        ✓      ✓      ✓
Trend intelligence                 ✓       ✓        ✓      ✓      ✓
Image analysis                     ✓       ✓        ✓      ✓      ✓
Pricing advisor                    ✓       ✓        ✓      ✓      ✓
Content generation                 ✓       ✓        ✓      ✓      ✓
Audience discovery                 ✗       ✗        ✓      ✓      ✓
Monthly strategic plan             ✗       ✗        ✓      ✓      ✓
A/B test tracking                  ✗       ✗        ✓      ✓      ✓
Custom brand voice                 ✗       ✗        ✓      ✓      ✓
All active listings (no cap)       ✗       ✗        ✗      ✓      ✓
Bulk content generation            ✗       ✗        ✗      ✓      ✓
CSV export                         ✗       ✗        ✗      ✓      ✓
Outbound webhooks                  ✗       ✗        ✗      ✓      ✓
Read API                           ✗       ✗        ✗      ✓      ✓
Write API                          ✗       ✗        ✗      ✗      ✓
White-label                        ✗       ✗        ✗      ✗      ✓
Client sub-accounts                ✗       ✗        ✗      ✗      ✓
Write-back to Etsy (trial blocked) ✗       ✓        ✓      ✓      ✓
```

---

## 2. AI Credits System Design

### 2.1 Credit Accounting Model

Credits are an **internal currency** that abstracts AI compute cost from the user. One credit ≈ $0.08 internal cost ≈ $0.10 user value. This gives a ~20% gross margin buffer on credit-driven operations, with subscription margin on top.

```
User perspective:            Internal reality:
100 credits = $10           100 credits × $0.08 = $8.00 AI cost
                             100 credits at $0.10 = $10.00 revenue
                             Gross margin: $2.00 (20%)

Subscription credits:
Starter: 100 credits/$19    $8.00 AI cost / $19.00 subscription = 42% GM on credits
                             (remaining $11 covers infra + overhead + profit)
```

### 2.2 Credit Cost per Operation

```python
# app/config/credit_costs.py

CREDIT_COSTS: dict[str, int] = {
    # Daily Agent Operations
    "daily_agent_run":              5,   # Full daily run (~$0.40-0.85 AI cost)
    "daily_agent_run_pro":          5,   # Same cost, different queue priority

    # On-Demand Analysis
    "seo_analysis_deep":            2,   # Single listing deep SEO (Fable 5)
    "seo_analysis_quick":           0,   # Included free with daily run (Haiku)
    "competitor_analysis":          2,   # Per-category competitor scan
    "trend_report_on_demand":       1,   # Instant trend fetch (outside daily run)
    "image_analysis":               1,   # Per listing image review

    # Content Generation
    "content_generation_premium":   1,   # Fable 5 rewrite (high-revenue listing)
    "content_generation_standard":  0,   # Haiku rewrite, bundled with daily run
    "bulk_content_generation":      3,   # Entire category rewrite (Pro+ only)

    # Reports & Planning
    "weekly_report":                3,   # Sunday auto-generated
    "monthly_strategic_plan":       5,   # Monthly (Growth+ only)
    "audience_discovery":           4,   # Deep persona analysis (Growth+ only)

    # Utility (zero-cost)
    "optimization_apply":           0,   # Applying to Etsy: no AI cost
    "pricing_check":                0,   # Included in daily run (Haiku)
}

# Hard daily credit cap per user (prevents runaway agent loops)
DAILY_CREDIT_CAP: dict[str, int] = {
    "trial":   10,
    "starter": 30,    # prevents burning monthly allotment in 3 days
    "growth":  60,
    "pro":     150,
    "agency":  500,
}
```

### 2.3 Credit Lifecycle

```
User subscribes → credits_balance += monthly_allotment (allocated at billing cycle start)
                     │
User runs agent  → credit_service.reserve(user_id, 5, run_id)
                     │
                     ├── Redis: credits:reserved:{user_id} += 5
                     │
                  AI calls execute...
                     │
                  Run completes → credit_service.settle_reservation(run_id, actual_cost)
                     │
                     ├── DB: users.credits_balance -= actual_cost
                     ├── DB: credit_transactions INSERT (balance_after = new_balance)
                     └── Redis: credits:reserved:{user_id} -= reserved (5)
                               Redis: credits:balance:{user_id} invalidated
```

### 2.4 Credit Reservation (Race Condition Prevention)

Two users on same account can't trigger concurrent overdraft:

```python
# app/services/credit_service.py
import redis
from app.db.session import get_db_session
import logging

logger = logging.getLogger(__name__)

RESERVE_LUA = """
local balance_key = KEYS[1]
local reserved_key = KEYS[2]
local amount = tonumber(ARGV[1])
local run_id = ARGV[2]
local reservation_ttl = tonumber(ARGV[3])

-- Read current state
local balance = tonumber(redis.call('GET', balance_key) or '0')
local reserved = tonumber(redis.call('GET', reserved_key) or '0')
local available = balance - reserved

if available < amount then
    return {0, available}  -- insufficient, return available balance
end

-- Reserve atomically
redis.call('INCRBY', reserved_key, amount)
redis.call('EXPIRE', reserved_key, reservation_ttl)
redis.call('SET', 'credits:run:' .. run_id, amount, 'EX', reservation_ttl)
return {1, available - amount}  -- success, return new available balance
"""


class CreditService:
    def __init__(self, r: redis.Redis):
        self.r = r
        self._reserve_script = r.register_script(RESERVE_LUA)

    def get_balance(self, user_id: str) -> dict:
        """Returns balance, reserved, and available credits."""
        cache_key = f"credits:balance:{user_id}"
        cached = self.r.get(cache_key)

        if cached:
            import json
            return json.loads(cached)

        with get_db_session() as db:
            row = db.execute(
                "SELECT credits_balance, subscription_tier FROM users WHERE id = :uid",
                {"uid": user_id}
            ).fetchone()
            balance = row.credits_balance if row else 0

        reserved = int(self.r.get(f"credits:reserved:{user_id}") or 0)
        result = {
            "balance": balance,
            "reserved": reserved,
            "available": balance - reserved,
        }
        import json
        self.r.setex(cache_key, 60, json.dumps(result))
        return result

    def reserve(self, user_id: str, amount: int, run_id: str) -> bool:
        """
        Atomic reserve. Returns True if sufficient credits available.
        Syncs DB balance to Redis on first call (cold cache).
        """
        balance_key = f"credits:balance:{user_id}"
        reserved_key = f"credits:reserved:{user_id}"

        # Warm the balance cache from DB if cold
        if not self.r.exists(balance_key):
            with get_db_session() as db:
                row = db.execute(
                    "SELECT credits_balance FROM users WHERE id = :uid",
                    {"uid": user_id}
                ).fetchone()
                balance = row.credits_balance if row else 0
            self.r.setex(balance_key, 300, str(balance))

        result = self._reserve_script(
            keys=[balance_key, reserved_key],
            args=[amount, run_id, 3600]
        )
        success, available = result[0], result[1]

        if not success:
            logger.warning(f"Credit reservation failed for user {user_id}: need {amount}, have {available}")
        return bool(success)

    def settle_reservation(self, run_id: str, actual_credits: int | None = None):
        """Deduct actual usage from DB, release reservation from Redis."""
        reserved = int(self.r.get(f"credits:run:{run_id}") or 0)
        cost = actual_credits if actual_credits is not None else reserved

        with get_db_session() as db:
            # Atomic deduct with denormalized balance_after
            user_row = db.execute("""
                UPDATE users
                SET credits_balance = GREATEST(0, credits_balance - :cost)
                WHERE id = (SELECT user_id FROM agent_runs WHERE id = :run_id)
                RETURNING id, credits_balance
            """, {"cost": cost, "run_id": run_id}).fetchone()

            if user_row:
                db.execute("""
                    INSERT INTO credit_transactions
                        (user_id, amount, transaction_type, reference_id, balance_after)
                    VALUES (:uid, :amount, 'agent_run_deduction', :run_id, :balance_after)
                """, {
                    "uid": str(user_row.id),
                    "amount": -cost,
                    "run_id": run_id,
                    "balance_after": user_row.credits_balance,
                })
                # Invalidate caches
                self.r.delete(
                    f"credits:balance:{user_row.id}",
                    f"credits:reserved:{user_row.id}",
                    f"credits:run:{run_id}",
                )

    def allocate_subscription_credits(self, user_id: str, tier: str):
        """
        Called on subscription creation and monthly renewal.
        Adds credits based on tier. Partial rollover for Growth+.
        """
        MONTHLY_CREDITS = {
            "trial":   30,
            "starter": 100,
            "growth":  300,
            "pro":     750,
            "agency":  2500,
        }
        ROLLOVER_PERCENT = {
            "trial":   0,
            "starter": 0,     # no rollover
            "growth":  50,    # carry 50% of unused credits
            "pro":     50,
            "agency":  100,   # full rollover
        }

        new_credits = MONTHLY_CREDITS.get(tier, 0)
        rollover_pct = ROLLOVER_PERCENT.get(tier, 0)

        with get_db_session() as db:
            current = db.execute(
                "SELECT credits_balance FROM users WHERE id = :uid",
                {"uid": user_id}
            ).scalar() or 0

            # Apply rollover cap
            max_rollover = int(current * rollover_pct / 100)
            carried = min(current, max_rollover)
            new_balance = carried + new_credits

            db.execute("""
                UPDATE users SET credits_balance = :balance WHERE id = :uid
            """, {"balance": new_balance, "uid": user_id})

            db.execute("""
                INSERT INTO credit_transactions
                    (user_id, amount, transaction_type, balance_after)
                VALUES (:uid, :amount, 'subscription_renewal', :balance_after)
            """, {
                "uid": user_id,
                "amount": new_credits,
                "balance_after": new_balance,
            })

        # Invalidate cached balance
        self.r.delete(f"credits:balance:{user_id}")
        logger.info(f"Allocated {new_credits} credits to user {user_id} (tier: {tier}, rolled over: {carried})")
```

### 2.5 Low Credit Warning System

```python
# app/services/credit_service.py — threshold alerts

LOW_CREDIT_THRESHOLDS = {
    "starter": 20,   # <20 credits = ~4 daily runs remaining
    "growth":  50,
    "pro":     100,
    "agency":  200,
}

def check_and_notify_low_credits(user_id: str, tier: str):
    """
    Called after each credit deduction. Sends in-app notification
    and email once per billing cycle when balance drops below threshold.
    """
    threshold = LOW_CREDIT_THRESHOLDS.get(tier, 20)
    balance_info = self.get_balance(user_id)

    if balance_info["available"] < threshold:
        notif_key = f"low_credit_notified:{user_id}:{_current_billing_cycle()}"
        if not self.r.exists(notif_key):
            # Send once per cycle
            _create_in_app_notification(user_id, "low_credits", {
                "available": balance_info["available"],
                "threshold": threshold,
                "top_up_url": "/billing/top-up",
            })
            _queue_low_credits_email(user_id, balance_info["available"])
            self.r.setex(notif_key, 30 * 24 * 3600, "1")  # 30 day TTL


def _current_billing_cycle() -> str:
    from datetime import datetime
    now = datetime.utcnow()
    return f"{now.year}-{now.month:02d}"
```

### 2.6 Credit Balance in API Response

Every authenticated API response includes a credit balance header so the frontend can stay updated without a separate call:

```python
# app/middleware/credit_header.py
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

class CreditBalanceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        user = getattr(request.state, "user", None)
        if user and response.status_code < 400:
            # Attach remaining credits to response header (no extra DB query — uses Redis cache)
            balance = credit_service.get_balance(str(user.id))
            response.headers["X-Credits-Available"] = str(balance["available"])
            response.headers["X-Credits-Balance"] = str(balance["balance"])

        return response
```

---

## 3. Revenue Projections — Year 1

### 3.1 Assumptions

| Parameter | Value | Source |
|---|---|---|
| Etsy active sellers | ~7.5M | Etsy 2024 annual report |
| Addressable (English-speaking, $1K+/year revenue) | ~1.5M | Estimate 20% of total |
| Currently using paid Etsy tools | ~15% | Industry estimate |
| Trial-to-paid conversion rate | 25% | SaaS benchmark for SMB tools |
| Monthly churn rate | 5% | SMB SaaS typical range |
| Annual plan take rate | 30% | Of paying customers |
| Average revenue per user (blended ARPU) | $38/month | Tier mix: 60/30/10 Starter/Growth/Pro |
| Credit top-up attachment rate | 15% | Of Starter users run low monthly |
| Top-up average order value | $14 | Median of package mix |

### 3.2 User Growth Model

```
Month  │ New Users │ Churned │ Total Users │ Notes
───────┼───────────┼─────────┼─────────────┼─────────────────────────────────
  1    │    20     │    0    │     20      │ Beta — friends, Etsy seller communities
  2    │    30     │    1    │     49      │ Beta continues
  3    │    50     │    2    │     97      │ Public launch, Product Hunt
  4    │    75     │    5    │    167      │ SEO content + Reddit posts gaining traction
  5    │    90     │    8    │    249      │ First affiliate partners onboarded
  6    │   100     │   12    │    337      │ Word-of-mouth compounding
  7    │   110     │   17    │    430      │ YouTube tutorial partnerships
  8    │   120     │   22    │    528      │ Etsy seller Facebook groups
  9    │   130     │   26    │    632      │
 10    │   135     │   32    │    735      │
 11    │   140     │   37    │    838      │
 12    │   150     │   42    │    946      │ Year-end target: ~950 users

Total Year 1 paying users acquired: 1,150
Average active users across Year 1: ~430
```

### 3.3 Tier Distribution (Steady-State)

| Tier | % of Users | Monthly Price | Notes |
|---|---|---|---|
| Trial (non-paying) | 20% | $0 | 14-day window; 25% convert |
| Starter | 55% | $19 | Entry point for solo sellers |
| Growth | 30% | $49 | Sellers with 2+ stores or heavy usage |
| Pro | 12% | $99 | Power sellers, serious businesses |
| Agency | 3% | $299 | Etsy consultants, account managers |

### 3.4 Monthly Recurring Revenue Build

```
Month  │ Total  │ Trial │Starter│Growth │  Pro  │Agency │  MRR     │  MoM%
───────┼────────┼───────┼───────┼───────┼───────┼───────┼──────────┼───────
  1    │   20   │   4   │  11   │   4   │   1   │   0   │  $458    │  —
  2    │   49   │  10   │  27   │  10   │   2   │   0   │ $1,131   │ +147%
  3    │   97   │  19   │  53   │  20   │   4   │   1   │ $2,366   │ +109%
  4    │  167   │  33   │  92   │  35   │   6   │   1   │ $4,002   │  +69%
  5    │  249   │  50   │ 137   │  52   │  10   │   2   │ $5,835   │  +46%
  6    │  337   │  67   │ 185   │  70   │  14   │   3   │ $8,050   │  +38%
  7    │  430   │  86   │ 237   │  89   │  17   │   4   │$10,198   │  +27%
  8    │  528   │ 106   │ 291   │ 109   │  21   │   5   │$12,533   │  +23%
  9    │  632   │ 126   │ 348   │ 131   │  25   │   6   │$15,008   │  +20%
 10    │  735   │ 147   │ 404   │ 152   │  29   │   7   │$17,455   │  +16%
 11    │  838   │ 168   │ 461   │ 173   │  33   │   9   │$20,079   │  +15%
 12    │  946   │ 189   │ 520   │ 196   │  37   │  10   │$22,622   │  +13%

MRR Calculation per month:
  Starter:  users × $19
  Growth:   users × $49
  Pro:      users × $99
  Agency:   users × $299
  (Trial users not counted; conversion assumed in next month's paying count)
```

### 3.5 Additional Revenue Streams

```
Credit Top-Ups (Month 6 onward, as Starter users hit limits)
───────────────────────────────────────────────────────────
Starter users on monthly: 185
Top-up attachment rate: 15%
Average order: $14
Monthly top-up revenue: 185 × 15% × $14 = $389 (Month 6)

Annual Plans (offered at 20% discount, collected upfront)
──────────────────────────────────────────────────────────
Annual plan take rate: 30% of new sign-ups from Month 3 onward
Average annual plan value: $38 × 12 × 0.80 = $365
Month 3-12 annual plan sign-ups: ~250 users
Annual plan revenue collected upfront: 250 × $365 = $91,250 (spread recognition)
Cash collected: large lumps at launch periods
```

### 3.6 Year 1 P&L Summary

```
Revenue
───────────────────────────────────────────────
Subscription MRR (cumulative, Jan-Dec)    $119,737
Credit top-up revenue                      $8,200
Annual plan cash collection               $91,250  (revenue recognized monthly)
                                         ──────────
Total Year 1 Revenue (recognized)        $127,937
Total Year 1 Cash Collected              $181,000  (annual plans boost cash)


Cost of Revenue
───────────────────────────────────────────────
AI costs (Anthropic + Voyage)              ~$18,000  (avg 430 users × $3.50/mo)
Paddle transaction fees (5% + $0.50)       ~$9,100
Database + hosting (Render → AWS)           ~$6,000
Email (SendGrid)                            ~$1,200
Redis Cloud                                 ~$1,800
Monitoring (Sentry + Datadog)              ~$2,400
                                         ──────────
Total COGS                                 $38,500

Gross Profit                               $89,437
Gross Margin                                   70%


Operating Expenses (founding team)
───────────────────────────────────────────────
Salaries / contractor (1-2 engineers)     ~$80,000
Marketing (content, ads, affiliates)      ~$15,000
Legal / incorporation / compliance          ~$3,000
Miscellaneous SaaS tools                    ~$2,400
                                         ──────────
Total OpEx                                $100,400

Net Operating Income (Loss)              ($10,963)
Breakeven MRR target:                    ~$16,700  (reached Month 9 at ~$15K)
Breakeven with salary:                   Month 10–11
```

### 3.7 Key SaaS Metrics

| Metric | Month 6 | Month 12 | Target |
|---|---|---|---|
| MRR | $8,050 | $22,622 | $20K by M12 ✓ |
| ARR | $96,600 | $271,464 | >$250K ✓ |
| ARPU (blended) | $32 | $38 | $35+ ✓ |
| Monthly churn rate | 5.5% | 4.2% | <5% |
| LTV (at 5% churn) | $640 | $760 | >$500 ✓ |
| CAC (est.) | $45 | $35 | <$50 ✓ |
| LTV:CAC ratio | 14:1 | 22:1 | >3:1 ✓ |
| Trial conversion rate | 23% | 28% | >25% |
| Net Revenue Retention | 98% | 105% | >100% (expansion) |

---

## 4. Scaling Strategy — 0 to 1,000 Users

### 4.1 Phase 0: Pre-Launch (Month -2 to 0)

**Goal:** Validate core loop before spending on acquisition. Target: 10 beta sellers, manually monitored.

**Infrastructure:** Single Render instance, manual DB. No Celery — run agent manually via `python run_agent.py`.

**Product:** Focus on SEO analysis + content generation only. Skip trends and competitors at first.

**Metrics to validate:**
- Does generated content improve Etsy search ranking within 2 weeks?
- Do sellers actually apply recommendations?
- Average session frequency > 3x/week?

**Acquisition:** Direct DMs in Etsy seller Facebook groups, r/EtsySellers, r/HandmadeMarket.

**Go/No-Go:** 7 of 10 beta sellers rate experience 8+ / 10. At least 3 share the product with another seller unprompted.

### 4.2 Phase 1: Beta Launch — 0 to 100 Users (Month 1–4)

**Infrastructure:**
```
Render Web Service (FastAPI)    — $25/month Starter
Render PostgreSQL               — $25/month (managed, daily backups)
Render Redis                    — $15/month
Render Background Worker        — $25/month (Celery)
Render Cron Job                 — $7/month (Celery Beat)
                                ─────────
Total infra:                    ~$97/month
```

**Code changes needed:**
- Feature flags table in DB (not ENV vars) — toggle features per user without redeploy
- Celery Beat running but limited to manually triggered agent runs
- Basic analytics dashboard for founders (admin portal on `/admin`)

**Acquisition strategy (zero-budget):**
- Post 3 valuable threads in r/EtsySellers per week (no spam — genuinely helpful)
- Guest posts on Etsy seller blogs (Handmade Business, EtsySellers.net)
- Product Hunt launch on Day 30 (coordinate upvotes from beta users)
- One YouTube video: "I used AI to optimize my Etsy store for 30 days — results"

**Conversion funnel at 100 users:**
```
Etsy seller discovers product → lands on homepage
    ↓ (40% bounce)
Signs up for trial (no credit card) → 60% sign up
    ↓ (25% trial-to-paid)
Enters credit card → 15% of signups (~9% of landings)
    ↓
Subscribes (mostly Starter $19)
```

### 4.3 Phase 2: Growth — 100 to 500 Users (Month 4–8)

**Infrastructure migration (month 5):**
```
Current (Render)     →   Target (AWS ECS + managed services)
─────────────────────────────────────────────────────────────
Render Web Service   →   AWS ECS Fargate (2 tasks × 0.5 vCPU, 1GB)
Render PostgreSQL    →   AWS RDS PostgreSQL 16 (db.t3.medium, Multi-AZ)
Render Redis         →   AWS ElastiCache Redis (cache.t3.micro)
Render Worker        →   AWS ECS Fargate (Celery worker, autoscale 1-5 tasks)
Render Cron          →   AWS ECS Fargate (Celery Beat, always-on 1 task)
                         AWS S3 (listing images cache, AI response cache)
                         AWS CloudFront (Next.js static + API edge caching)
                    ──────────────────────────────────────
                         ~$280/month at 200 users
                         ~$420/month at 500 users
```

**Product expansion unlocks:**
- Trend intelligence (Google Trends + Reddit integration)
- Audience discovery (Growth tier)
- Monthly strategic plan
- A/B test tracking for optimizations

**Acquisition strategy (small budget $1,500/month):**
```
Channel                    Budget    Expected CAC    Monthly Acq
────────────────────────────────────────────────────────────────
Content SEO                $0        $0 (organic)    20-30 (M6+)
YouTube partnerships       $500      $25             20
Facebook group ads         $500      $40             12
Affiliate program          $500      $30             15-20
(10% rev share for 6 mo)
                          ────────────────────────────────────
Total                     $1,500    $30 blended      50-60/mo
```

**Affiliate program design:**
- 10% revenue share for 6 months on referred subscribers
- Tracked via Paddle affiliate links
- Minimum payout: $50 (monthly)
- Target affiliates: Etsy coaches, YouTube channels (<50K subs), Etsy seller newsletters

### 4.4 Phase 3: Scale — 500 to 1,000 Users (Month 8–12)

**Infrastructure — read replicas + autoscaling:**
```yaml
# AWS ECS autoscaling policy
services:
  api:
    desired: 2
    min: 2
    max: 8
    scale_out: cpu_utilization > 70% for 3 min
    scale_in: cpu_utilization < 30% for 10 min

  celery_worker:
    desired: 3
    min: 2
    max: 10
    scale_out: celery_queue_depth > 100 tasks (CloudWatch custom metric)
    scale_in: celery_queue_depth < 20 tasks

database:
  primary: db.t3.large (Multi-AZ)
  read_replica: db.t3.medium (for analytics queries, dashboard reads)
  connection_pooling: PgBouncer (transaction mode, max 100 connections)

redis:
  cluster_mode: single node (cache.t3.small → cache.r6g.large at 800 users)
  backup: daily snapshot to S3
```

**Database partitioning (pre-emptive at 500K rows):**
```sql
-- Partition agent_run_logs by month (write-heavy, rarely queried beyond 30 days)
CREATE TABLE agent_run_logs (
    id UUID NOT NULL,
    run_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    -- ... other columns
) PARTITION BY RANGE (created_at);

CREATE TABLE agent_run_logs_2026_06 PARTITION OF agent_run_logs
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');

-- Automate via pg_partman extension
```

**Product: enterprise readiness for Agency tier:**
- White-label dashboard (custom CNAME + SSL via Let's Encrypt wildcard)
- Sub-account management
- Branded PDF report generation
- Full read/write API with API key management

**Acquisition at scale (budget $5,000/month):**
```
Channel                    Budget    Expected CAC    Monthly Acq
────────────────────────────────────────────────────────────────
SEO content (organic)      $500      $0 (organic)    40-60
Paid search (Google)       $1,500    $45             33
YouTube ads                $1,000    $40             25
Affiliate payouts          $1,000    $28             35
Etsy coach partnerships    $500      $20             25
Retargeting (trial→paid)   $500      $15             33
                          ────────────────────────────────────
Total                     $5,000    $29 blended      190-210/mo
```

### 4.5 Infrastructure Cost Model

```
Users    │ Monthly Infra  │ Monthly AI Cost │ Total COGS  │ COGS % of MRR
─────────┼────────────────┼─────────────────┼─────────────┼──────────────
  50     │    $97         │    $80          │    $177     │    87%  (losses)
 100     │    $150        │    $175         │    $325     │    39%
 250     │    $280        │    $450         │    $730     │    23%
 500     │    $420        │    $900         │   $1,320    │    18%
1,000    │    $750        │   $1,750        │   $2,500    │    14%

Note: AI cost = avg 430 users × $3.50/mo × 1.15 (overhead buffer)
Paddle fees (~5%) are separate and scale linearly with revenue
```

---

## 5. Paddle Payment Integration

### 5.1 Why Paddle (vs Stripe)

| Factor | Paddle | Stripe |
|---|---|---|
| Tax compliance | Merchant of Record — Paddle handles VAT, GST, sales tax globally | You handle tax yourself (or pay $0.50/transaction to Stripe Tax) |
| European VAT | Fully automatic | Requires Stripe Tax + configuration |
| US sales tax nexus | Handled | You're liable after $100K revenue in many states |
| Subscription management | Built-in dunning, retry, grace periods | Requires custom implementation |
| Payout | Paddle → your bank weekly | Stripe → your bank daily |
| Fee (subscriptions) | 5% + $0.50 | 2.9% + $0.30 (+ Stripe Tax 0.5%) |
| Complexity for solo founder | Low | Medium-high |

**Decision:** Paddle at MVP stage. Re-evaluate Stripe at $1M ARR if fees become material.

### 5.2 Paddle Account Setup

```bash
# Required Paddle account configuration:
# 1. Create products for each tier (not prices — products contain price variants)
# 2. Create recurring prices for monthly + annual variants
# 3. Create one-time prices for each credit top-up package
# 4. Configure webhook endpoints: https://api.yourapp.com/webhooks/paddle
# 5. Enable Paddle.js v2 CDN on frontend

# Paddle price IDs (set via environment variables — do NOT hardcode)
PADDLE_PRICE_STARTER_MONTHLY=pri_...
PADDLE_PRICE_STARTER_ANNUAL=pri_...
PADDLE_PRICE_GROWTH_MONTHLY=pri_...
PADDLE_PRICE_GROWTH_ANNUAL=pri_...
PADDLE_PRICE_PRO_MONTHLY=pri_...
PADDLE_PRICE_PRO_ANNUAL=pri_...
PADDLE_PRICE_AGENCY_MONTHLY=pri_...
PADDLE_PRICE_AGENCY_ANNUAL=pri_...
PADDLE_PRICE_TOPUP_50=pri_...
PADDLE_PRICE_TOPUP_150=pri_...
PADDLE_PRICE_TOPUP_400=pri_...
PADDLE_PRICE_TOPUP_1000=pri_...
PADDLE_WEBHOOK_SECRET=pdl_ntfset_...
PADDLE_API_KEY=...
PADDLE_ENVIRONMENT=sandbox  # or production
```

### 5.3 Frontend: Paddle.js Checkout

```tsx
// app/billing/page.tsx — Pricing page with Paddle.js overlay checkout

'use client'
import { useEffect } from 'react'
import { useSession } from 'next-auth/react'

declare global {
  interface Window {
    Paddle: {
      Setup: (options: { token: string; eventCallback?: (event: PaddleEvent) => void }) => void
      Checkout: {
        open: (options: CheckoutOptions) => void
      }
    }
  }
}

export function PricingCard({ tier, priceId, price, isAnnual }: PricingCardProps) {
  const { data: session } = useSession()

  useEffect(() => {
    // Load Paddle.js once (idempotent)
    if (typeof window !== 'undefined' && !window.Paddle) {
      const script = document.createElement('script')
      script.src = 'https://cdn.paddle.com/paddle/v2/paddle.js'
      script.onload = () => {
        window.Paddle.Setup({
          token: process.env.NEXT_PUBLIC_PADDLE_CLIENT_TOKEN!,
          eventCallback: (event) => {
            if (event.name === 'checkout.completed') {
              // Redirect to dashboard — webhook will have already updated the DB
              window.location.href = '/dashboard?upgraded=true'
            }
          },
        })
      }
      document.head.appendChild(script)
    }
  }, [])

  const handleSubscribe = () => {
    window.Paddle.Checkout.open({
      items: [{ priceId, quantity: 1 }],
      customer: {
        email: session?.user?.email ?? undefined,
      },
      customData: {
        user_id: session?.user?.id,   // passed to webhook for DB update
        tier,
        billing_period: isAnnual ? 'annual' : 'monthly',
      },
      settings: {
        displayMode: 'overlay',
        theme: 'light',
        locale: 'en',
      },
    })
  }

  return (
    <div className="pricing-card">
      {/* ... card UI ... */}
      <button onClick={handleSubscribe} className="btn-primary">
        Start 14-day free trial
      </button>
    </div>
  )
}
```

### 5.4 Credit Top-Up Checkout

```tsx
// components/billing/TopUpModal.tsx

export function TopUpModal({ onClose }: { onClose: () => void }) {
  const packages = [
    { credits: 50,   priceId: process.env.NEXT_PUBLIC_PADDLE_TOPUP_50,   price: '$4.99' },
    { credits: 150,  priceId: process.env.NEXT_PUBLIC_PADDLE_TOPUP_150,  price: '$12.99' },
    { credits: 400,  priceId: process.env.NEXT_PUBLIC_PADDLE_TOPUP_400,  price: '$29.99' },
    { credits: 1000, priceId: process.env.NEXT_PUBLIC_PADDLE_TOPUP_1000, price: '$59.99' },
  ]

  const handleTopUp = (priceId: string, credits: number) => {
    window.Paddle.Checkout.open({
      items: [{ priceId, quantity: 1 }],
      customData: {
        user_id: useSession().data?.user?.id,
        transaction_type: 'credit_topup',
        credits,
      },
      settings: { displayMode: 'overlay' },
    })
  }

  return (
    <Modal>
      {packages.map((pkg) => (
        <TopUpCard
          key={pkg.credits}
          credits={pkg.credits}
          price={pkg.price}
          onSelect={() => handleTopUp(pkg.priceId!, pkg.credits)}
        />
      ))}
    </Modal>
  )
}
```

### 5.5 Webhook Handler

```python
# app/api/routes/webhooks.py
from fastapi import APIRouter, Request, HTTPException, Header
from app.services.paddle_service import PaddleWebhookService
import hmac
import hashlib
import json
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Paddle sends all subscription lifecycle events to this endpoint
HANDLED_EVENTS = {
    "subscription.created",
    "subscription.updated",
    "subscription.cancelled",
    "subscription.paused",
    "subscription.resumed",
    "transaction.completed",      # covers both subscription payments and one-time top-ups
    "transaction.payment_failed",
}


@router.post("/webhooks/paddle")
async def paddle_webhook(
    request: Request,
    paddle_signature: str = Header(None, alias="Paddle-Signature"),
):
    body = await request.body()

    # Verify webhook signature (HMAC-SHA256)
    if not _verify_paddle_signature(body, paddle_signature):
        logger.warning("Paddle webhook signature verification failed")
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = json.loads(body)
    event_type = payload.get("event_type")
    event_id = payload.get("notification_id")

    if event_type not in HANDLED_EVENTS:
        return {"status": "ignored", "event_type": event_type}

    # Idempotency: skip if already processed
    service = PaddleWebhookService()
    if service.is_processed(event_id):
        logger.info(f"Paddle event {event_id} already processed, skipping")
        return {"status": "already_processed"}

    try:
        await service.handle(event_type, payload["data"])
        service.mark_processed(event_id)
        return {"status": "ok"}
    except Exception as exc:
        logger.error(f"Paddle webhook handler failed for {event_type}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Webhook processing failed")


def _verify_paddle_signature(body: bytes, signature_header: str | None) -> bool:
    if not signature_header:
        return False

    # Paddle sends: ts=timestamp;h1=hash
    parts = dict(kv.split("=", 1) for kv in signature_header.split(";"))
    ts = parts.get("ts", "")
    received_hash = parts.get("h1", "")

    secret = settings.PADDLE_WEBHOOK_SECRET.encode()
    signed_payload = f"{ts}:{body.decode()}"
    expected_hash = hmac.new(secret, signed_payload.encode(), hashlib.sha256).hexdigest()

    return hmac.compare_digest(expected_hash, received_hash)
```

### 5.6 Webhook Service: Event Handlers

```python
# app/services/paddle_service.py
from app.db.session import get_db_session
from app.services.credit_service import CreditService
from app.services.email_service import EmailService
import redis

TIER_FROM_PRICE_ID = {
    settings.PADDLE_PRICE_STARTER_MONTHLY:  "starter",
    settings.PADDLE_PRICE_STARTER_ANNUAL:   "starter",
    settings.PADDLE_PRICE_GROWTH_MONTHLY:   "growth",
    settings.PADDLE_PRICE_GROWTH_ANNUAL:    "growth",
    settings.PADDLE_PRICE_PRO_MONTHLY:      "pro",
    settings.PADDLE_PRICE_PRO_ANNUAL:       "pro",
    settings.PADDLE_PRICE_AGENCY_MONTHLY:   "agency",
    settings.PADDLE_PRICE_AGENCY_ANNUAL:    "agency",
}

CREDITS_FROM_TOPUP_PRICE_ID = {
    settings.PADDLE_PRICE_TOPUP_50:   50,
    settings.PADDLE_PRICE_TOPUP_150:  150,
    settings.PADDLE_PRICE_TOPUP_400:  400,
    settings.PADDLE_PRICE_TOPUP_1000: 1000,
}


class PaddleWebhookService:
    def __init__(self):
        self.r = redis.from_url(settings.REDIS_URL)
        self.credits = CreditService(self.r)
        self.email = EmailService()

    async def handle(self, event_type: str, data: dict):
        handlers = {
            "subscription.created":       self._on_subscription_created,
            "subscription.updated":       self._on_subscription_updated,
            "subscription.cancelled":     self._on_subscription_cancelled,
            "subscription.paused":        self._on_subscription_paused,
            "subscription.resumed":       self._on_subscription_resumed,
            "transaction.completed":      self._on_transaction_completed,
            "transaction.payment_failed": self._on_payment_failed,
        }
        handler = handlers.get(event_type)
        if handler:
            await handler(data)

    async def _on_subscription_created(self, data: dict):
        user_id = data["custom_data"]["user_id"]
        price_id = data["items"][0]["price"]["id"]
        tier = TIER_FROM_PRICE_ID.get(price_id, "starter")

        with get_db_session() as db:
            db.execute("""
                UPDATE users SET
                    subscription_status = 'active',
                    subscription_tier = :tier,
                    paddle_subscription_id = :sub_id,
                    paddle_customer_id = :customer_id,
                    trial_ends_at = NULL,
                    subscription_started_at = NOW(),
                    subscription_current_period_end = :period_end
                WHERE id = :user_id
            """, {
                "tier": tier,
                "sub_id": data["id"],
                "customer_id": data["customer_id"],
                "period_end": data["next_billed_at"],
                "user_id": user_id,
            })

        # Allocate first month's credits
        self.credits.allocate_subscription_credits(user_id, tier)

        # Welcome email
        await self.email.send_subscription_welcome(user_id, tier)

    async def _on_subscription_updated(self, data: dict):
        """Handles upgrades, downgrades, and billing cycle changes."""
        user_id = data["custom_data"].get("user_id")
        if not user_id:
            # Lookup by paddle_subscription_id
            user_id = self._get_user_by_subscription(data["id"])

        price_id = data["items"][0]["price"]["id"]
        new_tier = TIER_FROM_PRICE_ID.get(price_id)
        if not new_tier:
            return

        with get_db_session() as db:
            old_tier = db.execute(
                "SELECT subscription_tier FROM users WHERE id = :uid",
                {"uid": user_id}
            ).scalar()

            db.execute("""
                UPDATE users SET
                    subscription_tier = :tier,
                    subscription_current_period_end = :period_end
                WHERE id = :user_id
            """, {"tier": new_tier, "period_end": data["next_billed_at"], "user_id": user_id})

        # On upgrade: immediately top-up difference in credits
        if new_tier != old_tier:
            MONTHLY_CREDITS = {"starter": 100, "growth": 300, "pro": 750, "agency": 2500}
            old_alloc = MONTHLY_CREDITS.get(old_tier, 0)
            new_alloc = MONTHLY_CREDITS.get(new_tier, 0)
            diff = new_alloc - old_alloc
            if diff > 0:
                with get_db_session() as db:
                    db.execute(
                        "UPDATE users SET credits_balance = credits_balance + :diff WHERE id = :uid",
                        {"diff": diff, "uid": user_id}
                    )
            self.r.delete(f"credits:balance:{user_id}")

    async def _on_subscription_cancelled(self, data: dict):
        """
        Cancellation takes effect at period end (Paddle default).
        Set status to 'cancelling' now; 'cancelled' when period ends.
        """
        user_id = self._get_user_by_subscription(data["id"])

        with get_db_session() as db:
            db.execute("""
                UPDATE users SET
                    subscription_status = 'cancelling',
                    subscription_cancelled_at = NOW()
                WHERE id = :uid
            """, {"uid": user_id})

        await self.email.send_cancellation_confirmed(user_id, data.get("scheduled_change", {}).get("effective_at"))

    async def _on_transaction_completed(self, data: dict):
        """
        Handles both:
        1. Subscription renewal payments → allocate monthly credits
        2. One-time credit top-up purchases → add credits immediately
        """
        custom_data = data.get("custom_data", {})
        user_id = custom_data.get("user_id")
        transaction_type = custom_data.get("transaction_type")

        if transaction_type == "credit_topup":
            # One-time purchase: add credits immediately
            price_id = data["items"][0]["price"]["id"]
            credits_to_add = CREDITS_FROM_TOPUP_PRICE_ID.get(price_id, 0)

            if credits_to_add and user_id:
                with get_db_session() as db:
                    new_balance = db.execute("""
                        UPDATE users SET credits_balance = credits_balance + :credits
                        WHERE id = :uid RETURNING credits_balance
                    """, {"credits": credits_to_add, "uid": user_id}).scalar()

                    db.execute("""
                        INSERT INTO credit_transactions
                            (user_id, amount, transaction_type, reference_id, balance_after)
                        VALUES (:uid, :amount, 'topup_purchase', :paddle_txn, :balance)
                    """, {
                        "uid": user_id,
                        "amount": credits_to_add,
                        "paddle_txn": data["id"],
                        "balance": new_balance,
                    })

                self.r.delete(f"credits:balance:{user_id}")

        else:
            # Subscription renewal: allocate monthly credits (reset + rollover)
            sub_id = data.get("subscription_id")
            if sub_id:
                user_id = user_id or self._get_user_by_subscription(sub_id)
                tier = self._get_user_tier(user_id)
                self.credits.allocate_subscription_credits(user_id, tier)

                with get_db_session() as db:
                    db.execute("""
                        UPDATE users SET
                            subscription_current_period_end = :period_end
                        WHERE id = :uid
                    """, {"period_end": data.get("billing_period", {}).get("ends_at"), "uid": user_id})

    async def _on_payment_failed(self, data: dict):
        """
        Paddle handles 3 retry attempts automatically.
        We set subscription_status = 'past_due' and reduce feature access.
        After 3 failures (subscription.cancelled event), we fully restrict.
        """
        sub_id = data.get("subscription_id")
        user_id = self._get_user_by_subscription(sub_id)

        with get_db_session() as db:
            db.execute(
                "UPDATE users SET subscription_status = 'past_due' WHERE id = :uid",
                {"uid": user_id}
            )

        await self.email.send_payment_failed(user_id, data.get("billing_period", {}).get("ends_at"))

    def is_processed(self, event_id: str) -> bool:
        return bool(self.r.get(f"paddle:processed:{event_id}"))

    def mark_processed(self, event_id: str):
        self.r.setex(f"paddle:processed:{event_id}", 7 * 24 * 3600, "1")  # 7 day TTL

    def _get_user_by_subscription(self, paddle_sub_id: str) -> str:
        with get_db_session() as db:
            return str(db.execute(
                "SELECT id FROM users WHERE paddle_subscription_id = :sub_id",
                {"sub_id": paddle_sub_id}
            ).scalar())

    def _get_user_tier(self, user_id: str) -> str:
        with get_db_session() as db:
            return db.execute(
                "SELECT subscription_tier FROM users WHERE id = :uid",
                {"uid": user_id}
            ).scalar() or "starter"
```

### 5.7 Subscription Grace Period and Feature Gating

```python
# app/middleware/subscription_guard.py
from fastapi import Request, HTTPException
from datetime import datetime, timezone

GRACE_PERIOD_DAYS = 3  # Allow access 3 days after payment failure before hard block


def check_subscription_access(user, required_tier: str | None = None):
    """
    Gate all premium feature routes with this check.
    Called from FastAPI dependencies.
    """
    status = user.subscription_status

    if status == "active":
        pass  # always allow

    elif status == "trial":
        if user.trial_ends_at and user.trial_ends_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=402,
                detail={"code": "TRIAL_EXPIRED", "message": "Your trial has ended. Please subscribe to continue."}
            )

    elif status == "cancelling":
        # Still active until period end
        if user.subscription_current_period_end < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=402,
                detail={"code": "SUBSCRIPTION_ENDED", "message": "Your subscription has ended."}
            )

    elif status == "past_due":
        # Grace period check
        days_past_due = (datetime.now(timezone.utc) - user.subscription_current_period_end).days
        if days_past_due > GRACE_PERIOD_DAYS:
            raise HTTPException(
                status_code=402,
                detail={"code": "PAYMENT_FAILED", "message": "Please update your payment method to continue."}
            )

    elif status == "cancelled":
        raise HTTPException(
            status_code=402,
            detail={"code": "SUBSCRIPTION_CANCELLED", "message": "Please resubscribe to access this feature."}
        )

    # Tier check (after status check)
    if required_tier:
        tier_rank = {"trial": 0, "starter": 1, "growth": 2, "pro": 3, "agency": 4}
        user_rank = tier_rank.get(user.subscription_tier, 0)
        required_rank = tier_rank.get(required_tier, 0)

        if user_rank < required_rank:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "UPGRADE_REQUIRED",
                    "required_tier": required_tier,
                    "message": f"This feature requires {required_tier.capitalize()} or higher.",
                    "upgrade_url": "/billing/upgrade",
                }
            )
```

### 5.8 DB Schema Additions (Paddle-specific)

```sql
-- Add to users table (supplement to backend-spec.md)
ALTER TABLE users ADD COLUMN IF NOT EXISTS
    paddle_customer_id VARCHAR(100) UNIQUE,
    paddle_subscription_id VARCHAR(100) UNIQUE,
    subscription_status VARCHAR(20) NOT NULL DEFAULT 'trial'
        CHECK (subscription_status IN ('trial', 'active', 'past_due', 'cancelling', 'cancelled', 'paused')),
    subscription_tier VARCHAR(20) NOT NULL DEFAULT 'trial'
        CHECK (subscription_tier IN ('trial', 'starter', 'growth', 'pro', 'agency')),
    trial_ends_at TIMESTAMPTZ,
    subscription_started_at TIMESTAMPTZ,
    subscription_cancelled_at TIMESTAMPTZ,
    subscription_current_period_end TIMESTAMPTZ,
    billing_interval VARCHAR(10) DEFAULT 'monthly'
        CHECK (billing_interval IN ('monthly', 'annual'));

-- Paddle event log (idempotency + debugging)
CREATE TABLE paddle_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paddle_event_id VARCHAR(100) NOT NULL UNIQUE,
    event_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id UUID REFERENCES users(id),
    error_message TEXT
);

CREATE INDEX idx_paddle_events_user ON paddle_events(user_id);
CREATE INDEX idx_paddle_events_type ON paddle_events(event_type, processed_at DESC);

-- Replace the generic credit_transactions check with Paddle-aware types
-- (supplement to backend-spec.md credit_transactions table)
ALTER TABLE credit_transactions
    DROP CONSTRAINT IF EXISTS credit_transactions_transaction_type_check;

ALTER TABLE credit_transactions
    ADD CONSTRAINT credit_transactions_transaction_type_check
    CHECK (transaction_type IN (
        'subscription_renewal',   -- monthly allotment on billing cycle
        'topup_purchase',         -- one-time credit purchase via Paddle
        'agent_run_deduction',    -- AI usage deduction
        'manual_adjustment',      -- admin credit correction
        'trial_grant',            -- free credits on trial signup
        'referral_bonus'          -- affiliate/referral program bonus
    ));
```

### 5.9 Subscription Management UI Routes

```python
# app/api/routes/billing.py

@router.get("/billing/portal")
async def get_billing_portal_url(user = Depends(get_current_user)):
    """
    Returns Paddle Customer Portal URL.
    Paddle's portal handles: update payment method, cancel subscription,
    download invoices, view billing history.
    """
    import paddle
    portal = paddle.customers.create_auth_token(
        customer_id=user.paddle_customer_id
    )
    return {"portal_url": f"https://customer.paddle.com/login?token={portal.token}"}


@router.get("/billing/invoices")
async def list_invoices(user = Depends(get_current_user)):
    """Fetch invoices from Paddle API for display in dashboard."""
    import paddle
    transactions = paddle.transactions.list(
        customer_id=[user.paddle_customer_id],
        status=["completed"],
        per_page=20,
    )
    return {
        "invoices": [
            {
                "id": t.id,
                "date": t.billed_at,
                "amount": t.details.totals.total,
                "currency": t.currency_code,
                "invoice_url": t.invoice_pdf,
                "status": t.status,
            }
            for t in transactions.data
        ]
    }


@router.post("/billing/upgrade")
async def create_upgrade_checkout(
    request: UpgradeRequest,
    user = Depends(get_current_user),
):
    """
    Returns a Paddle checkout URL for plan upgrade.
    Paddle prorates the upgrade automatically.
    """
    price_map = {
        ("starter", "monthly"):  settings.PADDLE_PRICE_STARTER_MONTHLY,
        ("starter", "annual"):   settings.PADDLE_PRICE_STARTER_ANNUAL,
        ("growth",  "monthly"):  settings.PADDLE_PRICE_GROWTH_MONTHLY,
        ("growth",  "annual"):   settings.PADDLE_PRICE_GROWTH_ANNUAL,
        ("pro",     "monthly"):  settings.PADDLE_PRICE_PRO_MONTHLY,
        ("pro",     "annual"):   settings.PADDLE_PRICE_PRO_ANNUAL,
        ("agency",  "monthly"):  settings.PADDLE_PRICE_AGENCY_MONTHLY,
        ("agency",  "annual"):   settings.PADDLE_PRICE_AGENCY_ANNUAL,
    }
    price_id = price_map.get((request.tier, request.billing_interval))
    if not price_id:
        raise HTTPException(400, "Invalid tier or billing interval")

    return {
        "price_id": price_id,
        "customer_email": user.email,
        "user_id": str(user.id),
    }
```

---

## 6. Financial Controls & Risk

### 6.1 AI Cost Runaway Prevention

Three layers prevent unexpected AI cost spikes:

```python
# Layer 1: Per-run credit cap (enforced at task start)
if not credit_service.reserve(user_id, credits_needed, run_id):
    raise InsufficientCreditsError

# Layer 2: Daily credit cap per user (enforced in scheduler)
daily_used = _get_daily_credits_used(user_id)
if daily_used + credits_needed > DAILY_CREDIT_CAP[user.tier]:
    raise DailyLimitExceededError

# Layer 3: Account-level daily AI cost alert ($2 threshold)
# → sends Slack/email to founders if single account burns >$2/day
check_daily_cost_alert(user_id)
```

### 6.2 Churn Prevention Signals

Track these events and trigger automated interventions:

| Signal | Threshold | Action |
|---|---|---|
| Agent run not started | 3+ days since last run | In-app: "Your daily analysis is paused" + resume CTA |
| Optimization approval rate | <20% of suggestions approved | Email: "Customize your AI suggestions" tutorial |
| Login streak broken | 7+ days since last login | Email: "Store health check — here's what you missed" |
| Credits running low | <20% of monthly allotment | In-app banner + top-up prompt |
| Subscription 14 days from renewal | Always | Email: highlight value delivered (listings improved, estimated traffic gain) |
| Trial day 10 (4 days left) | Always | Email: "Your trial ends in 4 days — results so far: X" |
| Trial day 13 (1 day left) | No payment method | Email: urgency + one-click upgrade |

### 6.3 Revenue Recognition

Paddle is the Merchant of Record. Revenue recognition rules:
- **Monthly subscriptions:** Recognized ratably over the subscription month
- **Annual subscriptions:** Recognized ratably over 12 months (1/12 per month)
- **Credit top-ups:** Recognized when credits are consumed, not when purchased (deferred revenue)
- **Trial period:** Zero revenue during trial; recognized from first billing date

```python
# Deferred revenue tracking for credit top-ups
# credits_balance in users table represents a liability (unearned revenue)
# Revenue recognized when: credit_transactions.transaction_type = 'agent_run_deduction'
# Deferred liability: users.credits_balance × $0.10 per credit
```

### 6.4 Refund Policy (Paddle-backed)

- **Trial period:** No charge — no refund needed
- **First payment:** 7-day money-back guarantee (handled via Paddle refund API)
- **Subsequent months:** No refunds (standard SaaS)
- **Annual plans:** Pro-rated refund if cancelled within 30 days of annual renewal
- **Credit top-ups:** No refunds (non-refundable, per ToS)

Refund automation:
```python
# Handle refund request within 7 days of first subscription payment
@router.post("/billing/refund")
async def request_refund(user = Depends(get_current_user)):
    days_since_start = (datetime.utcnow() - user.subscription_started_at).days

    if days_since_start > 7:
        raise HTTPException(400, "Refund window has passed (7 days from first payment)")

    # Paddle refund via API
    import paddle
    transactions = paddle.transactions.list(
        subscription_id=[user.paddle_subscription_id],
        status=["completed"],
        per_page=1,
    )
    if transactions.data:
        paddle.transactions.refund(transactions.data[0].id, reason="customer_request")

    # Downgrade to cancelled in DB (webhook will also fire)
    with get_db_session() as db:
        db.execute(
            "UPDATE users SET subscription_status = 'cancelled' WHERE id = :uid",
            {"uid": str(user.id)}
        )
```

### 6.5 KPI Dashboard (Internal — `/admin`)

Track weekly:

| KPI | Alert Threshold | Source |
|---|---|---|
| New MRR | <$500/week | Paddle webhooks |
| Churn MRR | >5% of total MRR | Paddle + DB |
| Trial starts | <30/week in growth phase | DB |
| Trial conversion rate | <20% | DB |
| Daily agent run rate | <60% of active users | Celery logs |
| AI cost per user | >$5/month | agent_run_logs |
| Average optimization approval rate | <30% | listing_optimizations table |
| P99 agent run duration | >15 min | Celery task timing |
| Credit top-up revenue | Week-over-week | credit_transactions |
