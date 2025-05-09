import argparse
import base64
import json
import os
import pickle
import time
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# --- Config ---
BASE_DIR = Path(__file__).resolve().parent
PROCESSED_FILE = BASE_DIR / "processed_messages.json"
RESULTS_FILE = BASE_DIR / "results" / "gmail_query_fetcher.json"
LOGS_DIR = BASE_DIR / "logs"
TOKEN_FILE = BASE_DIR / "token.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

load_dotenv(override=True)
LOGS_DIR.mkdir(exist_ok=True)
logger.add(LOGS_DIR / "gmail_query_fetcher.log", rotation="1 week")

def get_credentials_file():
    path = os.getenv("GMAIL_CREDENTIALS_PATH")
    if not path:
        raise FileNotFoundError("Missing GMAIL_CREDENTIALS_PATH env variable")
    return Path(path)

def authenticate():
    credentials_file = get_credentials_file()
    creds = None
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "wb") as token:
            pickle.dump(creds, token)
    return build("gmail", "v1", credentials=creds)

def load_processed():
    if PROCESSED_FILE.exists():
        with PROCESSED_FILE.open("r") as f:
            return set(json.load(f))
    return set()

def save_processed(processed_ids):
    with PROCESSED_FILE.open("w") as f:
        json.dump(list(processed_ids), f, indent=2)

def extract_body(message):
    parts = message.get("payload", {}).get("parts", [])
    for part in parts:
        if part.get("mimeType") == "text/plain" and "data" in part.get("body", {}):
            data = part["body"]["data"]
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
    return message.get("snippet", "")

def fetch_matching_messages(query: str, service, processed_ids):
    logger.info(f"Searching Gmail for: {query}")
    result = service.users().messages().list(userId="me", q=query).execute()
    messages = result.get("messages", [])
    logger.info(f"Found {len(messages)} message(s)")

    results = []

    for msg in messages:
        msg_id = msg["id"]
        if msg_id in processed_ids:
            logger.debug(f"Already processed: {msg_id}")
            continue

        full = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
        headers = full.get("payload", {}).get("headers", [])
        subject = next((h["value"] for h in headers if h["name"].lower() == "subject"), "(no subject)")
        sender = next((h["value"] for h in headers if h["name"].lower() == "from"), "(no sender)")
        body = extract_body(full)

        results.append({
            "message_id": msg_id,
            "subject": subject,
            "sender": sender,
            "body": body
        })

        processed_ids.add(msg_id)
        logger.info(f"Fetched message {msg_id} from {sender} | Subject: {subject}")

    return results

def write_result(query: str, messages: list):
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "tool": "GmailQueryFetcher",
        "query": query,
        "messages_saved": messages,
        "timestamp": time.time()
    }
    with RESULTS_FILE.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    logger.info(f"Result JSON written to: {RESULTS_FILE}")

def main():
    parser = argparse.ArgumentParser(description="Fetch Gmail messages matching a search query.")
    parser.add_argument("query", help="Gmail search query (e.g., 'from:someone@example.com')")
    args = parser.parse_args()

    try:
        service = authenticate()
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        return

    processed_ids = load_processed()
    messages = fetch_matching_messages(args.query, service, processed_ids)
    write_result(args.query, messages)
    save_processed(processed_ids)

    logger.info(f"Done. {len(messages)} message(s) written to result.")

if __name__ == "__main__":
    main()
