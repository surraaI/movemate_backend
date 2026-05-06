from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

    PROJECT_NAME: str = "MoveMate API"
    VERSION: str = "0.1.0"

    DATABASE_URL: str = "postgresql+psycopg://user:password@localhost:5432/movemate"
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Firebase config
    FIREBASE_SERVICE_ACCOUNT: str
    FIREBASE_PROJECT_ID: str

    # Chapa payment config
    CHAPA_SECRET_KEY: str
    CHAPA_BASE_URL: str = "https://api.chapa.co/v1"
    CHAPA_CALLBACK_URL: str = "http://localhost:8000/api/v1/tickets/callback"
    CHAPA_RETURN_URL: str = "http://localhost:8000/success"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        # Accept legacy postgres URL format and pin to psycopg driver.
        if isinstance(value, str) and value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value


settings = Settings()

