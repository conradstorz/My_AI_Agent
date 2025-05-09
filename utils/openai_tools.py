# utils/openai_tools.py

import os
import json
from loguru import logger
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()

def summarize_document(content: str, filename: str) -> dict:
    logger.info(f"Starting summarization for: {filename}")
    truncated_content = content[:3500]
    
    prompt = f"""You are an assistant helping to classify and extract useful information from uploaded documents.

Here is the content of a file named '{filename}':
---
{truncated_content}
---

TASKS:
1. Summarize this document for a human reader.
2. Determine if this document contains structured tabular data, like invoices, reports, bank statements, or spreadsheets with labeled columns.
3. Respond in JSON with the following fields:
- "summary": <your summary>,
- "contains_structured_data": true or false,
- "notes": any extra comments about how reliable or clean the data looks.
"""

    logger.debug(f"[{filename}] Prepared prompt (first 200 chars):\n{prompt[:200]}...")

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        content = response.choices[0].message.content
        logger.debug(f"[{filename}] Raw OpenAI response:\n{content}")
        
        parsed = json.loads(content)
        result = {
            "summary": parsed.get("summary"),
            "contains_structured_data": parsed.get("contains_structured_data"),
            "notes": parsed.get("notes"),
            "success": True
        }
        logger.info(f"[{filename}] Summary success. Structured data: {result['contains_structured_data']}")
        return result

    except json.JSONDecodeError:
        logger.error(f"[{filename}] OpenAI response was not valid JSON.")
        return {
            "summary": content,
            "contains_structured_data": None,
            "success": False,
            "error": "invalid JSON"
        }

    except Exception as e:
        logger.exception(f"[{filename}] OpenAI error during summarization: {e}")
        return {
            "summary": None,
            "contains_structured_data": None,
            "success": False,
            "error": str(e)
        }
