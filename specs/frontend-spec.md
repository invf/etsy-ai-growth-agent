# Etsy AI Growth Agent — Frontend Specification

---

## Global Layout Shell

Every authenticated page shares this shell:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ HEADER                                                                        │
│ ┌──────────────┐  ┌───────────────────────────┐  ┌────────────────────────┐ │
│ │ ◈ EtsyAgent  │  │ 🏪 My Handmade Shop   ▾   │  │ 🔔 3  [Credits: 847]  │ │
│ │              │  │   (store selector)         │  │ ◎ V. Korobov       ▾  │ │
│ └──────────────┘  └───────────────────────────┘  └────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
│                    │
│  SIDEBAR           │  MAIN CONTENT AREA
│  ┌──────────────┐  │
│  │              │  │
│  │  ⊞ Overview  │  │
│  │  ◈ Audit     │  │
│  │  ⚔ Competitors│  │
│  │  ✦ SEO       │  │
│  │  ↗ Trends    │  │
│  │  ◎ Audience  │  │
│  │  ✎ Content   │  │
│  │  $ Pricing   │  │
│  │  ⚡ Optimizer │  │
│  │  ▦ Reports   │  │
│  │              │  │
│  │  ─────────── │  │
│  │  ⚙ Settings  │  │
│  │  ? Help      │  │
│  └──────────────┘  │
```

---

## Page 1: Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Overview                                    Last agent run: 2h ago  [▶ Run] │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │  STORE HEALTH SCORE                                                   │    │
│  │                                                                       │    │
│  │    ╭───────────────╮                                                  │    │
│  │    │               │   74 / 100   ████████████████░░░░░  Good        │    │
│  │    │      74       │                                                  │    │
│  │    │               │   ▲ +6 from last week                           │    │
│  │    ╰───────────────╯                                                  │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│                                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  VIEWS       │  │  FAVORITES   │  │  SALES       │  │  REVENUE     │    │
│  │              │  │              │  │              │  │              │    │
│  │   12,847     │  │    1,203     │  │     89       │  │  $2,340      │    │
│  │  ▲ +12% 30d  │  │  ▲ +8% 30d  │  │  ▼ -3% 30d  │  │  ▲ +5% 30d  │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
│                                                                                │
│  ┌─────────────────────────────────────┐  ┌─────────────────────────────┐   │
│  │  TOP RECOMMENDATIONS          [See all]│  │  AGENT ACTIVITY           │   │
│  │                                        │  │                           │   │
│  │  ● HIGH  "Summer Tote" title missing  │  │  Today 6:02am             │   │
│  │          3 high-vol keywords          │  │  ✓ Scanned 47 listings    │   │
│  │          [Fix with AI →]              │  │  ✓ 12 competitors found   │   │
│  │                                        │  │  ✓ 3 trend alerts         │   │
│  │  ● HIGH  Competitor "Crafty Corner"   │  │  ✓ 8 recommendations      │   │
│  │          undercuts you by $4 on       │  │                           │   │
│  │          your top 5 listings          │  │  Yesterday 6:01am         │   │
│  │          [View Analysis →]            │  │  ✓ Completed full scan    │   │
│  │                                        │  │  ✓ Weekly report ready    │   │
│  │  ● MED   "Lavender Candle" has only   │  │                           │   │
│  │          6 tags — 7 more available    │  │  [View Full History →]    │   │
│  │          [Add Tags →]                 │  └─────────────────────────────┘  │
│  │                                        │                                   │
│  │  ● MED   "Boho Earrings" main image   │  ┌─────────────────────────────┐  │
│  │          score: 48/100 — blurry bg    │  │  TRENDING NOW               │  │
│  │          [See Image Tips →]           │  │                             │  │
│  │                                        │  │  🔥 "cottagecore decor"   │  │
│  └─────────────────────────────────────┘  │     +340% this week         │  │
│                                            │                             │  │
│  ┌─────────────────────────────────────┐  │  📈 "personalized gifts"   │  │
│  │  LISTING HEALTH OVERVIEW            │  │     peak in 12 days         │  │
│  │                                     │  │                             │  │
│  │  47 active listings                 │  │  🌙 "mushroom lamp"        │  │
│  │                                     │  │     emerging, +180%         │  │
│  │  ████████████████░░░░  SEO  68%     │  │                             │  │
│  │  ██████████████████░░  IMG  80%     │  │  [View All Trends →]       │  │
│  │  ██████████████░░░░░░  PRC  72%     │  └─────────────────────────────┘  │
│  │                                     │                                    │
│  │  Needs attention:  12 listings      │                                    │
│  │  [View Listings →]                  │                                    │
│  └─────────────────────────────────────┘                                    │
│                                                                                │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Page 2: Store Audit

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Store Audit                        [▶ Re-run Audit]  Last run: Jun 10, 6am  │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │  STORE HEALTH SCORE BREAKDOWN                                         │    │
│  │                                                                       │    │
│  │  Overall: 74/100  ████████████████░░░░░  GOOD                        │    │
│  │                                                                       │    │
│  │  ┌────────────────────┬────────┬─────────────────────────────┐       │    │
│  │  │ Category           │ Score  │ Progress                    │       │    │
│  │  ├────────────────────┼────────┼─────────────────────────────┤       │    │
│  │  │ SEO Health         │ 68/100 │ ██████████████░░░░░░  FAIR  │       │    │
│  │  │ Image Quality      │ 80/100 │ ████████████████░░░░  GOOD  │       │    │
│  │  │ Pricing Strategy   │ 72/100 │ ██████████████░░░░░░  FAIR  │       │    │
│  │  │ Listing Completeness│ 85/100│ █████████████████░░░  GOOD  │       │    │
│  │  │ Review Health      │ 61/100 │ ████████████░░░░░░░░  FAIR  │       │    │
│  │  │ Conversion Signals │ 76/100 │ ███████████████░░░░░  GOOD  │       │    │
│  │  └────────────────────┴────────┴─────────────────────────────┘       │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│                                                                                │
│  ISSUES BY SEVERITY                              [Filter: All ▾] [Sort ▾]    │
│                                                                                │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │  🔴 CRITICAL  (2 issues)                                    [Fix All] │    │
│  │  ─────────────────────────────────────────────────────────────────── │    │
│  │  ▸ "Macrame Wall Hanging" — No main image alt description             │    │
│  │    Impact: -15% click-through   [Fix →]                               │    │
│  │  ▸ "Linen Tote Bag" — Price 40% above market average                  │    │
│  │    Impact: -22% conversion      [Fix →]                               │    │
│  │                                                                       │    │
│  │  🟡 WARNING  (8 issues)                                     [Fix All] │    │
│  │  ─────────────────────────────────────────────────────────────────── │    │
│  │  ▸ 12 listings have fewer than 10 tags (max 13 allowed)               │    │
│  │    Affected listings: [view 12 →]   [Fix All with AI →]               │    │
│  │  ▸ 5 listings missing materials field                                  │    │
│  │    Affected listings: [view 5 →]    [Fix →]                           │    │
│  │  ▸ "Boho Earrings" — description under 100 words                      │    │
│  │    Impact: lower search ranking     [Fix →]                           │    │
│  │  ▸ 3 listings — blurry/low-contrast main image                        │    │
│  │    Impact: -18% clicks             [View →]                           │    │
│  │  [ Show 4 more ▾ ]                                                    │    │
│  │                                                                       │    │
│  │  🔵 INFO  (11 issues)                                                 │    │
│  │  [ Show 11 ▾ ]                                                        │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│                                                                                │
│  ALL LISTINGS HEALTH TABLE                    [Search listings...]  [Export]  │
│                                                                                │
│  ┌─────┬──────────────────────────┬────────┬───────┬───────┬────────────┐   │
│  │     │ Listing                  │ SEO    │ Image │ Price │ Action     │   │
│  ├─────┼──────────────────────────┼────────┼───────┼───────┼────────────┤   │
│  │ 🔴  │ Linen Tote Bag           │ 72     │ 88    │  45   │ [Fix →]    │   │
│  │ 🟡  │ Boho Drop Earrings       │ 58     │ 74    │  81   │ [Fix →]    │   │
│  │ 🟡  │ Macrame Wall Hanging     │ 65     │ 91    │  73   │ [Fix →]    │   │
│  │ 🟢  │ Lavender Soy Candle      │ 84     │ 87    │  82   │ [View →]   │   │
│  │ 🟢  │ Summer Straw Hat         │ 91     │ 90    │  78   │ [View →]   │   │
│  │ ··· │ ···                      │ ···    │ ···   │ ···   │ ···        │   │
│  └─────┴──────────────────────────┴────────┴───────┴───────┴────────────┘   │
│                                   Showing 5 of 47   [< 1 2 3 ... >]          │
│                                                                                │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Page 3: Competitor Intelligence

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Competitor Intelligence                                                       │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  Analyze listing:  [🔍 Search your listings...              ▾]                │
│  ▶  Boho Drop Earrings  ×                                                     │
│                                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  COMPETITORS │  │  MKT OPPORT. │  │  AVG COMP.   │  │  YOUR RANK   │    │
│  │    FOUND     │  │    SCORE     │  │    PRICE     │  │              │    │
│  │      10      │  │    71/100    │  │    $18.40    │  │   #4 of 25   │    │
│  │              │  │  ▲ GOOD OPP. │  │  You: $22    │  │  for "boho"  │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
│                                                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  COMPETITOR LIST                          Analyzed: Jun 10  [↻ Refresh] │ │
│  │                                                                         │ │
│  │  ┌────┬──────────────────────────────┬────────┬───────┬──────┬───────┐ │ │
│  │  │ #  │ Listing / Shop               │  Price │ Sales │ ★    │ Score │ │ │
│  │  ├────┼──────────────────────────────┼────────┼───────┼──────┼───────┤ │ │
│  │  │ 1  │ "Dainty Boho Earrings"       │ $16.00 │ ~340  │ 4.9  │  92   │ │ │
│  │  │    │ BohoByBella                  │        │       │(287) │       │ │ │
│  │  │    │ Tags: boho, dangle, gold     │        │       │      │       │ │ │
│  │  ├────┼──────────────────────────────┼────────┼───────┼──────┼───────┤ │ │
│  │  │ 2  │ "Gold Boho Hoop Earrings"    │ $14.50 │ ~210  │ 4.8  │  88   │ │ │
│  │  │    │ WildRoseCrafts              │        │       │(156) │       │ │ │
│  │  ├────┼──────────────────────────────┼────────┼───────┼──────┼───────┤ │ │
│  │  │ 3  │ "Handmade Boho Drops"        │ $19.00 │ ~180  │ 4.7  │  81   │ │ │
│  │  │    │ EarthAndVine                │        │       │(122) │       │ │ │
│  │  ├────┼──────────────────────────────┼────────┼───────┼──────┼───────┤ │ │
│  │  │ YOU│ Boho Drop Earrings           │ $22.00 │  ~89  │ 4.6  │  68   │ │ │
│  │  │    │ (your listing)               │        │       │ (61) │       │ │ │
│  │  └────┴──────────────────────────────┴────────┴───────┴──────┴───────┘ │ │
│  │  [Show all 10 competitors ▾]                                            │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                                │
│  ┌─────────────────────────────────┐  ┌─────────────────────────────────┐   │
│  │  GAP ANALYSIS                   │  │  KEYWORD GAPS                   │   │
│  │                                 │  │                                 │   │
│  │  Tags your competitors use      │  │  Keywords in top competitors    │   │
│  │  that you DON'T:                │  │  NOT in your listing:           │   │
│  │                                 │  │                                 │   │
│  │  [minimalist]  [dangle]         │  │  • "boho jewelry" — vol: HIGH   │   │
│  │  [gold filled] [hypoallergenic] │  │  • "gold earrings gift"         │   │
│  │  [gift for her][lightweight]    │  │    vol: MED, competition: LOW   │   │
│  │  [bohemian]    [handcrafted]    │  │  • "dangle drop earrings"       │   │
│  │                                 │  │    vol: HIGH, competition: MED  │   │
│  │  [+ Add All Missing Tags →]     │  │  • "nickel free earrings"       │   │
│  │                                 │  │    vol: MED, competition: LOW   │   │
│  │  Opportunity score: 71/100      │  │                                 │   │
│  │  Niche: UNDERSERVED             │  │  [Add to SEO Optimizer →]       │   │
│  └─────────────────────────────────┘  └─────────────────────────────────┘   │
│                                                                                │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Page 4: SEO Optimizer

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  SEO Optimizer                                                                 │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  Select listing:  [🔍 Boho Drop Earrings                    ×]                │
│                                    [< Prev listing]  [Next listing >]         │
│                                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  SEO SCORE   │  │ TITLE SCORE  │  │  TAGS SCORE  │  │  RANK PROB.  │    │
│  │   58 / 100   │  │   62 / 100   │  │   51 / 100   │  │    34%       │    │
│  │  FAIR        │  │              │  │  6/13 tags   │  │  page 1      │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
│                                                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  TITLE                                                                  │ │
│  │                                                                         │ │
│  │  Current:                                                               │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐   │ │
│  │  │ Boho Drop Earrings, Handmade, Dangle Earrings                   │   │ │
│  │  └─────────────────────────────────────────────────────────────────┘   │ │
│  │  53 chars  ⚠ Missing high-vol keywords at start                        │ │
│  │                                                                         │ │
│  │  AI Recommended:                                              [✎ Edit]  │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐   │ │
│  │  │ Gold Boho Drop Earrings for Women, Minimalist Dangle Earrings,  │   │ │
│  │  │ Hypoallergenic Gift for Her, Handmade Bohemian Jewelry          │   │ │
│  │  └─────────────────────────────────────────────────────────────────┘   │ │
│  │  136 chars  ✓ Keywords front-loaded  ✓ Gift angle  ✓ Material mention  │ │
│  │                                                                         │ │
│  │  Expected score lift: 58 → 81     [Apply Title →]                      │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  TAGS  (6 / 13 used)                                                    │ │
│  │                                                                         │ │
│  │  Current tags:                                                          │ │
│  │  [boho earrings ×] [handmade ×] [dangle ×] [jewelry ×]                │ │
│  │  [earrings ×] [gift ×]                                                 │ │
│  │  + 7 slots remaining                                                   │ │
│  │                                                                         │ │
│  │  Recommended additions:                                                 │ │
│  │  [+ gold filled] [+ minimalist] [+ hypoallergenic]                     │ │
│  │  [+ gift for her] [+ bohemian] [+ drop earrings]                       │ │
│  │  [+ nickel free]                                                        │ │
│  │                                                                         │ │
│  │  [+ Add All 7 Recommended Tags]      [Customize Tags →]                │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  DESCRIPTION HEALTH                                                     │ │
│  │                                                                         │ │
│  │  ✓ 287 words (good length)                                              │ │
│  │  ⚠ Missing: "nickel free", "hypoallergenic", "gift wrapping"            │ │
│  │  ⚠ No size/dimensions mentioned                                         │ │
│  │  ⚠ No shipping time mentioned (affects conversion)                      │ │
│  │                                                                         │ │
│  │  [Rewrite Description with AI →]                                        │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                                │
│  ┌──────────────────────────────────────────────────────┐                    │
│  │  APPLY ALL SEO CHANGES                               │                    │
│  │                                                      │                    │
│  │  Changes queued:  Title ✓  Tags ✓  Description ✓     │                    │
│  │  Expected score:  58  →  84                          │                    │
│  │                                                      │                    │
│  │  [Review & Apply All Changes →]                      │                    │
│  └──────────────────────────────────────────────────────┘                    │
│                                                                                │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Page 5: Trend Discovery

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Trend Discovery                                    [↻ Refresh]  Jun 10, 2026 │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  [All Sources ▾]  [All Categories ▾]  [🔍 Search trends...]                  │
│                                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  EMERGING    │  │ PEAKING SOON │  │  SEASONAL    │  │ VIRAL NOW    │    │
│  │     12       │  │      5       │  │     8        │  │      3       │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
│                                                                                │
│  🔥 TRENDING KEYWORDS                                                         │
│                                                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  cottagecore decor                                              [+ Track] │ │
│  │  ▲ +340% this week   Score: 94/100   Sources: Pinterest TikTok Reddit    │ │
│  │                                                                           │ │
│  │  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░   Peak predicted: Jun 24      │ │
│  │  Jan  Feb  Mar  Apr  May  Jun  Jul  Aug                                  │ │
│  │                                                                           │ │
│  │  Related: [fairy cottage] [mushroom decor] [moss art] [woodland]         │ │
│  │  Your match: "Macrame Wall Hanging" — relevance 72%  [Optimize for this] │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  personalized jewelry gift                                      [+ Track] │ │
│  │  ▲ +180% this week   Score: 88/100   Sources: Google Etsy Pinterest      │ │
│  │                                                                           │ │
│  │  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░   Peak predicted: Jun 18         │ │
│  │                                                                           │ │
│  │  Related: [custom name] [initial jewelry] [birth month] [monogram]       │ │
│  │  Your match: "Boho Drop Earrings" — relevance 55%  [Optimize for this]  │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  mushroom lamp                                                  [+ Track] │ │
│  │  ▲ +220% this week   Score: 91/100   Sources: TikTok Instagram Reddit    │ │
│  │  🆕 EMERGING — early mover advantage                                     │ │
│  │                                                                           │ │
│  │  Related: [cottagecore lamp] [night light] [LED mushroom] [cozy decor]   │ │
│  │  Your match: None — [Create New Listing for This Trend →]                │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                                │
│  📅 SEASONAL CALENDAR                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  Jun ──────────── Jul ──────────── Aug ──────────── Sep ──────────────  │ │
│  │  🎄 Early xmas    🏖 Beach crafts  📚 Back to school 🍂 Fall decor      │ │
│  │  prep begins      peaking          starting          emerging            │ │
│  │  [View →]         [View →]         [View →]          [View →]           │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                                │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Page 6: Audience Insights

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Audience Insights                                    [↻ Re-analyze Audience] │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  CUSTOMER PERSONAS                                                             │
│                                                                                │
│  ┌───────────────────────────┐  ┌───────────────────────────┐               │
│  │  ◎ Persona 1              │  │  ◎ Persona 2              │               │
│  │  "The Aesthetic Decorator"│  │  "The Gift Giver"         │               │
│  │                           │  │                           │               │
│  │  Age: 24–35  Female       │  │  Age: 28–45  Female       │               │
│  │  Location: US/UK/AU       │  │  Location: US             │               │
│  │                           │  │                           │               │
│  │  Interests:               │  │  Interests:               │               │
│  │  • Interior design        │  │  • Thoughtful gifting     │               │
│  │  • Sustainable living     │  │  • Supporting small biz   │               │
│  │  • DIY crafts             │  │  • Unique finds           │               │
│  │  • Cottagecore aesthetic  │  │  • Personalization        │               │
│  │                           │  │                           │               │
│  │  Buys when:               │  │  Buys when:               │               │
│  │  • Redecorating           │  │  • Birthdays/holidays     │               │
│  │  • Found via Pinterest     │  │  • Found via Instagram    │               │
│  │  • Seasonal (Spring/Fall) │  │  • Seasonal (Nov/Dec)     │               │
│  │                           │  │                           │               │
│  │  Pain points:             │  │  Pain points:             │               │
│  │  • Mass-produced items    │  │  • Generic gifts          │               │
│  │  • Low quality photos     │  │  • Long shipping times    │               │
│  │  • No sustainability info │  │  • No gift wrapping option│               │
│  │                           │  │                           │               │
│  │  [View Content Ideas →]   │  │  [View Content Ideas →]   │               │
│  └───────────────────────────┘  └───────────────────────────┘               │
│                                                                                │
│  WHERE YOUR AUDIENCE HANGS OUT                                                 │
│                                                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  Platform     │ Community                    │ Size    │ Relevance      │ │
│  ├───────────────┼──────────────────────────────┼─────────┼────────────────┤ │
│  │  📌 Pinterest  │ "Cottagecore Home Decor"     │ 2.1M    │ ████████ 92%  │ │
│  │  📌 Pinterest  │ "Bohemian Jewelry"           │ 840K    │ ███████  87%  │ │
│  │  🟠 Reddit     │ r/cottagecore                │ 380K    │ ██████   78%  │ │
│  │  🟠 Reddit     │ r/handmade                   │ 210K    │ ██████   74%  │ │
│  │  🎵 TikTok     │ #bohojewelry                 │ 45M views│ █████   68%  │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                                │
│  CONTENT IDEAS FOR YOUR AUDIENCE                                               │
│                                                                                │
│  ┌──────────────────────────────┐  ┌──────────────────────────────┐         │
│  │  For Persona 1               │  │  For Persona 2               │         │
│  │  • "How I style boho jewelry │  │  • "Perfect gifts for her    │         │
│  │    for everyday looks"       │  │    under $25"                │         │
│  │  • "My sustainable jewelry   │  │  • "Unboxing our gift wrap   │         │
│  │    buying guide"             │  │    experience"               │         │
│  │  • Before/after styling tips │  │  • "Behind the scenes: how   │         │
│  │                              │  │    I handcraft each piece"   │         │
│  │  [Generate Content →]        │  │  [Generate Content →]        │         │
│  └──────────────────────────────┘  └──────────────────────────────┘         │
│                                                                                │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Page 7: Content Generator

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Content Generator                                                             │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  ┌───────────────────────────────┐  ┌────────────────────────────────────┐  │
│  │  GENERATE NEW CONTENT         │  │  RECENT CONTENT                    │  │
│  │                               │  │  [Filter: All types ▾]             │  │
│  │  Content type:                │  │                                    │  │
│  │  ┌───────────────────────┐    │  │  ┌──────────────────────────────┐  │  │
│  │  │ Etsy Title          ▾ │    │  │  │ Etsy Title                   │  │  │
│  │  └───────────────────────┘    │  │  │ "Gold Boho Drop Earrings for │  │  │
│  │                               │  │  │ Women, Minimalist Dangle..." │  │  │
│  │  For listing:                 │  │  │ Jun 10 · ★★★★★  [Apply ✓]   │  │  │
│  │  ┌───────────────────────┐    │  │  └──────────────────────────────┘  │  │
│  │  │ Boho Drop Earrings  ▾ │    │  │                                    │  │
│  │  └───────────────────────┘    │  │  ┌──────────────────────────────┐  │  │
│  │  (or leave blank for store)   │  │  │ Instagram Caption             │  │  │
│  │                               │  │  │ "These aren't just earrings—  │  │  │
│  │  Tone:                        │  │  │ they're a whole vibe ✨..."   │  │  │
│  │  ○ Professional  ● Casual     │  │  │ Jun 9 · ★★★★☆  [Copy]       │  │  │
│  │  ○ Playful       ○ Luxurious  │  │  └──────────────────────────────┘  │  │
│  │                               │  │                                    │  │
│  │  Keywords to include:         │  │  ┌──────────────────────────────┐  │  │
│  │  ┌───────────────────────┐    │  │  │ Pinterest Pin                │  │  │
│  │  │ boho, gift, minimalist│    │  │  │ "Shop the look: Boho gold    │  │  │
│  │  └───────────────────────┘    │  │  │ drops that go with anything" │  │  │
│  │                               │  │  │ Jun 9 · [Copy] [Delete]      │  │  │
│  │  Target audience:             │  │  └──────────────────────────────┘  │  │
│  │  ┌───────────────────────┐    │  │                                    │  │
│  │  │ Women 25-35, Pinterest│    │  │  [Load more ▾]                     │  │
│  │  └───────────────────────┘    │  └────────────────────────────────────┘  │
│  │                               │                                           │
│  │  [✨ Generate Content]        │                                           │
│  │  Uses ~15 AI credits          │                                           │
│  └───────────────────────────────┘                                           │
│                                                                                │
│  CONTENT TYPES                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │  [Etsy Title] [Etsy Desc] [Etsy Tags] [Pinterest] [Instagram]        │    │
│  │  [TikTok Script] [Facebook Post] [Blog Post] [Email Campaign]        │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│                                                                                │
│  ── GENERATED RESULT (last generation) ──────────────────────────────────── │
│                                                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  Etsy Title  for "Boho Drop Earrings"                    [Regenerate ↻] │ │
│  │                                                                         │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐   │ │
│  │  │ Gold Boho Drop Earrings for Women, Minimalist Dangle Earrings,  │   │ │
│  │  │ Hypoallergenic Gift for Her, Handmade Bohemian Jewelry          │   │ │
│  │  └─────────────────────────────────────────────────────────────────┘   │ │
│  │  136 chars  ✓ SEO optimized  ✓ Gift angle  ✓ Audience matched          │ │
│  │                                                                         │ │
│  │  Rate this:  [★ ★ ★ ★ ☆]                                               │ │
│  │  [📋 Copy]  [✓ Apply to Listing]  [✎ Edit then Apply]                  │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                                │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Page 8: Pricing Intelligence

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Pricing Intelligence                                                          │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  Select listing:  [🔍 Linen Tote Bag                        ×]                │
│                                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  YOUR PRICE  │  │  MARKET AVG  │  │  RECOMMEND.  │  │  DEMAND      │    │
│  │   $38.00     │  │   $27.40     │  │   $29.99     │  │   HIGH       │    │
│  │  ABOVE MKT   │  │  Range:      │  │  -$8 from    │  │  seasonal    │    │
│  │  by $10.60   │  │  $18–$45     │  │  current     │  │  peak soon   │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
│                                                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  PRICE POSITION                                                         │ │
│  │                                                                         │ │
│  │  $18          $27.40        $29.99           $38           $45          │ │
│  │  ├─────────────┼─────────────┼────────────────┼─────────────┤          │ │
│  │  MIN       MKT AVG     RECOMMENDED         YOU           MAX           │ │
│  │                                                                         │ │
│  │  You are in the top 25% of pricing.                                    │ │
│  │  At $29.99 you'd be at market median — estimated +22% conversion lift  │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                                │
│  ┌─────────────────────────────────────────┐  ┌───────────────────────────┐ │
│  │  COMPETITOR PRICES                      │  │  AI RECOMMENDATIONS       │ │
│  │                                         │  │                           │ │
│  │  Shop              Price   Sales est.   │  │  ● Reduce price to $29.99 │ │
│  │  ─────────────────────────────────────  │  │    to hit market median   │ │
│  │  NaturalBagCo      $24.00  ~450         │  │    (+22% est. conversion) │ │
│  │  EarthTotesEtsy    $26.50  ~310         │  │                           │ │
│  │  LilyPadCrafts     $27.00  ~280         │  │  ● Run 15% off sale       │ │
│  │  HandmadeByMoss    $29.00  ~195         │  │    for Summer promotion   │ │
│  │  YOU               $38.00   ~89         │  │    ($32.30 effective)     │ │
│  │  PremiumLinenShop  $42.00   ~60         │  │                           │ │
│  │                                         │  │  ● Bundle with Lavender   │ │
│  │  [View all 10 ▾]                        │  │    Candle for $52         │ │
│  └─────────────────────────────────────────┘  │    ("Self-care kit")      │ │
│                                                │                           │ │
│  ┌─────────────────────────────────────────┐  │  [Apply Recommendation →] │ │
│  │  BUNDLE OPPORTUNITIES                   │  └───────────────────────────┘ │
│  │                                         │                                │
│  │  "Summer Self-Care Kit"                 │                                │
│  │  Linen Tote + Lavender Candle           │                                │
│  │  Individual total: $59  Bundle: $49     │                                │
│  │  Est. conversion lift: +35%             │                                │
│  │  [Create Bundle Listing →]              │                                │
│  └─────────────────────────────────────────┘                                │
│                                                                                │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Page 9: Listing Optimizer

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Listing Optimizer                                                             │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  [Pending (8)] [Approved (2)] [Applied (24)] [Rejected (3)]                   │
│                                                                                │
│  ── PENDING APPROVAL ────────────────────────────────────────────────────── │
│                                                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  TITLE CHANGE                                                 Jun 10    │ │
│  │  Listing: Boho Drop Earrings                                            │ │
│  │                                                                         │ │
│  │  BEFORE  │ Boho Drop Earrings, Handmade, Dangle Earrings               │ │
│  │  AFTER   │ Gold Boho Drop Earrings for Women, Minimalist Dangle         │ │
│  │          │ Earrings, Hypoallergenic Gift for Her, Handmade Jewelry      │ │
│  │                                                                         │ │
│  │  Expected impact:  SEO 58→81  (+23pts)  Views +34%  (estimated)        │ │
│  │  Why: Adds 4 high-volume missing keywords, front-loads "gold" and       │ │
│  │  "for women" which are top search modifiers in your category            │ │
│  │                                                                         │ │
│  │  [✓ Approve & Apply]  [✎ Edit Before Applying]  [✗ Reject]             │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  TAGS CHANGE                                                  Jun 10    │ │
│  │  Listing: Boho Drop Earrings                                            │ │
│  │                                                                         │ │
│  │  ADDING   │ [gold filled] [minimalist] [hypoallergenic] [gift for her]  │ │
│  │           │ [bohemian] [drop earrings] [nickel free]                    │ │
│  │                                                                         │ │
│  │  Expected impact:  Tags 51→89  (+38pts)  Discoverability +41%           │ │
│  │                                                                         │ │
│  │  [✓ Approve & Apply]  [✎ Edit Before Applying]  [✗ Reject]             │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  PRICE CHANGE                                                 Jun 10    │ │
│  │  Listing: Linen Tote Bag                                                │ │
│  │                                                                         │ │
│  │  BEFORE  │ $38.00                                                       │ │
│  │  AFTER   │ $29.99  (-$8.01)                                             │ │
│  │                                                                         │ │
│  │  Expected impact:  Price score 45→78  Conversion +22%  (estimated)     │ │
│  │                                                                         │ │
│  │  [✓ Approve & Apply]  [✎ Edit Before Applying]  [✗ Reject]             │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                                │
│  [Show 5 more pending changes ▾]                                              │
│                                                                                │
│  ┌───────────────────────────────────────────────────────────────┐           │
│  │  BULK ACTIONS                                                 │           │
│  │  [✓ Approve All 8 Changes]  [Export for Review]              │           │
│  └───────────────────────────────────────────────────────────────┘           │
│                                                                                │
│  ── APPLIED HISTORY ─────────────────────────────────────────────────────── │
│                                                                                │
│  ┌───────┬─────────────────────────────┬───────┬──────────┬───────────────┐ │
│  │ Date  │ Change                       │ Listing│ Result  │ Impact        │ │
│  ├───────┼─────────────────────────────┼───────┼──────────┼───────────────┤ │
│  │ Jun 8 │ Title updated               │ Candle │ ✓ Live  │ +18% views    │ │
│  │ Jun 7 │ 7 tags added                │ Hat    │ ✓ Live  │ +31% views    │ │
│  │ Jun 5 │ Description rewritten       │ Candle │ ✓ Live  │ +12% conv.    │ │
│  └───────┴─────────────────────────────┴───────┴──────────┴───────────────┘ │
│                                                                                │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Page 10: Reports

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Reports                                                                       │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  [Daily] [Weekly ●] [Monthly]                          [📥 Download PDF]      │
│                                                                                │
│  Week of Jun 3–9, 2026                                    [< Prev]  [Next >]  │
│                                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ VIEWS        │  │ FAVORITES    │  │ SALES        │  │ REVENUE      │    │
│  │  +2,841      │  │   +187       │  │    +12       │  │  +$432       │    │
│  │  ▲ vs prev   │  │  ▲ vs prev   │  │  ▲ vs prev   │  │  ▲ vs prev   │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
│                                                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  WEEKLY SUMMARY (AI Generated)                                          │ │
│  │                                                                         │ │
│  │  This was your strongest week in 6 weeks. The title optimizations       │ │
│  │  applied on Jun 7 drove a 31% view increase on "Summer Straw Hat"       │ │
│  │  within 48 hours. Competitor "BohoByBella" dropped prices by 12%        │ │
│  │  — monitor conversion impact on your earrings listings.                 │ │
│  │                                                                         │ │
│  │  Top opportunity this week: "cottagecore decor" trending +340%          │ │
│  │  on Pinterest — your Macrame listing is well positioned if tags         │ │
│  │  are updated before the trend peaks (est. Jun 24).                      │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                                │
│  PERFORMANCE CHART                                                             │
│                                                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  Views   ─── Favorites - - - Sales ······                               │ │
│  │                                                                         │ │
│  │  500 ┤                                                    ╭─────        │ │
│  │  400 ┤                             ╭─────────────────────╯             │ │
│  │  300 ┤              ╭──────────────╯                                    │ │
│  │  200 ┤──────────────╯                                                   │ │
│  │  100 ┤                                                                  │ │
│  │      └─────┴─────┴─────┴─────┴─────┴─────┴─────                       │ │
│  │       Mon   Tue   Wed   Thu   Fri   Sat   Sun                           │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                                │
│  TOP PERFORMING LISTINGS                                                       │
│  ┌────────────────────────────────┬──────────┬──────────┬────────────────┐  │
│  │ Listing                        │ Views    │ Favs     │ Sales          │  │
│  ├────────────────────────────────┼──────────┼──────────┼────────────────┤  │
│  │ Summer Straw Hat               │ 1,204 ▲  │  89 ▲    │  18 ▲         │  │
│  │ Lavender Soy Candle            │  892 ▲   │  71 ▲    │  14 ▲         │  │
│  │ Boho Drop Earrings             │  647 ▼   │  45 ─    │   8 ▼         │  │
│  └────────────────────────────────┴──────────┴──────────┴────────────────┘  │
│                                                                                │
│  THIS WEEK'S ACTIONS TAKEN           NEXT WEEK'S RECOMMENDATIONS             │
│  ✓ 3 titles optimized               → Update Macrame tags for cottagecore    │
│  ✓ 12 tags added across 4 listings  → Review earrings pricing vs competition │
│  ✓ 1 price adjusted                 → Generate Pinterest content for Hat     │
│                                                                                │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Page 11: Settings

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Settings                                                                      │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  [Account] [Stores] [Agent] [Notifications] [Billing] [API]                   │
│                                                                                │
│  ── ACCOUNT ─────────────────────────────────────────────────────────────── │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  Name          [Viktor Korobov                    ] [Save]              │ │
│  │  Email         [v.korobov63@gmail.com             ] [Change]            │ │
│  │  Password      [●●●●●●●●●●●●                      ] [Change]            │ │
│  │  Timezone      [UTC+3 Moscow                     ▾] [Save]              │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                                │
│  ── CONNECTED STORES ────────────────────────────────────────────────────── │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  🏪 My Handmade Shop          Connected  47 listings  [Sync] [Remove]   │ │
│  │     Last sync: Jun 10, 6:02am            [Manage →]                     │ │
│  │                                                                         │ │
│  │  [+ Connect Another Store]  (Pro/Agency plan required for multiple)     │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                                │
│  ── AGENT SETTINGS ──────────────────────────────────────────────────────── │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  Daily agent run time    [06:00 UTC           ▾]                        │ │
│  │  Agent enabled           [● ON]                                         │ │
│  │                                                                         │ │
│  │  Run daily scan          [✓] SEO analysis                               │ │
│  │                          [✓] Competitor check                           │ │
│  │                          [✓] Trend monitoring                           │ │
│  │                          [✓] Pricing check                              │ │
│  │                          [○] Image analysis (uses more credits)         │ │
│  │                                                                         │ │
│  │  Auto-queue optimizations [✓] (still requires your approval to apply)   │ │
│  │  AI model preference      [Best quality (claude-fable-5)  ▾]            │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                                │
│  ── NOTIFICATIONS ───────────────────────────────────────────────────────── │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  Daily email digest        [✓]  Time: [08:00 UTC ▾]                     │ │
│  │  Agent run complete        [✓] In-app + Email                           │ │
│  │  High-priority opportunity [✓] In-app + Email                           │ │
│  │  Competitor price change   [✓] In-app only                              │ │
│  │  Trend alerts              [✓] In-app only                              │ │
│  │  Billing alerts            [✓] Email only                               │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                                │
│  ── BILLING ─────────────────────────────────────────────────────────────── │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  Current plan: PRO  $29/mo  [Upgrade to Agency]  [Cancel Plan]          │ │
│  │  Next billing: Jul 1, 2026                                              │ │
│  │                                                                         │ │
│  │  AI Credits: 847 / 2,000 remaining this month                           │ │
│  │  ████████████████████████████████████░░░░░░░░░░   42% used             │ │
│  │  Resets Jul 1  [Buy More Credits]                                       │ │
│  │                                                                         │ │
│  │  [Manage Billing →]  (opens Stripe portal)                              │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                                │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## User Flows

### Flow 1: Onboarding (New User)

```
[Landing Page]
     │
     ▼
