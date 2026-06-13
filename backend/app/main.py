import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    agent,
    auth,
    billing,
    listings,
    notifications,
    optimizations,
    seo,
    stores,
    webhooks,
)
from app.core.config import settings

if settings.APP_ENV == "production" and settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.APP_ENV,
        release="etsy-agent-backend@0.1.0",
        traces_sample_rate=0.1,
        send_default_pii=False,
    )

app = FastAPI(
    title="Etsy AI Growth Agent API",
    version="0.1.0",
    docs_url="/docs" if settings.APP_ENV != "production" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Credits-Available", "X-Credits-Balance", "X-Request-Id"],
)

app.include_router(auth.router, prefix="/v1")
app.include_router(stores.router, prefix="/v1")
app.include_router(listings.router, prefix="/v1")
app.include_router(seo.router, prefix="/v1")
app.include_router(optimizations.router, prefix="/v1")
app.include_router(agent.router, prefix="/v1")
app.include_router(billing.router, prefix="/v1")
app.include_router(notifications.router, prefix="/v1")
app.include_router(webhooks.router)  # Paddle posts to /webhooks/paddle (no /v1)


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}
