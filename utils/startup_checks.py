from pathlib import Path
from loguru import logger
import importlib
import os
import sys
import json
from dotenv import dotenv_values, load_dotenv
from constants import (
    STARTUP_CHECKS_REQUIRED_MODULES,
    STARTUP_CHECKS_REQUIRED_DIRS,
    STARTUP_CHECKS_REQUIRED_ENV_VARS,
    DIAGNOSTIC_DIR,
    DIAGNOSTIC_FILE,
)
import time

REQUIRED_MODULES = [
    "utils.openai_tools",
    "tools.gmail_downloader",
    "tools.file_analyzer"
]

REQUIRED_DIRS = [
    Path("tools/downloads"),
    Path("tools/analysis"),
    Path("tools/results"),
    Path("logs"),
]

REQUIRED_ENV_VARS = [
    "OPENAI_API_KEY",
    "GMAIL_CREDENTIALS_PATH"
]

def check_modules():
    for module in STARTUP_CHECKS_REQUIRED_MODULES:
        try:
            importlib.import_module(module)
            logger.info(f"✅ Import OK: {module}")
        except Exception as e:
            logger.error(f"❌ Import failed: {module} — {e}")

def check_directories():
    for d in STARTUP_CHECKS_REQUIRED_DIRS: 
        if not d.exists():
            logger.warning(f"🟡 Missing directory: {d}")
        else:
            logger.debug(f"📁 Exists: {d}")

def check_environment_vars():
    load_dotenv(override=True)
    env_file_values = dotenv_values()

    for var in STARTUP_CHECKS_REQUIRED_ENV_VARS:
        val = os.getenv(var)

        if val is None:
            logger.critical(f"❌ Missing required environment variable: {var}")
            sys.exit(1)
        else:
            if var not in env_file_values:
                logger.warning(f"🟡 {var} found in system environment but missing from .env file")
            else:
                logger.debug(f"🔑 {var} loaded from .env file")


def write_summary(status: str, summary: str):
    # heartbeat_dir = Path("heartbeat")
    DIAGNOSTIC_DIR.mkdir(exist_ok=True)
    summary_file = DIAGNOSTIC_FILE
    with summary_file.open("w") as f:
        json.dump({
            "timestamp": time.time(),
            "status": status,
            "summary": summary
        }, f, indent=2)

def run_startup_diagnostics():
    logger.info("Running startup diagnostics...")

    try:
        check_modules()
        check_directories()
        check_environment_vars()
        logger.info("✅ Startup check complete.")
        write_summary("ok", "All startup checks passed.")
    except SystemExit as e:
        write_summary("error", "Startup check failed. See logs for details.")
        raise  # Re-raise to halt execution
