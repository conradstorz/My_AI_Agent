# utils/openai_tools.py

from pathlib import Path
import json
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
      - summary            (string)
      - contains_structured_data (boolean)
      - notes              (string)
    The assistant MUST output only valid JSON—nothing else.
    """
    system = {
        "role": "system",
        "content": SYSTEM_PROMPT_FOR_IMAGES
    }
    user = {
        "role": "user",
        "content": (
            f"Image filename: {image_path.name}\n\n"
            "Please summarize the image and detect any structured data."
        )
    }

    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[system, user],
        temperature=OPENAI_TEMPERATURE,
        files=[{"file": image_path}]
    )
    raw = resp.choices[0].message.content.strip()
    # Optionally log raw for future debugging:
    logger.debug(f"[{image_path.name}] Raw JSON response:\n{raw}")

    # Parse and return
    return json.loads(raw)




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
