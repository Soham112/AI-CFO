"""Cross-border tax flags for a US/India investor. Rules as understood in 2026;
each carries a 'verify' flag because budgets change them."""
from __future__ import annotations

RULES = [
    {
        "id": "pfic",
        "when": lambda p: p.get("tax_residency") == "US",
        "severity": "high",
        "title": "Indian mutual funds and India-listed ETFs are PFICs for a US tax resident",
        "detail": ("The IRS treats foreign pooled funds as PFICs: gains are taxed at your top ordinary "
                   "rate plus an interest charge, and each fund needs Form 8621 every year. "
                   "Prefer US-listed India ETFs (INDA, EPI, SMIN, FLIN) or direct Indian shares via an "
                   "NRE/NRO PIS account. Existing Indian MF SIPs: consider pausing new money and ask a CPA "
                   "about a mark-to-market election."),
    },
    {
        "id": "nri_ppf",
        "when": lambda p: p.get("residency") != "India" and p.get("citizenship") == "India",
        "severity": "medium",
        "title": "NRIs cannot open new PPF accounts; EPF needs an Indian employer",
        "detail": ("An existing PPF can run to maturity (not extended). PPF/EPF interest is tax-free in "
                   "India but taxable income on your US return each year."),
    },
    {
        "id": "nre_fd",
        "when": lambda p: p.get("tax_residency") == "US" and p.get("citizenship") == "India",
        "severity": "medium",
        "title": "NRE FD interest is tax-free in India but taxed in the US",
        "detail": "Report it on Schedule B, and file FBAR / Form 8938 if foreign balances exceed the thresholds.",
    },
    {
        "id": "fbar",
        "when": lambda p: p.get("tax_residency") == "US",
        "severity": "medium",
        "title": "FBAR (FinCEN 114) above $10,000 aggregate foreign balances; FATCA Form 8938 at higher limits",
        "detail": "Penalties for missing these are steep even when no tax is owed.",
    },
    {
        "id": "us_shelters",
        "when": lambda p: p.get("tax_residency") == "US",
        "severity": "info",
        "title": "Fill US tax shelters first: 401(k) match, Roth/Backdoor Roth IRA, HSA",
        "detail": ("2026 limits: 401(k) $24,500 employee, IRA $7,500 (verify at irs.gov). Hold tax-inefficient "
                   "assets (gold ETFs taxed as collectibles up to 28%, bonds, REITs) inside these accounts."),
    },
    {
        "id": "india_cg",
        "when": lambda p: True,
        "severity": "info",
        "title": "India capital gains: listed equity LTCG 12.5% above Rs 1.25 lakh, STCG 20%",
        "detail": "From the July 2024 budget. NRIs have TDS deducted; claim it as a US foreign tax credit (Form 1116).",
    },
    {
        "id": "us_cg",
        "when": lambda p: p.get("tax_residency") == "US",
        "severity": "info",
        "title": "US: hold >1 year for 0/15/20% LTCG; harvest losses in down markets",
        "detail": ("A falling market is a chance to tax-loss harvest: sell a loser, buy a similar (not "
                   "'substantially identical') fund, bank the loss against gains plus $3,000 of income."),
    },
    {
        "id": "f1_nonresident",
        "when": lambda p: p.get("residency") == "US" and p.get("employment") in ("student", "job_searching"),
        "severity": "medium",
        "title": "Check your US tax status before worrying about PFIC",
        "detail": ("On an F-1/OPT visa you are usually a nonresident alien for US tax for your first 5 calendar "
                   "years, so Indian MFs are not yet a PFIC problem. Once you become a US tax resident (H-1B, "
                   "green card, or 5 years on F-1), stop adding to Indian MFs and plan the switch."),
    },
    {
        "id": "in_regime",
        "when": lambda p: p.get("tax_residency") == "India",
        "severity": "info",
        "title": "New vs old tax regime decides whether ELSS / 80C products make sense",
        "detail": ("Under the default new regime there is no 80C deduction, so pick ELSS, PPF or tax-saver FDs "
                   "on their merits, not for the tax break. Employer NPS (80CCD(2)) still works in the new regime."),
    },
    {
        "id": "in_debt_mf",
        "when": lambda p: p.get("tax_residency") == "India",
        "severity": "info",
        "title": "Debt funds bought after 1 Apr 2023 are taxed at your slab rate",
        "detail": "There is no indexation benefit, but tax is due only when you sell. FDs are taxed every year as interest accrues.",
    },
    {
        "id": "in_lrs",
        "when": lambda p: p.get("tax_residency") == "India",
        "severity": "info",
        "title": "US stocks from India: Indian-listed FoFs/ETFs or LRS (up to $250k a year)",
        "detail": ("LRS remittances above Rs 10 lakh a year attract 20% TCS (refundable or adjustable against tax). "
                   "Foreign shares must be shown in Schedule FA of the ITR. Many international FoFs have periodic "
                   "inflow caps from the RBI overseas limit."),
    },
    {
        "id": "in_gold",
        "when": lambda p: p.get("tax_residency") == "India",
        "severity": "info",
        "title": "Gold: ETFs / gold FoFs held over 12 months are taxed at 12.5% LTCG",
        "detail": "New Sovereign Gold Bond issues have stopped; SGBs bought in the secondary market and held to maturity are still tax-free.",
    },
    {
        "id": "crypto",
        "when": lambda p: True,
        "severity": "info",
        "title": "Crypto: US taxes it as property; India taxes gains at a flat 30% plus 1% TDS with no loss offset",
        "detail": "For a US resident, a US spot Bitcoin ETF in an IRA is the cleanest way to hold a small position.",
    },
]


def flags(profile: dict) -> list[dict]:
    return [{k: v for k, v in r.items() if k != "when"} for r in RULES if r["when"](profile)]
