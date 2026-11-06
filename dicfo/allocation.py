"""Turn signals into a target allocation and a staged buying plan."""
from __future__ import annotations

from .analysis.macro import ASSETS  # noqa: F401
from .analysis.technicals import dip_score

STRATEGIC = {
    "conservative":          {"us_equity": 30, "india_equity": 8, "emerging_equity": 2, "gold": 10, "silver": 0, "crypto": 0, "india_fixed_income": 10, "us_cash_bonds": 40},
    "moderate":              {"us_equity": 40, "india_equity": 12, "emerging_equity": 3, "gold": 10, "silver": 2, "crypto": 0, "india_fixed_income": 8, "us_cash_bonds": 25},
    "moderately_aggressive": {"us_equity": 47, "india_equity": 15, "emerging_equity": 5, "gold": 8, "silver": 2, "crypto": 2, "india_fixed_income": 4, "us_cash_bonds": 17},
    "aggressive":            {"us_equity": 52, "india_equity": 20, "emerging_equity": 7, "gold": 6, "silver": 2, "crypto": 5, "india_fixed_income": 0, "us_cash_bonds": 8},
}

# Home bias for someone who lives, earns and spends in INR. "us_cash_bonds" = liquid funds here.
STRATEGIC_INDIA = {
    "conservative":          {"us_equity": 5,  "india_equity": 30, "emerging_equity": 0, "gold": 12, "silver": 0, "crypto": 0, "india_fixed_income": 48, "us_cash_bonds": 5},
    "moderate":              {"us_equity": 10, "india_equity": 45, "emerging_equity": 0, "gold": 10, "silver": 2, "crypto": 0, "india_fixed_income": 28, "us_cash_bonds": 5},
    "moderately_aggressive": {"us_equity": 12, "india_equity": 55, "emerging_equity": 0, "gold": 8,  "silver": 2, "crypto": 1, "india_fixed_income": 17, "us_cash_bonds": 5},
    "aggressive":            {"us_equity": 15, "india_equity": 62, "emerging_equity": 0, "gold": 7,  "silver": 3, "crypto": 3, "india_fixed_income": 7,  "us_cash_bonds": 3},
}

# Structural (3y+) view per asset class; the tactical model only nudges around this.
LONG_VIEW = {"us_equity": "bullish", "india_equity": "bullish", "emerging_equity": "neutral",
             "gold": "neutral (diversifier)", "silver": "neutral (volatile)", "crypto": "speculative",
             "india_fixed_income": "capital preservation", "us_cash_bonds": "capital preservation"}

VEHICLES_US_RESIDENT = {
    "us_equity": "VOO / VTI (or the S&P 500 fund in your 401k); quality single names on dips",
    "india_equity": "US-listed INDA / FLIN (large+mid), SMIN (small); or direct NSE shares via NRE-PIS. Not Indian MFs (PFIC).",
    "emerging_equity": "VWO / IEMG (ex-India tilt: EMXC)",
    "gold": "IAU / GLDM, ideally inside an IRA (collectibles tax in taxable)",
    "silver": "SIVR / SLV, small and only on dips (very volatile)",
    "crypto": "Spot Bitcoin ETF (IBIT / FBTC) in an IRA, max a few %",
    "india_fixed_income": "Keep existing EPF/PPF to maturity; NRE FD only if you'll spend in INR",
    "us_cash_bonds": "T-bills / money market (state-tax free), I-bonds, short Treasury ETF (SGOV)",
}
VEHICLES_INDIA_RESIDENT = {
    "us_equity": "Nasdaq/S&P 500 FoFs or LRS to a US broker (VOO)",
    "india_equity": "Nifty 50 / Next 50 index funds, flexi-cap MF SIPs, quality direct stocks",
    "emerging_equity": "Usually skip; India already is the EM exposure",
    "gold": "Gold ETFs / gold MFs (new SGB issues stopped)",
    "silver": "Silver ETFs",
    "crypto": "Small, taxed 30% + TDS",
    "india_fixed_income": "EPF/VPF, PPF, FDs, short-duration debt funds",
    "us_cash_bonds": "Liquid / overnight funds for the emergency fund",
}


def score_assets(snap: dict, proxies: dict, data_drv: dict, news_hits: dict) -> dict:
    markets = snap.get("markets", {})
    overrides = snap.get("drivers", {})          # set by a skill after reading the news
    out = {}
    for a in ASSETS:
        m = markets.get(proxies.get(a), {})
        dip = dip_score(m) if m else 0.0
        drv = dict(data_drv.get(a, {}))
        # A skill's judgement on an asset replaces the cruder keyword tags for it,
        # so the same headline is not counted twice.
        for name, h in news_hits.items():
            if a in h["impact"] and a not in overrides:
                drv[f"news:{name}"] = h["impact"][a]
        for name, val in overrides.get(a, {}).items():
            drv[f"judgement:{name}"] = val["score"] if isinstance(val, dict) else val
        macro_sum = max(-2.0, min(2.0, sum(drv.values())))
        out[a] = {"dip": dip, "drivers": drv, "macro": macro_sum,
                  "score": round(max(-2.0, min(2.0, 0.6 * dip + 0.7 * macro_sum)), 2),
                  "proxy": proxies.get(a), "proxy_metrics": m}
    return out


def target(profile: dict, scores: dict) -> dict:
    table = STRATEGIC_INDIA if profile.get("residency") == "India" else STRATEGIC
    base = dict(table[profile.get("risk_tolerance", "moderate")])
    age = profile.get("age") or 0
    if age >= 50:   # glide path: shift ~1pt per year over 50 from equity to fixed income, max 15
        shift = min(15, age - 50)
        base["india_equity" if profile.get("residency") == "India" else "us_equity"] -= shift
        base["india_fixed_income" if profile.get("residency") == "India" else "us_cash_bonds"] += shift
    if profile.get("plans_to_return_to_india") == "yes":
        base["us_equity"] -= 12
        base["india_equity"] += 8
        base["india_fixed_income"] += 4
    tgt = {}
    for a, w in base.items():
        if w == 0:
            tgt[a] = 0.0
            continue
        band = max(3, w * 0.4)
        tilt = scores[a]["score"] * 2.5
        tgt[a] = max(0.0, min(w + band, max(w - band, w + tilt)))
    total = sum(tgt.values())
    tgt = {a: round(v * 100 / total, 1) for a, v in tgt.items()}
    return {"strategic": base, "tactical": tgt}


def dip_ladder(m: dict) -> list[dict]:
    """Staged entry plan for new lump-sum money into a falling market."""
    hi, px = m.get("high_52w"), m.get("price")
    if not (hi and px):
        return []
    steps = [(-0.05, 20), (-0.10, 25), (-0.15, 25), (-0.20, 30)]
    plan = []
    for dd, pct in steps:
        level = hi * (1 + dd)
        plan.append({"trigger_drawdown": dd, "index_level": round(level, 1), "deploy_pct": pct,
                     "status": "triggered" if px <= level else "pending"})
    return plan


