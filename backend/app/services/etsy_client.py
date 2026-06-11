import base64
import hashlib
from urllib.parse import urlencode

import httpx

from app.core.config import settings

ETSY_OAUTH_CONNECT_URL = "https://www.etsy.com/oauth/connect"
ETSY_OAUTH_TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"
ETSY_API_BASE = "https://openapi.etsy.com/v3"

OAUTH_SCOPES = "listings_r listings_w shops_r shops_w transactions_r"


def compute_code_challenge(code_verifier: str) -> str:
    """PKCE S256: base64url(sha256(code_verifier)) without padding."""
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def build_etsy_oauth_url(state: str, code_verifier: str) -> str:
    params = {
        "response_type": "code",
        "client_id": settings.ETSY_CLIENT_ID,
        "redirect_uri": settings.ETSY_REDIRECT_URI,
        "scope": OAUTH_SCOPES,
        "state": state,
        "code_challenge": compute_code_challenge(code_verifier),
        "code_challenge_method": "S256",
    }
    return f"{ETSY_OAUTH_CONNECT_URL}?{urlencode(params)}"


def exchange_oauth_code(code: str, code_verifier: str) -> dict:
    """Exchange authorization code for tokens.

    Returns {access_token, refresh_token, token_type, expires_in}.
    """
    resp = httpx.post(
        ETSY_OAUTH_TOKEN_URL,
        json={
            "grant_type": "authorization_code",
            "client_id": settings.ETSY_CLIENT_ID,
            "redirect_uri": settings.ETSY_REDIRECT_URI,
            "code": code,
            "code_verifier": code_verifier,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_current_shop(access_token: str) -> dict:
    """Fetch the shop belonging to the authenticated Etsy user."""
    resp = httpx.get(
        f"{ETSY_API_BASE}/application/users/me/shops",
        headers={
            "x-api-key": settings.ETSY_CLIENT_ID,
            "Authorization": f"Bearer {access_token}",
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    # Etsy returns either a single shop object or {count, results: [...]}
    if "results" in data:
        return data["results"][0]
    return data
