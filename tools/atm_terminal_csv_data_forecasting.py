'''
terminal_forecast.py

Advanced forecasting of future settlement trends per terminal
using seasonal ARIMA (SARIMA). Enhanced data parsing, output to CSV and enriched logging.
'''
import argparse
import sys
import time
from pathlib import Path
from datetime import datetime

import pandas as pd
from loguru import logger
import warnings
from statsmodels.tsa.statespace.sarimax import SARIMAX

# Suppress statsmodels warnings
warnings.filterwarnings("ignore")

# Setup logging
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
logger.add(LOG_DIR / "terminal_forecast.log", level="DEBUG", rotation="1 day", retention="7 days")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Forecast future settlement amounts per terminal using SARIMA."
    )
    parser.add_argument(
        "input_file",
        type=Path,
        help="Path to CSV file containing settlement data."
    )
    parser.add_argument(
        "--forecast_days", "-f",
        type=int,
        default=5,
        help="Number of days ahead to forecast."
    )
    parser.add_argument(
        "--order", "-o",
        type=int,
        nargs=3,
        default=[1, 1, 1],
        metavar=("p", "d", "q"),
        help="Non-seasonal ARIMA order p d q."
    )
    parser.add_argument(
        "--seasonal_order", "-s",
        type=int,
        nargs=4,
        default=[1, 1, 1, 7],
        metavar=("P", "D", "Q", "s"),
        help="Seasonal order P D Q s."
    )
    return parser.parse_args()


def load_data(csv_path: Path) -> pd.DataFrame:
    logger.info(f"Loading data from {csv_path}")
    if not csv_path.exists():
        logger.error(f"File not found: {csv_path}")
        raise FileNotFoundError(f"File not found: {csv_path}")
    df = pd.read_csv(csv_path)
    required = ["Terminal", "Settlement Date", "Amount"]
    missing = set(required) - set(df.columns)
    if missing:
        logger.error(f"Missing columns: {missing}")
        raise ValueError(f"Missing columns: {missing}")
    # Parse dates
    df["Settlement Date"] = pd.to_datetime(df["Settlement Date"], errors="coerce")
    # Clean currency values
    df["Amount"] = (
        df["Amount"].astype(str)
        .replace(r"[^0-9.\-]", "", regex=True)
        .replace("", "0")
        .astype(float)
    )
    return df


def prepare_daily_series(df: pd.DataFrame, terminal: str) -> pd.Series:
    daily = (
        df[df["Terminal"] == terminal]
        .resample('D', on='Settlement Date')["Amount"]
        .sum()
        .fillna(0)
    )
    return daily


def forecast_series(series: pd.Series, steps: int, order: tuple, seasonal_order: tuple) -> pd.DataFrame:
    logger.debug(f"Fitting SARIMA{order}x{seasonal_order} for {series.name}")
    model = SARIMAX(
        series,
        order=order,
        seasonal_order=seasonal_order,
        enforce_stationarity=False,
        enforce_invertibility=False
    )
    fit = model.fit(disp=False)
    forecast = fit.get_forecast(steps=steps)
    mean = forecast.predicted_mean
    ci = forecast.conf_int()
    result = pd.DataFrame({
        "Date": mean.index,
        "Predicted": mean.values,
        "LowerCI": ci.iloc[:, 0].values,
        "UpperCI": ci.iloc[:, 1].values
    })
    # Use .dt accessor to extract weekday name
    result["DayOfWeek"] = result["Date"].dt.day_name()
    return result


def save_output(df: pd.DataFrame, output_path: Path):
    df.to_csv(output_path, index=False)
    logger.info(f"Forecast results saved to {output_path}")


def main():
    start_time = time.time()
    args = parse_args()
    try:
        df = load_data(args.input_file)
    except Exception:
        logger.exception("Failed to load data")
        sys.exit(1)

    terminals = df["Terminal"].dropna().unique()
    logger.info(f"Starting forecast for {len(terminals)} terminals, {args.forecast_days} days ahead.")

    all_fc = []
    for term in terminals:
        logger.info(f"Terminal: {term}")
        series = prepare_daily_series(df, term)
        if series.sum() == 0:
            logger.warning(f"No activity for {term}; skipping.")
            continue
        try:
            fc = forecast_series(
                series,
                args.forecast_days,
                tuple(args.order),
                tuple(args.seasonal_order)
            )
            fc["Terminal"] = term
            all_fc.append(fc)
            logger.info(f"Forecast done for {term}.")
        except Exception:
            logger.exception(f"Forecast failed for {term}")

    if not all_fc:
        logger.error("No forecasts generated. Exiting.")
        sys.exit(1)

    forecast_df = pd.concat(all_fc, ignore_index=True)
    output_file = args.input_file.with_name(
        f"{args.input_file.stem}_forecast_{datetime.now():%Y%m%d%H%M%S}.csv"
    )
    save_output(forecast_df, output_file)
    logger.info("Sample forecast:\n" + forecast_df.head(10).to_string(index=False))

    elapsed = time.time() - start_time
    logger.info(f"Complete in {elapsed:.1f}s")
    print(f"Forecast CSV: {output_file}")

if __name__ == "__main__":
    main()
