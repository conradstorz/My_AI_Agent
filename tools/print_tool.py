#!/usr/bin/env python3
"""
Standalone printing tool for PDF and HTML files.

Usage:
    python print_tool.py [--printer PRINTER_NAME] file1 [file2 ...]

Supports sending PDF or HTML files to the system's default or specified printer.
"""
import argparse
import platform
import subprocess
from pathlib import Path
from loguru import logger

try:
    import win32print
except ImportError:
    win32print = None


def print_file(path: Path, printer: str = None):
    system = platform.system()
    if system in ("Linux", "Darwin"):
        cmd = ["lpr"]
        if printer:
            cmd.extend(["-P", printer])
        cmd.append(str(path))
        try:
            subprocess.run(cmd, check=True)
            logger.info(f"Sent {path.name} to printer{' ' + printer if printer else ''} via lpr.")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to print {path.name} via lpr: {e}")
    elif system == "Windows" and win32print:
        target_printer = printer or win32print.GetDefaultPrinter()
        try:
            hprinter = win32print.OpenPrinter(target_printer)
            win32print.StartDocPrinter(hprinter, 1, (path.name, None, "RAW"))
            win32print.StartPagePrinter(hprinter)
            with path.open("rb") as f:
                data = f.read()
                win32print.WritePrinter(hprinter, data)
            win32print.EndPagePrinter(hprinter)
            win32print.EndDocPrinter(hprinter)
            logger.info(f"Printed {path.name} on {target_printer}.")
        except Exception as e:
            logger.error(f"Failed to print {path.name} on Windows: {e}")
        finally:
            try:
                win32print.ClosePrinter(hprinter)
            except Exception:
                pass
    else:
        logger.error(f"Printing not supported on {system}. Ensure win32print is installed on Windows.")


def main():
    parser = argparse.ArgumentParser(
        description="Standalone printing tool for PDF and HTML files."
    )
    parser.add_argument(
        "files", nargs="+", type=Path,
        help="Paths to PDF or HTML files to print."
    )
    parser.add_argument(
        "--printer", "-P", type=str, default=None,
        help="Name of the printer (defaults to system default)."
    )
    parser.add_argument(
        "--log", type=Path, default=None,
        help="Optional path to log file (uses stdout if not set)."
    )
    args = parser.parse_args()

    # Configure logging
    if args.log:
        args.log.parent.mkdir(parents=True, exist_ok=True)
        logger.add(args.log, rotation="1 week")
    else:
        logger.remove()  # prevent duplicate default logs
        logger.add(lambda msg: print(msg, end=''))

    for file_path in args.files:
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            continue
        suffix = file_path.suffix.lower()
        if suffix not in {'.pdf', '.html'}:
            logger.warning(f"Unsupported file type {suffix}, skipping {file_path.name}.")
            continue
        print_file(file_path, args.printer)


if __name__ == '__main__':
    main()
