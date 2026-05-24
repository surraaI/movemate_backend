from __future__ import annotations

import csv
import statistics
import time
from dataclasses import dataclass
from math import asin, cos, pi, radians, sin, sqrt
from pathlib import Path

import joblib
import numpy as np
from sklearn.base import clone
from sklearn.ensemble import (
    ExtraTreesRegressor,
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.feature_extraction import DictVectorizer
from sklearn.metrics import (
    mean_absolute_error,
    mean_absolute_percentage_error,
    mean_squared_error,
    r2_score,
)
from sklearn.model_selection import train_test_split


# ── constants ─────────────────────────────────────────────────────────────────

COMPRESS  = ("zlib", 6)  # level 6 balances size vs load speed
TARGET_MB = 300.0


# ── data model ────────────────────────────────────────────────────────────────

@dataclass
class TrainingRow:
    day_of_week:      int    # 0–6  (DayofWeek)
    hour_of_day:      int    # 0–23 (TimeRange — confirmed to be the hour)
    beginning_minute: int    # 0–59 (Beginning Time — minute within the hour)
    mileage_km:       float  # driven distance; obtainable from a routing API pre-trip
    initial_latitude:  float
    initial_longitude: float
    final_latitude:    float
    final_longitude:   float
    month:             int   # 1–12
    target_hours:      float # total_time in hours — the prediction target


# ── helpers ───────────────────────────────────────────────────────────────────

def log(message: str) -> None:
    print(f"[INFO] {message}")


def separator(title: str = "") -> None:
    width = 60
    if title:
        pad = (width - len(title) - 2) // 2
        right = width - pad - len(title) - 2
        print(f"\n{'─' * pad} {title} {'─' * right}")
    else:
        print("─" * width)


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


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two (lat, lon) points."""
    R    = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a    = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return R * 2 * asin(sqrt(a))


# ── data loading ──────────────────────────────────────────────────────────────

def load_training_rows(dataset_path: Path) -> list[TrainingRow]:
    log(f"Loading dataset from: {dataset_path}")

    rows:    list[TrainingRow] = []
    skipped: int               = 0
    start                      = time.perf_counter()

    with dataset_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for index, raw in enumerate(reader, start=1):
            day        = _safe_int(raw.get("DayofWeek"))
            hour       = _safe_int(raw.get("TimeRange"))       # hour of day
            begin_min  = _safe_int(raw.get("Beginning Time"))  # minute within the hour
            mileage    = _safe_float(raw.get("Mileage"))
            init_lat   = _safe_float(raw.get("Initial latitude "))
            init_lon   = _safe_float(raw.get("Initial longitude"))
            fin_lat    = _safe_float(raw.get("Final latitude"))
            fin_lon    = _safe_float(raw.get("Final longitude"))
            month      = _safe_int(raw.get("Month"))
            total_time = _safe_float(raw.get("total_time"))

            # avg_speed_kph is intentionally excluded — it equals mileage / total_time,
            # which directly leaks the prediction target and produces artificially
            # perfect training accuracy that does not hold in production.
            # End Time is excluded — it is post-trip information.

            if None in (day, hour, begin_min, mileage,
                        init_lat, init_lon, fin_lat, fin_lon, month, total_time):
                skipped += 1
                continue

            if total_time <= 0 or mileage <= 0:
                skipped += 1
                continue

            rows.append(
                TrainingRow(
                    day_of_week=max(0, min(6, day)),
                    hour_of_day=max(0, min(23, hour)),
                    beginning_minute=max(0, min(59, begin_min)),
                    mileage_km=mileage,
                    initial_latitude=init_lat,
                    initial_longitude=init_lon,
                    final_latitude=fin_lat,
                    final_longitude=fin_lon,
                    month=max(1, min(12, month)),
                    target_hours=total_time,
                )
            )

            if index % 10000 == 0:
                log(f"  Processed {index:,} rows...")

    duration = time.perf_counter() - start
    log(f"Loaded {len(rows):,} usable rows  ({skipped:,} skipped)  in {duration:.2f}s")
    return rows


# ── feature engineering ───────────────────────────────────────────────────────

def build_features(rows: list[TrainingRow]) -> tuple[list[dict], list[float]]:
    """
    All features are available BEFORE a trip starts.

    Temporal:
      hour_of_day / hour_sin / hour_cos     — time of day with cyclical encoding
      beginning_minute / minute_sin / cos   — minute within the hour, cyclically encoded
      start_minute_of_day                   — absolute minute 0–1439 (hour*60 + minute)
      day_of_week / day_sin / day_cos       — weekday with cyclical encoding
      month                                 — seasonal signal

    Spatial:
      mileage_km                            — actual route distance (from routing API)
      haversine_km                          — straight-line origin→destination distance
      route_factor                          — mileage / haversine (detour ratio)
      lat_diff / lon_diff                   — coordinate deltas
      initial/final lat/lon                 — absolute position (area-level traffic patterns)

    Excluded:
      avg_speed_kph  — equals mileage / total_time; leaks the target
      End Time       — only known after the trip ends
    """
    log("Building feature dictionaries...")

    feature_dicts: list[dict] = []

    for row in rows:
        straight_km = haversine_km(
            row.initial_latitude,  row.initial_longitude,
            row.final_latitude,    row.final_longitude,
        )

        # Cyclical encodings: model sees 23→0 and 6→0 as small gaps, not large ones
        hour_rad   = 2 * pi * row.hour_of_day      / 24
        min_rad    = 2 * pi * row.beginning_minute  / 60
        day_rad    = 2 * pi * row.day_of_week       / 7

        feature_dicts.append({
            # temporal
            "hour_of_day":         row.hour_of_day,
            "hour_sin":            sin(hour_rad),
            "hour_cos":            cos(hour_rad),
            "beginning_minute":    row.beginning_minute,
            "minute_sin":          sin(min_rad),
            "minute_cos":          cos(min_rad),
            "start_minute_of_day": row.hour_of_day * 60 + row.beginning_minute,
            "day_of_week":         row.day_of_week,
            "day_sin":             sin(day_rad),
            "day_cos":             cos(day_rad),
            "month":               row.month,
            # spatial
            "mileage_km":          row.mileage_km,
            "haversine_km":        straight_km,
            "route_factor":        row.mileage_km / max(straight_km, 0.01),
            "lat_diff":            abs(row.final_latitude  - row.initial_latitude),
            "lon_diff":            abs(row.final_longitude - row.initial_longitude),
            "initial_latitude":    row.initial_latitude,
            "initial_longitude":   row.initial_longitude,
            "final_latitude":      row.final_latitude,
            "final_longitude":     row.final_longitude,
        })

    targets = [row.target_hours for row in rows]
    return feature_dicts, targets


# ── model training ────────────────────────────────────────────────────────────

def train_model(name, estimator, x_train, y_train, x_test, y_test):
    log(f"Training: {name}")
    t0      = time.perf_counter()
    estimator.fit(x_train, y_train)
    elapsed = time.perf_counter() - t0
    preds   = estimator.predict(x_test)
    mae     = mean_absolute_error(y_test, preds)
    log(f"  MAE={mae:.4f}h ({mae * 60:.2f} min)  time={elapsed:.1f}s")
    return mae, estimator


# ── evaluation ────────────────────────────────────────────────────────────────

def evaluate(
    model,
    vectorizer,
    feature_dicts: list[dict],
    targets: list[float],
    bundle_metrics: dict,
    model_path: Path,
) -> None:
    separator("Evaluation  —  held-out 20% test split")

    _, x_test_dicts, _, y_test = train_test_split(
        feature_dicts, targets, test_size=0.2, random_state=42
    )
    x_test = vectorizer.transform(x_test_dicts)
    y_test = np.array(y_test)

    t0     = time.perf_counter()
    y_pred = model.predict(x_test)
    inf_ms = (time.perf_counter() - t0) * 1000

    mae    = mean_absolute_error(y_test, y_pred)
    rmse   = mean_squared_error(y_test, y_pred) ** 0.5
    mape   = mean_absolute_percentage_error(y_test, y_pred) * 100
    r2     = r2_score(y_test, y_pred)
    errors = np.abs(y_test - y_pred)

    def fmt(h: float) -> str:
        return f"{h:.4f}h  ({h * 60:.2f} min)"

    print(f"\n  Samples          : {len(y_test):,}")
    print(f"  Inference        : {inf_ms:.1f} ms total  ({inf_ms / len(y_test) * 1000:.2f} µs/sample)")
    print()
    print(f"  MAE              : {fmt(mae)}")
    print(f"  RMSE             : {fmt(rmse)}")
    print(f"  MAPE             : {mape:.2f}%")
    print(f"  R²               : {r2:.6f}")
    print()
    print("  Error percentiles:")
    for p in [50, 75, 90, 95, 99]:
        v = np.percentile(errors, p)
        print(f"    p{p:>2}           : {fmt(v)}")

    separator("Feature importance")
    feature_names = bundle_metrics.get("feature_names", list(vectorizer.feature_names_))
    if hasattr(model, "feature_importances_"):
        ranked = sorted(
            zip(feature_names, model.feature_importances_),
            key=lambda x: x[1],
            reverse=True,
        )
        for fname, imp in ranked:
            bar = "█" * int(imp * 50)
            print(f"  {fname:<24} {imp:.4f}  {bar}")
    else:
        print("  (not available for this model type)")

    separator("Summary")
    size_mb = model_path.stat().st_size / 1e6
    print(f"  Model type       : {bundle_metrics['best_model']}")
    print(f"  Trained rows     : {bundle_metrics['rows']:,}")
    print(f"  File size        : {size_mb:.1f} MB")
    print(f"  Selection MAE    : {bundle_metrics['best_selection_mae_mean_minutes']:.4f}h  "
          f"({bundle_metrics['best_selection_mae_mean_minutes'] * 60:.2f} min)")
    print(f"  Holdout MAE      : {bundle_metrics['final_holdout_mae_minutes']:.4f}h  "
          f"({bundle_metrics['final_holdout_mae_minutes'] * 60:.2f} min)")

    if size_mb > TARGET_MB:
        print(f"\n  ⚠  Model is {size_mb:.1f} MB — exceeds {TARGET_MB:.0f} MB target.")
        print("     Reduce n_estimators or max_depth and retrain.")
    else:
        print(f"\n  ✓  Model is {size_mb:.1f} MB — within the {TARGET_MB:.0f} MB target.")

    separator()


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    total_start = time.perf_counter()

    project_root = Path(__file__).resolve().parents[1]
    dataset_path = project_root / "ETA_datasets" / "final_data.csv"
    model_path   = project_root / "ETA_datasets" / "eta_model.joblib"

    rows = load_training_rows(dataset_path)
    if len(rows) < 100:
        raise RuntimeError(f"Not enough usable rows: {len(rows)}")

    feature_dicts, targets = build_features(rows)

    test_size       = 0.2
    selection_seeds = [0, 1, 2]
    holdout_seed    = 42

    # Small models — fast; used only to pick the best algorithm
    candidate_models_small = {
        "extra_trees": ExtraTreesRegressor(
            n_estimators=80, max_depth=20, min_samples_leaf=2,
            random_state=42, n_jobs=-1,
        ),
        "random_forest": RandomForestRegressor(
            n_estimators=60, max_depth=18, min_samples_leaf=2,
            random_state=42, n_jobs=-1,
        ),
        "hist_gradient_boosting": HistGradientBoostingRegressor(
            learning_rate=0.05, max_depth=8, max_iter=250,
            early_stopping=True, random_state=42,
        ),
    }

    # Large models — capped so the saved file stays under TARGET_MB after compression
    candidate_models_large = {
        "extra_trees": ExtraTreesRegressor(
            n_estimators=150, max_depth=15, min_samples_leaf=8,
            max_features=0.5, random_state=42, n_jobs=-1,
        ),
        "random_forest": RandomForestRegressor(
            n_estimators=100, max_depth=14, min_samples_leaf=8,
            max_features=0.5, random_state=42, n_jobs=-1,
        ),
        "hist_gradient_boosting": HistGradientBoostingRegressor(
            learning_rate=0.05, max_depth=8, max_iter=400,
            min_samples_leaf=20, l2_regularization=0.1,
            early_stopping=True, n_iter_no_change=15, random_state=42,
        ),
    }

    # ── step 1: algorithm selection ───────────────────────────────────────────
    separator("Algorithm selection")
    selection_stats: dict[str, dict] = {}
    best_name           = ""
    best_selection_mean = float("inf")

    for name, base_estimator in candidate_models_small.items():
        maes: list[float] = []

        for seed in selection_seeds:
            x_tr_d, x_te_d, y_tr, y_te = train_test_split(
                feature_dicts, targets, test_size=test_size, random_state=seed
            )
            vec  = DictVectorizer(sparse=False)
            x_tr = vec.fit_transform(x_tr_d)
            x_te = vec.transform(x_te_d)
            mae, _ = train_model(
                name=f"{name} (seed={seed})",
                estimator=clone(base_estimator),
                x_train=x_tr, y_train=y_tr,
                x_test=x_te,  y_test=y_te,
            )
            maes.append(float(mae))

        mean_mae = float(statistics.mean(maes))
        std_mae  = float(statistics.pstdev(maes)) if len(maes) > 1 else 0.0
        selection_stats[name] = {
            "mae_values_hours": maes,
            "mae_mean_hours":   mean_mae,
            "mae_std_hours":    std_mae,
        }
        log(f"{name} → mean={mean_mae:.4f}h ({mean_mae * 60:.2f} min)  std={std_mae:.4f}h")

        if mean_mae < best_selection_mean:
            best_selection_mean = mean_mae
            best_name = name

    if not best_name:
        raise RuntimeError("No best model selected.")
    log(f"Selected: {best_name}")

    # ── step 2: holdout evaluation of large model ─────────────────────────────
    separator("Holdout evaluation (large model)")
    ho_tr_d, ho_te_d, y_tr, y_te = train_test_split(
        feature_dicts, targets, test_size=test_size, random_state=holdout_seed
    )
    vec_holdout = DictVectorizer(sparse=False)
    x_ho_tr     = vec_holdout.fit_transform(ho_tr_d)
    x_ho_te     = vec_holdout.transform(ho_te_d)

    best_large = candidate_models_large[best_name]
    holdout_mae, _ = train_model(
        name=f"{best_name} (large, seed={holdout_seed})",
        estimator=clone(best_large),
        x_train=x_ho_tr, y_train=y_tr,
        x_test=x_ho_te,  y_test=y_te,
    )

    # ── step 3: final training on full dataset ────────────────────────────────
    separator("Final training on full dataset")
    vec_final = DictVectorizer(sparse=False)
    x_full    = vec_final.fit_transform(feature_dicts)
    final_est = clone(best_large)
    final_est.fit(x_full, targets)

    bundle = {
        "model":      final_est,
        "vectorizer": vec_final,
        "metrics": {
            "best_model":                      best_name,
            "selection":                       selection_stats,
            "best_selection_mae_mean_minutes": float(best_selection_mean),
            "final_holdout_mae_minutes":       float(holdout_mae),
            "test_size":                       float(test_size),
            "selection_seeds":                 selection_seeds,
            "holdout_seed":                    holdout_seed,
            "rows":                            len(rows),
        },
        "feature_names": list(feature_dicts[0].keys()),
    }

    # ── step 4: save ──────────────────────────────────────────────────────────
    model_path.parent.mkdir(parents=True, exist_ok=True)
    log("Saving model...")
    joblib.dump(bundle, model_path, compress=COMPRESS)

    saved_mb   = model_path.stat().st_size / 1e6
    total_time = time.perf_counter() - total_start
    log(f"Saved: {model_path}  ({saved_mb:.1f} MB)")
    log(f"Total training time: {total_time:.1f}s")

    # ── step 5: built-in evaluation ───────────────────────────────────────────
    evaluate(
        model=final_est,
        vectorizer=vec_final,
        feature_dicts=feature_dicts,
        targets=targets,
        bundle_metrics={**bundle["metrics"], "feature_names": bundle["feature_names"]},
        model_path=model_path,
    )


if __name__ == "__main__":
    main()