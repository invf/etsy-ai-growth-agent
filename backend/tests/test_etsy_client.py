import base64
import hashlib
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

from app.services import etsy_client
from app.services.etsy_client import OAUTH_SCOPES, build_etsy_oauth_url, compute_code_challenge


def test_code_challenge_is_base64url_sha256_without_padding():
    verifier = "test-verifier-string"
    expected = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    challenge = compute_code_challenge(verifier)
    assert challenge == expected
    assert "=" not in challenge


def test_build_oauth_url_contains_required_params():
    url = build_etsy_oauth_url(state="my-state", code_verifier="my-verifier")
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "www.etsy.com"
    assert parsed.path == "/oauth/connect"
    assert params["response_type"] == ["code"]
    assert params["state"] == ["my-state"]
    assert params["scope"] == [OAUTH_SCOPES]
    assert params["code_challenge_method"] == ["S256"]
    assert params["code_challenge"] == [compute_code_challenge("my-verifier")]


def test_update_listing_joins_tags_and_authenticates(monkeypatch):
    monkeypatch.setattr(etsy_client, "_throttle", lambda: None)
    response = MagicMock()
    response.json.return_value = {"listing_id": 111}
    patch = MagicMock(return_value=response)
    monkeypatch.setattr(etsy_client.httpx, "patch", patch)

    result = etsy_client.update_listing(
        "tok", "shop1", 111, {"title": "New Title", "tags": ["a", "b c"]}
    )

    assert result == {"listing_id": 111}
    response.raise_for_status.assert_called_once()
    args, kwargs = patch.call_args
    assert args[0].endswith("/application/shops/shop1/listings/111")
    assert kwargs["data"] == {"title": "New Title", "tags": "a,b c"}
    assert kwargs["headers"]["Authorization"] == "Bearer tok"
