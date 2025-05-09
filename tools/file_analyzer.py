#!/usr/bin/env python3
"""
Flat functional File Analyzer for processing downloaded files and messages,
extracting content, summarizing via OpenAI, and storing analysis results.
"""
from pathlib import Path
import json
import time
from loguru import logger
from dotenv import load_dotenv
import fitz  # PyMuPDF
import pandas as pd
from utils.openai_tools import summarize_document

# Global paths and state files
BASE_DIR = Path(__file__).resolve().parent
DOWNLOADS_DIR = BASE_DIR / "downloads"
ANALYSIS_DIR = BASE_DIR / "analysis"
RESULTS_DIR = BASE_DIR / "results"
LOGS_DIR = BASE_DIR / "logs"
MEMORY_FILE = BASE_DIR / "categorization_memory.json"
UNHANDLED_FILE = BASE_DIR / "unhandled_filedata.json"

# In-memory state
memory = {}
unhandled = []
context = {}


def ensure_directories():
    """Create required directories if they don't exist."""
    for d in (DOWNLOADS_DIR, ANALYSIS_DIR, RESULTS_DIR, LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def configure_logging():
    """Configure Loguru to write to a rotating log file."""
    log_path = LOGS_DIR / "file_analyzer.log"
    logger.add(log_path, rotation="1 week", retention="4 weeks", level="DEBUG")


def load_json(path: Path, default):
    """Load JSON data from a file or return a default value."""
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"Failed to load JSON from {path.name}: {e}")
    return default


def save_json(data, path: Path):
    """Save data as JSON to the given path."""
    try:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to save JSON to {path.name}: {e}")


def load_context() -> dict:
    """Load file metadata from gmail_downloader.json."""
    path = RESULTS_DIR / "gmail_downloader.json"
    if not path.exists():
        logger.warning("No gmail_downloader.json found.")
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {
            item["filename"]: {"subject": item.get("subject", "(unknown)"), "sender": item.get("sender", "(unknown)")}
            for item in raw.get("downloads", [])
        }
    except Exception as e:
        logger.error(f"Failed to load context: {e}")
        return {}


def load_messages() -> list:
    """Load inline messages from gmail_query_fetcher.json."""
    path = RESULTS_DIR / "gmail_query_fetcher.json"
    if not path.exists():
        logger.warning("No gmail_query_fetcher.json found.")
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("messages_saved", [])
    except Exception as e:
        logger.error(f"Failed to load messages: {e}")
        return []


def is_analyzed(stem: str) -> bool:
    """Check if an analysis file already exists for a stem."""
    return (ANALYSIS_DIR / f"{stem}.analysis.json").exists()


def extract_pdf(file: Path) -> str:
    """Extract all text from a PDF using PyMuPDF."""
    doc = fitz.open(file)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text


def extract_excel(file: Path) -> str:
    """Read first 10 rows of each sheet in an Excel file."""
    try:
        sheets = pd.read_excel(file, sheet_name=None, engine="openpyxl")
    except Exception as e:
        logger.error(f"Excel read error: {file.name} - {e}")
        return ""
    blocks = []
    for name, df in sheets.items():
        blocks.append(f"--- Sheet: {name} ---")
        blocks.append(df.head(10).to_string(index=False))
    return "\n".join(blocks)


def extract_content(file: Path) -> str:
    """Extract text content or mark binary/unsupported types."""
    suffix = file.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf(file)
    if suffix in {".xls", ".xlsx"}:
        return extract_excel(file)
    if suffix in {".txt", ".html", ".csv", ".log"}:
        return file.read_text(encoding="utf-8", errors="ignore")
    if suffix in {".jpg", ".jpeg", ".png", ".gif", ".zip", ".rar"}:
        logger.info(f"Skipping binary file: {file.name}")
        record_unhandled(file, suffix)
        return f"[Binary file type: {suffix}]"
    logger.warning(f"Unsupported file type: {file.name}")
    record_unhandled(file, suffix)
    return f"[Unsupported file type: {suffix}]"


