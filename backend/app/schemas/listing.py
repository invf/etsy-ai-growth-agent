from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class ListingSummaryOut(BaseModel):
    id: str
    etsy_listing_id: int
    title: str | None
    price_usd: Decimal | None
    currency_code: str
    state: str
    main_image_url: str | None
    image_count: int
    views_count: int
    favorites_count: int
    sales_count: int
    seo_score: int | None
    image_score: int | None
    tags: list[str]
    primary_category: str | None
    etsy_updated_at: datetime | None
    synced_at: datetime


class ListingDetailOut(ListingSummaryOut):
    description: str | None
    materials: list[str]
    original_price: Decimal | None
    quantity: int | None
    is_customizable: bool
    image_urls: list[str]
    average_rating: Decimal | None
    review_count: int
    seo_scored_at: datetime | None
    image_scored_at: datetime | None
    taxonomy_path: list[str]
    etsy_created_at: datetime | None
    created_at: datetime


class ListingsMeta(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int