[Sign Up: email + password]
     │
     ▼
[Email Verification]
     │
     ├── Not verified → resend email screen (wait state)
     │
     ▼
[ONBOARDING WIZARD — Step 1/4]
┌─────────────────────────────────────────┐
│  Welcome! Let's connect your Etsy store │
│                                         │
│  ○ ─── ○ ─── ○ ─── ○                  │
│  [1]   [2]   [3]   [4]                 │
│                                         │
│  [Connect Your Etsy Store →]            │
└─────────────────────────────────────────┘
     │
     ▼
[STEP 2: Etsy OAuth popup]
┌─────────────────────────────────────────┐
│  Authorize EtsyAgent on Etsy.com...     │
│  (new window opens: Etsy OAuth page)    │
│                                         │
│  Scopes: read listings, write listings  │
│  [Authorize ✓] on Etsy                  │
└─────────────────────────────────────────┘
     │
     ▼  OAuth callback → store connected
[STEP 3: Syncing your store]
┌─────────────────────────────────────────┐
│  ✓ Connected: My Handmade Shop          │
│  Importing your 47 listings...          │
│  ████████████████░░░░  67%              │
│  This takes about 30 seconds            │
└─────────────────────────────────────────┘
     │
     ▼  sync complete
[STEP 4: Choose plan]
┌─────────────────────────────────────────┐
│  Starter    Pro        Agency           │
│  $9/mo      $29/mo     $79/mo           │
│  1 store    5 stores   Unlimited        │
│  500 cred   2000 cred  5000 cred        │
│             [Start Free Trial]          │
│                                         │
│  [Skip — continue free]                 │
└─────────────────────────────────────────┘
     │
     ▼
