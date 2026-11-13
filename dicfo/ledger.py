"""What was actually bought. One CSV per person: profiles/<name>-ledger.csv (git-ignored).

Columns: date, symbol, name, amount, units, price, asset_class, note
Open it in Excel if you prefer; the tool only appends rows.
"""
from __future__ import annotations

import csv
import datetime as dt
import io

from .config import PROFILES
from .security import read_private, write_private

MAX_SINGLE_ENTRY = 2_500_000   # anything above this needs explicit confirmation (typo guard)

FIELDS = ["date", "symbol", "name", "amount", "units", "price", "asset_class", "note"]


def path(profile_name: str):
    return PROFILES / f"{profile_name}-ledger.csv"


def load(profile_name: str) -> list[dict]:
    raw = read_private(path(profile_name))
    if not raw:
        return []
    return list(csv.DictReader(io.StringIO(raw.decode())))


def validate_row(r: dict, planned: float | None = None, confirm=input) -> bool:
    try:
        amt = float(r.get("amount", 0))
    except ValueError:
        print(f"  rejected: amount '{r.get('amount')}' is not a number")
        return False
    if amt <= 0:
        print("  rejected: amount must be positive (record sales as a note, not a negative buy)")
        return False
    d = str(r.get("date", ""))
    if d and d > dt.date.today().isoformat():
        print(f"  rejected: date {d} is in the future")
        return False
    big = amt > MAX_SINGLE_ENTRY or (planned and amt > 10 * planned)
    if big and confirm(f"  {amt:,.0f} is unusually large. Type YES to confirm: ").strip() != "YES":
        print("  not recorded")
        return False
    return True


def clear(profile_name: str) -> bool:
    """Delete the purchase record (used when the person redoes setup with their full, current holdings)."""
    from .security import shred
    gone = False
    for f in (path(profile_name), path(profile_name).with_name(path(profile_name).name + ".enc")):
        if f.exists():
            shred(f)
            gone = True
    return gone


def add(profile_name: str, rows: list[dict]):
    from .security import assert_clean
    rows = [dict(r) for r in rows]
    for r in rows:
        r.setdefault("date", dt.date.today().isoformat())
    assert_clean(rows, "this ledger entry")
    existing = load(profile_name)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS)
    w.writeheader()
    for r in existing + rows:
        w.writerow({k: r.get(k, "") for k in FIELDS})
    write_private(path(profile_name), buf.getvalue().encode())


def totals_by_class(rows: list[dict]) -> dict:
    out: dict[str, float] = {}
    for r in rows:
        if r.get("note", "").startswith("in-holdings"):
            continue   # already counted in the profile's holdings
        out[r.get("asset_class") or "india_equity"] = out.get(r.get("asset_class") or "india_equity", 0) + float(r["amount"] or 0)
    return out


def checkin(profile_name: str, pending: list[dict]):
    """Ask 'did you invest?' for each pending core item and record the answers."""
    if not pending:
        print("Nothing pending this month. All core investments are recorded.")
        return
    rows = []
    for c in pending:
        ans = input(f"Did you invest {c['pending']:,.0f} in {c['name']} this month? [y / n / other amount]: ").strip().lower()
        if ans in ("y", "yes"):
            amt = c["pending"]
        elif ans.replace(".", "", 1).isdigit():
            amt = float(ans)
        else:
            continue
        if not validate_row({"amount": amt}, c["monthly"]):
            continue
        rows.append({"symbol": c["symbol"], "name": c["name"], "amount": amt, "asset_class": c["asset_class"],
                     "note": "core"})
    extra = input("Anything else you bought (format: SYMBOL AMOUNT, blank to finish)? ").strip()
    while extra:
        try:
            sym, amt = extra.rsplit(" ", 1)
            from .analysis.plan import asset_class
            if validate_row({"amount": amt}):
                rows.append({"symbol": sym, "name": sym, "amount": float(amt),
                             "asset_class": asset_class({"symbol": sym}), "note": "extra"})
        except ValueError:
            print("  format: SYMBOL AMOUNT, e.g. RELIANCE.NS 20000")
        extra = input("More (blank to finish)? ").strip()
    add(profile_name, rows)
    print(f"Recorded {len(rows)} entr{'y' if len(rows) == 1 else 'ies'} in {path(profile_name)}")
