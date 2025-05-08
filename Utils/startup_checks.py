from pathlib import Path
from loguru import logger
import importlib
import os
import sys

REQUIRED_MODULES = [
    "utils.openai_tools",
    "Tools.GmailDownloader",
    "Tools.FileAnalyzer"
]

REQUIRED_DIRS = [
    Path("Tools/downloads"),
    Path("Tools/analysis"),
    Path("Tools/results"),
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

def run_startup_diagnostics():
    logger.info("Running startup diagnostics...")
    check_modules()
    check_directories()
    check_environment_vars()
    logger.info("Startup check complete.")
