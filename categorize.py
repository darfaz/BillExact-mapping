"""
categorize.py
---------------
Rule-first, explainable UTBMS coding with overrides.
"""
import json, re, sqlite3, os

SEED_PATH = os.environ.get("UTBMS_SEEDS", "rules/utbms_seeds.json")

def load_seeds(path=SEED_PATH):
    with open(path, "r") as f:
        return json.load(f)

def match_list(text, words):
    hits = []
    for w in words:
        if re.search(rf"\b{re.escape(w)}\b", text, flags=re.I):
            hits.append(w)
    return hits

def categorize_text(text: str, db_path: str = os.environ.get("BILLEXACT_DB","billexact.db")):
    t = (text or "").strip()
    if not t:
        return {"task_code": None, "activity_code": None, "confidence": 0.0, "why": [], "description": text}

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 1) overrides (exact phrase)
    cur.execute("CREATE TABLE IF NOT EXISTS utbms_overrides (id INTEGER PRIMARY KEY AUTOINCREMENT, phrase TEXT UNIQUE, task_code TEXT, activity_code TEXT, notes TEXT)")
    row = cur.execute("SELECT task_code, activity_code FROM utbms_overrides WHERE phrase=?", (t,)).fetchone()
    if row:
        return {"task_code": row[0], "activity_code": row[1], "confidence": 0.98, "why": ["override: exact phrase"], "description": text}

    seeds = load_seeds()
    why = []

    # 2) activity (verbs)
    a_best, a_hits = None, []
    for a_code, verbs in seeds["activity"].items():
        hits = match_list(t.lower(), verbs)
        if hits and len(hits) > len(a_hits):
            a_hits, a_best = hits, a_code
    if a_best: why.append(f"{a_best}: {a_hits}")

    # 3) task (phase nouns)
    l_best, l_hits = None, []
    for l_code, nouns in seeds["task"].items():
        hits = match_list(t.lower(), nouns)
        if hits and len(hits) > len(l_hits):
            l_hits, l_best = hits, l_code
    if l_best: why.append(f"{l_best}: {l_hits}")

    # 4) confidence
    conf = 0.35
    if a_best: conf += 0.25 + 0.05*len(a_hits)
    if l_best: conf += 0.25 + 0.05*len(l_hits)
    conf = min(0.99, conf)

    return {"task_code": l_best, "activity_code": a_best, "confidence": round(conf,2), "why": why, "description": text}
