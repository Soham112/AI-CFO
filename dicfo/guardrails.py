"""Hard safety rules. These run after the model and override it.

The model can be wrong; these rules make sure being wrong is survivable:
no leverage or derivatives, cash runway before risk, caps on any single bet,
and no buy signals on stale or suspicious data.
"""
from __future__ import annotations

import datetime as dt

RISK = {"conservative", "moderate", "moderately_aggressive", "aggressive"}
CAPS = {"crypto": 3.0, "silver": 5.0, "gold": 15.0}          # max % of portfolio
SINGLE_STOCK_MAX_PCT = 5.0                                     # of total portfolio
MAX_DATA_AGE_DAYS = 3
EQUITY = ("us_equity", "india_equity", "emerging_equity")
NEVER = ("Leverage, margin, loans to invest, F&O / options, short-selling, intraday trading and "
         "'guaranteed return' schemes are never recommended.")


def validate_profile(p: dict):
    errs = []
    age = p.get("age")
    if age is not None and not (18 <= age <= 100):
        errs.append(f"age {age} must be between 18 and 100")
    if p.get("risk_tolerance", "moderate") not in RISK:
        errs.append(f"risk_tolerance must be one of {sorted(RISK)}")
    for k in ("monthly_investable", "monthly_income"):
        v = p.get(k)
        if v is not None and (not isinstance(v, (int, float)) or v < 0):
            errs.append(f"{k} must be a number >= 0")
    h = p.get("horizon_years")
    if h is not None and not (0 <= h <= 60):
        errs.append("horizon_years must be 0-60")
    if errs:
        raise ValueError("Profile check failed: " + "; ".join(errs))


def _age_days(as_of) -> float | None:
    try:
        t = dt.datetime.fromisoformat(str(as_of).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=dt.timezone.utc)
        return (dt.datetime.now(dt.timezone.utc) - t).total_seconds() / 86400
    except ValueError:
        return None


def data_problems(snap: dict, max_age: float = MAX_DATA_AGE_DAYS) -> list[str]:
    out = []
    age = _age_days(snap.get("as_of"))
    if age is None or age > max_age:
        out.append(f"market data is {'of unknown age' if age is None else f'{age:.0f} days old'}")
    for sym, m in (snap.get("markets") or {}).items():
        c = m.get("chg_1d")
        if sym.startswith("^") and c is not None and abs(c) > 0.20:
            out.append(f"{sym} moved {c:+.0%} in a day, likely a data error")
        if m.get("price") is not None and m["price"] <= 0:
            out.append(f"{sym} has a non-positive price")
    return out


def apply(res: dict, profile: dict, snap: dict, max_age: float = MAX_DATA_AGE_DAYS) -> dict:
    notes = [NEVER]
    tac = res["allocation"]["tactical"]

    # 1. Caps on volatile assets
    for a, cap in CAPS.items():
        if tac.get(a, 0) > cap:
            notes.append(f"{a} capped at {cap:.0f}% (model wanted {tac[a]:.1f}%).")
            tac[a] = cap
    # 2. Equity ceiling by age and horizon
    age, hz = profile.get("age") or 30, profile.get("horizon_years") or 10
    eq_cap = 30.0 if hz < 3 else 50.0 if hz < 5 else max(40.0, 110.0 - age)
    eq = sum(tac.get(a, 0) for a in EQUITY)
    if eq > eq_cap:
        f = eq_cap / eq
        for a in EQUITY:
            tac[a] = round(tac.get(a, 0) * f, 1)
        notes.append(f"Equity limited to {eq_cap:.0f}% for age {age} / {hz}-year horizon.")
    # renormalise the remainder into safe assets
    safe = "india_fixed_income" if profile.get("residency") == "India" else "us_cash_bonds"
    tac[safe] = round(tac.get(safe, 0) + 100 - sum(tac.values()), 1)

    # 3. Runway before risk
    monthly = profile.get("monthly_investable") or 0
    no_income = profile.get("monthly_income") == 0 or profile.get("employment") == "job_searching"
    ef_have, ef_need = profile.get("emergency_fund_have_months"), profile.get("emergency_fund_months", 6)
    if no_income:
        res["monthly_split"] = {}
        notes.append("No income: no new risky investments are suggested until income resumes. "
                     "Existing SIPs only if paid from savings beyond 6-12 months of expenses.")
    elif ef_have is not None and ef_have < ef_need:
        res["monthly_split"] = {"us_cash_bonds": monthly}
        notes.append(f"Emergency fund is {ef_have} of {ef_need} months: all new money goes to a liquid "
                     "fund / savings until it's full.")
    else:
        res["monthly_split"] = {a: round(monthly * w / 100) for a, w in tac.items() if w > 0}

    # 4. Single-stock concentration
    total = (res.get("portfolio_review") or {}).get("total_value") or 0
    mp = res.get("monthly_plan") or {}
    if total:
        for o in mp.get("opportunistic", []):
            if o["budget_left"] > total * SINGLE_STOCK_MAX_PCT / 100:
                o["status"] = "CAPPED" if o["status"] == "BUY" else o["status"]
                o["message"] += (f" Budget exceeds {SINGLE_STOCK_MAX_PCT:.0f}% of the portfolio "
                                 f"({total * SINGLE_STOCK_MAX_PCT / 100:,.0f}); reduce it.")
    # 5. Stale or suspicious data: no buy signals
    probs = data_problems(snap, max_age)
    if probs:
        for o in mp.get("opportunistic", []):
            if o["status"] == "BUY":
                o["status"], o["message"] = "PAUSED", "Buy signal paused: data is not trustworthy today."
        for c in mp.get("core", []):
            if c["verdict"] == "CONTINUE + TOP-UP":
                c["verdict"], c["why"] = "CONTINUE", "Top-up paused until fresh data. Keep the regular SIP."
        notes.append("Data check failed (" + "; ".join(probs) + "). Buy signals and top-ups are paused; "
                     "regular SIPs continue.")
    res["guardrails"] = notes
    res["data_ok"] = not probs
    return res
