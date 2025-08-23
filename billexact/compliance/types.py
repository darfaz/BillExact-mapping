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
