'''
terminal_forecast.py

Advanced forecasting of future settlement trends per terminal
using seasonal ARIMA (SARIMA). Enhanced data parsing for currency fields.
'''
import argparse
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
from loguru import logger
import warnings
from statsmodels.tsa.statespace.sarimax import SARIMAX

# Suppress excessive statsmodels warnings
warnings.filterwarnings("ignore")

# Ensure logs directory exists
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
logger.add(LOG_DIR / "terminal_forecast.log", level="DEBUG", rotation="1 day", retention="7 days")


def parse_args():
    """
    Parse command-line arguments.

    :returns: Namespace with input_file, forecast_days, order, seasonal_order
    :rtype: argparse.Namespace
    """
    parser = argparse.ArgumentParser(
        description="Forecast future settlement amounts per terminal using SARIMA."
    )
    parser.add_argument(
        "input_file",
        type=Path,
        help="Path to the CSV file containing settlement data."
    )
    parser.add_argument(
        "--forecast_days", "-f",
        type=int,
        default=5,
        help="Number of days ahead to forecast (default: 5)."
    )
    parser.add_argument(
        "--order", "-o",
        type=int,
        nargs=3,
        default=[1, 1, 1],
        metavar=("p", "d", "q"),
        help="Non-seasonal ARIMA order (p d q), default 1 1 1."
    )
    parser.add_argument(
        "--seasonal_order", "-s",
        type=int,
        nargs=4,
        default=[1, 1, 1, 7],
        metavar=("P", "D", "Q", "s"),
        help="Seasonal order (P D Q s), default 1 1 1 7 for weekly seasonality."
    )
    return parser.parse_args()


def load_data(csv_path: Path) -> pd.DataFrame:
    """
    Load and validate CSV data, parsing dates and cleaning 'Amount' currency values.
    """
    logger.info(f"Loading data from {csv_path}")
    if not csv_path.exists():
        logger.error(f"File not found: {csv_path}")
        raise FileNotFoundError(f"File not found: {csv_path}")
    df = pd.read_csv(csv_path)
    # Required columns
    required = ["Terminal", "Settlement Date", "Amount"]
    missing = set(required) - set(df.columns)
    if missing:
        logger.error(f"Missing columns: {missing}")
        raise ValueError(f"Missing columns: {missing}")
    # Parse dates
    df["Settlement Date"] = pd.to_datetime(df["Settlement Date"], errors="coerce")
    # Clean currency values: remove any non-numeric except dot and minus
    df["Amount"] = (
        df["Amount"].astype(str)
        .replace(r"[^0-9.\-]", "", regex=True)
        .replace("", "0")
        .astype(float)
    )
    return df


def prepare_daily_series(df: pd.DataFrame, terminal: str) -> pd.Series:
    """
    Build a daily time series of total amounts for a given terminal.

    :param df: DataFrame with settlement data
    :param terminal: Terminal identifier
    :returns: pd.Series indexed by daily date of sums
    """
    # Resample on daily frequency
    daily = (
        df[df["Terminal"] == terminal]
        .resample('D', on='Settlement Date')["Amount"]
        .sum()
        .fillna(0)
    )
    return daily


def forecast_series(
    series: pd.Series,
    steps: int,
    order: tuple,
    seasonal_order: tuple
) -> pd.DataFrame:
    """
    Fit SARIMA model and forecast future values.

    :param series: Historical time series
    :param steps: Number of days to forecast
    :param order: ARIMA order (p, d, q)
    :param seasonal_order: Seasonal order (P, D, Q, s)
    :returns: DataFrame with Date, Predicted, LowerCI, UpperCI, DayOfWeek
    """
    logger.debug(f"Fitting SARIMA{order}x{seasonal_order} on series from {series.index.min().date()} to {series.index.max().date()}")
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
        "UpperCI": ci.iloc[:, 1].values,
    })
    result["DayOfWeek"] = result["Date"].day_name()
    return result


def main():
    args = parse_args()
    try:
        df = load_data(args.input_file)
    except Exception:
        logger.exception("Failed to load data")
        sys.exit(1)

    terminals = df["Terminal"].dropna().unique()
    logger.info(f"Forecasting {args.forecast_days} days ahead for {len(terminals)} terminals.")

    all_forecasts = []
    for term in terminals:
        logger.info(f"Processing terminal: {term}")
        series = prepare_daily_series(df, term)
        # Skip only if no historical non-zero volume
        if series.sum() == 0:
            logger.warning(f"Terminal {term} has no historical activity; skipping forecast.")
            continue
        fc = forecast_series(
            series,
            steps=args.forecast_days,
            order=tuple(args.order),
            seasonal_order=tuple(args.seasonal_order)
        )
        fc["Terminal"] = term
        all_forecasts.append(fc)

    if not all_forecasts:
        logger.error("No forecasts generated. Check data parsing.")
        sys.exit(1)

    forecast_df = pd.concat(all_forecasts, ignore_index=True)
    # Output
    print(forecast_df.to_string(index=False))

if __name__ == "__main__":
    main()
