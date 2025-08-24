
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, Optional
import yaml

_BASE = Path("billexact/policy/_base.yml")
_ENDURANCE = Path("billexact/policy/endurance.yml")

def _load_yaml(p: Path) -> Dict[str, Any]:
    if not p.exists():
        return {}
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}

def _deep_merge(a: Dict[str,Any], b: Dict[str,Any]) -> Dict[str,Any]:
    out = dict(a)
    for k,v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out

def load_policy_for_client(client_id: Optional[str]) -> Dict[str, Any]:
    base = _load_yaml(_BASE)
    if not client_id:
        return base
    cid = (client_id or "").strip().upper()
    overlay = {}
    end = _load_yaml(_ENDURANCE)
    appl = (end.get("applies_if") or {}).get("client_id_in") or []
    if any(cid == item.strip().upper() for item in appl):
        overlay = end
    # merge overlay over base (overlay wins)
    return _deep_merge(base, overlay)
