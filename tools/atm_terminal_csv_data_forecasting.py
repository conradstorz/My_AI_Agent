'''
terminal_forecast.py

Advanced forecasting of future settlement trends per terminal
using seasonal ARIMA (SARIMA) with a fallback to day-of-week mean on sparse data.
'''
import argparse
import sys
import time
from pathlib import Path
from datetime import datetime, date, timedelta

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
        description="Forecast future settlement amounts per terminal using SARIMA with fallback."
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
    """
    Load, validate, and clean CSV data. Only keeps rows where
    Settlement Type == 'Transaction'.
    """
    logger.info(f"Loading data from {csv_path}")
    if not csv_path.exists():
        logger.error(f"File not found: {csv_path}")
        raise FileNotFoundError(f"File not found: {csv_path}")
    df = pd.read_csv(csv_path)

    required = ["Terminal", "Location", "Settlement Date", "Amount", "Settlement Type"]
    missing = set(required) - set(df.columns)
    if missing:
        logger.error(f"Missing columns: {missing}")
        raise ValueError(f"Missing columns: {missing}")

    # Parse and clean
    df["Settlement Date"] = pd.to_datetime(df["Settlement Date"], errors="coerce")
    df["Amount"] = (
        df["Amount"].astype(str)
        .replace(r"[^0-9.\-]", "", regex=True)
        .replace("", "0")
        .astype(float)
    )

    # Filter only transactions
    original_count = len(df)
    df = df[df["Settlement Type"] == "Transaction"].copy()
    filtered_count = len(df)
    logger.info(f"Filtered settlement types: removed {original_count - filtered_count} rows; {filtered_count} 'Transaction' remain.")

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
    logger.debug(f"Fitting SARIMA{order}x{seasonal_order} for terminal {series.name}")
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
    result["DayOfWeek"] = result["Date"].dt.day_name()
    return result


def simple_dow_forecast(df: pd.DataFrame, terminal: str, steps: int) -> pd.DataFrame:
    """
    Simple fallback: forecast next `steps` days using historical day-of-week averages.
    """
    # Build daily totals
    hist = (
        df[df["Terminal"] == terminal]
        .groupby(df["Settlement Date"].dt.normalize())["Amount"]
        .sum()
        .reset_index(name="DailyTotal")
    )
    hist["DayOfWeek"] = hist["Settlement Date"].dt.day_name()
    dow_avg = hist.groupby("DayOfWeek")["DailyTotal"].mean().to_dict()
    overall_avg = hist["DailyTotal"].mean()

    today = date.today()
    rows = []
    for i in range(1, steps + 1):
        d = today + timedelta(days=i)
        dow = d.strftime("%A")
        amt = dow_avg.get(dow, overall_avg)
        rows.append({
            "Date": pd.to_datetime(d),
            "Predicted": amt,
            "LowerCI": amt,
            "UpperCI": amt,
            "DayOfWeek": dow
        })
    return pd.DataFrame(rows)


def save_output(df: pd.DataFrame, output_path: Path):
    df.to_csv(output_path, index=False)
    logger.info(f"Saved CSV: {output_path}")


def main():
    start_time = time.time()
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
        nonzero_days = (series > 0).sum()
        seasonal_period = args.seasonal_order[3]
        if nonzero_days < 2 * seasonal_period:
            logger.warning(f"Not enough non-zero history ({nonzero_days} days) for {term}; using day-of-week average fallback.")
            fc = simple_dow_forecast(df, term, args.forecast_days)
        else:
            try:
                fc = forecast_series(
                    series,
                    args.forecast_days,
                    tuple(args.order),
                    tuple(args.seasonal_order)
                )
            except Exception:
                logger.exception(f"SARIMA failed for {term}; using fallback.")
                fc = simple_dow_forecast(df, term, args.forecast_days)
        fc["Terminal"] = term
        all_forecasts.append(fc)
        logger.info(f"Forecast complete for {term}.")

    if not all_forecasts:
        logger.error("No forecasts generated. Exiting.")
        sys.exit(1)

    forecast_df = pd.concat(all_forecasts, ignore_index=True)

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    detailed_file = args.input_file.with_name(
        f"{args.input_file.stem}_forecast_{timestamp}.csv"
    )
    save_output(forecast_df, detailed_file)

    # Compute aggregate totals and include location
    totals_df = (
        forecast_df.groupby("Terminal")["Predicted"].sum().reset_index(name="TotalPredicted")
    )
    loc_map = df.groupby("Terminal")["Location"].first().reset_index()
    totals_df = totals_df.merge(loc_map, on="Terminal")
    totals_df["TotalPredicted"] = totals_df["TotalPredicted"].apply(lambda x: f"${x:,.2f}")
    totals_df = totals_df[["Terminal", "Location", "TotalPredicted"]]

    totals_file = args.input_file.with_name(
        f"{args.input_file.stem}_forecast_totals_{timestamp}.csv"
    )
    save_output(totals_df, totals_file)

    logger.info("Sample detailed forecast:\n" + forecast_df.head(10).to_string(index=False))
    logger.info("Aggregate totals per terminal with location:\n" + totals_df.to_string(index=False))

    elapsed = time.time() - start_time
    logger.info(f"Complete in {elapsed:.1f}s")

    print(f"Detailed forecast CSV: {detailed_file}")
    print(f"Totals forecast CSV: {totals_file}")

if __name__ == "__main__":
    main()
