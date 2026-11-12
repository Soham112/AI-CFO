"""Set up a profile by chatting with the Telegram bot, one question at a time.

Answers are kept in memory until the end, checked by the sensitive-data blocker and the
profile validator, then saved through security.write_private (encrypted if enabled).
"""
from __future__ import annotations

import re

import yaml

# (key, question, choices or None for typed number/text, kind)
QUESTIONS = [
    ("name", "What should I call you? (just a first name)", None, "text"),
    ("age", "How old are you?", None, "int"),
    ("employment", "What do you do?", [("Salaried job", "salaried"), ("Own business", "business"),
                                       ("Retired", "retired"), ("Looking for work", "job_searching")], "choice"),
    ("monthly_income", "Roughly how much comes in each month (take-home)? Type a number, e.g. 150000", None, "money"),
    ("monthly_investable", "How much can you invest every month? Type a number, e.g. 40000", None, "money"),
    ("emergency_fund_have_months", "If income stopped, how many months could your savings/FDs cover?",
     [("Under 3 months", 2), ("3-5 months", 4), ("6+ months", 6)], "choice"),
    ("horizon_years", "When might you need most of this money?",
     [("Within 3 years", 2), ("3-5 years", 4), ("5-10 years", 8), ("10+ years", 12)], "choice"),
    ("risk_tolerance", "If the market fell 30% tomorrow, what would you do?",
     [("Sell to stop losses", "conservative"), ("Wait it out", "moderate"),
      ("Buy a little more", "moderately_aggressive"), ("Buy a lot more", "aggressive")], "choice"),
    ("tax_regime", "Which income-tax regime do you use?", [("New", "new"), ("Old", "old"), ("Not sure", "new")], "choice"),
    ("funds", "Now your mutual funds. Send one per message like:\nParag Parikh Flexi Cap 500000 SIP 10000\n"
              "(name, current value, monthly SIP). Send done when finished.", None, "funds"),
    ("india_fixed_income", "Total in EPF + PPF + FDs + bonds? (number, 0 if none)", None, "money"),
    ("gold", "Gold you hold as ETF/SGB/coins (skip jewellery)? (number, 0 if none)", None, "money"),
    ("stocks", "Now the shares you hold directly (not through mutual funds). Send one company per message with "
               "the number of shares, like:\nHDFC Bank 50\nYour broker app (Zerodha, Groww, etc.) shows this. "
               "Send done when finished, or done now if you have none.", None, "stocks"),
    ("invest_abroad", "Do you want some money in companies outside India (like Google or Apple)?",
     [("No, India only", "no"), ("Yes, a little, through Indian funds", "yes")], "choice"),
]
STOCK_RX = re.compile(r"^(?P<name>.*?[A-Za-z].*?)\s+(?P<qty>[\d,]+)(?:\s*shares?)?\s*$", re.I)
FUND_RX = re.compile(r"^(?P<name>.+?)\s+(?P<value>[\d,]+)(?:\s+sip\s+(?P<sip>[\d,]+))?\s*$", re.I)


