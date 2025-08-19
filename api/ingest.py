"""
API: Ingest ActivityWatch Events
--------------------------------

This endpoint triggers ingestion of events from an ActivityWatch
instance into the local database. It accepts a JSON payload with the
ActivityWatch base URL, client and matter identifiers, timekeeper
details and an optional ``since`` timestamp. The ingestion process
fetches events from the ActivityWatch export API, categorises each
event into UTBMS codes and stores the result in the ``time_entries``
table. It returns the number of new entries inserted.

Example request:

```json
{
  "url": "http://localhost:5600",
  "client_id": "CLIENT001",
  "matter_id": "MATTERA",
  "timekeeper_id": "TK123",
  "timekeeper_name": "Alice Johnson",
  "user_id": "user123",
  "since": "2025-08-15T00:00:00Z"
}
```

Example response:

```json
{
  "inserted": 42
}
```
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any, Dict

from ingest import ingest_from_activitywatch


def _parse_iso(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
    except ValueError:
        return None


async def main(req) -> Dict[str, Any]:
    """HTTP endpoint implementation for ingestion.

    Parameters
    ----------
    req : Any
        The incoming request object. Databutton passes a request with
        ``json()`` method to retrieve the payload.

    Returns
    -------
    Dict[str, Any]
        A dictionary with a single key ``inserted`` indicating how
        many entries were added.
    """
    try:
        body = await req.json()
    except Exception:
        body = json.loads(req.body or "{}")
    url = body.get("url")
    client_id = body.get("client_id")
    matter_id = body.get("matter_id")
    timekeeper_id = body.get("timekeeper_id", "")
    timekeeper_name = body.get("timekeeper_name", "")
    user_id = body.get("user_id", "unknown")
    since = _parse_iso(body.get("since"))
    if not url or not client_id or not matter_id:
        return {"error": "url, client_id and matter_id are required"}
    inserted = ingest_from_activitywatch(
        url=url,
        client_id=client_id,
        matter_id=matter_id,
        timekeeper_id=timekeeper_id,
        timekeeper_name=timekeeper_name,
        user_id=user_id,
        since=since,
    )
    return {"inserted": inserted}