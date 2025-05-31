import subprocess
import time
import json
import os
import sys
from pathlib import Path
from loguru import logger

from constants import (
    WATCHDOG_HEARTBEAT_FILE,
    MAX_HEARTBEAT_AGE,
    CHECK_INTERVAL,
    AGENT_CMD,
    WATCHDOG_LOG_FILE,
    WATCHDOG_LOG_ROTATION,
)


def get_last_heartbeat():
    """
    Return the timestamp from the heartbeat file, or None if unavailable.
    """
    if not WATCHDOG_HEARTBEAT_FILE.exists():
        return None
    try:
        text = WATCHDOG_HEARTBEAT_FILE.read_text()
        data = json.loads(text)
        return data.get("timestamp")
    except (OSError, json.JSONDecodeError) as e:
        logger.error(f"Failed to read or parse heartbeat file: {e}")
        return None


def run_watchdog():
    """
    Monitor the agent's heartbeat. If stale, restart the agent.
    """
    # Ensure log directory exists and configure logging
    WATCHDOG_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logger.add(WATCHDOG_LOG_FILE, rotation=WATCHDOG_LOG_ROTATION, level="INFO")

    agent_process = None
    
    while True:
        last_ts = get_last_heartbeat()
        now = time.time()

        if last_ts is None:
            logger.warning("No heartbeat file found. Starting agent...")
            # Start agent if not already running
            if agent_process is None or agent_process.poll() is not None:
                agent_process = subprocess.Popen(AGENT_CMD)
                logger.info(f"Agent started with PID {agent_process.pid}")

        else:
            age = now - last_ts
            if age > MAX_HEARTBEAT_AGE:
                logger.warning(f"Heartbeat stale (age={age:.1f}s). Restarting agent...")
                # Terminate old process if still running
                if agent_process and agent_process.poll() is None:
                    logger.info("Terminating old agent process...")
                    agent_process.terminate()
                    agent_process.wait()

                # Launch new agent process
                agent_process = subprocess.Popen(AGENT_CMD)
                logger.info(f"Agent restarted with PID {agent_process.pid}")
            else:
                logger.debug(f"Heartbeat OK (age={age:.1f}s)")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    run_watchdog()
