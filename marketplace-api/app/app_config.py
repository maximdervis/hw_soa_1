"""Application configuration."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://marketplace:marketplace@db:5432/marketplace"
    jwt_secret: str = "change-me-in-production"
    access_token_minutes: int = 20
    refresh_token_days: int = 14
    order_rate_limit_minutes: int = 5

    class Config:
        env_prefix = "APP_"


settings = Settings()
