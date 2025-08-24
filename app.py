import os, sqlite3, datetime
from flask import Flask, render_template, request, jsonify, Response
from billexact.models import TimeEntry
from billexact.compliance.engine import run_compliance
from billexact.ledes.exporter import to_ledes_1998b
from billexact.policy.loader import load_policy_for_client
from billexact.compliance.types import ComplianceIssue, Severity
from billexact.mapper import map_utbms
DB_PATH = os.environ.get("BILLEXACT_DB", os.path.join("data","billexact.db"))
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
def db_bootstrap():
    conn = sqlite3.connect(DB_PATH)
    with open(os.path.join("db","init.sql"), "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit(); conn.close()
db_bootstrap()
app = Flask(__name__)
def fetch_entries(limit=200):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT id, date, description, duration, utbms_code, matter_id, client_id, timekeeper_id FROM time_entries ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    entries=[]
    for r in rows:
        _id, d, desc, dur, code, matter, client, tk = r
        try:
            dt = datetime.date.fromisoformat(d) if d else None
        except Exception:
            dt = None
        entries.append(TimeEntry(
            id=str(_id), work_date=dt, matter_id=matter, client_id=client, timekeeper_id=tk,
            duration_hours=float(dur or 0), description=desc or "", utbms_code=code
        ))
    return entries

def _load_desc_cfg():
    import yaml
    from pathlib import Path
    p = Path("billexact/config/descriptions.yml")
    if not p.exists():
        return {}
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}

def _dominant_client_id(entries):
    from collections import Counter
    c = Counter([ (e.client_id or "").strip() for e in entries if (e.client_id or "").strip() ])
    return c.most_common(1)[0][0] if c else None

def _policy_issues(entries, policy, desc_cfg):
    issues = []
    forbid = set( (desc_cfg.get("adequate_rules") or {}).get("forbid_vague_phrases", []) )
    require_participants = (desc_cfg.get("adequate_rules") or {}).get("require_participants_on_comms", False)

    for e in entries:
        desc = (e.description or "")
        low = desc.lower()

        # forbidden phrases
        for fp in forbid:
            if fp.lower() in low:
                issues.append(ComplianceIssue(
                    rule_id="policy_desc_vague",
                    entry_id=str(e.id),
                    severity=Severity.WARNING,
                    message=f'Vague phrase "{fp}" detected; add specifics.',
                    suggestion="Identify participants, purpose, scope, volume; split tasks if needed."
                ))
                break

        # L140 communications: require participants if policy says so
        if require_participants and (e.utbms_code or "").upper() == "L140":
            # naive check: look for "with " or a known email/phone cue
            if (" with " not in low) and ("@" not in low) and ("call" not in low):
                issues.append(ComplianceIssue(
                    rule_id="policy_comm_participants",
                    entry_id=str(e.id),
                    severity=Severity.WARNING,
                    message="Participants missing for communication entry (L140).",
                    suggestion="Include who you communicated with and the subject."
                ))
    return issues
@app.route("/")
def dashboard():
    entries = fetch_entries()
    issues = run_compliance(entries, config_path="billexact/config/rules.yml")
    return render_template("dashboard.html", entries=entries, issues=issues, error=None)
@app.route("/api/compliance", methods=["POST"])
def api_compliance():
    data = request.get_json(force=True); items=data.get("entries",[])
    entries=[]
    for it in items:
        entries.append(TimeEntry(
            id=str(it.get("id")), work_date=None,
            matter_id=it.get("matter_id"), client_id=it.get("client_id"), timekeeper_id=it.get("timekeeper_id"),
            duration_hours=float(it.get("duration_hours",0.0)), description=it.get("description",""),
            utbms_code=it.get("utbms_code")
        ))
    issues = run_compliance(entries, config_path="billexact/config/rules.yml")
    client_id = None
    if entries:
        client_id = entries[0].client_id
    policy = load_policy_for_client(client_id)
    desc_cfg = _load_desc_cfg()
    issues += _policy_issues(entries, policy, desc_cfg)
    return jsonify([{
        "rule_id": i.rule_id, "entry_id": i.entry_id, "severity": i.severity.value,
        "message": i.message, "suggestion": i.suggestion
    } for i in issues])
@app.route("/api/ledes/export", methods=["POST"])
def api_ledes_export():
    body = request.get_json(force=True)
    matter_id = body["matter_id"]; client_id=body.get("client_id","CLIENT1")
    invoice_id = body.get("invoice_id","INV-001"); timekeeper_id = body.get("timekeeper_id","TK1")
    rate = float(body.get("rate",250.0))
    all_entries = [e for e in fetch_entries(2000) if e.matter_id==matter_id]
    ledes = to_ledes_1998b(all_entries, client_id=client_id, matter_id=matter_id, timekeeper_id=timekeeper_id, rate=rate, invoice_id=invoice_id)
    return Response(ledes, mimetype="text/plain", headers={"Content-Disposition": f'attachment; filename="{invoice_id}.LED"'})

from billexact.ingest.activitywatch import summarize_events
@app.route("/api/ingest/aw", methods=["POST"])
def api_aw_ingest():
    """
    Body: {"start":"2025-08-20T00:00:00","end":"2025-08-21T00:00:00",
           "client_id":"CLIENT1","matter_id":"MATTER1","timekeeper_id":"TK1"}
    """
    body = request.get_json(force=True)
    start = body.get("start"); end = body.get("end")
    client_id = body.get("client_id","CLIENT1")
    matter_id = body.get("matter_id","MATTER1")
    timekeeper_id = body.get("timekeeper_id","TK1")
    # fetch from AW
    items = summarize_events(start, end)
    if not items:
        return jsonify({"inserted": 0, "note": "No AW server or no events in window."})
    # persist into SQLite
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    # ensure tables exist
    with open(os.path.join("db","init.sql"), "r", encoding="utf-8") as f:
        c.executescript(f.read())
    ins = "INSERT INTO time_entries(date,description,duration,utbms_code,matter_id,client_id,timekeeper_id) VALUES (?,?,?,?,?,?,?)"
    rows = 0
    for it in items:
        code = map_utbms(it.get("description"), it.get("app"), it.get("host"))
        c.execute(ins,(it["date"], it["description"], it["duration_hours"], code, matter_id, client_id, timekeeper_id))
        rows += 1
    conn.commit(); conn.close()
    return jsonify({"inserted": rows})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
