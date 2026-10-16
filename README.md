# Used-Car Fair Price Estimator

A compact machine-learning project that estimates a used car's asking-price level from its characteristics and compares the estimate with similar listings. The project is designed as a practical hiring-task submission: the workflow is reproducible, the modeling approach is intentionally understandable, and its limitations are stated explicitly.

## Project objective

Given a vehicle's brand, model, trim, model year, mileage, city, body condition, and optionally its advertised price, the system returns:

- **Estimated price** from the trained model
- **Indicative price range** as a lightweight uncertainty signal
- **Asking-price comparison** and a `Below Market`, `Fair`, or `Above Market` label when an asking price is supplied
- **Confidence** based partly on the amount of comparable evidence
- **Comparable vehicles** and their count

The result is decision support, not a substitute for an inspection or a confirmed sale price.

## Price terminology and data limitations

| Term | Meaning in this project |
|---|---|
| Asking Price | The amount advertised by the seller; this is the target available in the dataset. |
| Transaction Price | The amount actually paid after negotiation. Verified transaction prices are not available in the current dataset. |
| Fair Market Value | An estimate of the market level inferred from available listings. Here it is an approximate, asking-price-based estimate rather than a verified transaction value. |

Asking prices may be negotiable, stale, inaccurate, or affected by listing strategy. Consequently, model estimates should not be presented as guaranteed sale prices. The dataset is also a snapshot of the collected listings, so it may not represent every region, vehicle segment, or current market condition.

## Repository layout

- `data_cleaner.ipynb` — cleaning, text normalization, basic validation, duplicate handling, market sanity checks, outlier flags, and cleaned-data export.
- `model_training.ipynb` — feature preparation, model training, baseline comparison, validation metrics, error analysis, uncertainty estimation, comparable selection, explainability, temporal checks, and five held-out examples.
- `main.py` — FastAPI application for price estimates (if included in the submitted project directory).
- `scarper.py` - data collector from BAMA.ir
- `requirements.txt` — Python dependencies (if included in the submitted project directory).
- `cars_cleaned.csv` — cleaned dataset after implementing `data_cleaner.ipynb`
- `five_real_test_outputs.csv` 

## Data preparation

The cleaning notebook:

1. Loads the collected dataset and checks the expected fields.
2. Removes listing identifiers that should not act as price predictors.
3. Excludes identifiable pre-sale or transfer listings that are not comparable with ordinary used-car offers.
4. Normalizes text formatting, including Persian/Arabic character variants and extra whitespace.
5. Converts price, year, and mileage fields to numeric representations and keeps the target in a consistent unit (million Toman, matching the dataset convention).
6. Retains publication dates for market/time analysis without using them as direct features in the main model.
7. Removes exact duplicate rows and runs basic validation checks.
8. Flags suspicious prices for review rather than deleting them automatically.

Normalization is intentionally conservative. It standardizes text representation but does not guess that differently named models or trims are identical. Exact duplicate removal also does not guarantee that reposted or near-duplicate listings have all been identified.

## Modeling approach

The training notebook uses a preprocessing pipeline with numeric imputation and one-hot encoding for categorical fields, followed by a Random Forest regressor. The pipeline keeps preprocessing consistent between training and inference and avoids fitting transformations on the held-out test set.

A simple central-price baseline is reported alongside the model. The main metrics are:

- **MAE** — average absolute error in the target's price units.
- **RMSE** — penalizes large errors more heavily than MAE.
- **R²** — summarizes the variance explained relative to a constant-mean predictor.

The notebook also reviews the largest individual errors, reports aggregate feature importance, and checks a chronological hold-out split when publication dates are sufficiently usable. Random validation is a useful starting point, but a time-based split is more informative about performance on later listings. Neither split guarantees future-market accuracy.

## Comparable vehicles and uncertainty

Comparable listings are selected using a transparent similarity score based on vehicle identity and characteristics such as model/trim, brand, year, mileage, city, and body condition. Their count and quality help inform the confidence signal; their median asking price provides a second reference alongside the model estimate.

The reported price range uses the dispersion of predictions across Random Forest trees. It is a lightweight uncertainty indicator. It may understate uncertainty caused by market drift, missing details, or rare vehicles. Comparable listings are also asking prices, not verified sale records.

## Run the notebooks

Use Python 3.10 or newer if compatible with the supplied dependency versions.

1. Place the collected dataset at the path expected by the first cell of `data_cleaner.ipynb` (by default, this is expected to be `cars.csv` in the working directory).
2. Install the dependencies listed in `requirements.txt`, if that file is included:

   ```bash
   pip install -r requirements.txt
   ```

3. Open `data_cleaner.ipynb` and run all cells. Confirm the output dataset path at the end of the notebook.
4. Open `model_training.ipynb` and run all cells. It trains and evaluates the model, saves the model artifacts, and generates five examples from the held-out test set.
5. Keep the generated artifacts in the locations expected by `main.py` before starting the API.

Notebook paths are relative to the current working directory. If the project is run from a different folder, update the relevant path variables in the first cells rather than moving or overwriting the raw dataset.

## Run the API

If `main.py` and its model artifacts are included, install the dependencies and start the application from the project directory:

```bash
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000/docs` to try the request schema interactively. The exact required fields and artifact paths are defined by `main.py`; use those definitions as the source of truth if they differ from this overview. If an asking price is supplied, the API can compare it with the estimate and assign a market-position label. Without an asking price, it can only estimate the price level.

## Expected deliverables

After running the notebooks on the supplied dataset, retain:

- The cleaned dataset exported by the cleaning notebook
- The saved trained pipeline and any supporting metadata used by the API
- The evaluation metrics and error-analysis outputs
- The generated file containing five real held-out examples (if produced by the notebook)

The five examples should be generated from the actual test set rather than written manually. They are examples from the collected dataset, not live market quotes.

## Limitations and next steps

- The target is asking price, not transaction price.
- Rare models and trims have fewer examples and may receive less reliable estimates.
- Outlier are removed which could be better treated.
- Random splits can overstate performance when similar listings occur in both train and test sets; temporal validation helps, but more time periods would be needed for a strong drift assessment.
- Feature importance is descriptive, not causal.

Practical next steps are to refresh the dataset regularly, use rolling temporal validation, calibrate prediction intervals, improve near-duplicate detection and comparable retrieval, and incorporate verified transaction prices if they become available.
