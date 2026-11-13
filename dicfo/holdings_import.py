"""Read a broker / fund-app holdings download (CSV or Excel) and keep only what DICFO needs.

Works by finding the header row by its words, so Zerodha, Groww, Upstox, Angel One, Kuvera etc. all work
without a reader per app. Kept per row: name, symbol, quantity, average price (shares) or units, invested and
current value (funds). Everything else in the file (client ID, folio, ISIN, PAN, ...) is dropped and never stored.
"""
from __future__ import annotations

import csv
import io
import re

MAX_BYTES = 2_000_000

NAME = ("symbol", "instrument", "stock name", "stock", "scrip", "company", "security", "scheme name",
        "scheme", "fund name", "fund", "trading symbol", "tradingsymbol", "name")
QTY = ("quantity available", "qty.", "qty", "quantity", "units", "balance units", "net qty", "shares")
AVG = ("average price", "avg. cost", "avg cost", "average buy price", "avg price", "avg. price", "buy avg",
       "average cost", "avg buy price")
INVESTED = ("invested value", "invested amount", "invested", "buy value", "cost value", "investment", "amount invested")
CURRENT = ("current value", "cur. val", "cur val", "closing value", "market value", "present value", "value")
FUND_HINT = ("scheme", "fund", "units", "folio", "nav", "amc")


def _num(x) -> float | None:
    if x is None:
        return None
    s = str(x).replace(",", "").replace("₹", "").replace("Rs.", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _rows(data: bytes, filename: str) -> list[list]:
    if filename.lower().endswith((".xlsx", ".xlsm")):
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        out = []
        for ws in wb.worksheets:            # brokers put holdings on the first or a named sheet
            out += [list(r) for r in ws.iter_rows(values_only=True)] + [[]]
        return out
    if filename.lower().endswith(".xls"):
        raise ValueError("Please download it as .xlsx or .csv (the old .xls format isn't supported).")
    text = data.decode("utf-8-sig", errors="replace")
    return [r for r in csv.reader(io.StringIO(text))]


def _find(header: list[str], words) -> int | None:
    for w in words:                          # earlier words are preferred
        for i, h in enumerate(header):
            if h == w or (len(w) > 4 and h.startswith(w)):
                return i
    return None


def parse(data: bytes, filename: str) -> dict:
    """-> {'stocks': [...], 'funds': [...], 'skipped': [names]}. Raises ValueError with a plain message."""
    if len(data) > MAX_BYTES:
        raise ValueError("That file is too big. Please send only the holdings download.")
    if data[:4] == b"%PDF":
        raise ValueError("That's a PDF. Please download holdings as Excel (.xlsx) or CSV instead.")
    try:
        rows = _rows(data, filename)
    except ValueError:
        raise
    except Exception:
        raise ValueError("I couldn't open that file. If it has a password, please download it again without one.")
    stocks, funds, skipped = [], [], []
    i = 0
    while i < len(rows):
        header = [re.sub(r"\s+", " ", str(c or "")).strip().lower() for c in rows[i]]
        n, q = _find(header, NAME), _find(header, QTY)
        if n is None or q is None or n == q:
            i += 1
            continue
        a, inv, cur = _find(header, AVG), _find(header, INVESTED), _find(header, CURRENT)
        is_fund = any(any(h.startswith(w) for w in FUND_HINT) for h in header if h)
        i += 1
        while i < len(rows) and any(c not in (None, "") for c in rows[i]):
            r = rows[i] + [None] * (len(header) - len(rows[i]))
            name = str(r[n] or "").strip()
            qty = _num(r[q])
            i += 1
            if not name or qty is None or qty <= 0 or name.lower() in ("total", "grand total"):
                continue
            row = {"name": name, "qty": qty,
                   "avg": _num(r[a]) if a is not None else None,
                   "invested": _num(r[inv]) if inv is not None else None,
                   "current": _num(r[cur]) if cur is not None else None}
            if row["invested"] is None and row["avg"]:
                row["invested"] = row["avg"] * qty
            (funds if is_fund else stocks).append(row)
    if not stocks and not funds:
        raise ValueError("I couldn't find a holdings table in that file. Please send the 'Holdings' download "
                         "from your broker or fund app.")
    return {"stocks": stocks, "funds": funds, "skipped": skipped}


def to_profile_parts(parsed: dict, known: list[str], priced: set) -> dict:
    """Map names to NSE symbols. Broker names are real, so unmatched ones are kept by name with their file value."""
    from .names import to_symbol
    stocks, unmatched = [], []
    for r in parsed["stocks"]:
        sym, sure = to_symbol(r["name"], known)
        if sym and not sure and sym not in priced and not re.fullmatch(r"[A-Z0-9&-]{2,15}", r["name"].strip()):
            sym = None
        qty = int(r["qty"]) if float(r["qty"]).is_integer() else r["qty"]
        st = {"name": r["name"].title() if r["name"].isupper() and " " in r["name"] else r["name"],
              "symbol": sym, "shares": qty, "avg_price": round(r["avg"], 2) if r["avg"] else None}
        if not sym:
            st["value"] = r["current"]
            unmatched.append(r["name"])
        stocks.append(st)
    funds = [{"name": r["name"], "value": round(r["current"] or 0), "invested": round(r["invested"]) if r["invested"] else None,
              "units": r["qty"], "sip_monthly": 0, "plan": "regular" if "regular" in r["name"].lower() else "direct"}
             for r in parsed["funds"]]
    return {"stocks": stocks, "funds": funds, "unmatched": unmatched}
