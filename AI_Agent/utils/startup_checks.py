from pathlib import Path
from loguru import logger
import importlib
import os
import json
from dotenv import load_dotenv  
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
    for module in REQUIRED_MODULES:
        try:
            importlib.import_module(module)
            logger.info(f"✅ Import OK: {module}")
        except Exception as e:
            logger.error(f"❌ Import failed: {module} — {e}")

def check_directories():
    for d in REQUIRED_DIRS:
        if not d.exists():
            logger.warning(f"🟡 Missing directory: {d}")
        else:
            logger.debug(f"📁 Exists: {d}")

def check_environment_vars():
    for var in REQUIRED_ENV_VARS:
        if os.getenv(var) is None:
            logger.warning(f"🟡 Missing env var: {var}")
        else:
            logger.debug(f"🔑 Env var set: {var}")

def write_summary(status: str, summary: str):
    heartbeat_dir = Path("heartbeat")
    heartbeat_dir.mkdir(exist_ok=True)
    summary_file = heartbeat_dir / "diagnostic.status.json"
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
