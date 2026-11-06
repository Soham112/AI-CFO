"""Interactive set-up for a new person (e.g. Dad). Writes profiles/<name>.yaml."""
from __future__ import annotations

import yaml

from .config import PROFILES

CATEGORIES = ["index_largecap", "largecap", "flexi_cap", "large_mid", "midcap", "smallcap", "elss",
              "hybrid", "sectoral_thematic", "international", "gold", "debt", "liquid"]


def ask(q, default=None, cast=str):
    raw = input(f"{q}{f' [{default}]' if default is not None else ''}: ").strip()
    if not raw:
        return default
    try:
        return cast(raw)
    except ValueError:
        print("  (could not read that, keeping default)")
        return default


def run(name: str):
    print("DICFO set-up. Press Enter to accept the [default]. Amounts in your home currency.\n")
    p = {"name": ask("Name", name)}
    p["age"] = ask("Age", 55, int)
    p["residency"] = ask("Country you live in (India/US)", "India")
    p["tax_residency"] = ask("Country you pay tax in", p["residency"])
    p["citizenship"] = ask("Citizenship", "India")
    p["employment"] = ask("Employment (salaried/business/retired/job_searching)", "salaried")
    p["base_currency"] = "INR" if p["residency"] == "India" else "USD"
    p["spend_currency"] = p["base_currency"]
    p["monthly_income"] = ask("Monthly take-home income", 0, float)
    p["monthly_investable"] = ask("How much can you invest each month", 0, float)
    p["horizon_years"] = ask("For how many years can this money stay invested", 10, int)
    p["risk_tolerance"] = ask("If markets fell 30%, would you: sell (conservative) / wait (moderate) / "
                              "buy a bit (moderately_aggressive) / buy a lot (aggressive)", "moderate")
    p["emergency_fund_months"] = 6
    p["emergency_fund_have_months"] = ask("How many months of expenses do you hold in savings/FD right now", 6, float)
    p["tax"] = {"regime": ask("Tax regime (new/old)", "new") if p["tax_residency"] == "India" else None,
                "india_slab": ask("Income-tax slab rate (e.g. 0.3)", 0.3, float)}
    funds = []
    print("\nMutual funds. Find the scheme code with: python -m dicfo mf-search <name>. Blank name to finish.")
    while True:
        n = ask("  Fund name", "")
        if not n:
            break
        funds.append({
            "name": n, "scheme_code": ask("  AMFI scheme code", ""),
            "value": ask("  Current value", 0, float), "sip_monthly": ask("  Monthly SIP", 0, float),
            "plan": ask("  Plan (direct/regular)", "direct"),
            "category": ask(f"  Category {CATEGORIES}", "flexi_cap"),
        })
    other = {}
    print("\nOther holdings (current value, 0 if none)")
    for k, label in [("india_equity", "Direct Indian shares"), ("us_equity", "US shares / US funds"),
                     ("gold", "Gold (ETF, SGB, coins; skip jewellery)"), ("silver", "Silver"),
                     ("india_fixed_income", "EPF + PPF + FDs + bonds"), ("us_cash_bonds", "Savings / liquid funds"),
                     ("crypto", "Crypto")]:
        other[k] = ask(f"  {label}", 0, float)
    p["holdings"] = {"mutual_funds": funds, "other": other}
    PROFILES.mkdir(exist_ok=True)
    path = PROFILES / f"{name}.yaml"
    path.write_text(yaml.safe_dump(p, sort_keys=False))
    print(f"\nSaved {path}. Next: python -m dicfo daily --profile {name}")
