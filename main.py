from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "car_price_model.joblib"
DATA_PATH = BASE_DIR / "cars_cleaned.csv"

app = FastAPI(title="Used Car Fair Price Estimator", version="2.0.0")

model = joblib.load(MODEL_PATH)
market_data = pd.read_csv(DATA_PATH) if DATA_PATH.exists() else pd.DataFrame()

FEATURES = [
    "brand", "model", "trim", "year",
    "mileage_km", "city", "body_condition",
]


class CarInput(BaseModel):
    brand: str
    model: str
    trim: str
    year: int
    mileage_km: int = Field(ge=0)
    city: str
    body_condition: str
    asking_price: float | None = Field(default=None, gt=0)


def predict_distribution(row: pd.DataFrame):
    """Point estimate plus an uncalibrated RF tree-dispersion P10-P90 range."""
    estimated = float(model.predict(row)[0])
    preprocessor = model.named_steps["preprocessor"]
    regressor = model.named_steps["regressor"]
    transformed = preprocessor.transform(row)
    tree_predictions = np.array([tree.predict(transformed)[0] for tree in regressor.estimators_])
    p10, p50, p90 = np.percentile(tree_predictions, [10, 50, 90])
    return estimated, float(p10), float(p50), float(p90)


def find_comparables(car: dict, data: pd.DataFrame, n: int = 5):
    """Select nearby listings using transparent similarity rules."""
    if data.empty:
        return []

    required = {"brand", "model", "trim", "year", "mileage_km", "city", "body_condition", "price_toman"}
    if not required.issubset(data.columns):
        return []

    pool = data.copy()
    same_model = pool[(pool["brand"] == car["brand"]) & (pool["model"] == car["model"])].copy()
    if len(same_model) >= 3:
        pool = same_model

    score = np.zeros(len(pool), dtype=float)
    score += np.where(pool["brand"].eq(car["brand"]), 5, 0)
    score += np.where(pool["model"].eq(car["model"]), 10, 0)
    score += np.where(pool["trim"].eq(car["trim"]), 4, 0)
    score += np.where(pool["city"].eq(car["city"]), 2, 0)
    score += np.where(pool["body_condition"].eq(car["body_condition"]), 2, 0)
    score -= (pool["year"].astype(float) - float(car["year"])).abs() * 0.8
    score -= (pool["mileage_km"].astype(float) - float(car["mileage_km"])).abs() / 50000.0

    cols = ["brand", "model", "trim", "year", "mileage_km", "city", "body_condition", "price_toman"]
    pool = pool.assign(comparable_score=score).sort_values("comparable_score", ascending=False)
    return pool.head(n)[cols].round(2).to_dict(orient="records")


def confidence_label(price_low: float, price_high: float, comparable_count: int):
    width_pct = ((price_high - price_low) / max((price_high + price_low) / 2, 1)) * 100
    if comparable_count >= 5 and width_pct <= 30:
        return "High"
    if comparable_count >= 3 and width_pct <= 50:
        return "Medium"
    return "Low"


def market_position(asking_price: float, reference_price: float):
    if reference_price <= 0:
        return "Unknown", None
    difference = (asking_price - reference_price) / reference_price * 100
    if difference < -5:
        return "Below Market", difference
    if difference > 5:
        return "Above Market", difference
    return "Fair", difference


@app.get("/")
def root():
    return {"message": "Used Car Fair Price Estimator API is running", "docs": "/docs"}


@app.post("/predict")
def predict(car: CarInput):
    row = pd.DataFrame([{feature: getattr(car, feature) for feature in FEATURES}])
    estimated, p10, p50, p90 = predict_distribution(row)

    comparables = find_comparables(car.model_dump(), market_data, n=5)
    comparable_prices = [float(x["price_toman"]) for x in comparables]
    comparable_median = float(np.median(comparable_prices)) if comparable_prices else None
    confidence = confidence_label(p10, p90, len(comparables))

    result = {
        "estimated_price": round(estimated, 2),
        "price_range": [round(p10, 2), round(p90, 2)],
        "unit": "million Toman",
        "confidence": confidence,
        "comparable_count": len(comparables),
        "comparable_vehicles": comparables,
        "note": (
            "Estimated Fair Market Value is inferred from listing prices. "
            "Asking Price is not Transaction Price, and the range is model-based uncertainty, not a guaranteed sale interval."
        ),
    }

    if comparable_median is not None:
        result["comparable_median_price"] = round(comparable_median, 2)
        result["comparable_gap_percent"] = round((estimated - comparable_median) / comparable_median * 100, 2)

    if car.asking_price is not None:
        position, difference = market_position(car.asking_price, estimated)
        result.update({
            "asking_price": car.asking_price,
            "difference_percent": round(difference, 2) if difference is not None else None,
            "market_position": position,
        })

    return result
