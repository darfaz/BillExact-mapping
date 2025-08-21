import yaml
from dataclasses import dataclass
from typing import List

@dataclass
class TimeEntry:
    id: int
    duration: float  # hours
    narrative: str

@dataclass
class ComplianceIssue:
    rule_id: str
    message: str
    severity: str  # "WARNING" | "ERROR"

def run_compliance(entries: List[TimeEntry], config_path="billexact/config/rules.yml") -> List[ComplianceIssue]:
    with open(config_path) as f:
        rules = yaml.safe_load(f)
    issues = []
    for entry in entries:
        if entry.duration > rules["daily_hours_cap"]:
            issues.append(ComplianceIssue("daily_hours_cap", f"Entry {entry.id} exceeds daily cap", "WARNING"))
        for phrase in rules["forbidden_phrases"]:
            if phrase in entry.narrative.lower():
                issues.append(ComplianceIssue("forbidden_phrase", f"'{phrase}' found in entry {entry.id}", "ERROR"))
    return issues
