"""Transactional email via the SendGrid v3 HTTP API.

Uses plain httpx instead of the sendgrid SDK — one endpoint doesn't
justify a dependency. Sends are best-effort: a mail failure must never
break the calling task, so errors are logged and swallowed.
"""

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

SENDGRID_SEND_URL = "https://api.sendgrid.com/v3/mail/send"


def send_email(to_email: str, subject: str, html: str) -> bool:
    """Send one email; returns True when SendGrid accepted it."""
    if not settings.SENDGRID_API_KEY:
        logger.info("SENDGRID_API_KEY not set; skipping email to %s", to_email)
        return False
    try:
        response = httpx.post(
            SENDGRID_SEND_URL,
            headers={"Authorization": f"Bearer {settings.SENDGRID_API_KEY}"},
            json={
                "personalizations": [{"to": [{"email": to_email}]}],
                "from": {"email": settings.FROM_EMAIL, "name": "Etsy AI Growth Agent"},
                "subject": subject,
                "content": [{"type": "text/html", "value": html}],
            },
            timeout=10,
        )
        response.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        logger.warning("SendGrid send to %s failed: %s", to_email, exc)
        return False


def low_credits_email_html(name: str | None, available: int, top_up_url: str) -> str:
    greeting = f"Hi {name}," if name else "Hi,"
    return f"""\
<div style="font-family: -apple-system, Segoe UI, sans-serif; max-width: 480px; margin: 0 auto;">
  <h2 style="color: #18181b;">You're running low on credits</h2>
  <p style="color: #3f3f46;">{greeting}</p>
  <p style="color: #3f3f46;">
    You have <strong>{available} credits</strong> left this billing cycle.
    Each daily agent run uses 5 credits, so your automated optimizations
    may pause soon.
  </p>
  <p style="margin: 24px 0;">
    <a href="{top_up_url}"
       style="background: #4f46e5; color: #fff; padding: 10px 20px;
              border-radius: 8px; text-decoration: none;">
      Top up or upgrade
    </a>
  </p>
  <p style="color: #a1a1aa; font-size: 12px;">
    Etsy AI Growth Agent &middot; You receive this because email
    notifications are enabled in your settings.
  </p>
</div>"""
