# utils/openai_tools.py

import os
import json
from loguru import logger
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()

def summarize_document(content: str, filename: str) -> dict:
    prompt = f"""You are an assistant helping to classify and extract useful information from uploaded documents.

Here is the content of a file named '{filename}':
---
{content[:3500]}
---

TASKS:
1. Summarize this document for a human reader.
2. Determine if this document contains structured tabular data, like invoices, reports, bank statements, or spreadsheets with labeled columns.
3. Respond in JSON with the following fields:
- "summary": <your summary>,
- "contains_structured_data": true or false,
- "notes": any extra comments about how reliable or clean the data looks.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        content = response.choices[0].message.content
        parsed = json.loads(content)
        return {
            "summary": parsed.get("summary"),
            "contains_structured_data": parsed.get("contains_structured_data"),
            "notes": parsed.get("notes"),
            "success": True
        }
    except json.JSONDecodeError:
        logger.error("OpenAI response was not valid JSON.")
        return {
            "summary": content,
            "contains_structured_data": None,
            "success": False,
            "error": "invalid JSON"
        }
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return {
            "summary": None,
            "contains_structured_data": None,
            "success": False,
            "error": str(e)
        }
