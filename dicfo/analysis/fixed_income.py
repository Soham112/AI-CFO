"""Compare guaranteed instruments on an after-tax, after-inflation, after-FX basis
in the currency you will actually spend."""
from __future__ import annotations


def _tax_rate(inst: dict, profile: dict) -> float:
    t = profile.get("tax", {})
    us_ord = t.get("us_federal_marginal", 0) + t.get("us_state_marginal", 0)
    us_tax_resident = profile.get("tax_residency") == "US"
    us = {"ordinary": us_ord, "federal_only": t.get("us_federal_marginal", 0),
          "deferred_or_free": 0.0}.get(inst.get("us_tax"), us_ord) if us_tax_resident else 0.0
    if inst.get("currency") == "INR":
        india = {"exempt": 0.0, "exempt_mostly": 0.0, "slab": t.get("india_slab", 0.3)}.get(inst.get("india_tax"), t.get("india_slab", 0.3))
        # Foreign tax credit: you pay roughly the higher of the two, not both.
        return max(us, india)
    return us


def eligible(inst: dict, profile: dict) -> bool:
    who = set(inst.get("who", []))
    me = set()
    if profile.get("residency") == "US":
        me.add("us_resident")
        if profile.get("citizenship") == "India":
            me.add("nri")
    if profile.get("residency") == "India":
        me.add("india_resident")
        if profile.get("employment") == "salaried":
            me.add("india_employee")
    if inst.get("min_age") and (profile.get("age") or 0) < inst["min_age"]:
        return False
    return bool(who & me)


def compare(fi_cfg: dict, profile: dict, macro: dict) -> list[dict]:
    a = fi_cfg["assumptions"]
    spend = profile.get("spend_currency", "USD")
    us_inf = macro.get("us_cpi_yoy", 0.03)
    in_inf = macro.get("india_cpi_yoy", 0.05)
    fx = a.get("inr_usd_depreciation", 0.03)
    rows = []
    for key, inst in fi_cfg["instruments"].items():
        r = inst.get("rate")
        if r is None and key == "us_tbill":
            r = macro.get("us3m") or inst.get("fallback_rate")
        if r is None and key == "us_hysa":
            ff = macro.get("fed_funds")
            r = (ff - 0.003) if ff else inst.get("fallback_rate")
        if r is None:
            continue
        if not eligible(inst, profile) and inst["currency"] != profile.get("base_currency", "USD"):
            continue   # e.g. US T-bills for an India resident: not relevant
        tax = _tax_rate(inst, profile)
        after_tax = r * (1 - tax)
        if inst["currency"] == "INR" and spend == "USD":
            in_spend_ccy = (1 + after_tax) / (1 + fx) - 1
            real = in_spend_ccy - us_inf
        elif inst["currency"] == "INR":
            in_spend_ccy, real = after_tax, after_tax - in_inf
        else:
            in_spend_ccy, real = after_tax, after_tax - (us_inf if spend == "USD" else in_inf)
        rows.append({
            "key": key, "name": inst["name"], "nominal": r, "tax_rate": tax,
            "after_tax": after_tax, "in_spend_currency": in_spend_ccy, "real": real,
            "eligible_new_money": eligible(inst, profile), "liquidity": inst.get("liquidity"),
            "note": inst.get("note", ""), "as_of": inst.get("as_of", "live"),
        })
    rows.sort(key=lambda x: x["real"], reverse=True)
    return rows
