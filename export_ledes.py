"""
export_ledes.py
----------------
Export truly compliant LEDES 1998B (24 fields) with validation.
"""
import os, sqlite3, csv, datetime
from validators.ledes1998b import LEDES_1998B_FIELDS, validate_ledes_rows

DB_PATH = os.environ.get("BILLEXACT_DB","billexact.db")

def _fmt_date(dt):
    if isinstance(dt, (datetime.date, datetime.datetime)):
        return dt.strftime("%Y%m%d")
    # assume 'YYYY-MM-DD' or ISO strings
    s = str(dt)[:10]
    return s.replace("-", "")

def export_ledes1998b(client_matter_id: str, invoice_number: str, billing_start: str, billing_end: str, invoice_description: str = ""):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # Fetch matter & firm info
    m = cur.execute("""SELECT client_id, client_matter_id, law_firm_matter_id, law_firm_id, description FROM matters WHERE client_matter_id=?""", (client_matter_id,)).fetchone()
    if not m:
        raise ValueError("Matter not found. Please add it under 'matters'.")
    client_id, cmid, law_firm_matter_id, law_firm_id, m_desc = m

    # Fetch entries in range (assumes table time_entries exists with columns: date, narrative, units, timekeeper_id, task_code, activity_code, client_matter_id)
    rows = cur.execute("""
        SELECT date, narrative, units, timekeeper_id, task_code, activity_code
        FROM time_entries
        WHERE client_matter_id=? AND date BETWEEN ? AND ?
        ORDER BY date ASC
    """, (client_matter_id, billing_start, billing_end)).fetchall()

    # Build line items
    out_rows = []
    line_no = 1
    invoice_date = _fmt_date(billing_end)
    billing_start_f = _fmt_date(billing_start)
    billing_end_f = _fmt_date(billing_end)
    invoice_desc = invoice_description or (m_desc or "")

    invoice_total = 0.0
    for (line_date, description, units, tk_id, task_code, activity_code) in rows:
        tk = cur.execute("SELECT name, classification, rate FROM timekeepers WHERE id=?", (tk_id,)).fetchone()
        if not tk:
            raise ValueError(f"Missing timekeeper '{tk_id}'. Add it to timekeepers with a non-zero rate.")
        tk_name, tk_class, rate = tk
        units = float(units or 0)
        rate = float(rate or 0)
        adj = 0.0
        line_total = round(units*rate + adj, 2)
        invoice_total += line_total
        payload = {
          "INVOICE_DATE": invoice_date,
          "INVOICE_NUMBER": invoice_number,
          "CLIENT_ID": client_id,
          "LAW_FIRM_MATTER_ID": law_firm_matter_id,
          "INVOICE_TOTAL": "",  # set later once we know the total
          "BILLING_START_DATE": billing_start_f,
          "BILLING_END_DATE": billing_end_f,
          "INVOICE_DESCRIPTION": (invoice_desc or "").replace("|"," "),
          "LINE_ITEM_NUMBER": line_no,
          "EXP/FEE/INV_ADJ_TYPE": "F",
          "LINE_ITEM_NUMBER_OF_UNITS": f"{units:.2f}",
          "LINE_ITEM_ADJUSTMENT_AMOUNT": f"{adj:.2f}",
          "LINE_ITEM_TOTAL": f"{line_total:.2f}",
          "LINE_ITEM_DATE": _fmt_date(line_date),
          "LINE_ITEM_TASK_CODE": task_code or "",
          "LINE_ITEM_EXPENSE_CODE": "",
          "LINE_ITEM_ACTIVITY_CODE": activity_code or "",
          "TIMEKEEPER_ID": tk_id,
          "LINE_ITEM_DESCRIPTION": (description or "").replace("|", " "),
          "LAW_FIRM_ID": law_firm_id,
          "LINE_ITEM_UNIT_COST": f"{rate:.2f}",
          "TIMEKEEPER_NAME": tk_name,
          "TIMEKEEPER_CLASSIFICATION": tk_class,
          "CLIENT_MATTER_ID": cmid
        }
        out_rows.append(payload)
        line_no += 1

    # Now set invoice total for each row
    for r in out_rows:
        r["INVOICE_TOTAL"] = f"{invoice_total:.2f}"

    # Validate
    errs = validate_ledes_rows(out_rows)
    if errs:
        raise ValueError("LEDES validation failed:\n" + "\n".join(errs))

    # Write pipe-delimited file
    os.makedirs("exports", exist_ok=True)
    file_path = os.path.abspath(os.path.join("exports", f"{client_matter_id}_{invoice_number}_LEDES1998B.txt"))
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter="|")
        writer.writerow(LEDES_1998B_FIELDS)
        for r in out_rows:
            writer.writerow([r.get(k, "") for k in LEDES_1998B_FIELDS])

    return file_path

__all__ = ["export_ledes1998b"]
