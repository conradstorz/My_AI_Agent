# agent.py

import time
import subprocess
import sys
import time
from pathlib import Path
from loguru import logger

# Configuration
LOOP_DELAY = 300  # seconds between cycles

LOGS_DIR = Path(__file__).parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

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

def agent_loop():
    logger.add(LOGS_DIR / "agent.log", rotation="1 week")
    logger.info("Agent loop starting...")

    while True:
        logger.info("=== New agent cycle ===")

        run_tool("tools.gmail_downloader", "Gmail Downloader")
        run_tool("tools.file_analyzer", "File Analyzer")
        run_tool("tools.process_downloaded_data", "Process Downloaded Data")

        logger.info(f"Sleeping for {LOOP_DELAY} seconds...")
        time.sleep(LOOP_DELAY)

if __name__ == "__main__":
    agent_loop()
