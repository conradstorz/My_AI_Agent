import fitz  # PyMuPDF
import os
import json
import time
from pathlib import Path
from loguru import logger
import pandas as pd
from Utils.openAI_tools import summarize_document


BASE_DIR = Path(__file__).resolve().parent
DOWNLOADS_DIR = BASE_DIR / "downloads"
ANALYSIS_DIR = BASE_DIR / "analysis"
RESULT_LOG = BASE_DIR / "logs" / "file_analyzer.log"
ANALYSIS_DIR.mkdir(exist_ok=True, parents=True)

logger.add(RESULT_LOG, rotation="1 week")


def has_already_been_analyzed(file: Path) -> bool:
    out_file = ANALYSIS_DIR / f"{file.stem}.analysis.json"
    return out_file.exists()


def extract_text_from_pdf(pdf_path: Path) -> str:
    doc = fitz.open(pdf_path)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text


def extract_text_from_excel(file: Path) -> str:
    try:
        excel = pd.read_excel(file, sheet_name=None, engine="openpyxl")
    except Exception as e:
        logger.error(f"Failed to read Excel file: {file.name}, error: {e}")
        return ""

    summaries = []
    for sheet_name, df in excel.items():
        summaries.append(f"--- Sheet: {sheet_name} ---")
        summaries.append(df.head(10).to_string(index=False))  # Show top rows
        summaries.append("")

    return "\n".join(summaries)


def analyze_file(file: Path):
    logger.info(f"Analyzing file: {file.name}")
    suffix = file.suffix.lower()
    if suffix == ".pdf":
        content = extract_text_from_pdf(file)
    elif suffix == ".txt":
        content = file.read_text(encoding="utf-8", errors="ignore")
    elif suffix in {".xls", ".xlsx"}:
        content = extract_text_from_excel(file)
    else:
        logger.warning(f"Unsupported file type: {file.name}")
        return

    result = summarize_document(content, file.name)

    result.update({
        "filename": file.name,
        "timestamp": time.time(),
        "filetype": file.suffix.lower()
    })

    result_path = ANALYSIS_DIR / f"{file.stem}.analysis.json"
    with result_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    logger.info(f"Saved analysis to {result_path.name}")

def main():
    logger.info("FileAnalyzer starting...")
    for file in DOWNLOADS_DIR.glob("*.*"):
        if has_already_been_analyzed(file):
            logger.debug(f"Already analyzed: {file.name}")
            continue
        analyze_file(file)

if __name__ == "__main__":
    main()
