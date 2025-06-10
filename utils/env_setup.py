from pathlib import Path
from dotenv import load_dotenv
import os

from loguru import logger

# Define expected environment variables and dummy values
ENV_VARS = {
    "OPENAI_API_KEY": "your-openai-key-here",
    "GMAIL_CREDENTIALS_PATH": "D:/path/to/credentials.json",
    "GMAIL_TOKEN_PATH": "D:/path/to/token.json",  # optional
    "ANALYSIS_DIR": "analysis",
    "RESULTS_DIR": "results",
    "LOG_DIR": "logs"
}

ENV_FILE_PATH = Path(".env")


def ensure_env_file():
    """
    Ensure the .env file exists. If not, create it with dummy placeholders.
    """
    if not ENV_FILE_PATH.exists():
        logger.warning("⚠️  .env file not found. Creating with placeholder values...")
        with ENV_FILE_PATH.open("w", encoding="utf-8") as f:
            for key, value in ENV_VARS.items():
                f.write(f"{key}={value}\n")
        logger.info(f"✅ .env file created at {ENV_FILE_PATH.resolve()}")
        logger.warning("🔐 Please edit the .env file and replace placeholder values with your actual secrets.")
    else:
        logger.debug(".env file already exists.")


def load_env():
    """
    Load environment variables from the .env file.
    """
    load_dotenv()
    missing = [key for key in ENV_VARS if not os.getenv(key)]
    if missing:
        for key in missing:
            logger.critical(f"❌ Missing required environment variable: {key}")
        raise EnvironmentError("Some required environment variables are missing.")
    logger.info("✅ All required environment variables loaded.")


def setup_environment():
    """
    Main entry point for ensuring and loading env vars.
    """
    ensure_env_file()
    load_env()
