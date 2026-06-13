from pydantic import BaseModel, Field


class DigestOpportunity(BaseModel):
    """One concrete, listing-level action the seller should take next."""

    listing_title: str
    action: str
    expected_impact: str


class DailyDigest(BaseModel):
    """Validated structured output of the daily synthesizer (ai-agent-spec §3.8).

    Rolls up the day's per-listing SEO analyses into a single store-level
    briefing the seller reads in their morning notification.
    """

    headline: str = Field(max_length=120)
    summary: str
    store_health_score: int = Field(ge=0, le=100)
    key_insights: list[str]
    top_opportunities: list[DigestOpportunity] = Field(max_length=5)
    recommended_actions: list[str]
