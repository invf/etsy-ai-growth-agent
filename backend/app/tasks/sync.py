import hashlib
from datetime import datetime, timezone
from decimal import Decimal

from app.celery_app import celery_app
from app.db.models.listing import Listing
from app.db.models.store import Store
from app.db.session import get_db_session
from app.services.etsy_client import get_shop_listings
from app.services.etsy_token_service import get_valid_access_token

PAGE_SIZE = 100


def compute_content_hash(title: str | None, description: str | None, tags: list[str]) -> str:
    """SHA-256 over the SEO-relevant content; used to detect stale embeddings."""
    payload = "\n".join([title or "", description or "", ",".join(tags)])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _epoch_to_dt(value: int | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc)


def _money_to_decimal(price: dict | None) -> Decimal | None:
    if not price or price.get("amount") is None:
        return None
    return Decimal(price["amount"]) / Decimal(price.get("divisor") or 100)


def _apply_etsy_listing(listing: Listing, item: dict) -> None:
    listing.title = item.get("title")
    listing.description = item.get("description")
    listing.tags = item.get("tags") or []
    listing.materials = item.get("materials") or []
    listing.style = item.get("style") or []

    price = _money_to_decimal(item.get("price"))
    listing.original_price = price
    currency = (item.get("price") or {}).get("currency_code") or "USD"
    listing.currency_code = currency
    if currency == "USD":
        listing.price_usd = price

    listing.quantity = item.get("quantity")
    listing.is_customizable = bool(item.get("is_customizable"))
    listing.state = item.get("state") or "active"
    listing.taxonomy_id = item.get("taxonomy_id")

    images = item.get("images") or []
    listing.image_urls = [img["url_fullxfull"] for img in images if img.get("url_fullxfull")]
    listing.main_image_url = listing.image_urls[0] if listing.image_urls else None
    listing.image_count = len(listing.image_urls)

    listing.views_count = item.get("views") or 0
    listing.favorites_count = item.get("num_favorers") or 0

    listing.content_hash = compute_content_hash(
        listing.title, listing.description, listing.tags
    )
    listing.etsy_created_at = _epoch_to_dt(item.get("original_creation_timestamp"))
    listing.etsy_updated_at = _epoch_to_dt(item.get("last_modified_timestamp"))
    listing.synced_at = datetime.now(timezone.utc)


@celery_app.task(name="tasks.sync.sync_store_listings", bind=True, max_retries=3)
def sync_store_listings(self, store_id: str) -> dict:
    """Fetch all active listings from Etsy and upsert them into the listings table."""
    with get_db_session() as db:
        store = db.query(Store).filter_by(id=store_id).first()
        if not store:
            return {"status": "skipped", "reason": "store not found"}

        store.sync_status = "syncing"
        db.flush()

        try:
            token = get_valid_access_token(db, store)

            synced = 0
            offset = 0
            while True:
                page = get_shop_listings(
                    token, store.etsy_shop_id, limit=PAGE_SIZE, offset=offset
                )
                results = page.get("results") or []
                for item in results:
                    etsy_listing_id = item["listing_id"]
                    listing = (
                        db.query(Listing)
                        .filter_by(etsy_listing_id=etsy_listing_id)
                        .first()
                    )
                    if not listing:
                        listing = Listing(
                            store_id=store.id, etsy_listing_id=etsy_listing_id
                        )
                        db.add(listing)
                    _apply_etsy_listing(listing, item)
                    synced += 1

                offset += PAGE_SIZE
                if offset >= (page.get("count") or 0) or not results:
                    break

            store.listing_count = synced
            store.last_synced_at = datetime.now(timezone.utc)
            store.sync_status = "idle"
            store.sync_error = None
            return {"status": "ok", "synced": synced}
        except Exception as exc:
            store.sync_status = "error"
            store.sync_error = str(exc)[:1000]
            # commit now: the context manager would roll this back on raise
            db.commit()
            raise self.retry(exc=exc, countdown=60)
