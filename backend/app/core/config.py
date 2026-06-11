from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    DATABASE_URL_SYNC: str
    REDIS_URL: str
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    SECRET_KEY: str
    ETSY_TOKEN_ENCRYPTION_KEY: str
    ANTHROPIC_API_KEY: str = ""
    VOYAGE_API_KEY: str = ""
    ETSY_CLIENT_ID: str = ""
    ETSY_CLIENT_SECRET: str = ""
    ETSY_REDIRECT_URI: str = ""
    PADDLE_API_KEY: str = ""
    PADDLE_CLIENT_TOKEN: str = ""
    PADDLE_WEBHOOK_SECRET: str = ""
    PADDLE_ENVIRONMENT: str = "sandbox"
    SENDGRID_API_KEY: str = ""
    FROM_EMAIL: str = "hello@etsyagent.com"
    SENTRY_DSN: str = ""
    APP_ENV: str = "development"
    FRONTEND_URL: str = "http://localhost:3000"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24


settings = Settings()
