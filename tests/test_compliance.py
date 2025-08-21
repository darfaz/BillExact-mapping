from billexact.compliance.engine import TimeEntry, run_compliance

def e(i, hrs, txt): return TimeEntry(i, hrs, txt)

def test_daily_hours_cap():
    entries = [e(i, 1.5, "Research") for i in range(9)]  # 13.5h
    issues = run_compliance(entries)
    assert any(i.rule_id == "daily_hours_cap" for i in issues)

def test_forbidden_phrase():
    entries = [e(1, 1.0, "Research on case")]
    issues = run_compliance(entries)
    assert any(i.rule_id == "forbidden_phrase" for i in issues)
