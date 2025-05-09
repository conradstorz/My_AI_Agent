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

GMAIL_DOWNLOAD_RESULT = RESULTS_DIR / "gmail_downloader.json"
GMAIL_QUERY_RESULT = RESULTS_DIR / "gmail_query_fetcher.json"
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)
logger.add(LOGS_DIR / "file_analyzer.log", rotation="1 week")

ANALYSIS_DIR.mkdir(exist_ok=True, parents=True)
load_dotenv()

# --- Categorization memory ---
def load_memory() -> dict:
    if MEMORY_FILE.exists():
        with MEMORY_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_memory(memory: dict):
    with MEMORY_FILE.open("w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2)

def update_memory(memory: dict, key: str, entry: dict):
    if key not in memory:
        memory[key] = entry
        logger.info(f"Categorization memory updated with key: {key}")
    return memory

# --- File extractors ---
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

# --- Result source loaders ---
def load_downloaded_file_metadata() -> dict:
    if not GMAIL_DOWNLOAD_RESULT.exists():
        logger.warning("No gmail_downloader.json found.")
        return {}
    try:
        with GMAIL_DOWNLOAD_RESULT.open("r") as f:
            data = json.load(f)
            return {item["filename"]: {"subject": item["subject"], "sender": item["sender"]}
                    for item in data.get("downloads", [])}
    except Exception as e:
        logger.error(f"Failed to load gmail_downloader.json: {e}")
        return {}

def load_fetched_messages() -> list:
    if not GMAIL_QUERY_RESULT.exists():
        logger.warning("No gmail_query_fetcher.json found.")
        return []
    try:
        with GMAIL_QUERY_RESULT.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("messages_saved", [])
    except Exception as e:
        logger.error(f"Failed to load gmail_query_fetcher.json: {e}")
        return []

# --- Analysis logic ---
def analyze_file(file: Path, context: dict, memory: dict):
    logger.info(f"Analyzing file: {file.name}")
    suffix = file.suffix.lower()

    # Try to extract readable content
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
        logger.info(f"Binary file: {file.name} — logged for review.")
    else:
        content = f"[Unknown or unsupported file type: {suffix}]"
        logger.warning(f"Unknown file type: {file.name} — placeholder used.")

    metadata = context.get(file.name, {})
    subject = metadata.get("subject", "(unknown)")
    sender = metadata.get("sender", "(unknown)")

    result = summarize_document(content, file.name) if "No text content" not in content else {
        "summary": content,
        "contains_structured_data": False,
        "notes": "Skipped AI summarization due to unsupported format.",
        "success": True
    }

    result.update({
        "filename": file.name,
        "timestamp": time.time(),
        "filetype": suffix,
        "subject": subject,
        "sender": sender
    })

    out_file = ANALYSIS_DIR / f"{file.stem}.analysis.json"
    with out_file.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    logger.info(f"Saved analysis to {out_file.name}")

    memory_key = f"FILE::{file.name}"
    memory_entry = {
        "source": sender,
        "subject": subject,
        "summary": result.get("summary"),
        "contains_structured_data": result.get("contains_structured_data"),
        "category": "(uncategorized)",
        "notes": ""
    }
    update_memory(memory, memory_key, memory_entry)


def analyze_message_body(message: dict, memory: dict):
    msg_id = message.get("message_id", "unknown")
    if has_been_analyzed(msg_id):
        logger.debug(f"Already analyzed message: {msg_id}")
        return

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

    memory_key = f"MSG::{msg_id}"
    memory_entry = {
        "source": sender,
        "subject": subject,
        "summary": result.get("summary"),
        "contains_structured_data": result.get("contains_structured_data"),
        "category": "(uncategorized)",
        "notes": ""
    }
    update_memory(memory, memory_key, memory_entry)

# --- Entry ---
def main():
    logger.info("File Analyzer starting...")

    memory = load_memory()

    # Analyze files from downloads/
    attachment_context = load_downloaded_file_metadata()
    for file in DOWNLOADS_DIR.glob("*.*"):
        if has_been_analyzed(file.stem):
            logger.debug(f"Already analyzed: {file.name}")
            continue
        analyze_file(file, attachment_context, memory)

    # Analyze fetched messages
    for message in load_fetched_messages():
        analyze_message_body(message, memory)

    save_memory(memory)
    logger.info("File Analyzer finished.")

if __name__ == "__main__":
    main()
