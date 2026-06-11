from datetime import datetime

from pydantic import BaseModel


class StoreOut(BaseModel):
    id: str
    etsy_shop_id: str
    shop_name: str
    shop_url: str | None
    icon_url: str | None
    currency_code: str
    status: str
    sync_status: str
    listing_count: int
    health_score: int | None
    health_computed_at: datetime | None
    agent_enabled: bool
    agent_last_run_at: datetime | None
    last_synced_at: datetime | None
    created_at: datetime


class OAuthInitiateOut(BaseModel):
    oauth_url: str
    state: str
    expires_in: int = 600
