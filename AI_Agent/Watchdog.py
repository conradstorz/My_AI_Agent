import subprocess
import time
import json
import os
from pathlib import Path
from loguru import logger

HEARTBEAT_FILE = Path("heartbeat/agent.status.json")
MAX_HEARTBEAT_AGE = 120  # seconds before considered stale
CHECK_INTERVAL = 30      # how often to check
AGENT_CMD = ["python", "main.py"]

def get_last_heartbeat():
    if not HEARTBEAT_FILE.exists():
        return None
    try:
        with HEARTBEAT_FILE.open("r") as f:
            data = json.load(f)
            return data.get("timestamp")
    except Exception as e:
        logger.error(f"Failed to read heartbeat: {e}")
        return None

def is_heartbeat_stale(ts):
    if ts is None:
        return True
    age = time.time() - ts
    return age > MAX_HEARTBEAT_AGE

def run_watchdog():
    logger.add("watchdog.log", rotation="1 week")
    logger.info("Starting watchdog...")

    agent_process = None

    while True:
        heartbeat_ts = get_last_heartbeat()
        if is_heartbeat_stale(heartbeat_ts):
            logger.warning("Heartbeat stale or missing. Restarting agent...")

            if agent_process and agent_process.poll() is None:
                logger.info("Terminating old agent process...")
                agent_process.terminate()
                agent_process.wait()

            agent_process = subprocess.Popen(AGENT_CMD)
            logger.info(f"Agent restarted with PID {agent_process.pid}")
        else:
            logger.debug("Heartbeat OK.")

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    run_watchdog()
