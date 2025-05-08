import threading
import time
import json
from pathlib import Path
from loguru import logger
from Agent import agent_loop
from dotenv import load_dotenv
load_dotenv()

from Utils.startup_checks import run_startup_diagnostics


# Where to store agent heartbeat info
HEARTBEAT_FILE = Path("heartbeat/agent.status.json")
HEARTBEAT_INTERVAL = 60  # seconds

def heartbeat():
    Path("heartbeat").mkdir(exist_ok=True)
    while True:
        status = {
            "timestamp": time.time(),
            "status": "alive",
            "agent": "basic-agent",
        }
        with HEARTBEAT_FILE.open("w") as f:
            json.dump(status, f, indent=2)
        logger.debug("Heartbeat written.")
        time.sleep(HEARTBEAT_INTERVAL)


def main():
    LOGS_DIR = Path("logs")
    LOGS_DIR.mkdir(exist_ok=True)
    logger.add(LOGS_DIR / "main.log", rotation="1 week")

    logger.info("Checking imports...")
    run_startup_diagnostics()

    logger.info("Launching main agent process.")

    # Start heartbeat in a separate thread
    hb_thread = threading.Thread(target=heartbeat, daemon=True)
    hb_thread.start()

    try:
        agent_loop()
    except KeyboardInterrupt:
        logger.warning("Shutdown requested by user.")
    except Exception as e:
        logger.exception(f"Unexpected error in agent: {e}")
    finally:
        logger.info("Main loop exited.")

if __name__ == "__main__":
    main()
