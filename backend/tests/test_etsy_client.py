import base64
import hashlib
from urllib.parse import parse_qs, urlparse

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
