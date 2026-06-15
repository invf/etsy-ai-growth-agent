"""Etsy listing constraints, enforced before any write hits the Etsy API."""

from app.schemas.seo import ETSY_MAX_TAG_LENGTH, ETSY_MAX_TAGS

ETSY_MAX_TITLE_LENGTH = 140
ETSY_MAX_DESCRIPTION_LENGTH = 102400


def validate_listing_update(fields: dict) -> list[str]:
    """Return a list of constraint violations (empty means valid)."""
    errors: list[str] = []

    if "description" in fields:
        description = fields["description"]
        if not isinstance(description, str) or not description.strip():
            errors.append("description must be a non-empty string")
        elif len(description) > ETSY_MAX_DESCRIPTION_LENGTH:
            errors.append(
                f"description exceeds {ETSY_MAX_DESCRIPTION_LENGTH} characters "
                f"({len(description)})"
            )

    if "title" in fields:
        title = fields["title"]
        if not isinstance(title, str) or not title.strip():
            errors.append("title must be a non-empty string")
        elif len(title) > ETSY_MAX_TITLE_LENGTH:
            errors.append(
                f"title exceeds {ETSY_MAX_TITLE_LENGTH} characters ({len(title)})"
            )

    if "tags" in fields:
        tags = fields["tags"]
        if not isinstance(tags, list) or not tags:
            errors.append("tags must be a non-empty list")
        else:
            if len(tags) > ETSY_MAX_TAGS:
                errors.append(f"more than {ETSY_MAX_TAGS} tags ({len(tags)})")
            empty = [t for t in tags if not isinstance(t, str) or not t.strip()]
            if empty:
                errors.append("tags must be non-empty strings")
            too_long = [t for t in tags if isinstance(t, str) and len(t) > ETSY_MAX_TAG_LENGTH]
            if too_long:
                errors.append(
                    f"tags exceed {ETSY_MAX_TAG_LENGTH} characters: {too_long}"
                )
            lowered = [t.lower() for t in tags if isinstance(t, str)]
            if len(set(lowered)) != len(lowered):
                errors.append("tags must be unique")

    return errors
