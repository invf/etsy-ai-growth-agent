from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import httpx
import pytest

from app.core.encryption import decrypt, encrypt
from app.db.models.store import Store
from app.services import etsy_token_service
from app.services.etsy_token_service import StoreNotConnectedError, get_valid_access_token


def _http_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://api.etsy.com/v3/public/oauth/token")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError("boom", request=request, response=response)


def _store(expires_in_minutes: int) -> Store:
    return Store(
        etsy_shop_id="s1",
        shop_name="Shop",
        etsy_access_token=encrypt("old-access"),
        etsy_refresh_token=encrypt("old-refresh"),
        token_expires_at=datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes),
    )


def test_returns_current_token_when_not_expiring(monkeypatch):
    refresh = MagicMock()
    monkeypatch.setattr(etsy_token_service, "refresh_access_token", refresh)

    token = get_valid_access_token(MagicMock(), _store(expires_in_minutes=30))

    assert token == "old-access"
    refresh.assert_not_called()


def test_refreshes_and_persists_when_expiring(monkeypatch):
    refresh = MagicMock(
        return_value={
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "expires_in": 3600,
        }
    )
    monkeypatch.setattr(etsy_token_service, "refresh_access_token", refresh)

    store = _store(expires_in_minutes=2)  # inside the 5-minute refresh margin
    db = MagicMock()
    token = get_valid_access_token(db, store)

    assert token == "new-access"
    refresh.assert_called_once_with("old-refresh")
    assert decrypt(store.etsy_access_token) == "new-access"
    assert decrypt(store.etsy_refresh_token) == "new-refresh"
    assert store.token_expires_at > datetime.now(timezone.utc) + timedelta(minutes=50)
    db.flush.assert_called_once()


def test_raises_when_store_has_no_tokens():
    store = Store(etsy_shop_id="s2", shop_name="Shop")
    with pytest.raises(StoreNotConnectedError):
        get_valid_access_token(MagicMock(), store)


def test_refresh_rejection_means_store_not_connected(monkeypatch):
    refresh = MagicMock(side_effect=_http_error(400))
    monkeypatch.setattr(etsy_token_service, "refresh_access_token", refresh)

    with pytest.raises(StoreNotConnectedError):
        get_valid_access_token(MagicMock(), _store(expires_in_minutes=2))


def test_refresh_server_error_bubbles_up(monkeypatch):
    refresh = MagicMock(side_effect=_http_error(503))
    monkeypatch.setattr(etsy_token_service, "refresh_access_token", refresh)

    with pytest.raises(httpx.HTTPStatusError):
        get_valid_access_token(MagicMock(), _store(expires_in_minutes=2))


def test_force_refresh_ignores_expiry(monkeypatch):
    refresh = MagicMock(
        return_value={
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "expires_in": 3600,
        }
    )
    monkeypatch.setattr(etsy_token_service, "refresh_access_token", refresh)

    store = _store(expires_in_minutes=30)  # still fresh, but Etsy rejected it
    token = get_valid_access_token(MagicMock(), store, force_refresh=True)

    assert token == "new-access"
    refresh.assert_called_once_with("old-refresh")