[FIRST AUDIT RUNNING]
┌─────────────────────────────────────────┐
│  We're analyzing your store...          │
│                                         │
│  ✓ Scanning 47 listings                 │
│  ✓ Running SEO analysis                 │
│  ⋯ Checking competitors...              │
│                                         │
│  Est. 2 minutes                         │
└─────────────────────────────────────────┘
     │
     ▼  analysis complete
[OVERVIEW DASHBOARD]
  → notification: "Your store audit is ready! Score: 74/100"
  → top recommendation card highlighted
  → onboarding tooltip: "Click here to see your top fixes"
```

---

### Flow 2: Store Connect (Existing User)

```
[Settings → Stores tab]
     │
     ▼
[Click "+ Connect Another Store"]
     │ (Pro/Agency only)
     ├── Starter plan? → Upgrade prompt modal
     │
     ▼
[OAuth flow] → same as onboarding step 2–3
     │
     ▼
[Store added] → redirect to Overview with new store selected
```

---

### Flow 3: Daily Usage Flow

```
[User opens app — morning]
     │
     ▼
[Overview Dashboard]
  → "Agent ran at 6:02am — 8 new recommendations"
  → Notification bell: 3 unread
     │
     ▼ User clicks top recommendation
[SEO Optimizer — Boho Drop Earrings]
  → Sees current 58/100 score
  → Sees AI-recommended title
     │
     ├── [Apply Title →]
     │       │
     │       ▼ Creates listing_optimization (status=pending)
     │   [Listing Optimizer page: Pending tab]
     │       │
     │       ▼ User reviews diff
     │   [✓ Approve & Apply]
     │       │
     │       ▼ Celery task: apply to Etsy API
     │   [Success toast: "Title updated on Etsy!"]
     │       │
     │       ▼ 48h later: metrics show +31% views
     │   [Optimization Results notification]
     │
     ├── [Not now] → dismissed, surfaces tomorrow
     │
     └── [Generate New Title] → Content Generator prefilled
