"""
ingest.py
---------

This module provides functionality to ingest events from an ActivityWatch
instance, aggregate them and persist them in the local SQLite database
as time entries. The design is intentionally kept lightweight to
facilitate easy deployment on Databutton.

The primary function exposed is ``ingest_from_activitywatch`` which
fetches window events from a specified ActivityWatch API endpoint. It
then normalises these events, categorises their descriptions into
UTBMS codes using ``categorize_text`` from the ``categorize`` module and
stores the resulting entries into the ``time_entries`` table. The
function is idempotent: events are only ingested once based on
timestamp and description; duplicate ingestion attempts will skip
existing entries.

Dependencies: requests (for HTTP calls), pandas (for grouping),
sqlite3, datetime.

"""

from __future__ import annotations

import datetime as dt
import json
import logging
import sqlite3
from pathlib import Path
from typing import Iterable, List, Dict, Any

import pandas as pd
import requests

from categorize import categorize_text


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Path to the local SQLite database. The same path used in
# categorize.py should be used here to ensure consistency.
DB_PATH = Path("data.db")


def _initialise_db():
    """Ensure the database file and tables exist.

    This function reads the schema from the `db/schema.sql` file and
    executes it against the SQLite database. It is safe to call this
    function repeatedly; the `IF NOT EXISTS` clauses in the SQL
    statements prevent duplicate table creation.
    """
    schema_path = Path("db/schema.sql")
    if not schema_path.exists():
        logger.warning("Schema file db/schema.sql not found; skipping DB initialisation")
        return
    conn = sqlite3.connect(DB_PATH)
    with open(schema_path, "r") as f:
        sql = f.read()
    conn.executescript(sql)
    conn.commit()
    conn.close()


def fetch_activitywatch_events(url: str, since: dt.datetime) -> List[Dict[str, Any]]:
    """Fetch events from ActivityWatch.

    Parameters
    ----------
    url : str
        Base URL of the ActivityWatch instance (e.g. ``http://localhost:5600``).
    since : datetime.datetime
        Only events occurring after this timestamp will be returned.

    Returns
    -------
    List[Dict[str, Any]]
        A list of event dictionaries as returned by the ActivityWatch API.
    """
    # Compose the export endpoint for aw-watcher-window events
    since_iso = since.isoformat()
    endpoint = f"{url}/api/0/export?bucket=aw-watcher-window&since={since_iso}"
    logger.info("Fetching events from %s", endpoint)
    resp = requests.get(endpoint, timeout=30)
    resp.raise_for_status()
    events = resp.json()
    logger.info("Fetched %d events", len(events))
    return events


def _transform_events(events: Iterable[Dict[str, Any]]) -> pd.DataFrame:
    """Transform raw ActivityWatch events into a pandas DataFrame.

    The DataFrame contains columns: ``timestamp``, ``duration``, ``title``,
    ``app_name`` and ``date``. The ``date`` column is the calendar date
    extracted from the timestamp.

    Parameters
    ----------
    events : Iterable[Dict[str, Any]]
        Raw event dictionaries from ActivityWatch.

    Returns
    -------
    pandas.DataFrame
        Normalised event data.
    """
    rows = []
    for ev in events:
        data = ev.get("data", {}) or {}
        title = data.get("title", "")
        app_name = data.get("app", data.get("app_name", ""))
        timestamp = dt.datetime.fromisoformat(ev["timestamp"].replace("Z", "+00:00")).astimezone(dt.timezone.utc)
        duration_seconds = ev.get("duration", 0)
        rows.append({
            "timestamp": timestamp,
            "duration": duration_seconds / 3600.0,  # convert to hours
            "title": title,
            "app_name": app_name,
            "date": timestamp.date(),
        })
    return pd.DataFrame(rows)


def _get_existing_entries(conn: sqlite3.Connection) -> set[tuple[dt.datetime, str]]:
    """Return a set of (timestamp, description) pairs for existing entries.

    This helper is used to avoid inserting duplicate entries into the
    ``time_entries`` table. Because events may be fetched repeatedly,
    deduplication is performed based on the exact timestamp and
    description (title).

    Parameters
    ----------
    conn : sqlite3.Connection
        An open SQLite connection.

    Returns
    -------
    set[tuple[datetime.datetime, str]]
        A set of pairs corresponding to previously ingested events.
    """
    cur = conn.cursor()
    cur.execute("SELECT timestamp, description FROM time_entries")
    rows = cur.fetchall()
    return {(dt.datetime.fromisoformat(ts), desc) for ts, desc in rows}


