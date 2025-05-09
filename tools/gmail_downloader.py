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

# Load environment variables
load_dotenv()

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
HISTORY_FILE = BASE_DIR / "downloaded_attachments.json"
RESULTS_DIR = BASE_DIR / "results"
RESULTS_FILE = RESULTS_DIR / "gmail_downloader.json"
TOKEN_FILE = BASE_DIR / "token.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def get_credentials_file():
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
    credentials_file = get_credentials_file()
    creds = None

    if TOKEN_FILE.exists():
        logger.debug(f"Found token file: {TOKEN_FILE}")
        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)
    else:
        logger.debug("No token file found. Will initiate OAuth2 flow.")

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
    if HISTORY_FILE.exists():
        with HISTORY_FILE.open("r") as f:
            return json.load(f)
    return {"message_ids": set(), "attachments": set()}

def save_history(history):
    with HISTORY_FILE.open("w") as f:
        json.dump({
            "message_ids": list(history["message_ids"]),
            "attachments": list(history["attachments"])
        }, f, indent=2)

def hash_bytes(data):
    return hashlib.sha256(data).hexdigest()

def download_attachments(service, history):
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

        payload = message.get("payload", {})
        parts = payload.get("parts", [])

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

                path = DOWNLOAD_DIR / filename
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, "wb") as f:
                    f.write(data)

                logger.info(f"  Downloaded: {filename}")
                new_files.append({
                    "filename": filename,
                    "subject": subject,
                    "sender": sender
                })
                history["attachments"].add(hash_key)

        history["message_ids"].add(msg_id)

    logger.info(f"Total new files downloaded: {len(new_files)}")
    return new_files

def write_result(downloaded_info):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    result = {
        "tool": "GmailDownloader",
        "new_attachments": len(downloaded_info),
        "downloads": downloaded_info,
        "timestamp": time.time()
    }
    with RESULTS_FILE.open("w") as f:
        json.dump(result, f, indent=2)
    logger.info(f"Result JSON written to: {RESULTS_FILE}")

def main():
    LOGS_DIR = BASE_DIR / "logs"
    LOGS_DIR.mkdir(exist_ok=True)
    logger.add(LOGS_DIR / "gmail_downloader.log", rotation="1 week")

    DOWNLOAD_DIR.mkdir(exist_ok=True)

    try:
        service = authenticate()
    except FileNotFoundError as e:
        logger.error(f"Authentication failed: {e}")
        return

    history = load_history()
    history["message_ids"] = set(history.get("message_ids", []))
    history["attachments"] = set(history.get("attachments", []))

    try:
        downloaded_info = download_attachments(service, history)
        write_result(downloaded_info)
    finally:
        save_history(history)

if __name__ == "__main__":
    main()
