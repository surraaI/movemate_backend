from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from pathlib import Path

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore"
    )

    # 🔹 App Info
    PROJECT_NAME: str = "MoveMate API"
    VERSION: str = "0.1.0"

    # 🔹 Database
    DATABASE_URL: str = "postgresql+psycopg://user:password@localhost:5432/movemate"

    # 🔹 Auth
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # 🔥 Firebase Config
    FIREBASE_SERVICE_ACCOUNT: str
    FIREBASE_PROJECT_ID: str

    # ✅ Normalize DB URL
    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if isinstance(value, str) and value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    # 🔥 Validate Firebase path
    @field_validator("FIREBASE_SERVICE_ACCOUNT")
    @classmethod
    def validate_firebase_path(cls, value: str) -> str:
        path = Path(value)
        if not path.exists():
            raise ValueError(f"Firebase service account file not found: {value}")
        return value


# Singleton instance
settings = Settings()