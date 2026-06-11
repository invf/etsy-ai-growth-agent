from decimal import Decimal

from app.db.models.listing import Listing
from app.tasks.sync import _apply_etsy_listing, _money_to_decimal, compute_content_hash


def test_content_hash_changes_with_content():
    base = compute_content_hash("Title", "Desc", ["a", "b"])
    assert base == compute_content_hash("Title", "Desc", ["a", "b"])
    assert base != compute_content_hash("Title", "Desc", ["a", "c"])
    assert base != compute_content_hash("Other", "Desc", ["a", "b"])


def test_money_to_decimal():
    assert _money_to_decimal({"amount": 1250, "divisor": 100}) == Decimal("12.50")
    assert _money_to_decimal(None) is None
    assert _money_to_decimal({"amount": None}) is None


def test_apply_etsy_listing_maps_fields():
    listing = Listing(store_id=None, etsy_listing_id=111)
    item = {
        "listing_id": 111,
        "title": "Handmade mug",
        "description": "A nice mug",
        "tags": ["mug", "ceramic"],
        "materials": ["clay"],
        "price": {"amount": 2999, "divisor": 100, "currency_code": "USD"},
        "quantity": 5,
        "is_customizable": True,
        "state": "active",
        "taxonomy_id": 123,
        "views": 42,
        "num_favorers": 7,
        "images": [{"url_fullxfull": "https://img/1.jpg"}, {"url_fullxfull": "https://img/2.jpg"}],
        "original_creation_timestamp": 1700000000,
        "last_modified_timestamp": 1700001000,
    }

    _apply_etsy_listing(listing, item)

    assert listing.title == "Handmade mug"
    assert listing.tags == ["mug", "ceramic"]
    assert listing.price_usd == Decimal("29.99")
    assert listing.original_price == Decimal("29.99")
    assert listing.currency_code == "USD"
    assert listing.quantity == 5
    assert listing.is_customizable is True
    assert listing.main_image_url == "https://img/1.jpg"
    assert listing.image_count == 2
    assert listing.views_count == 42
    assert listing.favorites_count == 7
    assert listing.content_hash == compute_content_hash(
        "Handmade mug", "A nice mug", ["mug", "ceramic"]
    )
    assert listing.etsy_created_at is not None


def test_apply_etsy_listing_non_usd_price_not_normalized():
    listing = Listing(store_id=None, etsy_listing_id=222)
    item = {
        "listing_id": 222,
        "title": "Kubek",
        "price": {"amount": 5000, "divisor": 100, "currency_code": "PLN"},
    }

    _apply_etsy_listing(listing, item)

    assert listing.original_price == Decimal("50.00")
    assert listing.currency_code == "PLN"
    assert listing.price_usd is None
