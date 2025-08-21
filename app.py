from flask import Flask, render_template, request
from billexact.compliance.engine import TimeEntry, run_compliance
import sqlite3

app = Flask(__name__)

@app.route("/")
def dashboard():
    conn = sqlite3.connect("billexact.db")
    rows = conn.execute("SELECT id, date, narrative, duration FROM time_entries").fetchall()
    conn.close()
    entries = [TimeEntry(id=row[0], duration=row[3], narrative=row[2]) for row in rows]
    issues = run_compliance(entries)
    return render_template("dashboard.html", entries=entries, issues=issues)

if __name__ == "__main__":
    app.run(debug=True)
