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
import subprocess
from utils.openai_tools import summarize_document, summarize_image
from constants import (
    FILE_ANALYZER_DOWNLOADS_DIR,
    GMAIL_DOWNLOADER_RESULTS,
    FILE_ANALYZER_ANALYSIS_DIR,
    FILE_ANALYZER_RESULTS_DIR,
    FILE_ANALYZER_CONTEXT,
    FILE_ANALYZER_MEMORY_FILE,
    FILE_ANALYZER_UNHANDLED_FILE,
    ANALYSIS_FILE_SUFFIX,
    LOGS_DIR,
    FILE_ANALYZER_LOG_FILE,
    FILE_ANALYZER_LOG_ROTATION,
    FILE_ANALYZER_LOG_RETENTION,
    FILE_ANALYZER_DOWNLOADS_DIR,
    FILE_ANALYZER_MEMORY_FILE,
    FILE_ANALYZER_UNHANDLED_FILE,
    SENDER_MEMORY_PREFIX,    
)

# Global paths and state files
# BASE_DIR = Path(__file__).resolve().parent
# DOWNLOADS_DIR = BASE_DIR / "downloads"
# ANALYSIS_DIR = BASE_DIR / "analysis"
# RESULTS_DIR = BASE_DIR / "results"
# LOGS_DIR = BASE_DIR / "logs"
# MEMORY_FILE = BASE_DIR / "categorization_memory.json"
# UNHANDLED_FILE = BASE_DIR / "unhandled_filedata.json"

# In-memory state
memory = {}
unhandled = []
context = {}


def ensure_directories():
    """Create required directories if they don't exist."""
    for d in (FILE_ANALYZER_DOWNLOADS_DIR, 
              FILE_ANALYZER_ANALYSIS_DIR, 
              FILE_ANALYZER_RESULTS_DIR, 
              LOGS_DIR
              ):
        d.mkdir(parents=True, exist_ok=True)


