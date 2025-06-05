# run_tool.py
# a standardized tool for running sub-processes

import subprocess
import sys
from loguru import logger


def run_tool(module: str, label: str) -> bool:
    logger.info(f"Invoking {label}...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", module],
            check=True,
            capture_output=True,
            text=True
        )
        logger.debug(f"{label} stdout:\n{result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"{label} failed:\n{e.stderr}")
        return False
