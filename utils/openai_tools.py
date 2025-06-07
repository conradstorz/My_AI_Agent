# utils/openai_tools.py

from pathlib import Path
import json
import base64
from loguru import logger
from openai import OpenAI
from dotenv import load_dotenv
from constants import (
    OPENAI_MODEL,
    OPENAI_TEMPERATURE,
    SYSTEM_PROMPT_FOR_TEXT_CONTENT,
    SYSTEM_PROMPT_FOR_IMAGES,
)

load_dotenv(override=True)
client = OpenAI()

def summarize_image(image_path: Path) -> dict:
    """
    Summarizes an image and detects structure. 
    Returns exactly one JSON object with keys:
      - summary                  (string)
      - contains_structured_data (boolean)
      - notes                    (string)
    The assistant MUST output only valid JSON—nothing else.
    """
    # 1) Read and base64-encode the image
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    # 2) Build the multimodal user message
    message = {
        "role": "user",
        "content": [
            {"type": "input_text",  "text": SYSTEM_PROMPT_FOR_IMAGES},
            {"type": "input_image", "image_url": f"data:image/png;base64,{b64}"}
        ],
    }

    # 3) Call the Responses API with a list of messages
    resp = client.responses.create(
        model="gpt-4o-mini",
        input=[message]
    )
    # Optionally log raw for future debugging:
    raw = resp.output_text.strip()
    if not raw: # If the response is empty, log and raise an error
        logger.error(f"Empty response from assistant for image: {image_path}")
        raise ValueError(f"Empty response from assistant for image: {image_path}")              
    # Log the raw response for debugging
    Traw = resp.output_text.strip()
    if len(Traw) > 1000:  # Limit logging to first 1000 characters for brevity
        Traw = raw[:1000] + '... [truncated]'        
    logger.debug(f"[{image_path.name}] Raw JSON response:\n{Traw}")

    raw = resp.output_text.strip()

    # 4) Parse and return, with error handling
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON from assistant:\n{raw}")
        return "[ERROR] Failed to decode JSON from assistant. Please check the logs for details."




def summarize_document(text: str, filename: str) -> dict:
    """
    Summarizes text and detects structure. 
    Returns exactly one JSON object with keys:
      - summary            (string)
      - contains_structured_data (boolean)
      - notes              (string)
    The assistant MUST output only valid JSON—nothing else.
    """
    system = {
        "role": "system",
        "content": SYSTEM_PROMPT_FOR_TEXT_CONTENT
    }
    user = {
        "role": "user",
        "content": (
            f"Document filename: {filename}\n\n"
            "Here is the document text:\n"
            "```\n"
            f"{text}\n"
            "```\n"
            "Please respond with one valid JSON object as described."
        )
    }

    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[system, user],
        temperature=OPENAI_TEMPERATURE
    )
    raw = resp.choices[0].message.content.strip()
    # Optionally log raw for future debugging:
    logger.debug(f"[{filename}] Raw JSON response:\n{raw}")

    # Parse and return
    return json.loads(raw)