def ingest_from_activitywatch(
    url: str,
    client_id: str,
    matter_id: str,
    timekeeper_id: str,
    timekeeper_name: str,
    user_id: str = "unknown",
    since: dt.datetime | None = None,
) -> int:
    """Ingest ActivityWatch events and persist them as time entries.

    Parameters
    ----------
    url : str
        Base URL of the ActivityWatch instance.
    client_id : str
        Client ID for the current matter; stored on each time entry.
    matter_id : str
        Matter identifier; stored on each time entry.
    timekeeper_id : str
        Identifier for the attorney or timekeeper.
    timekeeper_name : str
        Display name of the timekeeper.
    user_id : str, optional
        Internal identifier for the user/attorney.
    since : datetime.datetime, optional
        Only ingest events after this timestamp. Defaults to 1 day ago if
        not provided.

    Returns
    -------
    int
        The number of new entries inserted into the database.
    """
    _initialise_db()
    if since is None:
        since = dt.datetime.utcnow() - dt.timedelta(days=1)
    events = fetch_activitywatch_events(url, since)
    df = _transform_events(events)
    if df.empty:
        return 0
    conn = sqlite3.connect(DB_PATH)
    existing = _get_existing_entries(conn)
    inserted = 0
    cur = conn.cursor()
    for _, row in df.iterrows():
        # Skip duplicates
        key = (row["timestamp"], row["title"])
        if key in existing:
            continue
        # Categorise the title into UTBMS codes
        result = categorize_text(row["title"])
        # Compute total by multiplying duration by rate. For the MVP
        # we default to zero and leave calculation to downstream UI.
        rate = None
        total = None
        cur.execute(
            """
            INSERT INTO time_entries (
              user_id, client_id, matter_id, timekeeper_id, timekeeper_name,
              date, description, duration_hours, task_code, activity_code,
              confidence, rate, total, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                client_id,
                matter_id,
                timekeeper_id,
                timekeeper_name,
                row["date"].isoformat(),
                row["title"],
                row["duration"],
                result.get("task_code"),
                result.get("activity_code"),
                result.get("confidence"),
                rate,
                total,
                row["timestamp"].isoformat(),
            ),
        )
        inserted += 1
    conn.commit()
    conn.close()
    logger.info("Inserted %d new time entries", inserted)
    return inserted


__all__ = ["ingest_from_activitywatch"]

# === Pilot-Ready Additions: Focus filters, merges, and bindings ===
import re, sqlite3, os, datetime

MIN_FOCUS_SEC = int(os.environ.get("BILLEXACT_MIN_FOCUS_SEC", "45"))
MERGE_WINDOW_MIN = int(os.environ.get("BILLEXACT_MERGE_WINDOW_MIN", "10"))
IGNORE_APPS = set([a.strip() for a in os.environ.get("BILLEXACT_IGNORE_APPS","Spotify,Photos,System Settings").split(",")])

def _is_focus_event(ev):
    return ev.get("duration",0) >= MIN_FOCUS_SEC and ev.get("app") not in IGNORE_APPS

def _merge_contiguous(entries):
    merged = []
    for ev in sorted(entries, key=lambda e: e["start"]):
        if merged and (
           merged[-1].get("app")==ev.get("app") and
           merged[-1].get("subject")==ev.get("subject") and
           (ev["start"] - merged[-1]["end"]).total_seconds() <= MERGE_WINDOW_MIN*60
        ):
            merged[-1]["end"] = ev["end"]
            merged[-1]["duration"] = (merged[-1]["end"] - merged[-1]["start"]).total_seconds()
        else:
            merged.append(ev)
    return merged

def _resolve_matter(subject: str, url_or_path: str):
    db_path = os.environ.get("BILLEXACT_DB","billexact.db")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        rows = cur.execute("SELECT kind, pattern, target FROM bindings").fetchall()
    except sqlite3.OperationalError:
        return None
    text = f"{subject or ''} {url_or_path or ''}"
    for kind, pat, tgt in rows:
        if re.search(pat, text, re.I):
            if kind == "do_not_bill":
                return "__DONOTBILL__"
            if kind == "matter":
                return tgt  # client_matter_id
    return None
