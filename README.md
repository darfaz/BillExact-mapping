# Passive Activity‑to‑LEDES Translator

This repository contains an app that passively collects
computer activity data via [ActivityWatch](https://github.com/ActivityWatch/activitywatch),
maps each activity to UTBMS task and activity codes and exports
LEDES 1998B compliant invoices. The implementation follows the product
requirements outlined in the supplied PRD.

## Features

- **Activity ingestion**: Fetches window events from ActivityWatch and
  stores them in a SQLite database. Each event is categorised using
  simple keyword matching into UTBMS task/activity codes.
- **Streamlit dashboard**: View a live feed of captured activities,
  test the categorisation engine, manage keyword mappings and export
  LEDES invoices via a simple web interface.
- **API endpoints**: Back‑end HTTP endpoints for categorising text,
  ingesting events and exporting invoices. These can be exposed as
  tools via Databutton’s MCP server for integration with agents such as
  Claude Desktop or Cursor.
- **LEDES export**: Generates pipe‑delimited LEDES 1998B files with
  core fields populated. Invoices can be downloaded directly from the
  UI or via the API.

## Running Locally

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Initialise the database and create the tables:

   ```bash
   python -c "import ingest; ingest._initialise_db()"
   ```

3. (Optional) Populate the `utbms_keywords` table with initial mappings.
   You can do this via the **Keyword Manager** page in the UI or via a
   SQLite client. For example:

   ```bash
   python - <<'PY'
   import sqlite3
   conn = sqlite3.connect('data.db')
   cur = conn.cursor()
   cur.execute("INSERT INTO utbms_keywords (keyword, task_code, activity_code, confidence_boost) VALUES (?,?,?,?)", ('motion', 'L240','A103',0.8))
   conn.commit()
   conn.close()
   PY
   ```

4. Run the Streamlit app:

   ```bash
   streamlit run pages/index.py
   ```

   Use the sidebar to navigate between pages (Activity Feed,
   Categorisation Test, LEDES Export, Keyword Manager).

5. Trigger ingestion via the API (example using `curl`):

   ```bash
   curl -X POST http://localhost:8000/api/ingest -H 'Content-Type: application/json' \
     -d '{"url": "http://localhost:5600", "client_id": "CLIENT1", "matter_id": "MATTER1", "timekeeper_id": "TK1", "timekeeper_name": "Alice"}'
   ```

   Replace the `url` value with the address of your local ActivityWatch
   agent. The ingestion process will fetch all events from the last
   day by default and store them in the database.

6. Export a LEDES invoice via the API:

   ```bash
   curl -X POST http://localhost:8000/api/export_ledes -H 'Content-Type: application/json' \
     -d '{"client_id": "CLIENT1", "matter_id": "MATTER1", "start_date": "2025-08-01", "end_date": "2025-08-16"}'
   ```

   The response will include the path of the generated LEDES file in the
   `exports/` directory.

## Databutton Deployment

To deploy this app on [Databutton](https://databutton.com), upload the
repository contents. The `pages` directory defines the Streamlit
front‑end, the `api` directory contains backend endpoints and the
`db/schema.sql` file defines the database schema. In Databutton’s
project settings you can schedule a task to call the `api/ingest` endpoint
every 10 minutes to keep time entries up to date.

### MCP Integration

If you enable MCP (Model Context Protocol) in your Databutton app,
these API endpoints become tools that can be invoked from clients such
as Claude Desktop or Cursor. For best results, include detailed
docstrings (as provided) in each API file so that the LLM knows how
to call the tool.

## Limitations and Future Work

This MVP uses simple keyword matching for categorisation and defaults
to zero billing rates. Future enhancements could include:

- Embedding‑based similarity matching for better accuracy.
- Learning from attorney corrections to improve keyword mappings.
- Integrating with a law firm’s rate tables to populate `rate` and
  `total` fields automatically.
- Implementing carrier‑specific validation rules prior to invoice
  generation.
- Adding authentication and multi‑user support.
## Pilot Upgrade Addendum

This repository has been upgraded for a pilot-ready MVP:
- True **LEDES 1998B (24 fields)** export with validation (`validators/ledes1998b.py`).
- **Explainable UTBMS coding** with seeds and overrides (`categorize.py`, `rules/utbms_seeds.json`).
- **Narrative policy warnings** to prevent rejections (`policy/narrative.py`).
- **Timekeepers, Matters, Bindings** schema (`db/migrations/001_add_mvp_pilot.sql`).
- **Focus filters, AFK merge**, basic matter binding helpers (appended to `ingest.py`).

### Quickstart
1. Ensure the SQLite DB exists (run app once) then run migration SQL in `db/migrations/001_add_mvp_pilot.sql`.
2. Seed timekeepers and matters:
   ```bash
   python3 tools/seed.py  # or python tools/seed.py path/to/your.db
   ```
3. Add bindings (via SQL or admin UI) to map subjects/paths to `client_matter_id`.
4. Generate an invoice:
   - From the UI, select matter & timekeeper, set invoice number & date range.
   - Click **Validate** then **Export LEDES 1998B**.
5. The file is saved under `exports/` and should import cleanly into standard LEDES portals.

Environment variables:
- `BILLEXACT_DB` path to SQLite database file
- `BILLEXACT_MIN_FOCUS_SEC` (default 45)
- `BILLEXACT_MERGE_WINDOW_MIN` (default 10)
- `UTBMS_SEEDS` path to UTBMS seed JSON

