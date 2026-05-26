from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Environment-backed configuration for the rerouting subsystem."""

    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

    REROUTING_CAPACITY_THRESHOLD: float = Field(default=0.75, ge=0.0, le=1.0)
    REROUTING_CONGESTION_PERCENTILE: float = Field(default=80.0, ge=0.0, le=100.0)
    REROUTING_MIN_ROWS_FOR_PHASE_TRANSITION: int = Field(default=5_000, ge=0)
    REROUTING_MIN_ROWS_FOR_RETRAIN: int = Field(default=500, ge=0)
    REROUTING_RETRAIN_HOUR: int = Field(default=2, ge=0, le=23)
    REROUTING_RETRAIN_MINUTE: int = Field(default=0, ge=0, le=59)
    REROUTING_MODEL_SAVE_PATH: str = Field(default="rerouting_models")
    REROUTING_OSMNX_PLACE_NAME: str = Field(default="Addis Ababa, Ethiopia")
    REROUTING_LOW_SPEED_THRESHOLD_KPH: float = Field(default=12.0, ge=0.0)
    REROUTING_DEFAULT_BUS_CAPACITY: int = Field(default=60, ge=1)
    REROUTING_KEEP_LAST_MODEL_VERSIONS: int = Field(default=3, ge=1)
    REROUTING_DEFAULT_TIME_WINDOW_MINUTES: int = Field(default=15, ge=1)
    REROUTING_PREDICTION_WINDOWS: int = Field(default=3, ge=1)
    REROUTING_GRAPH_NETWORK_TYPE: str = Field(default="drive")
    REROUTING_MODEL_REGISTRY_FILE: str = Field(default="active_model.json")

    @property
    def model_directory(self) -> Path:
        """Return the filesystem location where model artifacts are stored."""

        return Path(self.REROUTING_MODEL_SAVE_PATH)


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Return a cached config instance."""

    return Config()


settings = get_config()