```

---

### Flow 4: Manual SEO Optimization

```
[SEO Optimizer]
  → User selects listing from dropdown
  → Sees scores + recommendations
     │
     ▼ Clicks [▶ Re-analyze]
[Loading state: "Analyzing with AI... ~15s"]
     │
     ▼ Analysis complete
[Scores updated + diff shown]
     │
     ▼ User clicks [Apply All Changes]
[Review modal]
┌────────────────────────────────┐
│  Apply 3 changes to Etsy?      │
│                                │
│  ✓ Title (view diff)           │
│  ✓ Tags: +7 tags (view)        │
│  ✓ Description rewrite (view)  │
│                                │
│  Uses 45 AI credits            │
│  Credits remaining: 847 → 802  │
│                                │
│  [Confirm & Apply]  [Cancel]   │
└────────────────────────────────┘
     │
     ▼ User confirms
[Applying changes...]
[3 green toasts: "Title updated" / "Tags updated" / "Description updated"]
     │
     ▼
[Listing Optimizer → Applied tab]
  shows new entries with estimated impact
```

---

### Flow 5: Content Generation

```
[Content Generator]
  → Select type: "Instagram Caption"
  → Select listing: "Lavender Soy Candle"
  → Tone: Casual
  → Keywords: lavender, self-care, handmade
  → [✨ Generate]
     │
     ▼ Loading state (10-20s)