def record_unhandled(file: Path, suffix: str):
    """Record metadata for unsupported or binary files."""
    entry = {"filename": file.name, "filetype": suffix,
             "subject": context.get(file.name, {}).get("subject", "(unknown)"),
             "sender": context.get(file.name, {}).get("sender", "(unknown)"),
             "timestamp": time.time()}
    if entry not in unhandled:
        unhandled.append(entry)
        logger.info(f"Recorded unhandled file: {file.name}")


def summarize_content(content: str, identifier: str) -> dict:
    """Use AI to summarize content unless marked for skip."""
    if content.startswith("["):
        return {"summary": content, "contains_structured_data": False, "notes": "Skipped AI summarization."}
    try:
        return summarize_document(content, identifier)
    except Exception as e:
        logger.error(f"Summarization error for {identifier}: {e}")
        return {"summary": content, "contains_structured_data": False, "notes": ""}


def save_analysis(stem: str, analysis: dict):
    """Write analysis JSON to the analysis directory."""
    path = ANALYSIS_DIR / f"{stem}.analysis.json"
    try:
        path.write_text(json.dumps(analysis, indent=2), encoding="utf-8")
        logger.info(f"Saved analysis: {path.name}")
    except Exception as e:
        logger.error(f"Failed to save analysis for {stem}: {e}")


def update_memory(key: str, entry: dict):
    """Add a new entry to memory if key is not present."""
    if key not in memory:
        memory[key] = entry
        logger.info(f"Memory updated: {key}")


def process_file(file: Path):
    """Extract, summarize, and record analysis for a single file."""
    logger.info(f"Analyzing file: {file.name}")
    suffix = file.suffix.lower()
    meta = context.get(file.name, {})
    subject = meta.get("subject", "(unknown)")
    sender = meta.get("sender", "(unknown)")

    content = extract_content(file)
    summary_data = summarize_content(content, file.name)

    analysis = {"filename": file.name, "timestamp": time.time(),
                "filetype": suffix, "subject": subject, "sender": sender,
                **summary_data}
    save_analysis(file.stem, analysis)

    key = f"SENDER::{sender}::{suffix}"
    update_memory(key, {"source": sender, "filetype": suffix,
                          "summary": analysis["summary"],
                          "contains_structured_data": analysis["contains_structured_data"],
                          "category": "(uncategorized)", "notes": ""})


def process_message(message: dict):
    """Extract, summarize, and record analysis for an inline message."""
    msg_id = message.get("message_id", "unknown")
    logger.info(f"Analyzing message: {msg_id}")
    body = message.get("body", "")
    summary_data = summarize_content(body, f"{msg_id}.txt")

    analysis = {"message_id": msg_id, "timestamp": time.time(),
                "filetype": "inline-message", "subject": message.get("subject", "(no subject)"),
                "sender": message.get("sender", "(no sender)"), **summary_data}
    save_analysis(msg_id, analysis)

    key = f"MSG::{analysis['sender']}"
    update_memory(key, {"source": analysis["sender"],
                          "subject": analysis["subject"],
                          "summary": analysis["summary"],
                          "contains_structured_data": analysis["contains_structured_data"],
                          "category": "(uncategorized)", "notes": ""})


def run():
    """Analyze all downloaded files and fetched messages."""
    logger.info("Starting analysis...")
    for file in DOWNLOADS_DIR.glob("*.*"):
        if is_analyzed(file.stem):
            logger.debug(f"Already analyzed: {file.name}")
            continue
        process_file(file)

    for message in load_messages():
        msg_id = message.get("message_id", "")
        if is_analyzed(msg_id):
            logger.debug(f"Already analyzed message: {msg_id}")
            continue
        process_message(message)


def main():
    """Entry point: setup and execute analysis."""
    ensure_directories()
    configure_logging()
    load_dotenv()

    global memory, unhandled, context
    memory = load_json(MEMORY_FILE, {})
    unhandled = load_json(UNHANDLED_FILE, [])
    context = load_context()

    run()

    save_json(memory, MEMORY_FILE)
    save_json(unhandled, UNHANDLED_FILE)
    logger.info("Analysis complete.")


if __name__ == "__main__":
    main()
