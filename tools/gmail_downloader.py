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
from pathlib import Path
from loguru import logger
import base64
import hashlib
import json
import os
import pickle
import time
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Load environment variables (override existing values)
load_dotenv(override=True)

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
HISTORY_FILE = BASE_DIR / "downloaded_attachments.json"
RESULTS_DIR = BASE_DIR / "results"
RESULTS_FILE = RESULTS_DIR / "gmail_downloader.json"
TOKEN_FILE = BASE_DIR / "token.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_credentials_file():
    """
    Retrieve the Gmail API credentials file from the environment.

    :return: Path to the Gmail credentials JSON file.
    :rtype: pathlib.Path
    :raises FileNotFoundError: If the environment variable is missing or the file does not exist.
    """
    credentials_path = os.environ.get("GMAIL_CREDENTIALS_PATH")
    logger.debug(f"GMAIL_CREDENTIALS_PATH={credentials_path}")
    if not credentials_path:
        logger.error("Environment variable GMAIL_CREDENTIALS_PATH not set.")
        raise FileNotFoundError("Missing environment variable: GMAIL_CREDENTIALS_PATH")

    credentials_file = Path(credentials_path)
    if not credentials_file.exists():
        logger.error(f"Credentials file does not exist at: {credentials_file}")
        raise FileNotFoundError(f"Gmail credentials file not found: {credentials_file}")

    logger.info(f"Using credentials file: {credentials_file}")
    return credentials_file


def authenticate():
    """
    Authenticate with the Gmail API using OAuth2 credentials.

    This will attempt to load existing tokens from `TOKEN_FILE`, refresh them if expired,
    or initiate a new OAuth2 flow if necessary.

    :return: Authenticated Gmail API service instance.
    :rtype: googleapiclient.discovery.Resource
    """
    credentials_file = get_credentials_file()
    creds = None

    # Load existing token if present
    if TOKEN_FILE.exists():
        logger.debug(f"Found token file: {TOKEN_FILE}")
        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)
    else:
        logger.debug("No token file found. Will initiate OAuth2 flow.")

    # Refresh or request new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired credentials...")
            creds.refresh(Request())
        else:
            logger.info("Launching OAuth2 flow for Gmail API...")
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "wb") as token:
            pickle.dump(creds, token)
        logger.info("Credentials saved to token.json")

    logger.info("Gmail API client authenticated.")
    return build("gmail", "v1", credentials=creds)


def load_history():
    """
    Load the processing history of messages and attachments.

    :return: A dictionary containing sets of processed message IDs and attachment hashes.
    :rtype: dict
    """
    if HISTORY_FILE.exists():
        with HISTORY_FILE.open("r") as f:
            return json.load(f)
    return {"message_ids": set(), "attachments": set()}


def save_history(history):
    """
    Save the processing history of messages and attachments.

    :param history: Dictionary with keys `message_ids` and `attachments` containing sets of processed items.
    :type history: dict
    """
    with HISTORY_FILE.open("w") as f:
        json.dump({
            "message_ids": list(history["message_ids"]),
            "attachments": list(history["attachments"])
        }, f, indent=2)


def hash_bytes(data):
    """
    Compute the SHA-256 hash of the given binary data.

    :param data: Binary data to hash.
    :type data: bytes
    :return: Hexadecimal digest of the SHA-256 hash.
    :rtype: str
    """
    return hashlib.sha256(data).hexdigest()


def download_attachments(service, history):
    """
    Download unread Gmail attachments and update history.

    :param service: Authenticated Gmail API service instance.
    :type service: googleapiclient.discovery.Resource
    :param history: Dictionary tracking processed message IDs and attachment hashes.
    :type history: dict
    :return: List of dictionaries with metadata for each downloaded attachment.
    :rtype: list
    """
    logger.info("Checking Gmail for new unread messages with attachments...")
    query = "has:attachment is:unread"
    response = service.users().messages().list(userId="me", q=query).execute()
    messages = response.get("messages", [])
    logger.info(f"Found {len(messages)} message(s) matching query.")

    new_files = []
    for msg in messages:
        msg_id = msg["id"]
        if msg_id in history["message_ids"]:
            logger.debug(f"Skipping already-processed message: {msg_id}")
            continue

        message = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
        headers = message.get("payload", {}).get("headers", [])
        subject = next((h["value"] for h in headers if h["name"].lower() == "subject"), "(no subject)")
        sender = next((h["value"] for h in headers if h["name"].lower() == "from"), "(no sender)")

        logger.info(f"Processing message {msg_id}")
        logger.info(f"  Subject: {subject}")
        logger.info(f"  From:    {sender}")

        parts = message.get("payload", {}).get("parts", [])
        for part in parts:
            if part.get("filename") and "attachmentId" in part.get("body", {}):
                attachment_id = part["body"]["attachmentId"]
                filename = part["filename"]
                logger.debug(f"  Downloading attachment: {filename}")

                attachment = service.users().messages().attachments().get(
                    userId="me", messageId=msg_id, id=attachment_id).execute()

                data = base64.urlsafe_b64decode(attachment["data"])
                file_hash = hash_bytes(data)
                hash_key = f"{msg_id}:{file_hash}"

                if hash_key in history["attachments"]:
                    logger.debug(f"  Duplicate attachment detected (hash match), skipping: {filename}")
                    continue

                # Save the attachment using a hashed filename to prevent collisions
                filename_hashed = f"{file_hash}_{filename}"
                path = DOWNLOAD_DIR / filename_hashed
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, "wb") as f:
                    f.write(data)

                logger.info(f"  Downloaded: {filename}")
                new_files.append({
                    "filename": filename_hashed,
                    "subject": subject,
                    "sender": sender,
                    "attachment name": filename,
                })
                history["attachments"].add(hash_key)

        history["message_ids"].add(msg_id)

    logger.info(f"Total new files downloaded: {len(new_files)}")
    return new_files


def write_result(downloaded_info):
    """
    Write the download results to a JSON file for record keeping.

    :param downloaded_info: List of metadata dicts for each downloaded attachment.
    :type downloaded_info: list
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    result = {
        "tool": "GmailDownloader",
        "new_attachments": len(downloaded_info),
        "downloads": downloaded_info,
        "timestamp": time.time()
    }
    with RESULTS_FILE.open("a") as f:
        json.dump(result, f, indent=2)
    logger.info(f"Result JSON written to: {RESULTS_FILE}")


def main():
    """
    Entry point for the Gmail attachment downloader script.

    This will configure logging, authenticate with Gmail,
    download new attachments, record the results, and update history.
    """
    # Configure logging directory and rotation
    LOGS_DIR = BASE_DIR / "logs"
    LOGS_DIR.mkdir(exist_ok=True)
    logger.add(LOGS_DIR / "gmail_downloader.log", rotation="1 week")

    # Ensure download directory exists
    DOWNLOAD_DIR.mkdir(exist_ok=True)

    try:
        service = authenticate()
    except FileNotFoundError as e:
        logger.error(f"Authentication failed: {e}")
        return

    history = load_history()
    # Convert lists back to sets for processing
    history["message_ids"] = set(history.get("message_ids", []))
    history["attachments"] = set(history.get("attachments", []))

    try:
        downloaded_info = download_attachments(service, history)
        write_result(downloaded_info)
    finally:
        save_history(history)


if __name__ == "__main__":
    main()