[Result appears]
  → Shows caption with hashtags
  → SEO notes inline
     │
     ├── [📋 Copy] → clipboard + "Copied!" feedback
     ├── [★★★★☆] → user rates
     ├── [Regenerate ↻] → new variation
     └── [Apply to Listing] → only for title/description/tags types
```

---

## Next.js Component Structure

```
src/
├── app/                              # Next.js 14 App Router
│   ├── (auth)/                       # Route group: no sidebar
│   │   ├── login/page.tsx
│   │   ├── register/page.tsx
│   │   ├── forgot-password/page.tsx
│   │   └── layout.tsx               # Auth layout (centered card)
│   │
│   ├── (dashboard)/                  # Route group: sidebar + header
│   │   ├── layout.tsx               # AppShell layout
│   │   ├── overview/page.tsx
│   │   ├── audit/page.tsx
│   │   ├── competitors/page.tsx
│   │   ├── seo/page.tsx
│   │   ├── trends/page.tsx
│   │   ├── audience/page.tsx
│   │   ├── content/page.tsx
│   │   ├── pricing/page.tsx
│   │   ├── optimizer/page.tsx
│   │   ├── reports/page.tsx
│   │   └── settings/
│   │       ├── page.tsx
│   │       ├── account/page.tsx
│   │       ├── stores/page.tsx
│   │       ├── agent/page.tsx
│   │       ├── notifications/page.tsx
│   │       └── billing/page.tsx
│   │
│   ├── onboarding/                   # Separate flow, no sidebar
│   │   ├── layout.tsx
│   │   ├── connect/page.tsx
│   │   ├── syncing/page.tsx
│   │   ├── plan/page.tsx
│   │   └── analyzing/page.tsx
│   │
│   ├── api/                          # Next.js API routes (thin proxies to FastAPI)
│   │   └── auth/[...nextauth]/route.ts
│   │
│   ├── layout.tsx                    # Root layout: QueryClientProvider, Toaster
│   └── globals.css
│
├── components/
│   ├── layout/
│   │   ├── AppShell.tsx             # Sidebar + Header + main content area
│   │   ├── Sidebar.tsx              # Nav links, active state, collapse
│   │   ├── Header.tsx               # Store selector, notifications, user menu
│   │   ├── StoreSelector.tsx        # Dropdown: connected stores + add new
│   │   ├── NotificationBell.tsx     # Bell icon + unread count + dropdown
│   │   └── UserMenu.tsx             # Avatar + plan badge + menu
│   │
│   ├── overview/
│   │   ├── HealthScoreRing.tsx      # Circular progress for 74/100
│   │   ├── MetricCard.tsx           # Views/Favorites/Sales/Revenue cards
│   │   ├── RecommendationCard.tsx   # Single recommendation with priority badge
│   │   ├── RecommendationList.tsx   # Stacked list with "show more"
│   │   ├── AgentActivityFeed.tsx    # Timeline of agent run events
│   │   └── TrendingKeywords.tsx     # Mini trend cards
│   │
│   ├── audit/
│   │   ├── HealthBreakdown.tsx      # Score breakdown table with progress bars
│   │   ├── IssueGroup.tsx           # Expandable group: Critical/Warning/Info
│   │   ├── IssueRow.tsx             # Single issue with fix CTA
│   │   └── ListingHealthTable.tsx   # Sortable table with score columns
│   │
│   ├── competitors/
│   │   ├── CompetitorTable.tsx      # Ranked table with shop/price/score
│   │   ├── CompetitorRow.tsx        # Expandable row with tags preview
│   │   ├── GapAnalysisPanel.tsx     # Missing tags + keyword gaps
│   │   ├── MarketOpportunityCard.tsx
│   │   └── TagCloud.tsx             # Interactive clickable tags
│   │
│   ├── seo/
│   │   ├── SeoScoreBreakdown.tsx    # Title/Tags/Desc scores
│   │   ├── TitleDiff.tsx            # Before/after title with highlights
│   │   ├── TagsEditor.tsx           # Current + recommended + interactive
│   │   ├── DescriptionHealth.tsx    # Word count, missing terms, issues
│   │   └── ApplyAllPanel.tsx        # Confirm + credit cost + apply CTA
│   │
│   ├── trends/
│   │   ├── TrendCard.tsx            # Single trend: score + chart + actions
│   │   ├── TrendSparkline.tsx       # Inline Recharts sparkline
│   │   ├── SeasonalCalendar.tsx     # Horizontal timeline of seasonal peaks
│   │   ├── TrendFilters.tsx         # Source + Category filter bar
│   │   └── OpportunityBadge.tsx     # "EMERGING" / "PEAKING" labels
│   │
│   ├── audience/
│   │   ├── PersonaCard.tsx          # Full persona with all fields
│   │   ├── CommunityTable.tsx       # Platform + relevance table
│   │   └── ContentIdeasPanel.tsx    # Per-persona content suggestions
│   │
│   ├── content/
│   │   ├── ContentGeneratorForm.tsx # Type + listing + tone + keywords form
│   │   ├── ContentTypeSelector.tsx  # Tab/button grid for 9 content types
│   │   ├── GeneratedResult.tsx      # Result card: text + rate + copy + apply
│   │   ├── ContentHistoryList.tsx   # Scrollable past generations
│   │   └── CreditCostBadge.tsx      # "Uses ~15 credits" inline estimate
│   │
│   ├── pricing/
│   │   ├── PricePositionBar.tsx     # Min/Avg/Rec/You/Max visual range
│   │   ├── CompetitorPriceTable.tsx
│   │   ├── BundleOpportunity.tsx    # Bundle suggestion card
│   │   └── PriceRecommendation.tsx  # CTA card with estimated lift
│   │
│   ├── optimizer/
│   │   ├── OptimizationCard.tsx     # Before/After diff + approve/reject
│   │   ├── DiffViewer.tsx           # Word-level diff highlight
│   │   ├── ApprovalQueue.tsx        # Pending list with bulk approve
│   │   ├── OptimizationHistory.tsx  # Applied changes with results
│   │   └── ImpactEstimate.tsx       # "+23pts SEO" badge
│   │
│   ├── reports/
│   │   ├── ReportSummary.tsx        # AI-generated prose summary card
│   │   ├── PerformanceChart.tsx     # Recharts LineChart: views/favs/sales
│   │   ├── TopListingsTable.tsx
│   │   ├── ActionsTaken.tsx         # This week's applied changes
│   │   └── NextWeekRecs.tsx         # Forward-looking bullets
│   │
│   ├── agent/
│   │   ├── AgentRunButton.tsx       # "▶ Run Agent" with loading state
│   │   ├── AgentProgressStream.tsx  # SSE consumer → live progress UI
│   │   ├── AgentRunHistory.tsx      # Table of past runs
│   │   └── AgentStatusBadge.tsx     # running/complete/failed chip
│   │
│   ├── onboarding/
│   │   ├── OnboardingProgress.tsx   # Step indicator 1/4
│   │   ├── ConnectStoreStep.tsx
│   │   ├── SyncingStep.tsx          # Progress bar with status messages
│   │   ├── PlanPickerStep.tsx       # 3-column plan cards
│   │   └── AnalyzingStep.tsx        # First audit loading screen
│   │
│   └── ui/                          # shadcn/ui primitives + custom wrappers
│       ├── Button.tsx
│       ├── Card.tsx
│       ├── Badge.tsx               # priority / status / score badges
│       ├── ScoreBadge.tsx          # colored 0-100 score chip
│       ├── ProgressBar.tsx
│       ├── DataTable.tsx           # sortable, paginated table
│       ├── EmptyState.tsx          # (see UI States section)
│       ├── ErrorState.tsx
│       ├── LoadingSkeleton.tsx
│       ├── ConfirmModal.tsx        # generic confirm dialog
│       ├── CreditWarning.tsx       # inline low-credit alert
│       └── Tooltip.tsx
│
├── hooks/
│   ├── useStore.ts                  # current store from URL / context
│   ├── useStores.ts                 # GET /stores
│   ├── useListings.ts               # GET /stores/{id}/listings (paginated)
│   ├── useListing.ts                # GET /stores/{id}/listings/{id}
│   ├── useSeoAnalysis.ts            # GET /listings/{id}/seo
│   ├── useCompetitors.ts            # GET /listings/{id}/competitors
│   ├── useTrends.ts                 # GET /trends
│   ├── useOptimizations.ts          # GET /stores/{id}/optimizations
│   ├── useAgentRuns.ts              # GET /stores/{id}/agent/runs
│   ├── useAgentStream.ts            # SSE hook: EventSource → state
│   ├── useNotifications.ts          # GET /notifications + mark read
│   ├── useBilling.ts                # GET /billing/subscription + credits
│   ├── useCredits.ts                # balance + warning thresholds
│   └── useMutations.ts              # shared mutation helpers (toast on error)
│
├── lib/
│   ├── api.ts                       # axios instance, auth header, 401 intercept
│   ├── queryClient.ts               # TanStack Query config, stale times
│   ├── auth.ts                      # NextAuth config
│   ├── utils.ts                     # cn(), formatCurrency(), truncate()
│   └── constants.ts                 # PLAN_LIMITS, CREDIT_COSTS, SCORE_THRESHOLDS
│
├── store/
│   └── ui.ts                        # Zustand: sidebar open, active store
│
└── types/
    ├── api.ts                        # API response types (mirrors Pydantic models)
    ├── store.ts
    ├── listing.ts
    ├── seo.ts
    └── agent.ts
