#!/usr/bin/env python3
"""
Process downloaded data based on user directives in categorization_memory.json.
"""
import json
import subprocess
from pathlib import Path
from loguru import logger


# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent
DOWNLOADS_DIR = BASE_DIR / "downloads"
ANALYSIS_DIR = BASE_DIR / "analysis"
RESULTS_DIR = BASE_DIR / "results"
MEMORY_FILE = BASE_DIR / "categorization_memory.json"
UNHANDLED_FILEDATA = BASE_DIR / "unhandled_filedata.json"
LOGS_DIR = BASE_DIR / "logs"

# Configure logging
logger.add(LOGS_DIR / "process_downloads.log", rotation="1 week")



def main():
    logger.info("🚀 Starting ProcessDownloadedData tool")
    agent_root    = Path(__file__).resolve().parent.parent
    downloads_dir = agent_root / "downloads"
    archive_dir   = agent_root / "archive"
    tools_dir     = agent_root / "tools"
    archive_dir.mkdir(exist_ok=True)

    logger.debug(f"Agent root directory: {agent_root}")
    logger.debug(f"Downloads directory: {downloads_dir}")
    logger.debug(f"Archive directory:   {archive_dir}")
    logger.debug(f"Tools directory:     {tools_dir}")

    mem_path = tools_dir / "categorization_memory.json"
    if not mem_path.exists():
        logger.warning(f"No memory file found at {mem_path}; skipping post-processing.")
        return

    try:
        memory = json.loads(mem_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"Failed to load memory file at {mem_path}: {e}")
        return

    total_entries       = len(memory)
    entries_processed   = 0
    entries_skipped     = 0
    entries_printed     = 0
    total_files_found   = 0
    total_files_printed = 0
    total_errors        = 0

    logger.info(f"Loaded {total_entries} memory entries")

    # now load list of unhandled file data
    unhandled = []
    if UNHANDLED_FILEDATA.exists():
        try:
            unhandled = json.loads(UNHANDLED_FILEDATA.read_text(encoding="utf-8"))
            logger.info(f"Loaded {len(unhandled)} unhandled file data entries")
        except Exception as e:
            logger.error(f"Failed to load unhandled file data: {e}")
        





    for key, entry in memory.items():
        directive = entry.get("notes", "").strip().lower()
        logger.debug(f"Processing entry key={key!r}, directive={directive!r}")

        if directive != "print":
            entries_skipped += 1
            logger.trace(f"Skipping entry {key!r}: directive is not 'print'")
            continue
        entries_processed += 1

        filetype = entry.get("filetype", "")
        candidates = list(downloads_dir.glob(f"*{filetype}"))
        num_candidates = len(candidates)
        total_files_found += num_candidates

        logger.info(f"Entry {key!r}: found {num_candidates} file(s) with suffix {filetype!r}")
        if not candidates:
            logger.warning(f"No matching downloads for entry {key!r}; continuing")
            continue

        for file in candidates:
            try:
                logger.info(f"📠 Printing file {file.name} for entry {key!r}")
                subprocess.run(
                    ["python", str(agent_root / "print_tool.py"), str(file)],
                    check=True
                )
                total_files_printed += 1
                logger.debug(f"Print subprocess completed for {file.name}")

                target = archive_dir / file.name
                file.rename(target)
                entries_printed += 1
                logger.info(f"📂 Archived {file.name} → {target}")

            except subprocess.CalledProcessError as e:
                total_errors += 1
                logger.error(f"Printing subprocess failed for {file.name}: {e}")
            except Exception as e:
                total_errors += 1
                logger.exception(f"Unexpected error processing {file.name}: {e}")

    logger.info("🚦 ProcessDownloadedData summary:")
    logger.info(f"  Total entries in memory:      {total_entries}")
    logger.info(f"  Entries with print directive: {entries_processed}")
    logger.info(f"  Entries skipped:              {entries_skipped}")
    logger.info(f"  Total files found:            {total_files_found}")
    logger.info(f"  Total files printed:          {total_files_printed}")
    logger.info(f"  Total entries printed:        {entries_printed}")
    logger.info(f"  Total errors encountered:     {total_errors}")
    logger.info("✅ ProcessDownloadedData complete")

if __name__ == "__main__":
    main()
