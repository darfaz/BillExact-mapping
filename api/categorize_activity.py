"""
API: Categorise Activity
=======================

This endpoint accepts a JSON payload with a single ``text`` field
representing a free‑form description of a legal activity (for
example, a document title or email subject). It returns a JSON
response containing the suggested UTBMS task and activity codes along
with a confidence score between 0 and 1. If no suitable mapping is
found, both codes are returned as ``null`` and the confidence score
reflects the best match (if any). This API is used by the web UI
(`pages/categorize_test.py`) and can also be called by external
clients via the MCP server.

Example request:

```json
{
  "text": "Draft motion for summary judgment"
}
```

Example response:

```json
{
  "task_code": "L240",
  "activity_code": "A103",
  "confidence": 0.75,
  "description": "Draft motion for summary judgment"
}
```
"""

from __future__ import annotations

import json
from typing import Any, Dict

from categorize import categorize_text


async def main(req) -> Dict[str, Any]:
    """HTTP endpoint implementation for categorising activity text.

    Parameters
    ----------
    req : Any
        The incoming HTTP request object. Databutton passes a request
        object that provides an async ``json()`` method to extract
        JSON payloads.

    Returns
    -------
    Dict[str, Any]
        A dictionary containing the categorisation result. This will be
        serialised to JSON by the Databutton framework.
    """
    try:
        body = await req.json()
    except Exception:
        # Fallback for synchronous body parsing
        body = json.loads(req.body or "{}")
    text = body.get("text", "")
    result = categorize_text(text)
    return result