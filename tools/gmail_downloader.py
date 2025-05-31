"""
Gmail Downloader Module

This module handles authentication with the Gmail API, checks for new unread messages with attachments,
downloads attachments to a local directory, and records processing history and results.

Usage:
    python gmail_downloader.py

Requirements:
    - A `.env` file or environment variable `GMAIL_CREDENTIALS_PATH` pointing to the Gmail API credentials.
    - Google OAuth2 client libraries installed (`google-auth`, `google-auth-oauthlib`, `google-api-python-client`).

Files:
    - `token.json`: Stores OAuth2 tokens after the initial authentication flow.
    - `downloaded_attachments.json`: Tracks processed message IDs and attachment hashes.
    - `gmail_downloader.json`: Appends download results for each run.

"""
from pathlib import Path  # Simplifies filesystem path handling
from loguru import logger   # Structured logging library
import base64               # For decoding email attachment content
import hashlib              # For computing SHA-256 hashes
import json                 # JSON serialization/deserialization
import os                   # Environment variable access
import pickle               # Token storage format
import time                 # Timestamping results
from dotenv import load_dotenv  # Load .env files
from google.auth.transport.requests import Request  # Refresh OAuth tokens
from google_auth_oauthlib.flow import InstalledAppFlow  # OAuth2 flow
from googleapiclient.discovery import build  # Gmail API client builder
from google.auth.exceptions import RefreshError  # Handle token refresh errors
from constants import (
    DOWNLOAD_DIR,
    HISTORY_FILE,
    GMAIL_RESULTS_DIR,
    GMAIL_RESULTS_FILE,
    TOKEN_FILE,
    GMAIL_SCOPES,
    GMAIL_ATTACHMENT_QUERY,
    MAX_PAGE_SIZE,
    LOGS_DIR,
    GMAIL_LOG_FILE,
    GMAIL_LOG_ROTATION,
    GMAIL_SCOPES,
)
# Load environment variables from a .env file, overriding existing environment values
load_dotenv(override=True)

# --- Configuration constants ---
# BASE_DIR = Path(__file__).resolve().parent  # Root directory for module files
# DOWNLOAD_DIR = BASE_DIR / "downloads"     # Where attachments will be saved
# HISTORY_FILE = BASE_DIR / "downloaded_attachments.json"  # Tracks processed items
# RESULTS_DIR = BASE_DIR / "results"        # Stores run result logs
# RESULTS_FILE = RESULTS_DIR / "gmail_downloader.json"  # JSON file for each run's summary
# TOKEN_FILE = BASE_DIR / "token.json"      # OAuth token cache
# SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]  # Permissions for Gmail API


def get_credentials_file():
    """
    Retrieve the Gmail API credentials file path defined by the environment.

    :return: Path to the Gmail credentials JSON file.
    :rtype: pathlib.Path
    :raises FileNotFoundError: If the environment variable is missing or file not found.
    """
    # Read the credentials path from environment
    credentials_path = os.environ.get("GMAIL_CREDENTIALS_PATH")
    logger.debug(f"GMAIL_CREDENTIALS_PATH={credentials_path}")

    # If not set, abort with an error
    if not credentials_path:
        logger.error("Environment variable GMAIL_CREDENTIALS_PATH not set.")
        raise FileNotFoundError("Missing environment variable: GMAIL_CREDENTIALS_PATH")

    # Construct a Path object and verify it exists
    credentials_file = Path(credentials_path)
    if not credentials_file.exists():
        logger.error(f"Credentials file does not exist at: {credentials_file}")
        raise FileNotFoundError(f"Gmail credentials file not found: {credentials_file}")

    # Log and return the valid credentials file
    logger.info(f"Using credentials file: {credentials_file}")
    return credentials_file


def authenticate():
    """
    Authenticate with the Gmail API using OAuth2.

    Attempts to load a cached token, refresh it if expired, or perform a new OAuth flow.

    :return: Gmail API service client.
    :rtype: googleapiclient.discovery.Resource
    """
    # Locate the client secrets file
    credentials_file = get_credentials_file()
    creds = None

    # If a token cache exists, load it
    if TOKEN_FILE.exists():
        logger.debug(f"Found token file: {TOKEN_FILE}")
        with open(TOKEN_FILE, "rb") as token_fp:
            creds = pickle.load(token_fp)
    else:
        logger.debug("No token file found. Will initiate OAuth2 flow.")

    # If no valid credentials or expired, refresh or run the flow
    if not creds or not creds.valid:
        # If expired but refresh token available, try to refresh
        if creds and creds.expired and creds.refresh_token:
            try:
                logger.info("Refreshing expired credentials...")
                creds.refresh(Request())
            except RefreshError:
                logger.warning("Token expired or revoked: deleting token.json to re-authenticate.")
                TOKEN_FILE.unlink(missing_ok=True)
                creds = None
        # If we still don't have usable creds, run the full OAuth flow
        if not creds:
            # Launch local server for user to authorize the app
            logger.info("Launching OAuth2 flow for Gmail API...")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_file), GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)
        # Persist the refreshed or new credentials
        with open(TOKEN_FILE, "wb") as token_fp:
            pickle.dump(creds, token_fp)
        logger.info("Credentials saved to token.json")

    # Build and return the Gmail API client
    logger.info("Gmail API client authenticated.")
    return build("gmail", "v1", credentials=creds)


