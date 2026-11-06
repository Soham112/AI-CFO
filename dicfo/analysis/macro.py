"""Macro regime and driver scoring.

Drivers are scored -2..+2 for each asset class from data rules. A skill can
override any driver in `snapshot.drivers` after reading the news, and that
judgement wins (it is recorded in the report so you can see why).
"""
from __future__ import annotations

ASSETS = ["us_equity", "india_equity", "emerging_equity", "gold", "silver", "crypto",
          "india_fixed_income", "us_cash_bonds"]

# Keyword -> (driver name, {asset: impact}). Used to tag headlines.
NEWS_RULES = [
    (("tariff", "trade war", "sanction"), "trade_policy",
     {"india_equity": -0.5, "emerging_equity": -0.5, "us_equity": -0.25, "gold": 0.25}),
    (("trade deal", "trade agreement", "tariff cut", "tariff relief"), "trade_deal",
     {"india_equity": 0.5, "emerging_equity": 0.25}),
    (("ai selloff", "ai bubble", "ai stocks slide", "ai capex", "anti-ai", "data center opposition"), "ai_derating",
     {"us_equity": -0.5}),
    (("rate hike", "hawkish", "hike odds"), "tightening",
     {"us_equity": -0.25, "india_equity": -0.25, "gold": -0.25, "us_cash_bonds": 0.25,
      "india_fixed_income": 0.25, "crypto": -0.5}),
    (("rate cut", "dovish", "easing"), "easing",
     {"us_equity": 0.25, "india_equity": 0.25, "gold": 0.25, "crypto": 0.25}),
    (("hormuz", "iran", "opec cut", "oil spike", "middle east war"), "oil_supply_shock",
     {"india_equity": -0.5, "gold": 0.5, "us_equity": -0.25}),
    (("fii buying", "foreign inflows", "fpi inflow"), "india_flows",
     {"india_equity": 0.5}),
    (("fii selling", "fpi outflow"), "india_flows_neg", {"india_equity": -0.5}),
    (("central bank gold", "gold buying"), "gold_demand", {"gold": 0.25}),
    (("recession", "layoffs surge"), "growth_scare",
     {"us_equity": -0.5, "india_equity": -0.25, "us_cash_bonds": 0.5, "gold": 0.25, "silver": -0.25}),
]


def tag_news(items: list[dict]) -> dict:
    hits: dict[str, dict] = {}
    for it in items:
        t = it.get("title", "").lower()
        for kws, name, impact in NEWS_RULES:
            if any(k in t for k in kws):
                h = hits.setdefault(name, {"count": 0, "impact": impact, "headlines": []})
                h["count"] += 1
                if len(h["headlines"]) < 3:
                    h["headlines"].append(it["title"])
    return hits


def data_drivers(macro: dict, markets: dict, proxies: dict) -> dict:
    """Rule-based driver scores per asset class from macro numbers."""
    d = {a: {} for a in ASSETS}
    us_cpi, ff, us10 = macro.get("us_cpi_yoy"), macro.get("fed_funds"), macro.get("us10y")
    in_cpi, repo = macro.get("india_cpi_yoy"), macro.get("india_repo")
    brent, vix = macro.get("brent"), macro.get("us_vix")
    real = macro.get("us_real10y")
    if real is None and us10 is not None and us_cpi is not None:
        real = us10 - us_cpi

    # Oil: India imports ~85% of its crude. High oil = wider deficit, weaker INR, inflation.
    if brent:
        if brent > 95:
            d["india_equity"]["oil_high"] = -0.75
            d["gold"]["oil_high"] = 0.25
        elif brent > 85:
            d["india_equity"]["oil_high"] = -0.25
        elif brent < 70:
            d["india_equity"]["oil_low"] = 0.5
    # Real rates: gold's main headwind; cash/bonds' tailwind.
    if real is not None:
        if real > 0.02:
            d["gold"]["real_rates_high"] = -0.5
            d["us_cash_bonds"]["real_rates_high"] = 0.5
        elif real < 0.005:
            d["gold"]["real_rates_low"] = 0.5
    if us_cpi is not None and us_cpi > 0.035:
        d["gold"]["inflation_hedge"] = 0.5
        d["silver"]["inflation_hedge"] = 0.25
        d["us_equity"]["sticky_inflation"] = -0.25
    if ff and us_cpi is not None and ff - us_cpi < 0.005:
        d["us_cash_bonds"]["cash_real_yield_thin"] = -0.25
    # Fear gauge: contrarian for long horizons, but tells us to stage entries.
    if vix:
        if vix > 30:
            d["us_equity"]["fear_extreme"] = 0.75
        elif vix > 22:
            d["us_equity"]["fear_elevated"] = 0.25
        elif vix < 14:
            d["us_equity"]["complacency"] = -0.25
    if in_cpi is not None and repo is not None:
        if in_cpi > 0.05:
            d["india_equity"]["india_inflation_high"] = -0.25
            d["india_fixed_income"]["fd_rates_rising"] = 0.25
        if repo - in_cpi < 0:
            d["india_fixed_income"]["negative_real_policy_rate"] = -0.5
    # Rupee: a weak INR makes INR assets cheaper for a USD earner, but erodes INR returns.
    inr1y = macro.get("usdinr_ret_1y")
    if inr1y is not None and inr1y > 0.05:
        d["india_equity"]["inr_cheap_for_usd_buyer"] = 0.25
        d["india_fixed_income"]["inr_depreciation"] = -0.5
    # Relative valuation proxy: India's premium vs US. Supplied via overrides when known.
    if macro.get("nifty_pe") and macro.get("sp500_pe"):
        prem = macro["nifty_pe"] / macro["sp500_pe"] - 1
        d["india_equity"]["valuation_vs_us"] = -0.5 if prem > 0.15 else 0.5 if prem < -0.05 else 0
    return d


def regime(macro: dict, markets: dict, proxies: dict) -> str:
    sp = markets.get(proxies.get("us_equity"), {})
    vix = macro.get("us_vix") or 0
    dd = sp.get("off_high_52w") or 0
    if dd < -0.20:
        return "bear_market"
    if dd < -0.10 or vix > 28:
        return "correction"
    if dd < -0.05 or vix > 20:
        return "pullback_volatile"
    return "calm_bull"