```

---

## Key UI States

### Loading States

```
── SKELETON (initial page load) ──────────────────────────────────────────────

┌─────────────────────────────────────────────────────┐
│  ░░░░░░░░░░░░░░░  ░░░░░░░░░░  ░░░░░░░░░░░░          │
│                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │ ░░░░░░░░░░  │  │ ░░░░░░░░░░  │  │ ░░░░░░░░░░  │  │
│  │ ░░░░░░░░░░  │  │ ░░░░░░░░░░  │  │ ░░░░░░░░░░  │  │
│  │ ░░░░        │  │ ░░░░        │  │ ░░░░        │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  │
│                                                     │
│  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░    │
│  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░             │
└─────────────────────────────────────────────────────┘
-- Implementation: Tailwind animate-pulse on gray divs
-- Use <Skeleton> for every data-dependent render
-- Skeleton shape should match the loaded content shape exactly

── BUTTON LOADING (user clicked action) ──────────────────────────────────────

  Before: [✨ Generate Content]
  After:  [⋯ Generating... (12s)]   ← spinner + estimated time
  
  Rule: Disable button immediately on click. Never allow double-submit.
  Show progress text if operation > 3s.

── AGENT RUN IN PROGRESS (SSE stream) ────────────────────────────────────────

┌──────────────────────────────────────────────┐
│  Agent Running...                    [Cancel] │
│                                              │
│  ████████████████░░░░░░░░░░░░░░  52%         │
│                                              │
│  ✓ Synced 47 listings                        │
│  ✓ SEO analyzed: 47/47                       │
│  ⋯ Scanning competitors... (23/47)           │
│  ○ Trend analysis (pending)                  │
│  ○ Pricing check (pending)                   │
│  ○ Generating recommendations (pending)      │
└──────────────────────────────────────────────┘
```

---

### Empty States

```
── NO STORE CONNECTED ────────────────────────────────────────────────────────

┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│                    🏪                                            │
│                                                                  │
│              No Etsy store connected yet                         │
│         Connect your store to start growing your sales           │
│                                                                  │
│              [Connect Your Etsy Store →]                         │
│                                                                  │
│              Takes about 2 minutes                               │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

── NO ANALYSIS RUN YET (SEO page, new listing) ───────────────────────────────

┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│                    ✦                                             │
│                                                                  │
│           No SEO analysis for this listing yet                   │
│        Run an analysis to see your score and recommendations     │
│                                                                  │
│         [▶ Analyze SEO Now]   Uses ~15 AI credits                │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

── NO PENDING OPTIMIZATIONS ──────────────────────────────────────────────────

┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│                    ⚡                                            │
│                                                                  │
│              All caught up!                                      │
│         No optimizations waiting for your approval               │
│                                                                  │
│     The agent will surface new recommendations after tonight's   │
│     scan. Next run: Jun 11 at 6:00am UTC                         │
│                                                                  │
│         [▶ Run Agent Now]                                        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

── NO RESULTS (search / filter returned nothing) ─────────────────────────────

┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│                    🔍                                            │
│                                                                  │
│           No listings match "ceramic bowl"                       │
│                                                                  │
│         [Clear search]   or   [Sync store now]                   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

── FIRST TIME / FEATURE NOT YET USED (Audience page) ────────────────────────

┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│                    ◎                                             │
│                                                                  │
│           Discover who buys from you                             │
│                                                                  │
│  We'll analyze your listings and find your ideal customers       │
│  across Pinterest, Reddit, TikTok, and Instagram.                │
│                                                                  │
│         [◎ Discover My Audience]   Uses ~80 AI credits           │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

### Error States

```
── API ERROR (generic, recoverable) ──────────────────────────────────────────

┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│                    ⚠                                             │
│                                                                  │
│           Couldn't load your listings                            │
│         This might be a temporary issue                          │
│                                                                  │
│         [↻ Try Again]   or   [Contact Support]                   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

── ETSY TOKEN EXPIRED ────────────────────────────────────────────────────────

┌──────────────────────────────────────────────────────────────────┐
│  ⚠ Etsy connection needs re-authorizing                    [×]   │
│  Your Etsy access expired. Re-connect to continue syncing.        │
│  [Reconnect Etsy Store →]                                         │
└──────────────────────────────────────────────────────────────────┘
-- Shows as a dismissible banner at top of dashboard, not full page

── OPTIMIZATION APPLY FAILED ─────────────────────────────────────────────────

┌────────────────────────────────────────────────┐
│  ✗ Title update failed                   [×]   │
│  Etsy returned: "Title exceeds 140 chars"       │
│  [✎ Edit & Retry]   [View Error Details]        │
└────────────────────────────────────────────────┘
-- Inline in the OptimizationCard, not a modal

── OUT OF AI CREDITS ─────────────────────────────────────────────────────────

┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│  You've used all 500 credits for this month                      │
│                                                                  │
│  Resets in 18 days   OR   [Buy More Credits]   [Upgrade Plan]    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

── LOW CREDITS WARNING (inline, non-blocking) ────────────────────────────────

  ┌──────────────────────────────────────────────┐
  │  ⚠ 47 credits remaining this month           │
  │  This analysis uses ~15 credits    [OK]       │
  └──────────────────────────────────────────────┘
  -- Shown in confirm modal before expensive AI operations
  -- Only surfaces when balance < 100

── NETWORK OFFLINE ───────────────────────────────────────────────────────────

  [banner, top of app, full width]
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  ◌ No internet connection — changes will sync when you're back online    │
  └──────────────────────────────────────────────────────────────────────────┘
```

---

### Success States

```
── OPTIMIZATION APPLIED ──────────────────────────────────────────────────────

  [Toast, bottom-right, auto-dismiss 4s]
  ┌──────────────────────────────────────────┐
  │  ✓ Title updated on Etsy                 │
  │    "Boho Drop Earrings"                  │
  │    [View on Etsy ↗]          [Undo?]     │
  └──────────────────────────────────────────┘

── CONTENT GENERATED ─────────────────────────────────────────────────────────

  [Result card animates in, highlight pulse on first render]
  No toast — the result itself is the success signal.

── STORE CONNECTED ───────────────────────────────────────────────────────────

  [Full step transition in onboarding wizard]
  ┌──────────────────────────────────────────┐
  │  ✓ My Handmade Shop connected!           │
  │  Importing 47 listings...                │
  └──────────────────────────────────────────┘

── AGENT RUN COMPLETE ────────────────────────────────────────────────────────

  [Toast + notification badge update]
  ┌──────────────────────────────────────────┐
  │  ✓ Agent scan complete                   │
  │  8 new recommendations ready             │
  │  [View Recommendations →]                │
  └──────────────────────────────────────────┘

── BULK APPROVE COMPLETE ─────────────────────────────────────────────────────

  [Toast]
  ┌──────────────────────────────────────────┐
  │  ✓ 8 changes approved and applied        │
  │  SEO score improving across 5 listings   │
  │  [View in Optimizer →]                   │
  └──────────────────────────────────────────┘
```

---

## Component State Machine: OptimizationCard

```
PENDING
  ├── User clicks "Approve & Apply" → APPLYING (spinner)
  │     ├── API success → APPLIED (green, shows impact)
  │     └── API error → FAILED (red banner, retry CTA)
  ├── User clicks "Edit Before Applying" → EDITING (inline textarea)
  │     └── User saves → APPLYING → APPLIED / FAILED
  └── User clicks "Reject" → REJECTED (muted, collapsed)

Transitions:
APPROVED → APPLYING (automatic if no edit)
APPLIED → show OptimizationResult component after 48h with delta metrics
FAILED → show error + retry + "view raw error" toggle
```

---

## Responsive Behavior

```
Breakpoints: sm(640) md(768) lg(1024) xl(1280) 2xl(1536)

Desktop (lg+):
  Sidebar: 240px fixed left
  Header: full width
  Content: fluid, max-w-7xl centered

Tablet (md):
  Sidebar: collapsed to icons only (48px), expand on hover
  Metric cards: 2-column grid
  Tables: horizontal scroll

Mobile (sm):
  Sidebar: off-canvas drawer (hamburger menu)
  Metric cards: 1-column stacked
  Tables: card list view (no horizontal scroll)
  SEO Optimizer: sections stacked vertically
  Agent controls: floating action button (bottom-right)
```
