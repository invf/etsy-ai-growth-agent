from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.orm import Session

from app.core.encryption import decrypt, encrypt
from app.db.models.store import Store
from app.services.etsy_client import refresh_access_token

REFRESH_MARGIN = timedelta(minutes=5)


class StoreNotConnectedError(Exception):
    """Store has no usable Etsy tokens; user must reconnect via OAuth."""


def get_valid_access_token(
    db: Session, store: Store, force_refresh: bool = False
) -> str:
    """Return a decrypted access token, refreshing and persisting it if stale.

    force_refresh skips the expiry check — used after Etsy rejects a token
    that looked valid (e.g. revoked server-side).
    """
    if not store.etsy_access_token or not store.etsy_refresh_token:
        raise StoreNotConnectedError(f"Store {store.id} has no Etsy tokens")

    expires_at = store.token_expires_at
    if (
        not force_refresh
        and expires_at
        and expires_at > datetime.now(timezone.utc) + REFRESH_MARGIN
    ):
        return decrypt(store.etsy_access_token)

    try:
        tokens = refresh_access_token(decrypt(store.etsy_refresh_token))
    except httpx.HTTPStatusError as exc:
        # 400/401 means the refresh token itself is invalid or revoked —
        # retrying is pointless, the user must reconnect via OAuth
        if exc.response.status_code in (400, 401):
            raise StoreNotConnectedError(
                f"Etsy rejected the refresh token for store {store.id}"
            ) from exc
        raise
    store.etsy_access_token = encrypt(tokens["access_token"])
    store.etsy_refresh_token = encrypt(tokens["refresh_token"])
    store.token_expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=tokens["expires_in"]
    )
    db.flush()
    return tokens["access_token"]
