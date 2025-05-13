'''
terminal_analysis.py

Script to analyze CSV data focusing on the 'Terminal' column in various ways.
'''
import argparse
import sys
from pathlib import Path

import pandas as pd
from loguru import logger

# Ensure logs directory exists
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
logger.add(LOG_DIR / "terminal_analysis.log", level="DEBUG", rotation="1 day", retention="7 days")


def parse_args():
    """
    Parse command-line arguments.

    :returns: Namespace containing input_file (Path to the CSV file)
    :rtype: argparse.Namespace
    """
    parser = argparse.ArgumentParser(
        description="Analyze 'Terminal' column in CSV data and provide summary statistics."
    )
    parser.add_argument(
        "input_file",
        type=Path,
        help="Path to the CSV file to analyze."
    )
    return parser.parse_args()


def load_data(csv_path: Path) -> pd.DataFrame:
    """
    Load CSV data into a pandas DataFrame.

    :param csv_path: Path to the CSV file
    :type csv_path: Path
    :returns: DataFrame containing the CSV data
    :rtype: pandas.DataFrame
    :raises FileNotFoundError: if the file does not exist
    :raises ValueError: if required columns are missing
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
    return df


def list_unique_terminals(df: pd.DataFrame) -> pd.Series:
    """
    List unique Terminal values.

    :param df: DataFrame with 'Terminal' column
    :type df: pandas.DataFrame
    :returns: Series of unique Terminal values
    :rtype: pandas.Series
    """
    uniques = df["Terminal"].dropna().unique()
    logger.debug(f"Found {len(uniques)} unique terminals")
    return pd.Series(uniques)


def count_transactions_per_terminal(df: pd.DataFrame) -> pd.DataFrame:
    """
    Count the number of transactions per terminal.

    :param df: DataFrame with 'Terminal' column
    :type df: pandas.DataFrame
    :returns: DataFrame with 'Terminal' and 'TransactionCount'
    :rtype: pandas.DataFrame
    """
    counts = df.groupby("Terminal").size().reset_index(name="TransactionCount")
    logger.debug("Computed transaction counts per terminal")
    return counts


def sum_amount_per_terminal(df: pd.DataFrame) -> pd.DataFrame:
    """
    Sum the 'Amount' per terminal.

    :param df: DataFrame with 'Terminal' and 'Amount' columns
    :type df: pandas.DataFrame
    :returns: DataFrame with 'Terminal' and 'TotalAmount'
    :rtype: pandas.DataFrame
    """
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    sums = df.groupby("Terminal")["Amount"].sum().reset_index(name="TotalAmount")
    logger.debug("Computed total amount per terminal")
    return sums


def average_amount_per_terminal(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute average 'Amount' per terminal.

    :param df: DataFrame with 'Terminal' and 'Amount' columns
    :type df: pandas.DataFrame
    :returns: DataFrame with 'Terminal' and 'AverageAmount'
    :rtype: pandas.DataFrame
    """
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    averages = df.groupby("Terminal")["Amount"].mean().reset_index(name="AverageAmount")
    logger.debug("Computed average amount per terminal")
    return averages


def group_by_terminal_and_settlement_type(df: pd.DataFrame) -> pd.DataFrame:
    """
    Group transactions by terminal and settlement type.

    :param df: DataFrame with 'Terminal', 'Settlement Type', and 'Amount' columns
    :type df: pandas.DataFrame
    :returns: DataFrame with 'Terminal', 'Settlement Type', and summed 'Amount'
    :rtype: pandas.DataFrame
    """
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    grouped = df.groupby(["Terminal", "Settlement Type"])["Amount"].sum()
    logger.debug("Grouped by terminal and settlement type")
    return grouped.reset_index(name="TotalAmount")


def main():
    """
    Main entry point for the terminal analysis script.
    """
    args = parse_args()
    try:
        df = load_data(args.input_file)
    except Exception:
        logger.exception("Failed to load data")
        sys.exit(1)

    # Unique terminals
    uniques = list_unique_terminals(df)
    logger.info(f"Unique terminals ({len(uniques)}): {uniques.tolist()}")

    # Transaction counts
    counts = count_transactions_per_terminal(df)
    logger.info("Transaction counts per terminal:")
    logger.info(counts.to_string(index=False))

    # Total amounts
    sums = sum_amount_per_terminal(df)
    logger.info("Total amount per terminal:")
    logger.info(sums.to_string(index=False))

    # Average amounts
    avgs = average_amount_per_terminal(df)
    logger.info("Average amount per terminal:")
    logger.info(avgs.to_string(index=False))

    # Group by settlement type
    grouped = group_by_terminal_and_settlement_type(df)
    logger.info("Amount by terminal and settlement type:")
    logger.info(grouped.to_string(index=False))


if __name__ == "__main__":
    main()
