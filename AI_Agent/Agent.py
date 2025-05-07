import subprocess
import json
import time
from pathlib import Path
from loguru import logger

TOOLS_DIR = Path(__file__).parent / "Tools"
RESULTS_DIR = TOOLS_DIR / "results"
GMAIL_DOWNLOADER_SCRIPT = TOOLS_DIR / "GmailDownloader.py"
GMAIL_RESULT = RESULTS_DIR / "gmail_downloader.json"

# Set how often the agent loops (in seconds)
LOOP_DELAY = 300  # 5 minutes

def run_gmail_downloader():
    logger.info("Invoking Gmail Downloader...")
    try:
        result = subprocess.run(
            ["python", str(GMAIL_DOWNLOADER_SCRIPT)],
            check=True,
            capture_output=True,
            text=True
        )
        logger.debug(f"Gmail Downloader stdout: {result.stdout}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Gmail Downloader failed: {e.stderr}")
        return None

    if GMAIL_RESULT.exists():
        try:
            with GMAIL_RESULT.open("r") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode result JSON: {e}")
    return None

def agent_loop():
    logger.add("agent.log", rotation="1 week")
    logger.info("Agent starting up...")

    while True:
        result = run_gmail_downloader()
        if result:
            logger.info(f"Gmail Downloader result: {json.dumps(result, indent=2)}")
            # Add more agent decision logic here if needed

        logger.info(f"Sleeping for {LOOP_DELAY} seconds...")
        time.sleep(LOOP_DELAY)

if __name__ == "__main__":
    agent_loop()
