#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# --- venv & deps ---
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip

# pyproject for editable package (only writes if missing)
if [ ! -f pyproject.toml ]; then
  cat > pyproject.toml <<'TOML'
[project]
name = "billexact"
version = "0.0.1"
requires-python = ">=3.10"
dependencies = ["Flask>=3.0.0","PyYAML>=6.0"]

[build-system]
requires = ["setuptools>=64","wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["."]
include = ["billexact*"]
TOML
fi

python -m pip install -e .
python -m pip install Flask PyYAML

# --- package layout (idempotent) ---
mkdir -p billexact/compliance billexact/ledes billexact/config templates db data tools
[ -f billexact/__init__.py ] || : > billexact/__init__.py
[ -f billexact/compliance/__init__.py ] || : > billexact/compliance/__init__.py
[ -f billexact/ledes/__init__.py ] || : > billexact/ledes/__init__.py

# --- core models ---
cat > billexact/models.py <<'PY'
from dataclasses import dataclass
from datetime import date
from typing import Optional
@dataclass
class TimeEntry:
    id: str
    work_date: Optional[date]
    matter_id: Optional[str]
    client_id: Optional[str]
    timekeeper_id: Optional[str]
    duration_hours: float
    description: str
    utbms_code: Optional[str] = None
PY

# --- compliance engine ---
cat > billexact/compliance/types.py <<'PY'
from dataclasses import dataclass
from enum import Enum
from typing import Optional
class Severity(str, Enum):
    WARNING = "warning"
    ERROR = "error"
@dataclass
class ComplianceIssue:
    rule_id: str
    entry_id: Optional[str]
    severity: Severity
    message: str
    suggestion: Optional[str] = None
PY

cat > billexact/compliance/rules.py <<'PY'
import re
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import date
from typing import Dict, Iterable, List, Optional
from .types import ComplianceIssue, Severity
from ..models import TimeEntry
class Rule(ABC):
    @property
    @abstractmethod
    def rule_id(self) -> str: ...
    @abstractmethod
    def apply(self, entries: Iterable[TimeEntry]) -> List[ComplianceIssue]: ...
class DescriptionLengthRule(Rule):
    def __init__(self, min_chars: int = 20): self.min_chars = min_chars
    @property
    def rule_id(self) -> str: return "description_length"
    def apply(self, entries):
        issues=[]
        for e in entries:
            desc=(e.description or "").strip()
            if len(desc)<self.min_chars:
                issues.append(ComplianceIssue(self.rule_id,e.id,Severity.WARNING,
                    f"Description too short ({len(desc)} chars).",
                    f"Add specifics (who/what/why); ≥{self.min_chars} chars."))
        return issues
class BlockBillingRule(Rule):
    VERBS=["draft","revise","review","research","analyze","email","call","meet","prepare","edit","summarize","outline","negotiate"]
    @property
    def rule_id(self) -> str: return "block_billing"
    def apply(self, entries):
        issues=[]
        for e in entries:
            d=(e.description or "").lower()
            likely=False
            if sum(1 for s in [";"," & "," and ",", "] if s in d) >= 2: likely=True
            if sum(1 for v in self.VERBS if re.search(rf"\b{re.escape(v)}(ing)?\b",d)) >= 2: likely=True
            if likely:
                issues.append(ComplianceIssue(self.rule_id,e.id,Severity.WARNING,
                    "Possible block billing (multiple tasks).",
                    "Split into discrete entries per task."))
        return issues
class DailyHoursCapRule(Rule):
    def __init__(self, max_hours: float = 12.0): self.max_hours = max_hours
    @property
    def rule_id(self) -> str: return "daily_hours_cap"
    def apply(self, entries):
        issues=[]; by_day=defaultdict(float)
        for e in entries:
            if e.work_date: by_day[e.work_date]+=e.duration_hours
        for d,total in by_day.items():
            if total>self.max_hours:
                issues.append(ComplianceIssue(self.rule_id,None,Severity.WARNING,
                    f"Total billed {total:.2f}h on {d.isoformat()} > {self.max_hours:.1f}h cap.",
                    "Add justification or reallocate if appropriate."))
        return issues
class TravelTimeRule(Rule):
    def __init__(self, keywords=None, note="Many carriers pay 50% for travel time."):
        self.keywords=keywords or ["travel","drive","commute","flight","uber","lyft","cab","taxi"]; self.note=note
    @property
    def rule_id(self) -> str: return "travel_time"
    def apply(self, entries):
        issues=[]
        for e in entries:
            d=(e.description or "").lower()
            if any(k in d for k in self.keywords):
                issues.append(ComplianceIssue(self.rule_id,e.id,Severity.WARNING,
                    "Travel time detected.", self.note+" Consider separate entry and reduced rate if required."))
        return issues
class MaxEntryDurationRule(Rule):
    def __init__(self, max_hours: Optional[float] = None): self.max_hours=max_hours
    @property
    def rule_id(self) -> str: return "max_entry_duration"
    def apply(self, entries):
        if not self.max_hours: return []
        issues=[]
        for e in entries:
            if e.duration_hours>self.max_hours:
                issues.append(ComplianceIssue(self.rule_id,e.id,Severity.WARNING,
                    f"Entry {e.duration_hours:.2f}h > {self.max_hours:.2f}h guideline.",
                    "Split into smaller tasks."))
        return issues
class VaguePhraseRule(Rule):
    DEFAULT=["work on","misc","general","review docs","review documents","admin","administrative","follow up","follow-up"]
    def __init__(self, phrases=None): self.phrases=phrases or self.DEFAULT
    @property
    def rule_id(self) -> str: return "vague_phrase"
    def apply(self, entries):
        issues=[]
        for e in entries:
            d=(e.description or "").lower().strip()
            for p in self.phrases:
                if p in d and len(d.split())<6:
                    issues.append(ComplianceIssue(self.rule_id,e.id,Severity.WARNING,
                        f'Vague phrase "{p}" without specifics.',"Specify document names, parties, dates, or purpose."))
                    break
        return issues
PY

cat > billexact/compliance/engine.py <<'PY'
import json
from pathlib import Path
from typing import Iterable, List, Optional, Sequence
try: import yaml
except ImportError: yaml=None
from .rules import (DescriptionLengthRule, BlockBillingRule, DailyHoursCapRule,
                    TravelTimeRule, MaxEntryDurationRule, VaguePhraseRule, Rule)
from .types import ComplianceIssue
from ..models import TimeEntry
DEFAULT_RULES: Sequence[Rule] = (
    DescriptionLengthRule(min_chars=20),
    VaguePhraseRule(),
    BlockBillingRule(),
    DailyHoursCapRule(max_hours=12.0),
    TravelTimeRule(),
    MaxEntryDurationRule(max_hours=None),
)
def _load_config(path: Optional[str]) -> dict:
    if not path: return {}
    p=Path(path)
    if not p.exists(): return {}
    txt=p.read_text(encoding="utf-8")
    if p.suffix.lower() in (".yml",".yaml") and yaml is not None:
        return yaml.safe_load(txt) or {}
    return json.loads(txt)
def _rules_from_config(cfg: dict):
    rules=[]; rcfg=(cfg or {}).get("rules",{})
    def on(name, default=True): return rcfg.get(name,{}).get("enabled",default)
    if on("description_length",True): rules.append(DescriptionLengthRule(min_chars=int(rcfg.get("description_length",{}).get("min_chars",20))))
    if on("vague_phrase",True): rules.append(VaguePhraseRule(phrases=rcfg.get("vague_phrase",{}).get("phrases",None)))
    if on("block_billing",True): rules.append(BlockBillingRule())
    if on("daily_hours_cap",True): rules.append(DailyHoursCapRule(max_hours=float(rcfg.get("daily_hours_cap",{}).get("max_hours",12.0))))
    if on("travel_time",True): rules.append(TravelTimeRule(keywords=rcfg.get("travel_time",{}).get("keywords",None)))
    if on("max_entry_duration",False):
        mx=rcfg.get("max_entry_duration",{}).get("max_hours",None)
        if mx is not None: rules.append(MaxEntryDurationRule(max_hours=float(mx)))
    return rules
def run_compliance(entries: Iterable[TimeEntry], config_path: Optional[str] = "billexact/config/rules.yml") -> List[ComplianceIssue]:
    cfg=_load_config(config_path) if config_path else {}
    rules=_rules_from_config(cfg) if cfg else list(DEFAULT_RULES)
    issues=[]; entries_list=list(entries)
    for r in rules: issues.extend(r.apply(entries_list))
    return issues
PY

# --- LEDES exporter ---
cat > billexact/ledes/exporter.py <<'PY'
from typing import Iterable
from ..models import TimeEntry
def to_ledes_1998b(entries: Iterable[TimeEntry], *, client_id:str, matter_id:str, timekeeper_id:str, rate:float, invoice_id:str) -> str:
    lines=[]
    header="INVOICE_DATE|CLIENT_ID|LAW_FIRM_MATTER_ID|INVOICE_NUMBER|LINE_ITEM_NUMBER|EXP/FEE/INV_ADJ|LINE_ITEM_DATE|TIMEKEEPER_ID|TASK_CODE|ACTIVITY_CODE|LINE_ITEM_UNITS|LINE_ITEM_RATE|LINE_ITEM_AMOUNT|LINE_ITEM_DESCRIPTION"
    lines.append(header)
    i=1
    for e in entries:
        amt = round(e.duration_hours*rate,2)
        date_str = e.work_date.isoformat() if e.work_date else ""
        desc = (e.description or "").replace("|","/")
        task = e.utbms_code or ""
        cols = ["", client_id, matter_id, invoice_id, str(i), "F", date_str, timekeeper_id, task, "", f"{e.duration_hours:.2f}", f"{rate:.2f}", f"{amt:.2f}", desc]
        lines.append("|".join(cols)); i+=1
    return "\n".join(lines) + "\n"
PY

# --- default rules config ---
cat > billexact/config/rules.yml <<'YML'
rules:
  description_length: { enabled: true, min_chars: 24 }
  vague_phrase: { enabled: true, phrases: ["work on","misc","general","review docs","review documents","follow up"] }
  block_billing: { enabled: true }
  daily_hours_cap: { enabled: true, max_hours: 10 }
  travel_time: { enabled: true, keywords: ["travel","drive","uber","cab","taxi"] }
  max_entry_duration: { enabled: false, max_hours: 0.3 }
YML

# --- DB schema + seed ---
cat > db/init.sql <<'SQL'
CREATE TABLE IF NOT EXISTS clients (client_id TEXT PRIMARY KEY, name TEXT);
CREATE TABLE IF NOT EXISTS matters (matter_id TEXT PRIMARY KEY, client_id TEXT, description TEXT);
CREATE TABLE IF NOT EXISTS timekeepers (id TEXT PRIMARY KEY, name TEXT);
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
SQL

cat > tools/seed_demo.py <<'PY'
import os, sqlite3, datetime, pathlib
db=os.environ.get("BILLEXACT_DB","data/billexact.db")
pathlib.Path(db).parent.mkdir(parents=True, exist_ok=True)
conn=sqlite3.connect(db); c=conn.cursor()
c.executescript(open("db/init.sql","r",encoding="utf-8").read())
today=datetime.date.today().isoformat()
c.execute("INSERT OR IGNORE INTO clients(client_id,name) VALUES(?,?)",("CLIENT1","Acme Insurance"))
c.execute("INSERT OR IGNORE INTO matters(matter_id,client_id,description) VALUES(?,?,?)",("MATTER1","CLIENT1","Smith v. Acme"))
c.execute("INSERT OR IGNORE INTO timekeepers(id,name) VALUES(?,?)",("TK1","Alice Attorney"))
rows=c.execute("SELECT COUNT(*) FROM time_entries").fetchone()[0]
if rows==0:
    c.executemany("INSERT INTO time_entries(date,description,duration,utbms_code,matter_id,client_id,timekeeper_id) VALUES (?,?,?,?,?,?,?)",[
        (today,"Draft motion for summary judgment; emails to client",0.8,"L310","MATTER1","CLIENT1","TK1"),
        (today,"Review docs",0.2,"","MATTER1","CLIENT1","TK1"),
        (today,"Travel to deposition",1.0,"","MATTER1","CLIENT1","TK1"),
    ])
conn.commit(); conn.close()
print("DB ready at:", db)
PY

# --- Flask app on 0.0.0.0:5050 ---
cat > app.py <<'PY'
import os, sqlite3, datetime
from flask import Flask, render_template, request, jsonify, Response
from billexact.models import TimeEntry
from billexact.compliance.engine import run_compliance
from billexact.ledes.exporter import to_ledes_1998b
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
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
PY

# --- dashboard template ---
cat > templates/dashboard.html <<'HTML'
<!doctype html><html><head><meta charset="utf-8" />
<title>BillExact — Daily Review</title>
<style>
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:24px}
table{border-collapse:collapse;width:100%}
th,td{border:1px solid #e4e4e4;padding:8px 10px;text-align:left}
th{background:#f7f7f7}.warn{color:#b26b00}.err{color:#c62828}
.badge{display:inline-block;padding:2px 6px;border-radius:6px;font-size:12px}
.badge-warn{background:#fff3cd;color:#7a5a00}.badge-err{background:#fdecea;color:#7a1a1a}
</style></head><body>
<h1>BillExact — Daily Review</h1>
<table><tr><th>ID</th><th>Date</th><th>Description</th><th>UTBMS</th><th>Duration (h)</th><th>Compliance</th></tr>
{% for e in entries %}
<tr>
<td>{{ e.id }}</td>
<td>{{ e.work_date or '' }}</td>
<td>{{ e.description }}</td>
<td>{{ e.utbms_code or '' }}</td>
<td>{{ '%.2f'|format(e.duration_hours) }}</td>
<td>
{% set flagged = [] %}
{% for i in issues if i.entry_id == e.id %}
  {% set cls = 'badge-warn' if i.severity == 'warning' else 'badge-err' %}
  <span class="badge {{ cls }}">{{ i.rule_id }}</span>
  <div class="{{ 'warn' if i.severity == 'warning' else 'err' }}">{{ i.message }}{% if i.suggestion %} — {{ i.suggestion }}{% endif %}</div>
  {% set flagged = flagged + [i.rule_id] %}
{% endfor %}
{% if flagged|length == 0 %}
  <span class="badge" style="background:#e8f5e9;color:#1b5e20;">clean</span>
{% endif %}
</td>
</tr>
{% endfor %}
</table>
</body></html>
HTML

# --- seed & run ---
export BILLEXACT_DB="$(pwd)/data/billexact.db"
python tools/seed_demo.py

# free 5050 then run foreground (see logs)
lsof -ti tcp:5050 | xargs kill -9 2>/dev/null || true
python app.py