class Onboarding:
    def __init__(self):
        self.i, self.ans, self.funds, self.stocks = 0, {}, [], []

    def current(self) -> dict:
        key, q, choices, kind = QUESTIONS[self.i]
        opts = "\n" + "\n".join(f"{n}. {label}" for n, (label, _) in enumerate(choices, 1)) + \
            "\nReply with the number." if choices else ""
        return {"text": f"({self.i + 1}/{len(QUESTIONS)}) {q}{opts}", "buttons": []}

    def answer(self, value: str) -> str | None:
        """Return an error message, or None if accepted (then call current() / finished())."""
        key, _, choices, kind = QUESTIONS[self.i]
        v = value.strip()
        if kind == "choice":
            vals = {str(n): c[1] for n, c in enumerate(choices, 1)}
            vals.update({str(c[1]): c[1] for c in choices})
            vals.update({c[0].lower(): c[1] for c in choices})
            if v.lower() not in vals:
                return f"Please reply with a number from 1 to {len(choices)}."
            self.ans[key] = vals[v.lower()]
        elif kind in ("int", "money"):
            n = v.replace(",", "").replace("₹", "").strip()
            if not n.replace(".", "", 1).isdigit():
                return "Please type just a number."
            self.ans[key] = int(float(n))
            if kind == "int" and not 18 <= self.ans[key] <= 100:
                return "Please type an age between 18 and 100."
        elif kind == "text":
            if not (1 <= len(v) <= 40) or any(ch.isdigit() for ch in v):
                return "Just a first name, please."
            self.ans[key] = v
        elif kind == "funds":
            if v.lower() != "done":
                m = FUND_RX.match(v)
                if not m:
                    return "Please write it like: UTI Nifty 50 Index 300000 SIP 10000"
                self.funds.append({"name": m["name"].strip(), "value": int(m["value"].replace(",", "")),
                                   "sip_monthly": int((m["sip"] or "0").replace(",", "")),
                                   "plan": "regular" if "regular" in m["name"].lower() else "direct",
                                   "category": _guess_category(m["name"])})
                return f"Added {m['name'].strip()} ✅ Send the next fund, or done."
        elif kind == "stocks":
            if v.lower() != "done":
                m = STOCK_RX.match(v)
                qty = int(m["qty"].replace(",", "")) if m else 0
                if not m or not 0 < qty < 10_000_000:
                    return "Please write the company name and number of shares, like: HDFC Bank 50"
                from . import config
                from .names import resolve
                known = (config.load("universe").get("stocks") or {}).get("india", [])
                sym, problem = resolve(m["name"], known, _priced())
                if problem:
                    return problem.replace("like: TCS 10", "like: HDFC Bank 50")
                self.stocks.append({"name": m["name"].strip(), "symbol": sym, "shares": qty})
                return f"Added {m['name'].strip()}, {qty} shares ✅ Send the next one, or done."
        self.i += 1
        return None

    def finished(self) -> bool:
        return self.i >= len(QUESTIONS)

    def profile(self) -> dict:
        a = self.ans
        core = [{"symbol": f.get("scheme_code") or f["name"], "type": "mf", "name": f["name"], "monthly": f["sip_monthly"]}
                for f in self.funds if f["sip_monthly"]]
        return {
            "name": a.get("name"), "language": "en", "age": a.get("age"),
            "residency": "India", "tax_residency": "India", "citizenship": "India",
            "employment": a.get("employment"), "base_currency": "INR", "spend_currency": "INR",
            "monthly_income": a.get("monthly_income"), "monthly_investable": a.get("monthly_investable"),
            "horizon_years": a.get("horizon_years"), "risk_tolerance": a.get("risk_tolerance"),
            "emergency_fund_months": 6, "emergency_fund_have_months": a.get("emergency_fund_have_months"),
            "tax": {"regime": a.get("tax_regime"), "india_slab": 0.3},
            "invest_abroad": a.get("invest_abroad", "no"),
            "holdings": {"mutual_funds": self.funds, "stocks": self.stocks,
                         "other": {k: a.get(k, 0) for k in ("india_fixed_income", "gold")}},
            "plan": {"core": core, "opportunistic": [], "opportunistic_monthly_reserve": 0},
        }


def _priced() -> set:
    """Symbols that have a price in the latest market data (a guessed ticker counts only if it's real)."""
    try:
        from .data import snapshot as sm
        lp = sm.latest()
        return {k for k, v in (sm.load(lp).get("markets", {}) if lp else {}).items() if (v or {}).get("price")}
    except Exception:
        return set()


def _guess_category(name: str) -> str:
    n = name.lower()
    for k, c in [("nifty 50", "index_largecap"), ("index", "index_largecap"), ("flexi", "flexi_cap"),
                 ("large & mid", "large_mid"), ("large and mid", "large_mid"), ("mid", "midcap"), ("small", "smallcap"),
                 ("elss", "elss"), ("tax saver", "elss"), ("gold", "gold"), ("liquid", "liquid"), ("debt", "debt"),
                 ("hybrid", "hybrid"), ("balanced", "hybrid"), ("nasdaq", "international"), ("us ", "international"),
                 ("bluechip", "largecap"), ("large", "largecap")]:
        if k in n:
            return c
    return "sectoral_thematic" if any(k in n for k in ("infra", "pharma", "bank", "tech", "psu", "defence")) else "flexi_cap"


def save(profile_name: str, p: dict):
    from .config import PROFILES
    from .guardrails import validate_profile
    from .security import assert_clean, harden, write_private
    assert_clean(p, "this profile")
    validate_profile(p)
    write_private(PROFILES / f"{profile_name}.yaml", yaml.safe_dump(p, sort_keys=False, allow_unicode=True).encode())
    harden()
