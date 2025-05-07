from pathlib import Path
from loguru import logger
import base64
import hashlib
import json
import os
import pickle
import time
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# --- Configurable paths ---
BASE_DIR = Path(__file__).resolve().parent
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"
DOWNLOAD_DIR = BASE_DIR / "downloads"
HISTORY_FILE = BASE_DIR / "downloaded_attachments.json"
RESULTS_DIR = BASE_DIR / "results"
RESULTS_FILE = RESULTS_DIR / "gmail_downloader.json"

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def authenticate():
    creds = None
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "wb") as token:
            pickle.dump(creds, token)
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
    import hashlib
    return hashlib.sha256(data).hexdigest()

def download_attachments(service, history):
    query = "has:attachment is:unread"
    response = service.users().messages().list(userId="me", q=query).execute()
    messages = response.get("messages", [])

    new_files = []
    for msg in messages:
        msg_id = msg["id"]
        if msg_id in history["message_ids"]:
            continue

        message = service.users().messages().get(userId="me", id=msg_id).execute()
        payload = message.get("payload", {})
        parts = payload.get("parts", [])

        for part in parts:
            if part.get("filename") and "attachmentId" in part.get("body", {}):
                attachment_id = part["body"]["attachmentId"]
                filename = part["filename"]

                attachment = service.users().messages().attachments().get(
                    userId="me", messageId=msg_id, id=attachment_id).execute()

                data = base64.urlsafe_b64decode(attachment["data"])
                file_hash = hash_bytes(data)
                hash_key = f"{msg_id}:{file_hash}"

                if hash_key in history["attachments"]:
                    continue

                path = DOWNLOAD_DIR / filename
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, "wb") as f:
                    f.write(data)

                logger.info(f"Downloaded: {filename} from message {msg_id}")
                new_files.append(filename)
                history["attachments"].add(hash_key)

        history["message_ids"].add(msg_id)

    return new_files

def write_result(downloaded_files):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    result = {
        "tool": "GmailDownloader",
        "new_attachments": len(downloaded_files),
        "downloaded_files": downloaded_files,
        "timestamp": time.time()
    }
    with RESULTS_FILE.open("w") as f:
        json.dump(result, f, indent=2)

def main():
    logger.add(BASE_DIR / "logs" / "gmail_downloader.log", rotation="1 week")
    DOWNLOAD_DIR.mkdir(exist_ok=True)
    (BASE_DIR / "logs").mkdir(exist_ok=True)

    service = authenticate()
    history = load_history()
    history["message_ids"] = set(history.get("message_ids", []))
    history["attachments"] = set(history.get("attachments", []))

    try:
        downloaded_files = download_attachments(service, history)
        write_result(downloaded_files)
    finally:
        save_history(history)

if __name__ == "__main__":
    main()
