from pathlib import Path
import json
import time
from loguru import logger
from dotenv import load_dotenv
import fitz  # PyMuPDF
import pandas as pd
from utils.openai_tools import summarize_document

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent
DOWNLOADS_DIR = BASE_DIR / "downloads"
ANALYSIS_DIR = BASE_DIR / "analysis"
RESULTS_DIR = BASE_DIR / "results"
MEMORY_FILE = BASE_DIR / "categorization_memory.json"
UNHANDLED_FILEDATA = BASE_DIR / "unhandled_filedata.json"
LOGS_DIR = BASE_DIR / "logs"

# Ensure necessary directories exist
LOGS_DIR.mkdir(exist_ok=True)
ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Configure logging
logger.add(LOGS_DIR / "file_analyzer.log", rotation="1 week")

# Load environment
load_dotenv()

# --- Memory management ---
def load_memory() -> dict:
    if MEMORY_FILE.exists():
        with MEMORY_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_memory(memory: dict):
    with MEMORY_FILE.open("w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2)

# --- Unhandled file data management ---
def load_unhandled() -> list:
    if UNHANDLED_FILEDATA.exists():
        with UNHANDLED_FILEDATA.open("r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_unhandled(unhandled: list):
    with UNHANDLED_FILEDATA.open("w", encoding="utf-8") as f:
        json.dump(unhandled, f, indent=2)

def update_unhandled(unhandled: list, file, suffix: str, subject: str, sender: str) -> list:
    entry = {
        "filename": file.name,
        "filetype": suffix,
        "subject": subject,
        "sender": sender,
        "timestamp": time.time()
    }
    if entry not in unhandled:
        unhandled.append(entry)
        logger.info(f"Recorded unhandled file type: {file.name}")
    return unhandled

# --- Memory entry update ---
def update_memory(memory: dict, key: str, entry: dict) -> dict:
    if key not in memory:
        memory[key] = entry
        logger.info(f"Categorization memory updated with key: {key}")
    else:
        logger.debug(f"Memory key already exists: {key}")
    return memory

# --- Helpers ---
def extract_text_from_pdf(file: Path) -> str:
    doc = fitz.open(file)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text


def extract_text_from_excel(file: Path) -> str:
    try:
        excel = pd.read_excel(file, sheet_name=None, engine="openpyxl")
    except Exception as e:
        logger.error(f"Failed to read Excel file {file.name}: {e}")
        return ""
    summaries = []
    for sheet, df in excel.items():
        summaries.append(f"--- Sheet: {sheet} ---")
        summaries.append(df.head(10).to_string(index=False))
        summaries.append("")
    return "\n".join(summaries)


def has_been_analyzed(stem: str) -> bool:
    return (ANALYSIS_DIR / f"{stem}.analysis.json").exists()


def load_downloaded_file_metadata() -> dict:
    gd = RESULTS_DIR / "gmail_downloader.json"
    if not gd.exists():
        logger.warning("No gmail_downloader.json found.")
        return {}
    try:
        with gd.open("r") as f:
            data = json.load(f)
        return {item["filename"]: {"subject": item.get("subject"), "sender": item.get("sender")}
                for item in data.get("downloads", [])}
    except Exception as e:
        logger.error(f"Failed to load gmail_downloader.json: {e}")
        return {}


def load_fetched_messages() -> list:
    gq = RESULTS_DIR / "gmail_query_fetcher.json"
    if not gq.exists():
        logger.warning("No gmail_query_fetcher.json found.")
        return []
    try:
        with gq.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("messages_saved", [])
    except Exception as e:
        logger.error(f"Failed to load gmail_query_fetcher.json: {e}")
        return []

# --- Main analyzers ---
def analyze_file(file: Path, context: dict, memory: dict, unhandled: list):
    logger.info(f"Analyzing file: {file.name}")
    suffix = file.suffix.lower()
    meta = context.get(file.name, {})
    subject = meta.get("subject", "(unknown)")
    sender = meta.get("sender", "(unknown)")

    # Content extraction
    if suffix == ".pdf":
        content = extract_text_from_pdf(file)
    elif suffix == ".txt":
        content = file.read_text(encoding="utf-8", errors="ignore")
    elif suffix in {".xls", ".xlsx"}:
        content = extract_text_from_excel(file)
    elif suffix in {".html", ".ics", ".csv", ".log"}:
        content = file.read_text(encoding="utf-8", errors="ignore")
    elif suffix in {".jpg", ".jpeg", ".png", ".gif", ".zip", ".rar"}:
        content = f"[Binary file type: {suffix}. No text content extracted.]"
        logger.info(f"Binary file: {file.name} — skipping summarization.")
    else:
        content = f"[Unknown or unsupported file type: {suffix}]"
        logger.warning(f"Unknown file type: {file.name} — recorded for later review.")
        unhandled = update_unhandled(unhandled, file, suffix, subject, sender)

    # Summarize if text-based or placeholder
    if "No text content" not in content and "Unknown or unsupported" not in content:
        result = summarize_document(content, file.name)
    else:
        result = {
            "summary": content,
            "contains_structured_data": False,
            "notes": "Skipped AI summarization.",
            "success": True
        }

    result.update({
        "filename": file.name,
        "timestamp": time.time(),
        "filetype": suffix,
        "subject": subject,
        "sender": sender
    })

    # Save analysis output
    out_file = ANALYSIS_DIR / f"{file.stem}.analysis.json"
    with out_file.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    logger.info(f"Saved analysis to {out_file.name}")

    # Categorization memory update
    if suffix in {".jpg", ".jpeg", ".png", ".gif", ".zip", ".rar"}:
        key = f"SENDER::{sender}::{suffix}"
        entry = {
            "source": sender,
            "filetype": suffix,
            "summary": f"[Binary file type: {suffix}. Multiple files from this sender.]",
            "contains_structured_data": False,
            "category": "(uncategorized)",
            "notes": ""
        }
    elif "Unknown or unsupported" in content:
        key = f"UNHANDLED::{file.name}"
        entry = {
            "source": sender,
            "filetype": suffix,
            "summary": content,
            "contains_structured_data": False,
            "category": "(awaiting user guidance)",
            "notes": ""
        }
    else:
        key = f"FILE::{file.name}"
        entry = {
            "source": sender,
            "subject": subject,
            "summary": result.get("summary"),
            "contains_structured_data": result.get("contains_structured_data"),
            "category": "(uncategorized)",
            "notes": ""
        }
    memory = update_memory(memory, key, entry)
    return memory, unhandled


def analyze_message_body(message: dict, memory: dict, unhandled: list):
    msg_id = message.get("message_id", "unknown")
    if has_been_analyzed(msg_id):
        logger.debug(f"Already analyzed message: {msg_id}")
        return memory, unhandled

    subject = message.get("subject", "(no subject)")
    sender = message.get("sender", "(no sender)")
    body = message.get("body", "")

    logger.info(f"Analyzing message ID: {msg_id}")
    result = summarize_document(body, f"{msg_id}.txt")
    result.update({
        "message_id": msg_id,
        "timestamp": time.time(),
        "filetype": "inline-message",
        "subject": subject,
        "sender": sender
    })

    out_file = ANALYSIS_DIR / f"{msg_id}.analysis.json"
    with out_file.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    logger.info(f"Saved analysis to {out_file.name}")

    key = f"MSG::{msg_id}"
    entry = {
        "source": sender,
        "subject": subject,
        "summary": result.get("summary"),
        "contains_structured_data": result.get("contains_structured_data"),
        "category": "(uncategorized)",
        "notes": ""
    }
    memory = update_memory(memory, key, entry)
    return memory, unhandled

# --- Entry point ---
def main():
    logger.info("File Analyzer starting...")

    memory = load_memory()
    unhandled = load_unhandled()
    attachment_context = load_downloaded_file_metadata()

    for file in DOWNLOADS_DIR.glob("*.*"):
        if has_been_analyzed(file.stem):
            logger.debug(f"Already analyzed: {file.name}")
            continue
        memory, unhandled = analyze_file(file, attachment_context, memory, unhandled)

    for message in load_fetched_messages():
        memory, unhandled = analyze_message_body(message, memory, unhandled)

    save_memory(memory)
    save_unhandled(unhandled)
    logger.info("File Analyzer finished.")

if __name__ == "__main__":
    main()
