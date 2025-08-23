import re

KEYS_RESEARCH = ("westlaw","lexis","casetext","scholar.google","fastcase","heinonline")
KEYS_EMAIL = ("outlook","gmail","mail","imap","smtp","owa")
KEYS_MOTION = ("motion","ms word","word",".doc","pleading","brief")
KEYS_DISCOVERY = ("relativity","everlaw","discovery","interrogatories","rfo","rpd")
KEYS_DEPO = ("zoom","webex","teams","gotomeeting","deposition")

# very simple mapper; you can refine as you go
# returns UTBMS code string (ABA Litigation set)
# L120 Research; L140 Communications; L210 Pleadings; L230 Discovery; L240 Motions; L310 Written Motions/Briefs; L330 Depositions

def map_utbms(desc: str, app: str|None=None, host: str|None=None) -> str:
    s = (desc or "").lower()
    a = (app or "").lower()
    h = (host or "").lower()
    text = " ".join([s,a,h])
    if any(k in text for k in KEYS_RESEARCH):
        return "L120"
    if any(k in text for k in KEYS_EMAIL):
        return "L140"
    if any(k in text for k in KEYS_DISCOVERY):
        return "L230"
    if any(k in text for k in KEYS_DEPO):
        return "L330"
    if any(k in text for k in KEYS_MOTION):
        # try to distinguish briefs/motions; default to motions & submissions
        return "L310"
    # fallbacks by app/category
    if "pdf" in s or "preview" in a:
        return "L230"
    if "word" in a or s.endswith('.doc'):
        return "L310"
    if "chrome" in a or "safari" in a or "firefox" in a:
        return "L120"
    return "L130"  # case assessment/strategy
