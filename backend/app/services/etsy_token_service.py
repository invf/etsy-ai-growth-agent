from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.encryption import decrypt, encrypt
from app.db.models.store import Store
from app.services.etsy_client import refresh_access_token

REFRESH_MARGIN = timedelta(minutes=5)


class StoreNotConnectedError(Exception):
    """Store has no usable Etsy tokens; user must reconnect via OAuth."""


def get_valid_access_token(db: Session, store: Store) -> str:
    """Return a decrypted access token, refreshing and persisting it if stale."""
    if not store.etsy_access_token or not store.etsy_refresh_token:
        raise StoreNotConnectedError(f"Store {store.id} has no Etsy tokens")

    expires_at = store.token_expires_at
    if expires_at and expires_at > datetime.now(timezone.utc) + REFRESH_MARGIN:
        return decrypt(store.etsy_access_token)

    tokens = refresh_access_token(decrypt(store.etsy_refresh_token))
    store.etsy_access_token = encrypt(tokens["access_token"])
    store.etsy_refresh_token = encrypt(tokens["refresh_token"])
    store.token_expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=tokens["expires_in"]
    )
    db.flush()
    return tokens["access_token"]
