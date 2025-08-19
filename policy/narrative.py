# policy/narrative.py
import re

FORBIDDEN = [r"\bvarious tasks\b", r"\betc\.\b", r"\badmin(istrative)?\b"]
REQUIRES_DETAIL = [r"\breview(ed)?\b", r"\bwork(ed)? on\b", r"\bprepare(d)?\b"]
TRAVEL = [r"\btravel\b", r"\bdrive\b", r"\bflight\b", r"\buber\b", r"\bcab\b"]

def check_narrative(text: str):
    t = (text or "").strip()
    warnings = []
    for pat in FORBIDDEN:
        if re.search(pat, t, re.I):
            warnings.append("Avoid vague terms like 'various tasks' or 'etc.'")
    if any(re.search(p, t, re.I) for p in REQUIRES_DETAIL) and len(t.split()) < 6:
        warnings.append("Add who/what/why (e.g., which docs, purpose, counterpart).")
    if any(re.search(p, t, re.I) for p in TRAVEL) and " to " not in t.lower():
        warnings.append("Travel requires destination and purpose (e.g., 'Travel to court for hearing').")
    return warnings
