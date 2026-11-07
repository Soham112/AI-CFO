"""Run the whole analysis on a snapshot for one person and return a JSON-able result.

This is the backend contract: any future web/mobile app calls `run()` (or reads
reports/*.json) and renders it.
"""
from __future__ import annotations

from . import DISCLAIMER, config
from .allocation import (LONG_VIEW, VEHICLES_INDIA_RESIDENT, VEHICLES_US_RESIDENT, dip_ladder,
                         score_assets, target)
from .analysis import fixed_income, horizons, macro as macro_mod, plan as plan_mod, portfolio, tax
from .analysis.fundamentals import analyse_stock


def run(snap: dict, profile: dict | None = None, ledger: list[dict] | None = None) -> dict:
    profile = profile or config.load_profile()
    uni = config.load("universe")
    fi_cfg = config.load("fixed_income")
    proxies = uni["asset_class_proxies"]
    mk, macro = snap.get("markets", {}), snap.get("macro", {})

    hits = macro_mod.tag_news(snap.get("news", []))
    drv = macro_mod.data_drivers(macro, mk, proxies)
    scores = score_assets(snap, proxies, drv, hits)
    alloc = target(profile, scores)
    views = horizons.asset_views(scores)
    for a in views:
        views[a]["long"] = LONG_VIEW[a]

    bond = macro.get("us10y")
    stocks = []
    for region, syms in uni["stocks"].items():
        for s in syms:
            f, m = snap.get("fundamentals", {}).get(s), mk.get(s)
            if f and m:
                r = analyse_stock(s, f, m, bond if region == "us" else macro.get("india10y", 0.065))
                r["region"] = region
                r["horizons"] = horizons.stock_views(r, m)
                stocks.append(r)
    stocks.sort(key=lambda r: r["composite"], reverse=True)

    monthly = profile.get("monthly_investable") or 0
    tilt = alloc["tactical"]
    monthly_split = {a: round(monthly * w / 100) for a, w in tilt.items() if w > 0}

    vehicles = VEHICLES_US_RESIDENT if profile.get("tax_residency") == "US" else VEHICLES_INDIA_RESIDENT
    return {
        "as_of": snap.get("as_of"),
        "person": profile.get("name"),
        "currency": profile.get("base_currency"),
        "data_source": snap.get("source"),
        "regime": macro_mod.regime(macro, mk, proxies),
        "macro": macro,
        "asset_scores": scores,
        "horizon_views": views,
        "allocation": alloc,
        "monthly_split": monthly_split,
        "portfolio_review": portfolio.review(profile, snap, tilt, ledger or []),
        "monthly_plan": plan_mod.review(profile, snap, ledger or []),
        "dip_plans": {"S&P 500": dip_ladder(mk.get(proxies["us_equity"], {})),
                      "Nifty 50": dip_ladder(mk.get(proxies["india_equity"], {}))},
        "vehicles": vehicles,
        "stocks": stocks,
        "mutual_funds": snap.get("mutual_funds", {}),
        "fixed_income": fixed_income.compare(fi_cfg, profile, macro),
        "tax_flags": tax.flags(profile),
        "news_signals": hits,
        "judgements": snap.get("drivers", {}),
        "notes": snap.get("notes", []),
        "data_errors": snap.get("errors", []),
        "disclaimer": DISCLAIMER,
    }
