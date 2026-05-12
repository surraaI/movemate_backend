from __future__ import annotations

import shutil
from pathlib import Path

from huggingface_hub import hf_hub_download

from app.core.config import settings


def ensure_eta_model_downloaded() -> Path:
    """
    Ensure ETA model exists locally.
    If missing and a Hugging Face repo is configured, download and cache it.
    """
    model_path = Path(settings.ETA_MODEL_PATH).expanduser()
    if model_path.exists():
        return model_path

    if not settings.ETA_MODEL_HF_REPO_ID:
        return model_path

    model_path.parent.mkdir(parents=True, exist_ok=True)

    downloaded = Path(
        hf_hub_download(
            repo_id=settings.ETA_MODEL_HF_REPO_ID,
            filename=settings.ETA_MODEL_HF_FILENAME,
            revision=settings.ETA_MODEL_HF_REVISION,
            token=settings.HUGGINGFACE_HUB_TOKEN,
            local_dir=str(model_path.parent),
        )
    )

    if downloaded.resolve() != model_path.resolve():
        shutil.copy2(downloaded, model_path)

    return model_path
