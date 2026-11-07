"""What was actually bought. One CSV per person: profiles/<name>-ledger.csv (git-ignored).

Columns: date, symbol, name, amount, units, price, asset_class, note
Open it in Excel if you prefer; the tool only appends rows.
"""
from __future__ import annotations

import csv
import datetime as dt

from .config import PROFILES

FIELDS = ["date", "symbol", "name", "amount", "units", "price", "asset_class", "note"]


def path(profile_name: str):
    return PROFILES / f"{profile_name}-ledger.csv"


def load(profile_name: str) -> list[dict]:
    p = path(profile_name)
    if not p.exists():
        return []
    with open(p, newline="") as f:
        return list(csv.DictReader(f))


def add(profile_name: str, rows: list[dict]):
    p = path(profile_name)
    new = not p.exists()
    with open(p, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for r in rows:
            r.setdefault("date", dt.date.today().isoformat())
            w.writerow({k: r.get(k, "") for k in FIELDS})


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
        rows.append({"symbol": c["symbol"], "name": c["name"], "amount": amt, "asset_class": c["asset_class"],
                     "note": "core"})
    extra = input("Anything else you bought (format: SYMBOL AMOUNT, blank to finish)? ").strip()
    while extra:
        try:
            sym, amt = extra.rsplit(" ", 1)
            from .analysis.plan import asset_class
            rows.append({"symbol": sym, "name": sym, "amount": float(amt), "asset_class": asset_class({"symbol": sym}),
                         "note": "extra"})
        except ValueError:
            print("  format: SYMBOL AMOUNT, e.g. RELIANCE.NS 20000")
        extra = input("More (blank to finish)? ").strip()
    add(profile_name, rows)
    print(f"Recorded {len(rows)} entr{'y' if len(rows) == 1 else 'ies'} in {path(profile_name)}")
