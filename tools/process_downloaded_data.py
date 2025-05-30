#!/usr/bin/env python3
"""
Process downloaded data based on user directives in categorization_memory.json
Breaks the workflow into discrete functions for clarity and testability.
"""
import json
import subprocess
from pathlib import Path
from loguru import logger

# --- Configuration Constants ---
LOG_FILENAME = "process_downloads.log"
MEMORY_FILENAME = "categorization_memory.json"
UNHANDLED_FILENAME = "unhandled_filedata.json"
PRINT_TOOL_SCRIPT = "print_tool.py"


def configure_paths():
    """
    Resolve and return all key directories and file paths as a dict.
    """
    base_dir = Path(__file__).resolve().parent
    agent_root = base_dir.parent

    paths = {
        "agent_root": agent_root,
        "downloads_dir": agent_root / "downloads",
        "archive_dir":  agent_root / "archive",
        "tools_dir":    agent_root / "tools",
        "logs_dir":     agent_root / "logs",
        "mem_path":     agent_root / "tools" / MEMORY_FILENAME,
        "unhandled_path": agent_root / UNHANDLED_FILENAME,
        "print_tool":   agent_root / PRINT_TOOL_SCRIPT,
    }
    return paths


def setup_logging(logs_dir: Path):
    """
    Configure Loguru to write to a rotating log file under logs_dir.
    """
    logs_dir.mkdir(exist_ok=True)
    logger.add(logs_dir / LOG_FILENAME, rotation="1 week")
    logger.info("Logging configured: {}", logs_dir / LOG_FILENAME)


def load_json(path: Path, default=None):
    """
    Load JSON data from path or return default on failure.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning("JSON file not found: {}", path)
    except Exception as err:
        logger.error("Failed to load {}: {}", path, err)
    return default


def process_file(file_path: Path, key: str, print_tool: Path, archive_dir: Path, stats: dict):
    """
    Invoke the external print tool on file_path, then archive it.
    Update stats accordingly.
    """
    try:
        logger.info("Printing {} for entry {}", file_path.name, key)
        subprocess.run(["python", str(print_tool), str(file_path)], check=True)
        stats["files_printed"] += 1

        target = archive_dir / file_path.name
        file_path.rename(target)
        stats["archived"] += 1
        logger.info("Archived {} → {}", file_path.name, target)
    except subprocess.CalledProcessError as e:
        stats["errors"] += 1
        logger.error("Print subprocess failed for {}: {}", file_path.name, e)
    except Exception as e:
        stats["errors"] += 1
        logger.exception("Unexpected error processing {}: {}", file_path.name, e)


def process_memory_entries(memory: dict, downloads_dir: Path, archive_dir: Path, print_tool: Path):
    """
    Iterate memory entries, process those marked 'print', and collect statistics.
    """
    stats = {
        "total_entries":      len(memory),
        "to_print_entries":   0,
        "skipped_entries":    0,
        "files_found":        0,
        "files_printed":      0,
        "archived":           0,
        "errors":             0,
    }

    for key, entry in memory.items():
        directive = entry.get("notes", "").strip().lower()
        if directive != "print":
            stats["skipped_entries"] += 1
            logger.debug("Skipping {} (directive={!r})", key, directive)
            continue

        stats["to_print_entries"] += 1
        suffix = entry.get("filetype", "")
        matched = list(downloads_dir.glob(f"*{suffix}"))
        stats["files_found"] += len(matched)
        logger.info("Entry {}: found {} files with suffix {!r}", key, len(matched), suffix)

        if not matched:
            continue

        for file_path in matched:
            process_file(file_path, key, print_tool, archive_dir, stats)

    return stats


def summarize(stats: dict):
    """
    Log a summary of the processing run.
    """
    logger.info("----- ProcessDownloadedData Summary -----")
    logger.info("Total entries:            {}", stats.get("total_entries"))
    logger.info("Entries to print:         {}", stats.get("to_print_entries"))
    logger.info("Entries skipped:          {}", stats.get("skipped_entries"))
    logger.info("Files found:              {}", stats.get("files_found"))
    logger.info("Files printed:            {}", stats.get("files_printed"))
    logger.info("Files archived:           {}", stats.get("archived"))
    logger.info("Errors encountered:       {}", stats.get("errors"))
    logger.info("---------------------------------------")


def main():
    """
    Main entry point: configure environment, load data, process entries, and summarize.
    """
    paths = configure_paths()
    setup_logging(paths["logs_dir"])
    logger.info("🚀 Starting ProcessDownloadedData")

    memory = load_json(paths["mem_path"], default={})
    if not memory:
        logger.warning("No memory entries to process. Exiting.")
        return

    # Ensure archive directory exists
    paths["archive_dir"].mkdir(exist_ok=True)

    # load unhandled data 
    unhandled_data = load_json(paths["unhandled_path"], default=[])

    if unhandled_data:
        logger.info(f"Found unhandled data: {len(unhandled_data)} entries")
        # Remove entries from unhandled data that are already in memory
        for entry in unhandled_data:
            key = entry.get("key")
            if key in memory:
                logger.info(f"Removing {key} from unhandled data")
                unhandled_data.remove(entry)

        # process each item in unhandled data
        for entry in unhandled_data:
            file_path = entry.get("file_path")
            if file_path:
                file_path = paths["downloads_dir"] / file_path
                if file_path.exists():
                    logger.info(f"Processing unhandled file: {file_path.name}")
                    # read the notes for this data item and see if there is processing we can do.
                else:
                    logger.warning(f"File not found: {file_path.name}")
            else:
                logger.warning("No file path provided in unhandled data entry")


        # Save updated unhandled data
        with paths["unhandled_path"].open("w") as f:
            json.dump(unhandled_data, f, indent=2)
    stats = process_memory_entries(
        memory,
        paths["downloads_dir"],
        paths["archive_dir"],
        paths["print_tool"],
    )

    summarize(stats)
    logger.info("✅ ProcessDownloadedData complete")


if __name__ == "__main__":
    main()
