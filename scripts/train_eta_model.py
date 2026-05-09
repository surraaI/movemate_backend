from __future__ import annotations

import csv
import statistics
import time
from dataclasses import dataclass
from pathlib import Path

import joblib
from sklearn.base import clone
from sklearn.ensemble import (
    ExtraTreesRegressor,
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.feature_extraction import DictVectorizer
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split


@dataclass
class TrainingRow:
    day_of_week: int
    beginning_hour: int
    mileage_km: float
    initial_latitude: float
    initial_longitude: float
    final_latitude: float
    final_longitude: float
    month: int
    avg_speed_kph: float
    target_minutes: float


def log(message: str) -> None:
    print(f"[INFO] {message}")


def _safe_float(value: str | None) -> float | None:
    if value is None or value.strip() == "":
        return None

    try:
        return float(value)
    except ValueError:
        return None


def _safe_int(value: str | None) -> int | None:
    parsed = _safe_float(value)
    return int(parsed) if parsed is not None else None


def load_training_rows(dataset_path: Path) -> list[TrainingRow]:
    log(f"Loading dataset from: {dataset_path}")

    rows: list[TrainingRow] = []
    skipped = 0

    start = time.perf_counter()

    with dataset_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for index, raw in enumerate(reader, start=1):
            day = _safe_int(raw.get("DayofWeek"))
            hour = _safe_int(raw.get("Beginning Time"))
            mileage = _safe_float(raw.get("Mileage"))
            initial_lat = _safe_float(raw.get("Initial latitude "))
            initial_lon = _safe_float(raw.get("Initial longitude"))
            final_lat = _safe_float(raw.get("Final latitude"))
            final_lon = _safe_float(raw.get("Final longitude"))
            month = _safe_int(raw.get("Month"))
            avg_speed = _safe_float(raw.get("Avg_Speed"))
            total_time = _safe_float(raw.get("total_time"))

            if None in (
                day,
                hour,
                mileage,
                initial_lat,
                initial_lon,
                final_lat,
                final_lon,
                month,
                avg_speed,
                total_time,
            ):
                skipped += 1
                continue

            if total_time <= 0 or mileage <= 0:
                skipped += 1
                continue

            rows.append(
                TrainingRow(
                    day_of_week=max(0, min(6, day)),
                    beginning_hour=max(0, min(23, hour)),
                    mileage_km=mileage,
                    initial_latitude=initial_lat,
                    initial_longitude=initial_lon,
                    final_latitude=final_lat,
                    final_longitude=final_lon,
                    month=max(1, min(12, month)),
                    avg_speed_kph=max(0.0, avg_speed),
                    target_minutes=total_time,
                )
            )

            if index % 10000 == 0:
                log(f"Processed {index:,} rows...")

    duration = time.perf_counter() - start

    log(f"Loaded usable rows: {len(rows):,}")
    log(f"Skipped rows: {skipped:,}")
    log(f"Dataset loading took: {duration:.2f} seconds")

    return rows


def build_features(rows: list[TrainingRow]):
    log("Building feature dictionaries...")

    feature_dicts = []

    for row in rows:
        feature_dicts.append(
            {
                "day_of_week": row.day_of_week,
                "beginning_hour": row.beginning_hour,
                "mileage_km": row.mileage_km,
                "initial_latitude": row.initial_latitude,
                "initial_longitude": row.initial_longitude,
                "final_latitude": row.final_latitude,
                "final_longitude": row.final_longitude,
                "month": row.month,
                "avg_speed_kph": row.avg_speed_kph,

                # derived features
                "lat_diff": abs(row.final_latitude - row.initial_latitude),
                "lon_diff": abs(row.final_longitude - row.initial_longitude),
            }
        )

    targets = [row.target_minutes for row in rows]

    return feature_dicts, targets


def train_model(name, estimator, x_train, y_train, x_test, y_test):
    log(f"Training model: {name}")

    start = time.perf_counter()

    estimator.fit(x_train, y_train)

    training_time = time.perf_counter() - start

    predictions = estimator.predict(x_test)

    mae = mean_absolute_error(y_test, predictions)

    log(f"{name} completed")
    log(f"{name} MAE: {mae:.3f} minutes")
    log(f"{name} training time: {training_time:.2f} seconds")

    return mae, estimator


def main() -> None:
    total_start = time.perf_counter()

    project_root = Path(__file__).resolve().parents[1]

    dataset_path = project_root / "ETA_datasets" / "final_data.csv"

    model_path = project_root / "ETA_datasets" / "eta_model.joblib"

    rows = load_training_rows(dataset_path)

    if len(rows) < 100:
        raise RuntimeError(
            f"Not enough usable rows for training: {len(rows)}"
        )

    feature_dicts, targets = build_features(rows)

    # HistGradientBoostingRegressor requires dense input; use dense features for all models.
    test_size = 0.2
    selection_seeds = [0, 1, 2]  # repeated splits for robust selection metrics
    holdout_seed = 42  # single holdout to report final "large model" MAE

    # Keep selection models relatively small for speed, then retrain a larger-capacity
    # model on the full dataset for improved accuracy.
    candidate_models_small = {
        "extra_trees": ExtraTreesRegressor(
            n_estimators=80,
            max_depth=20,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1,
        ),
        "random_forest": RandomForestRegressor(
            n_estimators=60,
            max_depth=18,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1,
        ),
        "hist_gradient_boosting": HistGradientBoostingRegressor(
            learning_rate=0.05,
            max_depth=8,
            max_iter=250,
            early_stopping=True,
            random_state=42,
        ),
    }

    candidate_models_large = {
        "extra_trees": ExtraTreesRegressor(
            n_estimators=600,
            max_depth=None,
            min_samples_leaf=1,
            random_state=42,
            n_jobs=-1,
        ),
        "random_forest": RandomForestRegressor(
            n_estimators=400,
            max_depth=None,
            min_samples_leaf=1,
            random_state=42,
            n_jobs=-1,
        ),
        "hist_gradient_boosting": HistGradientBoostingRegressor(
            learning_rate=0.03,
            max_depth=None,
            max_iter=800,
            early_stopping=True,
            n_iter_no_change=20,
            random_state=42,
        ),
    }

    log("Robust evaluation across multiple splits...")
    selection_stats: dict[str, dict[str, object]] = {}
    best_name = ""
    best_selection_mean = float("inf")

    for name, base_estimator in candidate_models_small.items():
        maes: list[float] = []

        for seed in selection_seeds:
            x_train_dicts, x_test_dicts, y_train, y_test = train_test_split(
                feature_dicts,
                targets,
                test_size=test_size,
                random_state=seed,
            )

            vectorizer = DictVectorizer(sparse=False)
            x_train = vectorizer.fit_transform(x_train_dicts)
            x_test = vectorizer.transform(x_test_dicts)

            estimator = clone(base_estimator)
            mae, _ = train_model(
                name=f"{name} (seed={seed})",
                estimator=estimator,
                x_train=x_train,
                y_train=y_train,
                x_test=x_test,
                y_test=y_test,
            )
            maes.append(float(mae))

        maes_mean = float(statistics.mean(maes))
        maes_std = float(statistics.pstdev(maes)) if len(maes) > 1 else 0.0

        selection_stats[name] = {
            "mae_values_minutes": maes,
            "mae_mean_minutes": maes_mean,
            "mae_std_minutes": maes_std,
        }

        log(f"{name} selection MAE mean: {maes_mean:.3f}, std: {maes_std:.3f}")

        if maes_mean < best_selection_mean:
            best_selection_mean = maes_mean
            best_name = name

    if not best_name:
        raise RuntimeError("Training failed: no best model selected")

    log(f"Best model selected for final training: {best_name}")

    # Holdout evaluation for the chosen large-capacity model.
    log("Evaluating larger-capacity model on a holdout split...")
    holdout_train_dicts, holdout_test_dicts, y_train, y_test = train_test_split(
        feature_dicts,
        targets,
        test_size=test_size,
        random_state=holdout_seed,
    )
    vectorizer_holdout = DictVectorizer(sparse=False)
    x_holdout_train = vectorizer_holdout.fit_transform(holdout_train_dicts)
    x_holdout_test = vectorizer_holdout.transform(holdout_test_dicts)

    best_large_estimator = candidate_models_large[best_name]
    holdout_estimator = clone(best_large_estimator)
    holdout_mae, _ = train_model(
        name=f"{best_name} (large, holdout_seed={holdout_seed})",
        estimator=holdout_estimator,
        x_train=x_holdout_train,
        y_train=y_train,
        x_test=x_holdout_test,
        y_test=y_test,
    )

    # Final training: fit the chosen large-capacity model on ALL data.
    log("Training final large-capacity model on full dataset...")
    vectorizer_final = DictVectorizer(sparse=False)
    x_full = vectorizer_final.fit_transform(feature_dicts)
    final_estimator = clone(best_large_estimator)
    final_estimator.fit(x_full, targets)

    bundle = {
        "model": final_estimator,
        "vectorizer": vectorizer_final,
        "metrics": {
            "best_model": best_name,
            "selection": selection_stats,
            "best_selection_mae_mean_minutes": float(best_selection_mean),
            "final_holdout_mae_minutes": float(holdout_mae),
            "test_size": float(test_size),
            "selection_seeds": selection_seeds,
            "holdout_seed": holdout_seed,
            "rows": len(rows),
        },
        "feature_names": list(feature_dicts[0].keys()),
    }

    model_path.parent.mkdir(parents=True, exist_ok=True)

    log("Saving trained model...")

    joblib.dump(bundle, model_path)

    total_time = time.perf_counter() - total_start

    log(f"Model saved to: {model_path}")
    log(f"Selection best MAE mean: {best_selection_mean:.3f} minutes")
    log(f"Final large-model holdout MAE: {holdout_mae:.3f} minutes")
    log(f"Total training time: {total_time:.2f} seconds")


if __name__ == "__main__":
    main()