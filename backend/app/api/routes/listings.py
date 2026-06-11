import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.listing import Listing
from app.db.models.store import Store
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.listing import ListingDetailOut, ListingsMeta, ListingSummaryOut

router = APIRouter(prefix="/stores/{store_id}/listings", tags=["listings"])

SORT_COLUMNS = {
    "seo_score": Listing.seo_score,
    "views": Listing.views_count,
    "favorites": Listing.favorites_count,
    "sales": Listing.sales_count,
    "price": Listing.price_usd,
    "updated_at": Listing.etsy_updated_at,
}

VALID_STATES = {"active", "inactive", "draft", "expired", "sold_out", "removed", "all"}


def _get_owned_store(store_id: str, user: User, db: Session) -> Store:
    store = db.query(Store).filter_by(id=store_id, user_id=user.id).first()
    if not store:
        raise HTTPException(
            404, detail={"code": "NOT_FOUND", "message": "Store not found"}
        )
    return store


def _summary(listing: Listing) -> ListingSummaryOut:
    return ListingSummaryOut(
        id=str(listing.id),
        etsy_listing_id=listing.etsy_listing_id,
        title=listing.title,
        price_usd=listing.price_usd,
        currency_code=listing.currency_code,
        state=listing.state,
        main_image_url=listing.main_image_url,
        image_count=listing.image_count,
        views_count=listing.views_count,
        favorites_count=listing.favorites_count,
        sales_count=listing.sales_count,
        seo_score=listing.seo_score,
        image_score=listing.image_score,
        tags=listing.tags or [],
        primary_category=listing.primary_category,
        etsy_updated_at=listing.etsy_updated_at,
        synced_at=listing.synced_at,
    )


def _detail(listing: Listing) -> ListingDetailOut:
    return ListingDetailOut(
        **_summary(listing).model_dump(),
        description=listing.description,
        materials=listing.materials or [],
        original_price=listing.original_price,
        quantity=listing.quantity,
        is_customizable=listing.is_customizable,
        image_urls=listing.image_urls or [],
        average_rating=listing.average_rating,
        review_count=listing.review_count,
        seo_scored_at=listing.seo_scored_at,
        image_scored_at=listing.image_scored_at,
        taxonomy_path=listing.taxonomy_path or [],
        etsy_created_at=listing.etsy_created_at,
        created_at=listing.created_at,
    )


@router.get("", response_model=dict)
def list_listings(
    store_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    state: str = Query("active"),
    sort: str = Query("-views"),
    q: str | None = Query(None, max_length=200),
    min_seo_score: int | None = Query(None, ge=0, le=100),
    max_seo_score: int | None = Query(None, ge=0, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    store = _get_owned_store(store_id, current_user, db)

    if state not in VALID_STATES:
        raise HTTPException(
            422,
            detail={
                "code": "INVALID_PARAM",
                "message": f"state must be one of {sorted(VALID_STATES)}",
            },
        )

    descending = sort.startswith("-")
    sort_key = sort.lstrip("-")
    column = SORT_COLUMNS.get(sort_key)
    if column is None:
        raise HTTPException(
            422,
            detail={
                "code": "INVALID_PARAM",
                "message": f"sort must be one of {sorted(SORT_COLUMNS)}",
            },
        )

    query = db.query(Listing).filter(Listing.store_id == store.id)
    if state != "all":
        query = query.filter(Listing.state == state)
    if q:
        query = query.filter(Listing.title.ilike(f"%{q}%"))
    if min_seo_score is not None:
        query = query.filter(Listing.seo_score >= min_seo_score)
    if max_seo_score is not None:
        query = query.filter(Listing.seo_score <= max_seo_score)

    total = query.count()
    ordered = column.desc().nulls_last() if descending else column.asc().nulls_last()
    rows = (
        query.order_by(ordered, Listing.id)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    meta = ListingsMeta(
        page=page,
        per_page=per_page,
        total=total,
        total_pages=max(1, math.ceil(total / per_page)),
    )
    return {
        "data": [_summary(item).model_dump(mode="json") for item in rows],
        "meta": meta.model_dump(),
    }


@router.get("/{listing_id}", response_model=dict)
def get_listing(
    store_id: str,
    listing_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    store = _get_owned_store(store_id, current_user, db)
    listing = db.query(Listing).filter_by(id=listing_id, store_id=store.id).first()
    if not listing:
        raise HTTPException(
            404, detail={"code": "NOT_FOUND", "message": "Listing not found"}
        )
    return {"data": _detail(listing).model_dump(mode="json")}
