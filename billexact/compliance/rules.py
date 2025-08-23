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
