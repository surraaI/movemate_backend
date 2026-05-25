from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import joblib

from app.core.config import settings


def ensure_eta_model_available() -> Path:
    """Return the local ETA model path if it exists."""
    model_path = Path(settings.ETA_MODEL_PATH).expanduser()
    if not model_path.exists():
        raise FileNotFoundError(
            f"ETA model not found at {model_path}. Place eta_model.joblib in ETA_datasets/ or update ETA_MODEL_PATH."
        )
    return model_path


def load_eta_model_bundle() -> dict[str, Any]:
    """Load the local ETA model bundle saved by scripts/train_eta_model.py."""
    model_path = ensure_eta_model_available()
    bundle = joblib.load(model_path)
    if not isinstance(bundle, Mapping):
        raise TypeError("ETA model bundle must be a mapping with model and vectorizer entries")
    if "model" not in bundle or "vectorizer" not in bundle:
        raise KeyError("ETA model bundle is missing required model or vectorizer entries")
    return dict(bundle)
