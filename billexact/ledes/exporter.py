from typing import Iterable
from ..models import TimeEntry
def to_ledes_1998b(entries: Iterable[TimeEntry], *, client_id:str, matter_id:str, timekeeper_id:str, rate:float, invoice_id:str) -> str:
    lines=[]
    header="INVOICE_DATE|CLIENT_ID|LAW_FIRM_MATTER_ID|INVOICE_NUMBER|LINE_ITEM_NUMBER|EXP/FEE/INV_ADJ|LINE_ITEM_DATE|TIMEKEEPER_ID|TASK_CODE|ACTIVITY_CODE|LINE_ITEM_UNITS|LINE_ITEM_RATE|LINE_ITEM_AMOUNT|LINE_ITEM_DESCRIPTION"
    lines.append(header)
    i=1
    for e in entries:
        if not (getattr(e, "utbms_code", "") or "").strip() or (e.utbms_code or "").upper()=="NB":
            continue
        amt = round(e.duration_hours*rate,2)
        date_str = e.work_date.isoformat() if e.work_date else ""
        desc = (e.description or "").replace("|","/")
        task = e.utbms_code or ""
        cols = ["", client_id, matter_id, invoice_id, str(i), "F", date_str, timekeeper_id, task, "", f"{e.duration_hours:.2f}", f"{rate:.2f}", f"{amt:.2f}", desc]
        lines.append("|".join(cols)); i+=1
    return "\n".join(lines) + "\n"
