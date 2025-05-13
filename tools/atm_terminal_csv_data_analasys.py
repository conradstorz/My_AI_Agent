'''
terminal_analysis.py

Script to analyze CSV data focusing on the 'Terminal' column and forecast future settlement amounts.
'''
import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
from loguru import logger

# Ensure logs directory exists
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
logger.add(LOG_DIR / "terminal_analysis.log", level="DEBUG", rotation="1 day", retention="7 days")


def parse_args():
    """
    Parse command-line arguments.

    :returns: Namespace containing input_file and forecast_days
    :rtype: argparse.Namespace
    """
    parser = argparse.ArgumentParser(
        description="Analyze and forecast 'Terminal' settlement data in a CSV file."
    )
    parser.add_argument(
        "input_file",
        type=Path,
        help="Path to the CSV file to analyze."
    )
    parser.add_argument(
        "--forecast_days", "-f",
        type=int,
        default=5,
        help="Number of future days to forecast (default: 5)."
    )
    return parser.parse_args()


def load_data(csv_path: Path) -> pd.DataFrame:
    """
    Load CSV data into a pandas DataFrame and validate required columns.
    """
    logger.info(f"Loading data from {csv_path}")
    if not csv_path.exists():
        logger.error(f"File not found: {csv_path}")
        raise FileNotFoundError(f"File not found: {csv_path}")
    df = pd.read_csv(csv_path)
    required_columns = [
        "Market Partner Code", "Market Partner", "Terminal", "Acct Number",
        "Group", "Location", "Settlement Date", "Settlement Type", "Amount"
    ]
    missing = set(required_columns) - set(df.columns)
    if missing:
        logger.error(f"Missing required columns: {missing}")
        raise ValueError(f"Missing required columns: {missing}")
    # Parse dates and numeric
    df["Settlement Date"] = pd.to_datetime(df["Settlement Date"], errors="coerce")
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0)
    return df


def list_unique_terminals(df: pd.DataFrame) -> pd.Series:
    uniques = df["Terminal"].dropna().unique()
    logger.debug(f"Found {len(uniques)} unique terminals")
    return pd.Series(uniques)


def count_transactions_per_terminal(df: pd.DataFrame) -> pd.DataFrame:
    return df.groupby("Terminal").size().reset_index(name="TransactionCount")


def sum_amount_per_terminal(df: pd.DataFrame) -> pd.DataFrame:
    return df.groupby("Terminal")["Amount"].sum().reset_index(name="TotalAmount")


def average_amount_per_terminal(df: pd.DataFrame) -> pd.DataFrame:
    return df.groupby("Terminal")["Amount"].mean().reset_index(name="AverageAmount")


def group_by_terminal_and_settlement_type(df: pd.DataFrame) -> pd.DataFrame:
    return df.groupby(["Terminal", "Settlement Type"])["Amount"].sum().reset_index(name="TotalAmount")


def forecast_next_days(df: pd.DataFrame, days: int) -> pd.DataFrame:
    """
    Predict total settlement amounts per terminal for the next `days` days,
    using historical day-of-week averages.
    """
    # Compute daily totals per terminal
    daily = (
        df.groupby([
            "Terminal",
            df["Settlement Date"].dt.normalize().rename("Date")
        ])
        ["Amount"].sum()
        .reset_index(name="DailyTotal")
    )
    # Add day of week
    daily["DayOfWeek"] = daily["Date"].dt.day_name()

    # Historical averages by terminal & day-of-week
    dow_avg = (
        daily.groupby(["Terminal", "DayOfWeek"])\
.reset_index()[["Terminal", "DayOfWeek"]]
    )
    dow_avg = daily.groupby(["Terminal", "DayOfWeek"])["DailyTotal"].mean().reset_index(name="AvgDailyTotal")

    # Overall terminal average fallback
    overall_avg = daily.groupby("Terminal")["DailyTotal"].mean().reset_index(name="OverallAvg")

    # Build forecast
    today = datetime.now().date()
    forecast_rows = []
    terminals = df["Terminal"].dropna().unique()
    for i in range(1, days + 1):
        forecast_date = today + timedelta(days=i)
        dow = forecast_date.strftime("%A")
        for term in terminals:
            match = dow_avg.loc[
                (dow_avg["Terminal"] == term) &
                (dow_avg["DayOfWeek"] == dow),
                "AvgDailyTotal"
            ]
            if not match.empty:
                amt = match.iloc[0]
            else:
                amt = overall_avg.loc[overall_avg["Terminal"] == term, "OverallAvg"].iloc[0]
            forecast_rows.append({
                "Terminal": term,
                "Date": forecast_date,
                "DayOfWeek": dow,
                "PredictedAmount": amt
            })
    return pd.DataFrame(forecast_rows)


def main():
    args = parse_args()
    try:
        df = load_data(args.input_file)
    except Exception:
        logger.exception("Failed to load data")
        sys.exit(1)

    # Existing analyses
    uniques = list_unique_terminals(df)
    logger.info(f"Unique terminals ({len(uniques)}): {uniques.tolist()}")
    counts = count_transactions_per_terminal(df)
    logger.info("Transaction counts per terminal:\n" + counts.to_string(index=False))
    sums = sum_amount_per_terminal(df)
    logger.info("Total amount per terminal:\n" + sums.to_string(index=False))
    avgs = average_amount_per_terminal(df)
    logger.info("Average amount per terminal:\n" + avgs.to_string(index=False))
    grouped = group_by_terminal_and_settlement_type(df)
    logger.info("Amount by terminal and settlement type:\n" + grouped.to_string(index=False))

    # Forecasting
    forecast_df = forecast_next_days(df, args.forecast_days)
    logger.info(
        f"Forecast for next {args.forecast_days} days (with day-of-week):\n" +
        forecast_df.to_string(index=False)
    )


if __name__ == "__main__":
    main()
