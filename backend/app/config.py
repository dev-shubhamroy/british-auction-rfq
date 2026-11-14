from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres@localhost:5432/rfq_auction"
    test_database_url: str = "postgresql+psycopg://postgres@localhost:5432/rfq_auction_test"
    cors_origins: str = "http://localhost:5173"

    closer_interval_seconds: int = 5


settings = Settings()