def configure_logging():
    """Configure Loguru to write to a rotating log file."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logger.add(
        FILE_ANALYZER_LOG_FILE,
        rotation=FILE_ANALYZER_LOG_ROTATION,
        retention=FILE_ANALYZER_LOG_RETENTION,
        level="DEBUG"
    )


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
    """
    Load file metadata from GMAIL_DOWNLOADER_RESULTS and return a mapping:
      filename → {"subject": ..., "sender": ...}
    Works whether your JSON is:
      - a dict keyed by timestamps: { "2025-06-07T12:00Z": { "downloads":[…] }, … }
      - or a list of run-objects: [ { "downloads":[…] }, … ]
    """
    path = FILE_ANALYZER_CONTEXT
    if not path.exists():
        logger.warning(f"No {GMAIL_DOWNLOADER_RESULTS} found at {path}")
        return {}

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"Failed to load context file {path}: {e}")
        return {}

    # Gather every run’s downloads list
    runs = []
    if isinstance(raw, dict):
        for run in raw.values():
            if isinstance(run, dict) and "downloads" in run:
                runs.extend(run["downloads"])
    elif isinstance(raw, list):
        for run in raw:
            if isinstance(run, dict) and "downloads" in run:
                runs.extend(run["downloads"])

    # Build the filename → metadata map
    context_map = {}
    for item in runs:
        fn = item.get("filename")
        if not fn:
            continue
        context_map[fn] = {
            "subject": item.get("subject", "(unknown)"),
            "sender":  item.get("sender", "(unknown)")
        }

    return context_map



def load_messages() -> list:
    """Load inline messages from GMAIL_DOWNLOADER_RESULTS."""
    path = FILE_ANALYZER_RESULTS_DIR / GMAIL_DOWNLOADER_RESULTS 
    if not path.exists():
        logger.warning(f"No {path} found.")
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("messages_saved", [])
    except Exception as e:
        logger.error(f"Failed to load messages: {e}")
        return []


def is_analyzed(stem: str) -> bool:
    """Check if an analysis file already exists for a stem."""
    return (FILE_ANALYZER_ANALYSIS_DIR / f"{stem}{ANALYSIS_FILE_SUFFIX}").exists()


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

def ai_examine(file: Path) -> str:
    """Use AI to analyze image content."""
    try:
        content_dict = summarize_image(file)
        if isinstance(content_dict, str):
            logger.error(f"AI examination returned string instead of JSON: {content_dict}")
            return f"[Error analyzing image: {file.name}]"
        if not isinstance(content_dict, dict):
            logger.error(f"AI examination returned non-dict type: {type(content_dict)} for {file.name}")
            return f"[Error analyzing image: {file.name}]"
        summary = content_dict.get("summary", "")
        contains_structured_data = content_dict.get("contains_structured_data", False)
        notes = content_dict.get("notes", "")
        if not summary:
            logger.error(f"AI examination returned empty summary for {file.name}")
            return f"[Error analyzing image: {file.name}]"
        return summary
    
    except Exception as e:
        logger.error(f"{e}: AI examination error for {file.name}")
        return f"[Error analyzing image: {file.name}]"

def extract_content(file: Path) -> str:
    """Extract text content or mark binary/unsupported types."""
    suffix = file.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf(file)
    if suffix in {".xls", ".xlsx"}:
        return extract_excel(file)
    if suffix in {".txt", ".html", ".csv", ".log"}:
        return file.read_text(encoding="utf-8", errors="ignore")
    if suffix in {".jpg", ".jpeg", ".png", ".gif"}:
        return ai_examine(file)
    if suffix in {".zip", ".rar"}:
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
        return {"summary": content, "contains_structured_data": False, "notes": f"Skipped AI summarization. {identifier}"}
    try:
        return summarize_document(content, identifier)
    except Exception as e:
        logger.error(f"Summarization error for {identifier}: {e}")
        return {"summary": content, "contains_structured_data": False, "notes": ""}


def save_analysis(stem: str, analysis: dict):
    """Write analysis JSON to the analysis directory."""
    # path = FILE_ANALYZER_ANALYSIS_DIR / f"{stem}.analysis.json"
    path = FILE_ANALYZER_ANALYSIS_DIR / f"{stem}{ANALYSIS_FILE_SUFFIX}"
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
    logger.debug(f"Metadata for {file.name}: {meta}")
    subject = meta.get("subject", "(unknown)")
    sender = meta.get("sender", "(unknown)")

    content = extract_content(file)

    logger.debug(f"Content length: {len(content)} characters")
    logger.debug(f"Content type: {type(content)}")    
    if not content:
        logger.warning(f"No content extracted from {file.name}, skipping analysis.")
        record_unhandled(file, suffix)
        return

    logger.debug(f"Extracted content from {file.name} ({suffix}): {content}...") 

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
    for file in FILE_ANALYZER_DOWNLOADS_DIR.glob("*.*"):
        if is_analyzed(file.stem):
            logger.debug(f"Already analyzed: {file.name}")
            continue
        logger.info(f"Processing file: {file.name}")
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
    memory = load_json(FILE_ANALYZER_MEMORY_FILE, {})
    unhandled = load_json(FILE_ANALYZER_UNHANDLED_FILE, [])
    context = load_context()

    run()

    # ─── Re‐visit unhandled entries to see if notes were filled in ───
    remaining_unhandled = []
    for entry in unhandled:
        sender   = entry.get("sender", "(unknown)")
        filetype = entry.get("filetype", "")
        filename = entry.get("filename", "")
        # Rebuild the memory key exactly as update_memory() did:
        key = f"{SENDER_MEMORY_PREFIX}{sender}::{filetype}"
        mem_entry = memory.get(key)

        # If this sender+filetype now has non‐empty notes, process it:
        if mem_entry and mem_entry.get("notes", "").strip():
            # The user has populated “notes” since last run—invoke your processor.
            file_path = FILE_ANALYZER_DOWNLOADS_DIR / filename
            if file_path.exists():
                logger.info(f"Reprocessing unhandled '{filename}' because notes were added.")
                try:
                    # You can call your existing processor script (e.g. process_downloaded_data.py).
                    # Replace the next line with however you normally invoke your processor:
                    subprocess.run(
                        ["python3", "utils/process_downloaded_data.py", "--input", str(file_path)],
                        check=True,
                    )
                    # run_tool("utils.process_downloaded_data", "Process Downloaded Data", arguments=["--input", str(file_path)])
                    logger.info(f"Processor completed for '{filename}'.")
                except Exception as e:
                    logger.error(f"Processor failed on '{filename}': {e}")
            else:
                logger.warning(f"File not found (cannot reprocess): {filename}")
            # Do NOT add this entry back to remaining_unhandled (it’s now handled)

        else:
            # Still no notes → keep in unhandled for next time
            remaining_unhandled.append(entry)

    # Overwrite unhandled with only those still missing notes:
    unhandled = remaining_unhandled
    # ────────────────────────────────────────────────────────────────────────────

    save_json(memory, FILE_ANALYZER_MEMORY_FILE)
    save_json(unhandled, FILE_ANALYZER_UNHANDLED_FILE)
    logger.info("Analysis complete.")


if __name__ == "__main__":
    main()
