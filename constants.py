"""
constants.py

Centralized configuration values for the entire agentic project:
- File and directory paths (heartbeat, downloads, logs, etc.)
- Magic numbers (intervals, timeouts, rotation schedules)
- API settings (OpenAI model, Gmail scopes, etc.)
- Static prompts or command templates

All paths are built off ROOT_DIR (the directory containing this file).
"""

from pathlib import Path

# Root directory for the project
ROOT_DIR = Path(__file__).parent
TOOLS_DIR = ROOT_DIR / "tools"

# ================================
# Common constants
# ================================
HASH_ALGORITHM = "sha256"
FILENAME_FORMAT = "{hash}_{original_name}"
API_TIMEOUT_SECONDS = 30

# ================================
# main.py constants
# ================================
# Heartbeat settings
HEARTBEAT_DIR = ROOT_DIR / "heartbeat"
HEARTBEAT_FILE = HEARTBEAT_DIR / "agent.status.json"
HEARTBEAT_INTERVAL = 60  # seconds

# Agent metadata
AGENT_NAME = "basic-agent"

# Logging settings for main
LOGS_DIR = ROOT_DIR / "logs"
MAIN_LOG_FILE = LOGS_DIR / "main.log"
MAIN_LOG_ROTATION = "1 week"

# ================================
# agent.py constants
# ================================
# Loop timing
LOOP_DELAY = 300  # seconds between cycles

# Logging settings for agent
AGENT_LOG_FILE = LOGS_DIR / "agent.log"
AGENT_LOG_ROTATION = "1 week"

# Modules and labels for run_tool calls
AGENT_MODULES = [
    ("tools.gmail_downloader", "Gmail Downloader"),
    ("tools.file_analyzer", "File Analyzer"),
    ("tools.process_downloaded_data", "Process Downloaded Data"),
]

# ================================
# gmail_downloader.py constants
# ================================
# File paths
TOKEN_FILE = ROOT_DIR / "token.json"
DOWNLOAD_DIR = ROOT_DIR / "downloads"
HISTORY_FILE = ROOT_DIR / "downloaded_attachments.json"
GMAIL_RESULTS_DIR = ROOT_DIR / "results"
GMAIL_RESULTS_FILE = GMAIL_RESULTS_DIR / "gmail_downloader.json"

# Gmail API settings
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
]
GMAIL_ATTACHMENT_QUERY = "has:attachment"
MAX_PAGE_SIZE = 100

# Logging settings for gmail_downloader
GMAIL_LOG_FILE = LOGS_DIR / "gmail_downloader.log"
GMAIL_LOG_ROTATION = "1 week"

# ================================
# file_analyzer.py constants
# ================================
# File paths
FILE_ANALYZER_DOWNLOADS_DIR = ROOT_DIR / "downloads"
FILE_ANALYZER_ANALYSIS_DIR = ROOT_DIR / "analysis"
FILE_ANALYZER_RESULTS_DIR = GMAIL_RESULTS_DIR
# RESULTS_DIR already defined above
FILE_ANALYZER_CONTEXT = GMAIL_RESULTS_FILE

FILE_ANALYZER_MEMORY_FILE = ROOT_DIR / "categorization_memory.json"
FILE_ANALYZER_UNHANDLED_FILE = ROOT_DIR / "unhandled_filedata.json"

# Logging settings for file_analyzer
FILE_ANALYZER_LOG_FILE = LOGS_DIR / "file_analyzer.log"
FILE_ANALYZER_LOG_ROTATION = "1 week"
FILE_ANALYZER_LOG_RETENTION = "4 weeks"

# ================================
# process_downloaded_data.py constants
# ================================
# Logging settings
PROCESS_DOWNLOADS_LOG_FILE = LOGS_DIR / "process_downloads.log"
PROCESS_DOWNLOADS_LOG_ROTATION = "1 week"

# Memory & data filenames (for process module)
PROCESS_DOWNLOADS_MEMORY_FILE = TOOLS_DIR / "categorization_memory.json"
PROCESS_DOWNLOADS_UNHANDLED_FILE = ROOT_DIR / "unhandled_filedata.json"
PROCESS_DOWNLOADS_PRINT_TOOL_PATH = TOOLS_DIR / "print_tool.py"

# Agent directories (flatten naming)
AGENT_ROOT = ROOT_DIR
AGENT_DOWNLOADS_DIR = AGENT_ROOT / "downloads"
AGENT_ARCHIVE_DIR = AGENT_ROOT / "archive"
AGENT_TOOLS_DIR = AGENT_ROOT / "tools"
AGENT_LOGS_DIR = AGENT_ROOT / "logs"

# ================================
# print_tool.py constants
# ================================
SUPPORTED_SUFFIXES = {'.pdf', '.html'}
LPR_CMD = 'lpr'
LPR_PRINTER_FLAG = '-P'
PRINT_TOOL_LOG_ROTATION = '1 week'

# ================================
# openai_tools.py constants
# ================================
OPENAI_MODEL = 'gpt-4o-mini'
OPENAI_TEMPERATURE = 0
SYSTEM_PROMPT_CONTENT: str = """\
You are a document-processing assistant. When given text, you will output exactly one JSON object
and nothing else—no bullet points, no introductory text, no code fences. The JSON MUST have these three fields:
  • summary (a concise prose summary)
  • contains_structured_data (true or false)
  • notes (any caveats or observations)
"""  # Note that the first character is '\' to avoid the first line being blank in this multiline string.

# ================================
# startup_checks.py constants
# ================================
STARTUP_CHECKS_REQUIRED_MODULES = [
    'utils.openai_tools',
    'tools.gmail_downloader',
    'tools.file_analyzer',
]
STARTUP_CHECKS_REQUIRED_DIRS = [
    TOOLS_DIR / 'downloads',
    TOOLS_DIR / 'analysis',
    TOOLS_DIR / 'results',
    LOGS_DIR,
]
STARTUP_CHECKS_REQUIRED_ENV_VARS = [
    'OPENAI_API_KEY',
    'GMAIL_CREDENTIALS_PATH',
]
DIAGNOSTIC_DIR = ROOT_DIR / 'heartbeat'
DIAGNOSTIC_FILE = DIAGNOSTIC_DIR / 'diagnostic.status.json'

# ================================
# watchdog.py constants
# ================================
WATCHDOG_HEARTBEAT_FILE = ROOT_DIR / 'heartbeat' / 'agent.status.json'
MAX_HEARTBEAT_AGE = 120  # seconds before considered stale
CHECK_INTERVAL = 30      # seconds between checks
AGENT_CMD = [
    sys.executable if (sys := __import__('sys')) else 'python',
    str(ROOT_DIR / 'main.py')
]
WATCHDOG_LOG_FILE = LOGS_DIR / 'watchdog.log'
WATCHDOG_LOG_ROTATION = '1 week'
