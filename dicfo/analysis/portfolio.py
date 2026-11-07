"""Review a person's actual portfolio and challenge it, like a CFO would."""
from __future__ import annotations

from collections import Counter

THEMATIC = ("sectoral", "thematic", "sector", "psu", "infra", "manufacturing", "defence", "pharma",
            "banking", "technology", "consumption", "esg", "energy")


def current_mix(profile: dict, ledger: list[dict] | None = None) -> dict:
    h = profile.get("holdings") or {}
    mix = Counter()
    for mf in h.get("mutual_funds", []) or []:
        cat = str(mf.get("category", "")).lower()
        if any(k in cat for k in ("debt", "liquid", "gilt", "money_market", "short_duration")):
            mix["india_fixed_income"] += mf.get("value", 0)
        elif "gold" in cat:
            mix["gold"] += mf.get("value", 0)
        elif any(k in cat for k in ("international", "us_", "nasdaq", "s&p")):
            mix["us_equity"] += mf.get("value", 0)
        else:
            mix["india_equity"] += mf.get("value", 0)
    for k, v in (h.get("other") or {}).items():
        mix[k] += v or 0
    if ledger:   # purchases recorded after the profile was written
        from ..ledger import totals_by_class
        for k, v in totals_by_class(ledger).items():
            mix[k] += v
    return dict(mix)


def review(profile: dict, snap: dict, tactical: dict, ledger: list[dict] | None = None,
           benchmark_code: str = "120716") -> dict:
    h = profile.get("holdings") or {}
    funds = h.get("mutual_funds", []) or []
    mf_data = snap.get("mutual_funds", {})
    issues = []

    def add(sev, title, detail):
        issues.append({"severity": sev, "title": title, "detail": detail})

    # 1. Can you afford to invest right now?
    have, need = profile.get("emergency_fund_have_months"), profile.get("emergency_fund_months", 6)
    if profile.get("monthly_income") == 0 or profile.get("employment") == "job_searching":
        add("high", "No income right now: protect your runway first",
            "Keep SIPs only if they are paid from savings beyond 6-12 months of living costs. If not, pause or "
            "cut them (a pause is free and reversible) rather than redeem units in a falling market.")
    if have is not None and have < need:
        add("high", f"Emergency fund is {have} months, target {need}",
            "Fill this in a savings account / liquid fund before adding risk.")

    # 2. Fund hygiene
    eq = [f for f in funds if "debt" not in str(f.get("category", "")).lower()]
    if len(eq) > 5:
        add("medium", f"{len(eq)} equity funds is too many",
            "Beyond 4-5 funds the holdings overlap and you end up with an expensive index fund. "
            "Consolidate into 1 index + 1 flexi-cap + optional mid/small-cap.")
    cats = Counter(str(f.get("category")) for f in eq)
    for c, n in cats.items():
        if n > 1 and c != "None":
            add("medium", f"{n} funds in the same category ({c})", "They hold mostly the same stocks; keep the best one.")
    for f in funds:
        if str(f.get("plan", "")).lower() == "regular" or "regular" in str(f.get("name", "")).lower():
            add("medium", f"Regular plan: {f.get('name')}",
                "Regular plans pay ~0.5-1.5% a year in commission. The Direct plan of the same fund is identical "
                "and cheaper. Switching is a sale for tax, so switch new SIPs now and move old units in "
                "tranches using the Rs 1.25 lakh yearly LTCG exemption.")
        if any(k in str(f.get("category", "")).lower() or k in str(f.get("name", "")).lower() for k in THEMATIC):
            add("low", f"Thematic/sector fund: {f.get('name')}",
                "Fine as a small satellite (<10% of equity). Sector funds rarely beat the index over 10 years.")

    # 3. Performance vs a plain Nifty 50 index fund
    bench = mf_data.get(benchmark_code, {})
    for f in funds:
        d = mf_data.get(str(f.get("scheme_code")), {})
        for key, label in (("ret_3y_cagr", "3y"), ("ret_1y", "1y")):
            if d.get(key) is not None and bench.get(key) is not None:
                gap = d[key] - bench[key]
                if label == "3y" and gap < -0.02:
                    add("medium", f"{f.get('name')} trails the Nifty 50 index by {gap * -100:.1f}%/yr over 3 years",
                        "Give an active fund 3-5 years; if it still lags, move the SIP to an index fund.")
                break

    # 4. US tax residents holding Indian MFs
    if profile.get("tax_residency") == "US" and funds:
        add("high", "Indian MFs are PFICs for US tax residents",
            "See the tax flags. Do not add new money until you've confirmed your tax status.")

    # 5. Allocation gaps
    mix = current_mix(profile, ledger)
    total = sum(mix.values())
    gaps = {}
    if total:
        for a, w in tactical.items():
            cur = mix.get(a, 0) / total * 100
            gaps[a] = {"current_pct": round(cur, 1), "target_pct": w, "gap_value": round((w - cur) / 100 * total)}
            if abs(w - cur) > 7:
                how = ("EPF/PPF are locked in, so don't break them: steer new money elsewhere and let maturing FDs "
                       "fund the other gaps." if a == "india_fixed_income" and w < cur else
                       "Rebalance with new money first; sell only if the gap is large (and mind capital-gains tax).")
                add("low", f"{a.replace('_', ' ').capitalize()} is {cur:.0f}% vs target {w:.0f}%", how)
    sip_total = sum(f.get("sip_monthly", 0) or 0 for f in funds)
    inc = profile.get("monthly_income") or 0
    if inc and sip_total / inc < 0.15 and profile.get("emergency_fund_have_months", 0) >= 6:
        add("low", f"SIPs are {sip_total / inc:.0%} of income",
            "With the emergency fund in place, 20-30% of income invested is a healthy target.")
    return {"current_mix": mix, "total_value": total, "gaps": gaps, "sip_total": sip_total, "issues": issues}
