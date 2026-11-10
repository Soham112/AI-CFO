"""Monthly buying plan: a CORE list bought every month whatever the market does
(rupee/dollar-cost averaging) and an OPPORTUNISTIC list bought only on dips.

The CFO's job on the core list is not timing, it is checking the reason to own
each item still holds. On the opportunistic list it is telling you when a buy
level is hit.
"""
from __future__ import annotations

import datetime as dt

from .fundamentals import analyse_stock


def asset_class(item: dict) -> str:
    if item.get("asset_class"):
        return item["asset_class"]
    sym = str(item.get("symbol", ""))
    if item.get("type") == "mf":
        cat = str(item.get("category", "")).lower()
        return ("india_fixed_income" if "debt" in cat or "liquid" in cat else "gold" if "gold" in cat
                else "us_equity" if "international" in cat else "india_equity")
    return "india_equity" if sym.endswith((".NS", ".BO")) else "us_equity"


def _logged_this_month(ledger: list[dict], symbol: str, month: str) -> float:
    return sum(float(r.get("amount", 0)) for r in ledger
               if str(r.get("symbol")) == str(symbol) and str(r.get("date", "")).startswith(month))


def review(profile: dict, snap: dict, ledger: list[dict], today: dt.date | None = None) -> dict:
    plan = profile.get("plan") or {}
    today = today or dt.date.today()
    month = today.strftime("%Y-%m")
    mk, fu, mfs = snap.get("markets", {}), snap.get("fundamentals", {}), snap.get("mutual_funds", {})
    core_out, opp_out, warnings = [], [], []

    core = plan.get("core") or []
    total_core = sum(i.get("monthly", 0) for i in core) or 0
    single = sum(i.get("monthly", 0) for i in core if i.get("type") == "stock")
    if total_core and single / total_core > 0.4:
        warnings.append("More than 40% of the monthly core is single stocks. Keep the core mostly in index / "
                        "diversified funds; single stocks belong in the opportunistic list.")

    for it in core:
        sym, amt = str(it.get("symbol")), it.get("monthly", 0)
        verdict, why = "CONTINUE", "Buy every month regardless of price; that is what averages your cost down."
        if it.get("type") == "stock" and sym in fu and sym in mk:
            a = analyse_stock(sym, fu[sym], mk[sym], 0.065 if sym.endswith(".NS") else snap.get("macro", {}).get("us10y"))
            if a["quality"] < 4:
                verdict, why = "REVIEW", (f"Business quality has dropped to {a['quality']:.0f}/10. Pause new buys "
                                          "until you re-check why you own it.")
            elif a["dip"] >= 1:
                verdict, why = "CONTINUE + TOP-UP", (f"{(mk[sym].get('off_high_52w') or 0) * 100:.0f}% below its high with "
                                                     "quality intact: add an extra instalment from the reserve if you have it.")
            elif a["value"] <= -2:
                verdict, why = "CONTINUE (no top-ups)", "Looks expensive; keep the SIP but don't add extra."
        elif it.get("type") == "mf" and sym in mfs:
            m = mfs[sym]
            if m.get("off_high_52w") is not None and m["off_high_52w"] < -0.10:
                verdict, why = "CONTINUE + TOP-UP", f"NAV is {m['off_high_52w'] * 100:.0f}% off its high: SIPs buy more units now."
        done = _logged_this_month(ledger, sym, month)
        core_out.append({"symbol": sym, "name": it.get("name", sym), "monthly": amt, "verdict": verdict, "why": why,
                         "done_this_month": done, "pending": max(0, amt - done) if verdict != "REVIEW" else 0,
                         "asset_class": asset_class(it)})

    for it in plan.get("opportunistic") or []:
        sym = str(it.get("symbol"))
        m = mk.get(sym) or mfs.get(sym) or {}
        dd, trig = m.get("off_high_52w"), it.get("buy_below_pct", -10) / 100
        budget, tranches = it.get("budget", 0), it.get("tranches", 3)
        spent = sum(float(r.get("amount", 0)) for r in ledger if str(r.get("symbol")) == sym
                    and str(r.get("date", "")) >= str(it.get("since", "2000-01-01")))
        left = max(0, budget - spent)
        q_ok = True
        if sym in fu and sym in mk:
            q_ok = analyse_stock(sym, fu[sym], mk[sym], 0.065)["quality"] >= 5
        if dd is None:
            status, msg = "NO DATA", "No price yet."
        elif not q_ok:
            status, msg = "SKIP", "Cheap, but quality is weak; a falling price alone is not a reason to buy."
        elif left <= 0:
            status, msg = "DONE", "Budget fully used."
        elif dd <= trig:
            status, msg = "BUY", (f"{abs(dd) * 100:.0f}% below its 52-week high (trigger {trig * 100:.0f}%). Buy one tranche "
                                  f"of {left / max(1, tranches):,.0f}; next tranche if it falls another 5-8%.")
        else:
            status, msg = "WAIT", f"Now {abs(dd) * 100:.0f}% below the high; buys start at {abs(trig) * 100:.0f}% below."
        opp_out.append({"symbol": sym, "name": it.get("name", sym), "status": status, "message": msg, "off_high": dd, "trigger": trig,
                        "budget_left": left, "asset_class": asset_class(it)})

    pending = [c for c in core_out if c["pending"] > 0]
    return {"month": month, "core": core_out, "opportunistic": opp_out, "warnings": warnings,
            "pending": pending, "reserve_monthly": plan.get("opportunistic_monthly_reserve", 0)}
