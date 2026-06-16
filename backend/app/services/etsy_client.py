import base64
import hashlib
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.services.rate_limiter import get_etsy_rate_limiter

ETSY_OAUTH_CONNECT_URL = "https://www.etsy.com/oauth/connect"
ETSY_OAUTH_TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"
ETSY_API_BASE = "https://openapi.etsy.com/v3"

OAUTH_SCOPES = "listings_r listings_w shops_r shops_w transactions_r"


def _throttle() -> None:
    """Take one token from the app-wide Etsy bucket (ETSY_RATE_LIMIT_QPS) before any call."""
    get_etsy_rate_limiter().acquire()


def _api_headers(access_token: str) -> dict[str, str]:
    """Headers for authenticated v3 application calls.

    Etsy requires x-api-key to be "<keystring>:<shared_secret>" (a bare
    keystring returns 403 "Shared secret is required in x-api-key header").
    """
    return {
        "x-api-key": f"{settings.ETSY_CLIENT_ID}:{settings.ETSY_CLIENT_SECRET}",
        "Authorization": f"Bearer {access_token}",
    }


def _public_headers() -> dict[str, str]:
    """Headers for public (no-OAuth) v3 endpoints like marketplace search."""
    return {"x-api-key": f"{settings.ETSY_CLIENT_ID}:{settings.ETSY_CLIENT_SECRET}"}


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
    _throttle()
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


def refresh_access_token(refresh_token: str) -> dict:
    """Refresh an expired access token.

    Returns {access_token, refresh_token, token_type, expires_in}.
    """
    _throttle()
    resp = httpx.post(
        ETSY_OAUTH_TOKEN_URL,
        json={
            "grant_type": "refresh_token",
            "client_id": settings.ETSY_CLIENT_ID,
            "refresh_token": refresh_token,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def get_shop_listings(
    access_token: str, shop_id: str, limit: int = 100, offset: int = 0
) -> dict:
    """One page of active listings: {count, results: [...]}. Max limit is 100."""
    _throttle()
    resp = httpx.get(
        f"{ETSY_API_BASE}/application/shops/{shop_id}/listings/active",
        headers=_api_headers(access_token),
        params={"limit": limit, "offset": offset, "includes": "Images"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def search_active_listings(
    keywords: str,
    limit: int = 24,
    taxonomy_id: int | None = None,
    sort_on: str = "score",
    sort_order: str = "down",
) -> dict:
    """Public marketplace search: {count, results: [...]}.

    Powers competitor/keyword context for SEO analysis — finds the listings a
    buyer sees when they search ``keywords``. Public endpoint (x-api-key only,
    no OAuth). ``sort_on=score`` returns Etsy's own relevancy ranking.
    """
    _throttle()
    params: dict[str, str | int] = {
        "keywords": keywords,
        "limit": limit,
        "sort_on": sort_on,
        "sort_order": sort_order,
    }
    if taxonomy_id:
        params["taxonomy_id"] = taxonomy_id
    resp = httpx.get(
        f"{ETSY_API_BASE}/application/listings/active",
        headers=_public_headers(),
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def get_listing_images(access_token: str, etsy_listing_id: int) -> dict:
    """Images for one listing: {count, results: [...]}.

    The shop listings collection endpoint ignores includes=Images, so images
    have to be fetched per listing. getListingImages is listing-scoped
    (NOT shop-scoped — the /shops/... path is the POST upload endpoint).
    """
    _throttle()
    resp = httpx.get(
        f"{ETSY_API_BASE}/application/listings/{etsy_listing_id}/images",
        headers=_api_headers(access_token),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def update_listing(
    access_token: str, shop_id: str, etsy_listing_id: int, fields: dict
) -> dict:
    """Write listing changes (title/tags/description) back to Etsy.

    Etsy v3 updateListing is a form-encoded PATCH; tags go as a
    comma-separated string.
    """
    _throttle()
    data = dict(fields)
    if isinstance(data.get("tags"), list):
        data["tags"] = ",".join(data["tags"])
    resp = httpx.patch(
        f"{ETSY_API_BASE}/application/shops/{shop_id}/listings/{etsy_listing_id}",
        headers=_api_headers(access_token),
        data=data,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_current_shop(access_token: str) -> dict:
    """Fetch the shop belonging to the authenticated Etsy user.

    getShopByOwnerUserId needs a numeric user_id, not the `me` alias (which
    returns 400 "Expected int value for 'user_id'"). Etsy prefixes the access
    token with that user_id: "<user_id>.<token>".
    """
    user_id = access_token.split(".")[0]
    _throttle()
    resp = httpx.get(
        f"{ETSY_API_BASE}/application/users/{user_id}/shops",
        headers=_api_headers(access_token),
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    # Etsy returns either a single shop object or {count, results: [...]}
    if "results" in data:
        return data["results"][0]
    return data