def load_history():
    """
    Load processing history of message IDs and attachment hashes.
    Always returns sets for deduplication logic.
    """
    history = {"message_ids": set(), "attachments": set()}
    if HISTORY_FILE.exists():
        with HISTORY_FILE.open("r") as f:
            data = json.load(f)
        # Convert loaded lists into sets
        history["message_ids"]  = set(data.get("message_ids", []))
        history["attachments"]   = set(data.get("attachments", []))
    return history


def save_history(history):
    """
    Save updated history back to disk.

    :param history: Dict containing `message_ids` and `attachments` sets.
    :type history: dict
    """
    # Convert sets to lists for JSON serialization
    data = {
        "message_ids": list(history["message_ids"]),
        "attachments": list(history["attachments"])
    }
    with HISTORY_FILE.open("w") as f:
        json.dump(data, f, indent=2)
    logger.debug(f"History saved to: {HISTORY_FILE}")


def hash_bytes(data):
    """
    Compute a SHA-256 hash for the given byte data.

    :param data: Raw binary data to hash.
    :type data: bytes
    :return: Hex digest of the hash.
    :rtype: str
    """
    # Use hashlib for SHA-256
    digest = hashlib.sha256(data).hexdigest()
    logger.debug(f"Computed SHA256 hash: {digest}")
    return digest


def download_attachments(service, history):
    logger.info("Checking Gmail for messages with attachments…")
    page_token = None
    new_files = []

    while True:
        response = service.users().messages().list(
            userId="me",
            q=GMAIL_ATTACHMENT_QUERY,
            maxResults=MAX_PAGE_SIZE,
            pageToken=page_token
        ).execute()
        messages = response.get("messages", [])
        logger.info(f"Found {len(messages)} message(s) on this page.")

        for msg in messages:
            msg_id = msg["id"]
            if msg_id in history["message_ids"]:
                logger.debug(f"Skipping already-processed message: {msg_id}")
                continue

            # Fetch the full message
            message = service.users().messages().get(
                userId="me", id=msg_id, format="full"
            ).execute()

            # Extract headers
            headers = message.get("payload", {}).get("headers", [])
            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(no subject)")
            sender  = next((h["value"] for h in headers if h["name"] == "From"), "(no sender)")

            downloaded_this_msg = 0
            for part in message.get("payload", {}).get("parts", []):
                filename = part.get("filename")
                body     = part.get("body", {})
                if not filename or "attachmentId" not in body:
                    continue

                attachment = service.users().messages().attachments().get(
                    userId="me",
                    messageId=msg_id,
                    id=body["attachmentId"]
                ).execute()
                raw_data = base64.urlsafe_b64decode(attachment.get("data", ""))
                file_hash = hash_bytes(raw_data)

                if file_hash in history["attachments"]:
                    logger.debug(f"  Duplicate attachment (hash {file_hash}), skipping {filename}")
                    continue

                # Save the new attachment
                save_name = f"{file_hash}_{filename}"
                save_path = DOWNLOAD_DIR / save_name
                save_path.parent.mkdir(parents=True, exist_ok=True)
                save_path.write_bytes(raw_data)
                logger.info(f"  Attachment saved to: {save_path}")

                history["attachments"].add(file_hash)
                downloaded_this_msg += 1

                new_files.append({
                    "filename":      save_name,
                    "subject":       subject,
                    "sender":        sender,
                    "original_name": filename,
                })

            # **Always** mark this message as seen, attachment or not
            history["message_ids"].add(msg_id)

        # pagination?
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    logger.info(f"Total new attachments downloaded: {len(new_files)}")
    return new_files


def write_result(downloaded_info):
    """
    Append this run's download summary to the results JSON file.

    :param downloaded_info: List of metadata dicts for downloaded attachments.
    :type downloaded_info: list
    """
    # Ensure the results directory exists
    GMAIL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    # Build result payload
    result = {
        "tool": "GmailDownloader",
        "new_attachments": len(downloaded_info),
        "downloads": downloaded_info,
        "timestamp": time.time()
    }
    # Append JSON object to the results file for auditing
    with GMAIL_RESULTS_FILE.open("a") as f:  # this does not work it corrupts the json file
        json.dump(result, f, indent=2)
    logger.info(f"Result JSON appended to: {GMAIL_RESULTS_FILE}")


def main():
    """
    Main entry point for the Gmail attachment downloader.

    Configures logging, authenticates, downloads attachments, writes results, and updates history.
    """
    # Set up log directory and rotation policy (weekly)
    # LOGS_DIR = BASE_DIR / "logs"
    LOGS_DIR.mkdir(exist_ok=True)
    logger.add(GMAIL_LOG_FILE, rotation=GMAIL_LOG_ROTATION)  # Rotate logs every week

    # Ensure download folder exists before any downloads
    DOWNLOAD_DIR.mkdir(exist_ok=True)

    # Authenticate and build the Gmail service client
    try:
        service = authenticate()
    except FileNotFoundError as e:
        logger.error(f"Authentication failed: {e}")
        return  # Exit if credentials are missing

    # Load or initialize history (now already in sets)
    history = load_history()

    try:
        downloaded_info = download_attachments(service, history)
        write_result(downloaded_info)
    finally:
        save_history(history)

if __name__ == "__main__":
    main()
# End of file