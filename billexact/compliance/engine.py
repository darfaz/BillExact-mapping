import json
from pathlib import Path
from typing import Iterable, List, Optional, Sequence
try: import yaml
except ImportError: yaml=None
from .rules import (DescriptionLengthRule, BlockBillingRule, DailyHoursCapRule,
                    TravelTimeRule, MaxEntryDurationRule, VaguePhraseRule, Rule)
from .types import ComplianceIssue
from ..models import TimeEntry
DEFAULT_RULES: Sequence[Rule] = (
    DescriptionLengthRule(min_chars=20),
    VaguePhraseRule(),
    BlockBillingRule(),
    DailyHoursCapRule(max_hours=12.0),
    TravelTimeRule(),
    MaxEntryDurationRule(max_hours=None),
)
def _load_config(path: Optional[str]) -> dict:
    if not path: return {}
    p=Path(path)
    if not p.exists(): return {}
    txt=p.read_text(encoding="utf-8")
    if p.suffix.lower() in (".yml",".yaml") and yaml is not None:
        return yaml.safe_load(txt) or {}
    return json.loads(txt)
def _rules_from_config(cfg: dict):
    rules=[]; rcfg=(cfg or {}).get("rules",{})
    def on(name, default=True): return rcfg.get(name,{}).get("enabled",default)
    if on("description_length",True): rules.append(DescriptionLengthRule(min_chars=int(rcfg.get("description_length",{}).get("min_chars",20))))
    if on("vague_phrase",True): rules.append(VaguePhraseRule(phrases=rcfg.get("vague_phrase",{}).get("phrases",None)))
    if on("block_billing",True): rules.append(BlockBillingRule())
    if on("daily_hours_cap",True): rules.append(DailyHoursCapRule(max_hours=float(rcfg.get("daily_hours_cap",{}).get("max_hours",12.0))))
    if on("travel_time",True): rules.append(TravelTimeRule(keywords=rcfg.get("travel_time",{}).get("keywords",None)))
    if on("max_entry_duration",False):
        mx=rcfg.get("max_entry_duration",{}).get("max_hours",None)
        if mx is not None: rules.append(MaxEntryDurationRule(max_hours=float(mx)))
    return rules
def run_compliance(entries: Iterable[TimeEntry], config_path: Optional[str] = "billexact/config/rules.yml") -> List[ComplianceIssue]:
    cfg=_load_config(config_path) if config_path else {}
    rules=_rules_from_config(cfg) if cfg else list(DEFAULT_RULES)
    issues=[]; entries_list=list(entries)
    for r in rules: issues.extend(r.apply(entries_list))
    return issues
