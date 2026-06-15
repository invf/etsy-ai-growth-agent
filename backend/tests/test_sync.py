from contextlib import contextmanager
from decimal import Decimal
from unittest.mock import MagicMock

import httpx
import pytest

from app.db.models.listing import Listing
from app.db.models.store import Store
from app.services.etsy_token_service import StoreNotConnectedError
from app.tasks import sync as sync_mod
from app.tasks.sync import _apply_etsy_listing, _money_to_decimal, compute_content_hash


def _http_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://openapi.etsy.com/v3/test")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError("boom", request=request, response=response)


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


def test_fetch_page_force_refreshes_on_401(monkeypatch):
    used_tokens = []

    def fake_get_shop_listings(token, shop_id, limit, offset):
        used_tokens.append(token)
        if token == "stale":
            raise _http_error(401)
        return {"count": 0, "results": []}

    monkeypatch.setattr(sync_mod, "get_shop_listings", fake_get_shop_listings)
    monkeypatch.setattr(
        sync_mod, "get_valid_access_token", MagicMock(return_value="fresh")
    )

    store = Store(etsy_shop_id="s1", shop_name="Shop")
    page, token = sync_mod._fetch_page(MagicMock(), store, "stale", offset=0)

    assert token == "fresh"
    assert used_tokens == ["stale", "fresh"]
    assert page == {"count": 0, "results": []}


def test_fetch_page_non_401_error_bubbles_up(monkeypatch):
    monkeypatch.setattr(
        sync_mod, "get_shop_listings", MagicMock(side_effect=_http_error(500))
    )
    refresh = MagicMock()
    monkeypatch.setattr(sync_mod, "get_valid_access_token", refresh)

    store = Store(etsy_shop_id="s1", shop_name="Shop")
    with pytest.raises(httpx.HTTPStatusError):
        sync_mod._fetch_page(MagicMock(), store, "tok", offset=0)
    refresh.assert_not_called()


def test_sync_fetches_images_when_listing_omits_them(monkeypatch):
    store = Store(etsy_shop_id="s1", shop_name="Shop", status="active", sync_status="idle")
    listing = Listing(store_id=None, etsy_listing_id=111)
    db = MagicMock()
    # first() is called for the Store, then for the Listing
    db.query.return_value.filter_by.return_value.first.side_effect = [store, listing]

    @contextmanager
    def fake_session():
        yield db

    monkeypatch.setattr(sync_mod, "get_db_session", fake_session)
    monkeypatch.setattr(sync_mod, "get_valid_access_token", MagicMock(return_value="tok"))
    monkeypatch.setattr(
        sync_mod,
        "get_shop_listings",
        MagicMock(return_value={"count": 1, "results": [{"listing_id": 111, "title": "X"}]}),
    )
    images = MagicMock(return_value={"results": [{"url_fullxfull": "https://x/1.jpg"}]})
    monkeypatch.setattr(sync_mod, "get_listing_images", images)

    result = sync_mod.sync_store_listings("some-id")

    assert result == {"status": "ok", "synced": 1}
    images.assert_called_once_with("tok", "s1", 111)
    assert listing.main_image_url == "https://x/1.jpg"
    assert listing.image_count == 1


def test_sync_marks_store_disconnected_on_revoked_token(monkeypatch):
    store = Store(etsy_shop_id="s1", shop_name="Shop", status="active", sync_status="idle")
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = store

    @contextmanager
    def fake_session():
        yield db

    monkeypatch.setattr(sync_mod, "get_db_session", fake_session)
    monkeypatch.setattr(
        sync_mod,
        "get_valid_access_token",
        MagicMock(side_effect=StoreNotConnectedError("revoked")),
    )

    result = sync_mod.sync_store_listings("some-id")

    assert result == {"status": "error", "reason": "store_disconnected"}
    assert store.status == "disconnected"
    assert store.sync_status == "error"
    assert "revoked" in store.sync_error
