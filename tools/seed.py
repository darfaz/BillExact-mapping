#!/usr/bin/env python3
"""
tools/seed.py
Load seeds for timekeepers and matters into the SQLite DB.
"""
import json, sqlite3, sys, os

DB_PATH = os.environ.get("BILLEXACT_DB", "billexact.db")
if len(sys.argv) > 1:
    DB_PATH = sys.argv[1]

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

def load_json(path):
    with open(path, "r") as f:
        return json.load(f)

def upsert_timekeepers(items):
    for tk in items:
        cur.execute("""
        INSERT INTO timekeepers (id, name, classification, rate)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET name=excluded.name, classification=excluded.classification, rate=excluded.rate
        """, (tk["id"], tk["name"], tk["classification"], tk["rate"]))
    conn.commit()

def insert_matters(items):
    for m in items:
        cur.execute("""
        INSERT INTO matters (client_id, client_matter_id, law_firm_matter_id, law_firm_id, description, billing_start, billing_end)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (m["client_id"], m["client_matter_id"], m["law_firm_matter_id"], m["law_firm_id"], m.get("description",""), m.get("billing_start",""), m.get("billing_end","")))
    conn.commit()

if __name__ == "__main__":
    upsert_timekeepers(load_json("seeds/timekeepers.json"))
    insert_matters(load_json("seeds/matters.json"))
    print(f"Seeded timekeepers and matters into {DB_PATH}")
