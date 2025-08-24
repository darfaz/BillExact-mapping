import os, sqlite3, datetime
from flask import Flask, render_template, request, jsonify, Response
from billexact.models import TimeEntry
from billexact.compliance.engine import run_compliance
from billexact.compliance.types import ComplianceIssue, Severity
from billexact.ledes.exporter import to_ledes_1998b
from billexact.ingest.activitywatch import summarize_events
from billexact.mapper import map_utbms

DB_PATH = os.environ.get("BILLEXACT_DB", os.path.join("data","billexact.db"))
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def db_bootstrap():
    conn = sqlite3.connect(DB_PATH)
    init_sql_path = os.path.join("db","init.sql")
    if os.path.exists(init_sql_path):
        with open(init_sql_path, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
    conn.commit()
    conn.close()
db_bootstrap()

app = Flask(__name__)

def fetch_entries(limit=200):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, date, description, duration, utbms_code, matter_id, client_id, timekeeper_id "
        "FROM time_entries ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    entries=[]
    for r in rows:
        _id, d, desc, dur, code, matter, client, tk = r
        try:
            wdate = datetime.date.fromisoformat(d) if d else None
        except Exception:
            wdate = None
        entries.append(TimeEntry(
            id=str(_id),
            work_date=wdate,
            matter_id=matter,
            client_id=client,
            timekeeper_id=tk,
            duration_hours=float(dur or 0.0),
            description=desc or "",
            utbms_code=code
        ))
    return entries

@app.route("/")
def dashboard():
    entries = fetch_entries()
    totals = {}
    total_h = 0.0
    for e in entries:
        code = (e.utbms_code or "").upper() or "UNCODED"
        totals[code] = totals.get(code, 0.0) + float(e.duration_hours or 0.0)
        total_h += float(e.duration_hours or 0.0)
    issues = run_compliance(entries, config_path="billexact/config/rules.yml")
    return render_template("dashboard.html", entries=entries, issues=issues, totals=totals, total_h=total_h, error=None)

@app.route("/api/entry/<entry_id>", methods=["POST"])
def api_update_entry(entry_id):
    data = request.get_json(force=True)
    fields, params = [], []
    for k in ("description","utbms_code","client_id","matter_id","timekeeper_id"):
        if k in data and data[k] is not None:
            fields.append(f"{k}=?"); params.append(data[k])
    if not fields:
        return jsonify({"updated":0,"msg":"no fields"}), 400
    params.append(entry_id)
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute(f"UPDATE time_entries SET {', '.join(fields)} WHERE id=?", params)
    conn.commit(); conn.close()
    return jsonify({"updated":1})

@app.route("/api/compliance", methods=["POST"])
def api_compliance():
    data = request.get_json(force=True); items = data.get("entries",[])
    entries = []
    for it in items:
        entries.append(TimeEntry(
            id=str(it.get("id")), work_date=None,
            matter_id=it.get("matter_id"), client_id=it.get("client_id"), timekeeper_id=it.get("timekeeper_id"),
            duration_hours=float(it.get("duration_hours",0.0)),
            description=it.get("description") or "",
            utbms_code=it.get("utbms_code")
        ))
    issues = run_compliance(entries, config_path="billexact/config/rules.yml")
    return jsonify([{
        "rule_id": i.rule_id, "entry_id": i.entry_id, "severity": i.severity.value,
        "message": i.message, "suggestion": i.suggestion
    } for i in issues])

@app.route("/api/seed/synthetic", methods=["POST"])
def api_seed_synthetic():
    body = request.get_json(force=True) if request.is_json else {}
    client_id = (body.get("client_id") or "ENDURANCE").strip()
    matter_id = (body.get("matter_id") or "MATTER-DEMO").strip()
    timekeeper_id = (body.get("timekeeper_id") or "TK1").strip()
    today = datetime.date.today().isoformat()
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS time_entries (
      id INTEGER PRIMARY KEY,
      date TEXT,
      description TEXT,
      duration REAL,
      utbms_code TEXT,
      matter_id TEXT,
      client_id TEXT,
      timekeeper_id TEXT
    );
    """)
    demo = [
      (today, "Email with adjuster Smith re discovery schedule — next steps: serve RFP set 1", 0.4, "L140"),
      (today, "Draft Motion to Compel further responses; review prior objections", 1.2, "L310"),
      (today, "Prepare RFP Set One to plaintiff (scope: medicals/employment); review responses and follow-up", 1.0, "L230"),
      (today, "Research: sanctions standard for refusal to answer in deposition; memo to file", 0.8, "L120"),
      (today, "Prepare Dr. Lee for deposition (topics: causation, treatment gaps; exhibits: MRI/Bates 100-145)", 0.9, "L330"),
      (today, "Early case assessment (liability/venue/damages) — strategy options and budget impact", 0.6, "L130")
    ]
    for d in demo:
        c.execute(
          "INSERT INTO time_entries(date,description,duration,utbms_code,matter_id,client_id,timekeeper_id) VALUES (?,?,?,?,?,?,?)",
          (d[0], d[1], d[2], d[3], matter_id, client_id, timekeeper_id)
        )
    conn.commit(); conn.close()
    return jsonify({"inserted": len(demo), "client_id": client_id, "matter_id": matter_id, "timekeeper_id": timekeeper_id})

@app.route("/api/ingest/aw", methods=["POST"])
def api_aw_ingest():
    body = request.get_json(force=True)
    start = body.get("start"); end = body.get("end")
    client_id = (body.get("client_id") or "CLIENT1").strip()
    matter_id = (body.get("matter_id") or "MATTER1").strip()
    timekeeper_id = (body.get("timekeeper_id") or "TK1").strip()
    items = summarize_events(start, end)
    if not items:
        return jsonify({"inserted": 0, "note": "No AW server or no events in window."})
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS time_entries (
      id INTEGER PRIMARY KEY,
      date TEXT,
      description TEXT,
      duration REAL,
      utbms_code TEXT,
      matter_id TEXT,
      client_id TEXT,
      timekeeper_id TEXT
    );
    """)
    inserted=0
    for it in items:
        code = map_utbms(it.get("description"), it.get("app"), it.get("host"))
        c.execute(
          "INSERT INTO time_entries(date,description,duration,utbms_code,matter_id,client_id,timekeeper_id) VALUES (?,?,?,?,?,?,?)",
          (it["date"], it["description"], it["duration_hours"], code, matter_id, client_id, timekeeper_id)
        )
        inserted += 1
    conn.commit(); conn.close()
    return jsonify({"inserted": inserted})

@app.route("/api/ledes/export", methods=["POST"])
def api_ledes_export():
    body = request.get_json(force=True)
    matter_id = body["matter_id"]
    client_id = body.get("client_id","CLIENT1")
    invoice_id = body.get("invoice_id","INV-001")
    timekeeper_id = body.get("timekeeper_id","TK1")
    rate = float(body.get("rate",250.0))
    all_entries = [e for e in fetch_entries(2000) if e.matter_id==matter_id]
    ledes = to_ledes_1998b(all_entries, client_id=client_id, matter_id=matter_id, timekeeper_id=timekeeper_id, rate=rate, invoice_id=invoice_id)
    return Response(ledes, mimetype="text/plain", headers={"Content-Disposition": f'attachment; filename="{invoice_id}.LED"'})
