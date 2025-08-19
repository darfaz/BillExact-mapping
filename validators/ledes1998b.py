# validators/ledes1998b.py

LEDES_1998B_FIELDS = [
  "INVOICE_DATE","INVOICE_NUMBER","CLIENT_ID","LAW_FIRM_MATTER_ID","INVOICE_TOTAL",
  "BILLING_START_DATE","BILLING_END_DATE","INVOICE_DESCRIPTION","LINE_ITEM_NUMBER",
  "EXP/FEE/INV_ADJ_TYPE","LINE_ITEM_NUMBER_OF_UNITS","LINE_ITEM_ADJUSTMENT_AMOUNT",
  "LINE_ITEM_TOTAL","LINE_ITEM_DATE","LINE_ITEM_TASK_CODE","LINE_ITEM_EXPENSE_CODE",
  "LINE_ITEM_ACTIVITY_CODE","TIMEKEEPER_ID","LINE_ITEM_DESCRIPTION","LAW_FIRM_ID",
  "LINE_ITEM_UNIT_COST","TIMEKEEPER_NAME","TIMEKEEPER_CLASSIFICATION","CLIENT_MATTER_ID"
]

def validate_ledes_rows(rows):
    errs = []
    for i, r in enumerate(rows, start=1):
        def must(k, cond, msg):
            if not cond: errs.append(f"Line {i}: {k} {msg}")
        try_float = lambda v: float(v) if str(v).strip() != "" else 0.0
        must("TIMEKEEPER_ID", bool(r.get("TIMEKEEPER_ID")), "is required")
        must("LINE_ITEM_NUMBER_OF_UNITS", try_float(r.get("LINE_ITEM_NUMBER_OF_UNITS", 0))>0, "> 0")
        must("LINE_ITEM_UNIT_COST", try_float(r.get("LINE_ITEM_UNIT_COST", 0))>0, "> 0")
        calc_total = try_float(r.get("LINE_ITEM_NUMBER_OF_UNITS",0))*try_float(r.get("LINE_ITEM_UNIT_COST",0)) + try_float(r.get("LINE_ITEM_ADJUSTMENT_AMOUNT",0))
        must("LINE_ITEM_TOTAL", abs(try_float(r.get("LINE_ITEM_TOTAL",0)) - calc_total) < 0.01, "must equal units*rate+adj")
        # Required header fields
        for k in ["INVOICE_DATE","INVOICE_NUMBER","CLIENT_ID","LAW_FIRM_MATTER_ID","LAW_FIRM_ID","CLIENT_MATTER_ID"]:
            must(k, bool(str(r.get(k,"")).strip()), "is required")
    return errs
