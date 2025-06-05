# agent.py

import time
import subprocess
import sys
import time
from pathlib import Path
from loguru import logger

from tools.run_tool import run_tool

from constants import (
    LOOP_DELAY,
    LOGS_DIR,
    AGENT_LOG_FILE,
    AGENT_LOG_ROTATION,
    AGENT_MODULES,
)

def agent_loop():
    logger.add(AGENT_LOG_FILE, rotation=AGENT_LOG_ROTATION)
    logger.info("Agent loop starting...")
    for module, label in AGENT_MODULES:
        logger.info(f"Loading module: {label} ({module})")
        try:
            __import__(module)
            logger.info(f"Module {label} loaded successfully.")
        except ImportError as e:
            logger.error(f"Failed to load module {label}: {e}")

    while True:
        logger.info("=== New agent cycle ===")

        for module, label in AGENT_MODULES:
            run_tool(module, label)

        logger.info(f"Sleeping for {LOOP_DELAY} seconds...")
        time.sleep(LOOP_DELAY)

if __name__ == "__main__":
    agent_loop()
