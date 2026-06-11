import os

# Provide safe defaults so app.core.config can load without a real .env
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/etsy_agent_test"
)
os.environ.setdefault(
    "DATABASE_URL_SYNC", "postgresql://postgres:postgres@localhost:5432/etsy_agent_test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "test-secret-key-only-for-tests-32chars!")
os.environ.setdefault("ETSY_TOKEN_ENCRYPTION_KEY", "0" * 64)
