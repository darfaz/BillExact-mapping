"""
API: Export LEDES 1998B
----------------------

This endpoint generates a LEDES 1998B invoice file for a specified
client/matter combination and date range. The output file is saved
under the ``exports`` directory and the path to the file is returned
to the caller. Optionally a specific timekeeper can be specified to
filter the entries.

Example request:

```json
{
  "client_id": "CLIENT001",
  "matter_id": "MATTERA",
  "start_date": "2025-08-01",
  "end_date": "2025-08-16",
  "timekeeper_id": "TK123",
  "timekeeper_name": "Alice Johnson"
}
```

Example response:

```json
{
  "file_path": "exports/ledes_INV-20250816...txt"
}
```
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any, Dict

from export_ledes import export_ledes1998b


def _parse_date(date_str: str | None) -> dt.date | None:
    if not date_str:
        return None
    try:
        return dt.date.fromisoformat(date_str)
    except ValueError:
        return None


async def main(req) -> Dict[str, Any]:
    try:
        body = await req.json()
    except Exception:
        body = json.loads(req.body or "{}")
    client_id = body.get("client_id")
    matter_id = body.get("matter_id")
    start_date = _parse_date(body.get("start_date"))
    end_date = _parse_date(body.get("end_date"))
    timekeeper_id = body.get("timekeeper_id") or None
    timekeeper_name = body.get("timekeeper_name") or None
    if not client_id or not matter_id or not start_date or not end_date:
        return {"error": "client_id, matter_id, start_date and end_date are required"}
    if start_date > end_date:
        return {"error": "start_date must be <= end_date"}
    file_path = export_ledes1998b(
        client_id=client_id,
        matter_id=matter_id,
        start_date=start_date,
        end_date=end_date,
        timekeeper_id=timekeeper_id,
        timekeeper_name=timekeeper_name,
    )
    return {"file_path": file_path}