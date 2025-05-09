#!/usr/bin/env python3
"""
Process downloaded data based on user directives in categorization_memory.json.
"""
import json  # for loading and parsing JSON files
import subprocess  # to invoke the print tool as an external subprocess
from pathlib import Path  # for filesystem path manipulations
from loguru import logger  # for structured logging throughout the script

# --- Paths ---
# BASE_DIR: directory where this script resides
BASE_DIR = Path(__file__).resolve().parent
# Directory where downloaded files are stored
DOWNLOADS_DIR = BASE_DIR / "downloads"
# Directory for analysis results (not directly used in this script)
ANALYSIS_DIR = BASE_DIR / "analysis"
# Directory where processing results are written (not directly used here)
RESULTS_DIR = BASE_DIR / "results"
# Path to the memory file that contains processing directives for each download
MEMORY_FILE = BASE_DIR / "categorization_memory.json"
# Path to JSON storing data entries that could not be automatically handled
UNHANDLED_FILEDATA = BASE_DIR / "unhandled_filedata.json"
# Directory for log files
LOGS_DIR = BASE_DIR / "logs"

# Configure logging: create a rotating log file under LOGS_DIR
# Rotation policy: new file every week
logger.add(LOGS_DIR / "process_downloads.log", rotation="1 week")


def main():
    """
    Main entry point for processing downloaded data according to user-defined directives.
    """
    # Log the start of the processing routine
    logger.info("🚀 Starting ProcessDownloadedData tool")

    # Determine the agent's root directory (one level up from this script)
    agent_root = Path(__file__).resolve().parent.parent
    # Define key directories relative to the agent root
    downloads_dir = agent_root / "downloads"
    archive_dir = agent_root / "archive"
    tools_dir = agent_root / "tools"
    # Ensure the archive directory exists to move processed files into
    archive_dir.mkdir(exist_ok=True)

    # Log resolved paths for debugging purposes
    logger.debug(f"Agent root directory: {agent_root}")
    logger.debug(f"Downloads directory: {downloads_dir}")
    logger.debug(f"Archive directory:   {archive_dir}")
    logger.debug(f"Tools directory:     {tools_dir}")

    # Construct path to the memory file in the tools directory
    mem_path = tools_dir / "categorization_memory.json"
    # If memory file does not exist, warn and exit
    if not mem_path.exists():
        logger.warning(f"No memory file found at {mem_path}; skipping post-processing.")
        return

    # Attempt to load the memory file content
    try:
        memory = json.loads(mem_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"Failed to load memory file at {mem_path}: {e}")
        return

    # Initialize counters for summary statistics
    total_entries       = len(memory)
    entries_processed   = 0
    entries_skipped     = 0
    entries_printed     = 0
    total_files_found   = 0
    total_files_printed = 0
    total_errors        = 0

    logger.info(f"Loaded {total_entries} memory entries")

    # Load any unhandled filedata entries for potential future use
    unhandled = []
    if UNHANDLED_FILEDATA.exists():
        try:
            unhandled = json.loads(UNHANDLED_FILEDATA.read_text(encoding="utf-8"))
            logger.info(f"Loaded {len(unhandled)} unhandled file data entries")
        except Exception as e:
            # Log failure to load unhandled entries but continue processing
            logger.error(f"Failed to load unhandled file data: {e}")

    # Iterate over each entry in memory to process as directed
    for key, entry in memory.items():
        # Extract and normalize the user-specified directive (e.g., "print")
        directive = entry.get("notes", "").strip().lower()
        logger.debug(f"Processing entry key={key!r}, directive={directive!r}")

        # If directive is not "print", count as skipped and continue
        if directive != "print":
            entries_skipped += 1
            logger.trace(f"Skipping entry {key!r}: directive is not 'print'")
            continue
        # Count entries we will attempt to process
        entries_processed += 1

        # Find all downloaded files matching the specified filetype suffix
        filetype = entry.get("filetype", "")
        candidates = list(downloads_dir.glob(f"*{filetype}"))
        num_candidates = len(candidates)
        total_files_found += num_candidates

        # Log how many matching files were found for this entry
        logger.info(f"Entry {key!r}: found {num_candidates} file(s) with suffix {filetype!r}")
        # If no files found, warn and move to next entry
        if not candidates:
            logger.warning(f"No matching downloads for entry {key!r}; continuing")
            continue

        # Process each matching file: invoke print tool, then archive
        for file in candidates:
            try:
                # Log which file is being sent to print
                logger.info(f"📠 Printing file {file.name} for entry {key!r}")
                # Call the external print_tool.py script with the file path
                subprocess.run(
                    ["python", str(agent_root / "print_tool.py"), str(file)],
                    check=True
                )
                total_files_printed += 1
                logger.debug(f"Print subprocess completed for {file.name}")

                # After successful print, move the file to the archive directory
                target = archive_dir / file.name
                file.rename(target)
                entries_printed += 1
                logger.info(f"📂 Archived {file.name} → {target}")

            except subprocess.CalledProcessError as e:
                # Handle errors returned by the subprocess
                total_errors += 1
                logger.error(f"Printing subprocess failed for {file.name}: {e}")
            except Exception as e:
                # Catch-all for unexpected errors during processing
                total_errors += 1
                logger.exception(f"Unexpected error processing {file.name}: {e}")

    # Log a summary of the processing run
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
    # Execute main if this script is run directly
    main()
