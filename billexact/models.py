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
