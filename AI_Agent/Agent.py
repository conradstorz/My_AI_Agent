import subprocess
import sys
import json
import time
from pathlib import Path
from loguru import logger

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent.parent
TOOLS_DIR = BASE_DIR / "Tools"
RESULTS_DIR = TOOLS_DIR / "Results"
LOGS_DIR = BASE_DIR / "logs"

GMAIL_DOWNLOADER_SCRIPT = TOOLS_DIR / "Gmail_Downloader.py"
FILE_ANALYZER_SCRIPT = TOOLS_DIR / "FileAnalyzer.py"
GMAIL_RESULT = RESULTS_DIR / "gmail_downloader.json"

LOOP_DELAY = 300  # seconds (5 minutes)

def run_tool(script_path: Path, label: str) -> bool:
    logger.info(f"Invoking {label}...")
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
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
    LOGS_DIR.mkdir(exist_ok=True)
    logger.add(LOGS_DIR / "agent.log", rotation="1 week")
    logger.info("Agent loop starting...")

    while True:
        logger.info("=== New agent cycle ===")

        # Step 1: Download Gmail attachments
        success = run_tool(GMAIL_DOWNLOADER_SCRIPT, "Gmail Downloader")

        # Step 2: Analyze downloaded files regardless of success
        run_tool(FILE_ANALYZER_SCRIPT, "File Analyzer")

        logger.info(f"Sleeping for {LOOP_DELAY} seconds...")
        time.sleep(LOOP_DELAY)

if __name__ == "__main__":
    agent_loop()
